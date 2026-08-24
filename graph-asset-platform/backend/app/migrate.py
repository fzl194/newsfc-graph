"""首次建库迁移：扫 assets md 全量 parse → 填 objects/edges 表。

复用 ``index.py:Index.build`` 的解析逻辑（parse_md + edges + split_id + registry），
但写入 SQLite 而非内存 dict。建库后 ``Index.load_from_db`` 从 SQLite 加载内存。

users / telemetry / tests 的迁移函数（``migrate_users`` / ``migrate_telemetry`` /
``migrate_tests``）分别在阶段 4/5/6 加入此模块。
"""
import sqlite3

from .edges import parse_edges
from .logical_id import split_id
from .md_parser import parse_md
from .repos import edges_repo, objects_repo
from .store import Store
from .registry import Registry


def build_index_db(conn: sqlite3.Connection, store: Store, registry: Registry) -> dict:
    """全量扫 md → objects/edges 表（清空两表后重写）。返回 {objects, edges, skipped}。

    用于首次建库与手动 reindex（兜底）。users/telemetry/tests 表不受影响。
    """
    conn.execute("DELETE FROM objects")
    conn.execute("DELETE FROM edges")
    files = store.list_md()
    total = len(files)
    print(f"[migrate] 全量解析 {total} 个 md → SQLite…", flush=True)
    n_obj = n_edge = n_skip = 0
    for i, rel in enumerate(files, 1):
        if total >= 2000 and i % 2000 == 0:
            print(f"[migrate] 已解析 {i}/{total}…", flush=True)
        try:
            text = store.read(rel)
            fm, body, edge_sec = parse_md(text)
        except Exception:
            n_skip += 1
            continue
        id_ = fm.get("id")
        typ = fm.get("type")
        if not id_ or not typ or not registry.known(typ):
            n_skip += 1
            continue
        try:
            nf, _t, _l = split_id(id_)
        except ValueError:
            n_skip += 1
            continue
        version = fm.get("version")
        entry = registry.get(typ) or {}
        scope = entry.get("scope")
        layer = entry.get("layer")
        mtime = store.abspath(rel).stat().st_mtime
        # 出边（与 Index.build 一致：有 ## 边 用显式；否则 ref + 正文 wikilink）
        edges = list(parse_edges(edge_sec, from_id=id_, from_version=version))
        objects_repo.upsert(
            conn,
            id=id_, version=version, type=typ, layer=layer, scope=scope,
            nf=nf, domain=fm.get("domain"), scenario=fm.get("scenario"),
            source_path=rel, name=fm.get("name"), frontmatter=fm,
            body_md=body, raw_md=text, mtime=mtime,
        )
        edges_repo.replace_for_node(conn, id_, version, edges)
        n_obj += 1
        n_edge += len(edges)
    # dangling 标志（meta 表）：是否存在 to 不在 objects.id 的边
    dangling = conn.execute(
        "SELECT EXISTS(SELECT 1 FROM edges WHERE \"to\" NOT IN (SELECT id FROM objects))"
    ).fetchone()[0]
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES('dangling', ?)",
        (str(bool(dangling)),),
    )
    # FTS 全量重建（objects 清空重写，md_fts 同步重灌——单事务原子替换）
    from .repos import fts_repo
    fts_repo.rebuild_from_objects(conn)
    conn.commit()
    print(f"[migrate] 完成：{n_obj} 对象 / {n_edge} 边 / {n_skip} 跳过", flush=True)
    return {"objects": n_obj, "edges": n_edge, "skipped": n_skip}


def migrate_users(conn: sqlite3.Connection) -> int:
    """users.json → users 表（仅首次，users 表空时）。返回迁移用户数。

    迁移后 users.json 保留作备份，但平台不再读写（users 表是权威）。
    """
    from .repos import users_repo
    if users_repo.count(conn) > 0:
        return 0
    import json
    from .config import USERS_FILE
    path = USERS_FILE
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return 0
    n = 0
    for u in data.get("users", []):
        try:
            # 旧 json 无 can_assets → 默认随 is_admin（admin 拥有资产权限）
            u.setdefault("can_assets", bool(u.get("is_admin")))
            users_repo.insert(conn, u)
            n += 1
        except Exception:  # noqa: BLE001 单用户失败不阻塞
            continue
    conn.commit()
    if n:
        print(f"[migrate] 导入 {n} 个用户 → users 表", flush=True)
    return n


def migrate_telemetry(conn: sqlite3.Connection) -> int:
    """telemetry jsonl → telemetry 表（首次，一次性导入历史数据）。返回迁移条数。

    迁移后 recorder 改写 DB，jsonl 不再增长；jsonl 文件保留作 raw 备份。
    """
    import json
    from .config import TELEMETRY_OBJECTS_FILE, TELEMETRY_REQUESTS_FILE
    from .repos import telemetry_repo
    n = 0
    for path, default_level in [(TELEMETRY_OBJECTS_FILE, "object"),
                                (TELEMETRY_REQUESTS_FILE, "request")]:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except ValueError:
                continue
            try:
                telemetry_repo.insert(
                    conn,
                    ts=rec.get("ts", ""), level=rec.get("level", default_level),
                    caller=rec.get("caller", ""), endpoint=rec.get("endpoint", ""),
                    obj_id=rec.get("id", ""), obj_type=rec.get("type", ""),
                    user=rec.get("user", ""), operator=rec.get("operator", ""),
                    session_id=rec.get("session_id", ""),
                )
                n += 1
            except Exception:  # noqa: BLE001
                continue
    conn.commit()
    if n:
        print(f"[migrate] 导入 {n} 条打点 → telemetry 表", flush=True)
    return n


def migrate_tests(conn, store) -> dict:
    """全量扫 tests md → 内存 TestIndex → 写 test_* 表。

    tests 子系统数据少（个位数），全量重建可接受（替代增量 UPSERT 的复杂度）。
    启动 + 每次写操作后调。
    """
    from .tests.index import TestIndex
    from .repos import tests_repo
    idx = TestIndex.build(store)
    tests_repo.replace_all(conn, idx)
    return {"cases": len(idx.cases), "runs": len(idx.runs), "reviews": len(idx.reviews)}
