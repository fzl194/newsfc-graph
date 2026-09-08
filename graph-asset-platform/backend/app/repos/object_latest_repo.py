"""object_latest 维护：每 ID 最新版本物化（需求 §7.5/§12.1）。

刷新一律用 Python ``latest_version()``（语义化点分比较）——**禁止 SQL
MAX(version)**：字符串序与语义序不一致（如 20.9.0 > 20.10.0 字典序反了）。
调用方保证与 objects/FTS 写入同一事务（commit 由调用方控制）。

version 沿用 objects 的 DB 表示：无版本对象=空串 ""（NOT NULL 列禁写 None）。
"""
import sqlite3

from ..version import latest_version


def refresh(conn: sqlite3.Connection, ids) -> None:
    """按 ``old_ids ∪ new_ids`` 刷新：查每个 ID 全部现存版本，UPSERT 最新；
    ID 已无任何版本时 DELETE latest 行（删除最后版本 → 行消失，§12.1）。"""
    for id_ in set(ids):
        versions = [r["version"] for r in conn.execute(
            "SELECT version FROM objects WHERE id=?", (id_,)).fetchall()]
        if not versions:
            conn.execute("DELETE FROM object_latest WHERE id=?", (id_,))
            continue
        best = latest_version(versions)
        conn.execute(
            "INSERT INTO object_latest(id, version) VALUES(?,?) "
            "ON CONFLICT(id) DO UPDATE SET version=excluded.version",
            (id_, best))


def rebuild(conn: sqlite3.Connection, chunk: int = 5000) -> int:
    """全量重建（objects 全量重写后调用）。流式扫 + 分块提交，返回 ID 数。"""
    conn.execute("DELETE FROM object_latest")
    conn.commit()
    best: dict = {}
    total = 0
    cur = conn.execute("SELECT id, version FROM objects ORDER BY id")
    while True:
        rows = cur.fetchmany(chunk)
        if not rows:
            break
        for r in rows:
            v = best.get(r["id"])
            if v is None or latest_version([r["version"], v]) == r["version"]:
                best[r["id"]] = r["version"]
        conn.executemany(
            "INSERT OR REPLACE INTO object_latest(id, version) VALUES(?,?)",
            list(best.items()))
        conn.commit()
        total += len(best)
        best = {}
    return total


def integrity_ok(conn: sqlite3.Connection) -> bool:
    """对账：每个 objects.id 恰好一行（PK 保证唯一）+ version 实际存在于
    objects（§12.1）。数量一致由前两条共同保证。"""
    missing = conn.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT id FROM objects "
        "EXCEPT SELECT id FROM object_latest)").fetchone()[0]
    if missing:
        return False
    dangling = conn.execute(
        "SELECT COUNT(*) FROM object_latest ol WHERE NOT EXISTS("
        "SELECT 1 FROM objects o WHERE o.id=ol.id AND o.version=ol.version)"
    ).fetchone()[0]
    if dangling:
        return False
    n_ids = conn.execute("SELECT COUNT(DISTINCT id) FROM objects").fetchone()[0]
    n_lat = conn.execute("SELECT COUNT(*) FROM object_latest").fetchone()[0]
    return n_ids == n_lat
