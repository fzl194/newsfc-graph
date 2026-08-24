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
        # FTS 对账状态：True=重建中（search_md 应明确报错而非静默残缺，审查 C3）
        self.fts_rebuilding = False
        # mtime 校验后台异步（21178 文件 stat 在 Windows ~数十秒，不阻塞启动；完成后 reload）
        if not first_time:
            import threading as _t
            _t.Thread(target=self._fts_reconcile_async, daemon=True).start()
            _t.Thread(target=self._sync_mtime_async, daemon=True).start()

    def _fts_reconcile_async(self) -> None:
        """后台对账 md_fts：count + 总字节双校验，不一致 → 持写锁全量重建。"""
        from .repos import fts_repo
        try:
            if fts_repo.integrity_ok(self.db):
                return
            self.fts_rebuilding = True
            try:
                with import_lock:
                    n = fts_repo.rebuild_from_objects(self.db)
                    self.db.commit()
                print(f"[startup] md_fts 与 objects 不一致，已后台重建 {n} 行", flush=True)
            finally:
                self.fts_rebuilding = False
        except Exception:  # noqa: BLE001 后台线程绝不抛
            self.fts_rebuilding = False

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
        """单文件 parse → UPSERT DB（objects/edges/md_fts）。不重载内存（调用方 reload_index）。

        id/type/version 变了的旧节点按 source_path 清除（``objects_repo.delete_by_source``）；
        FTS 旧 (id,version) 行同源删除（不留幽灵命中，审查 C1）。
        """
        from .edges import parse_edges
        from .logical_id import split_id
        from .md_parser import parse_md
        from .repos import edges_repo, fts_repo, objects_repo
        # 删旧节点 + 其边 + FTS 旧行（source_path 维度，稳）
        old_pairs = list(objects_repo.delete_by_source(self.db, rel))
        for oid, over in old_pairs:
            edges_repo.delete_for_node(self.db, oid, over)
        fts_repo.delete_many(self.db, old_pairs)
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
        fts_repo.upsert(self.db, obj_id=id_, version=version, body=body)
        self.db.commit()

    def unindex_path(self, rel: str) -> None:
        """删该 source_path 的 DB 节点 + 边 + FTS 行（md 被删时）。"""
        from .repos import edges_repo, fts_repo, objects_repo
        old_pairs = list(objects_repo.delete_by_source(self.db, rel))
        for oid, over in old_pairs:
            edges_repo.delete_for_node(self.db, oid, over)
        fts_repo.delete_many(self.db, old_pairs)
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

    # ---------- 正文全文搜索（MCP search_md 的 service 层实现） ----------

    def search_md(self, q: str, layer=None, type=None, nf=None, version=None,
                  limit: int = 20, offset: int = 0) -> dict:
        """FTS5 trigram 正文搜索：相关度排序 + 高亮片段 + 元数据/版本过滤。

        版本语义：不传 version → 只保留每个 id 的**最新现存版本**命中行（最新版
        不含关键词则该 id 不出现——FTS 按行命中，非"分组后错位取最新"，审查 C6）；
        传 version → 锁定该版本。q<3 字符走 LIKE 路径（trigram 索引加速，无相关度）。

        返回 {total, hits: [{id, type, name, version, score, snippet}]}；
        hits 不含正文全文——召回后调 get_md 取完整 md。
        """
        from .repos import fts_repo
        q = (q or "").strip()
        if not q:
            raise ValueError("查询词不能为空")
        if getattr(self, "fts_rebuilding", False):  # __new__ 绕过 __init__ 的测试实例无此属性
            raise RuntimeError("全文索引重建中，请稍后重试")

        # 命中行（FTS 层，无元数据过滤）→ 内存索引过滤（node 存在 + 元数据 + 版本语义）
        if len(q) >= 3:
            rows = fts_repo.search_match(self.db, q)
            for r in rows:
                r.pop("body", None)
        else:
            raw = fts_repo.search_like(self.db, q)
            rows = [self._like_row_with_snippet(r, q) for r in raw]

        idx = self.index
        # layer 语义与 list_objects 一致：UI 层名（中文）→ 类型集合；type 优先（层内收窄）
        types: Optional[set] = None
        if type:
            types = {type}
        elif layer:
            from .ui_layers import UI_LAYER_TYPES
            types = set(UI_LAYER_TYPES.get(layer, []))
        filtered = []
        for r in rows:
            ver = r["version"] or None
            obj = idx.node(r["obj_id"], ver)
            if obj is None:
                continue  # DB 有行内存无节点（刚删除未 reload）——跳过
            if types is not None and obj.type not in types:
                continue
            if nf and obj.nf != nf:
                continue
            if version is not None:
                if ver != version:
                    continue
            else:
                latest = idx.latest_version_of_id(r["obj_id"])
                if ver != latest:
                    continue
            filtered.append({
                "id": r["obj_id"], "type": obj.type, "name": obj.frontmatter.get("name"),
                "version": ver, "score": r.get("score"), "snippet": r["snippet"],
            })
        total = len(filtered)
        start = max(0, offset)
        return {"total": total, "hits": filtered[start:start + max(1, limit)]}

    @staticmethod
    def _like_row_with_snippet(r: dict, q: str) -> dict:
        """LIKE 路径手工造 snippet（FTS5 snippet() 仅对 MATCH 有效）：48 字符窗口高亮。"""
        body = r.get("body") or ""
        pos = body.find(q)
        if pos < 0:
            snip = body[:48]
        else:
            half = max(0, pos - 20)
            seg = body[half:pos + len(q) + 28]
            snip = ("…" if half > 0 else "") + seg.replace(q, f"【{q}】", 1) + "…"
        return {"obj_id": r["obj_id"], "version": r["version"], "snippet": snip}


_service: Optional[Service] = None


def get_service() -> Service:
    """延迟初始化的全局单例（lifespan 启动时预热）。"""
    global _service
    if _service is None:
        _service = Service()
    return _service
