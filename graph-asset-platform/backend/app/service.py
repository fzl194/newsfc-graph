"""单例 Service：持有 store / registry / db / index。

启动从 SQLite 加载内存 Index（毫秒~百毫秒级，替代全量 parse md 的 380s）；写操作
增量 UPSERT DB + reload 内存（毫秒级，替代全量 rebuild）。DB 不存在则 migrate 全量
建库（首次启动一次性慢）。

测试隔离：``Service.__new__`` 绕过 ``__init__``，手动建（含 db）指向 tmp 目录。
"""
import threading
from typing import Optional

from .config import ASSETS_DIR
from .db import get_shared_db
from .index import Index
from .registry import Registry
from .store import Store

# 模块级写锁：写盘 + DB UPSERT + reload 内存必须串行化（单例跨线程共享）。
import_lock = threading.Lock()


class Service:
    def __init__(self):
        self.store = Store(ASSETS_DIR)
        self.registry = Registry.load_default()
        self.db = get_shared_db()
        # 首次迁移（DB 空表）：objects 全量 parse；users/telemetry 从旧文件导入
        from .migrate import build_index_db, migrate_users, migrate_telemetry
        first_time = self._table_empty("objects")
        if first_time:
            build_index_db(self.db, self.store, self.registry)
        if self._table_empty("users"):
            migrate_users(self.db)
        if first_time:
            migrate_telemetry(self.db)  # jsonl 历史数据一次性导入
        self.index = Index.load_from_db(self.db, self.registry)
        # mtime 校验后台异步（21178 文件 stat 在 Windows ~数十秒，不阻塞启动；完成后 reload）
        if not first_time:
            import threading as _t
            _t.Thread(target=self._sync_mtime_async, daemon=True).start()

    def _sync_mtime_async(self) -> None:
        """后台 mtime 校验：stat 扫描不取锁（慢但不阻塞写），reindex/reload 取锁（短）。"""
        try:
            changed, deleted = self._scan_mtime_changes()
            if changed or deleted:
                with import_lock:
                    for rel in changed:
                        self.reindex_path(rel)
                    for rel in deleted:
                        self.unindex_path(rel)
                    self.reload_index()
        except Exception:  # noqa: BLE001 后台线程绝不抛
            pass

    def _table_empty(self, name: str) -> bool:
        return self.db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] == 0

    def _scan_mtime_changes(self) -> tuple:
        """扫所有 md 的 stat 比对 DB mtime，返回 (changed_rels, deleted_rels)。

        只读：**一次 SELECT** 拿全部 (source_path, mtime) 建 dict（避免 per-file SELECT
        长时间占用连接、阻塞写操作的 reload/打点）。stat 仍 O(n) 但不持 db 连接。
        """
        disk_md = set(self.store.list_md())
        db_mtime = {r["source_path"]: r["m"] for r in self.db.execute(
            "SELECT source_path, MAX(mtime) AS m FROM objects GROUP BY source_path"
        ).fetchall()}
        changed = []
        for rel in disk_md:
            try:
                d = self.store.abspath(rel).stat().st_mtime
            except OSError:
                continue
            m = db_mtime.get(rel)
            if m is None or abs(d - m) > 0.001:
                changed.append(rel)
        deleted = [p for p in db_mtime if p not in disk_md]
        return changed, deleted

    def _sync_mtime(self) -> None:
        """同步 mtime：reindex 变化 + unindex 删除。**不取锁**——调用方负责（测试或 _sync_mtime_async）。"""
        changed, deleted = self._scan_mtime_changes()
        for rel in changed:
            self.reindex_path(rel)
        for rel in deleted:
            self.unindex_path(rel)

    def reload_index(self) -> None:
        """从 DB 重载内存 Index（写操作末尾调用）。"""
        self.index = Index.load_from_db(self.db, self.registry)

    def reindex_path(self, rel: str) -> None:
        """单文件 parse → UPSERT DB（objects/edges）。不重载内存（调用方 reload_index）。

        id/type/version 变了的旧节点按 source_path 清除（``objects_repo.delete_by_source``）。
        """
        from .edges import parse_edges
        from .logical_id import split_id
        from .md_parser import parse_md
        from .repos import edges_repo, objects_repo
        # 删旧节点 + 其边（source_path 维度，稳）
        for oid, over in objects_repo.delete_by_source(self.db, rel):
            edges_repo.delete_for_node(self.db, oid, over)
        # 重新 parse + 入库
        try:
            text = self.store.read(rel)
            fm, body, edge_sec = parse_md(text)
        except Exception:
            self.db.commit()
            return
        id_ = fm.get("id")
        typ = fm.get("type")
        if not id_ or not typ or not self.registry.known(typ):
            self.db.commit()
            return
        try:
            nf, _t, _l = split_id(id_)
        except ValueError:
            self.db.commit()
            return
        version = fm.get("version")
        entry = self.registry.get(typ) or {}
        mtime = self.store.abspath(rel).stat().st_mtime
        edges = list(parse_edges(edge_sec, from_id=id_, from_version=version))
        objects_repo.upsert(
            self.db,
            id=id_, version=version, type=typ,
            layer=entry.get("layer"), scope=entry.get("scope"),
            nf=nf, domain=fm.get("domain"), scenario=fm.get("scenario"),
            source_path=rel, name=fm.get("name"), frontmatter=fm,
            body_md=body, raw_md=text, mtime=mtime,
        )
        edges_repo.replace_for_node(self.db, id_, version, edges)
        self.db.commit()

    def unindex_path(self, rel: str) -> None:
        """删该 source_path 的 DB 节点 + 边（md 被删时）。"""
        from .repos import edges_repo, objects_repo
        for oid, over in objects_repo.delete_by_source(self.db, rel):
            edges_repo.delete_for_node(self.db, oid, over)
        self.db.commit()

    def reindex_prefixes(self, prefixes: list) -> dict:
        """**按前缀增量索引**（与 reindex_path 同一套 DB/锁/解析语义，目录级）。

        挖掘（自动抽取）/批量覆盖共用；替代全量 rebuild——耗时与**变更量**成正比，
        与库总规模无关（百万级 md 下全量重建不可行）：
        - 磁盘上这些前缀下的全部 md → 逐个 reindex_path（内容变更 UPSERT）
        - DB 中前缀下已不在磁盘的 source_path → unindex_path（force 清理/删除）
        - 最后 reload_index

        prefixes 如 ``["Command/UDG/20.15.2", "Feature/UDG/20.15.2"]``；
        **调用方须持 import_lock**（与 fs 写端点一致）。返回 {"indexed", "removed"}。
        """
        pfx = tuple(p.rstrip("/") + "/" for p in prefixes if p and p.strip("/"))
        if not pfx:
            return {"indexed": 0, "removed": 0}
        disk = [rel for rel in self.store.list_md() if rel.startswith(pfx)]
        disk_set = set(disk)
        for rel in disk:
            self.reindex_path(rel)
        removed = 0
        rows = self.db.execute("SELECT DISTINCT source_path FROM objects").fetchall()
        for r in rows:
            p = r["source_path"] or ""
            if p.startswith(pfx) and p not in disk_set:
                self.unindex_path(p)
                removed += 1
        self.reload_index()
        return {"indexed": len(disk), "removed": removed}

    def rebuild(self) -> None:
        """全量 reindex 兜底：扫 md 重建 DB + 内存（手动触发，慢；用于数据不一致时）。"""
        from .migrate import build_index_db
        with import_lock:
            build_index_db(self.db, self.store, self.registry)
            self.index = Index.load_from_db(self.db, self.registry)


_service: Optional[Service] = None


def get_service() -> Service:
    """延迟初始化的全局单例（lifespan 启动时预热）。"""
    global _service
    if _service is None:
        _service = Service()
    return _service
