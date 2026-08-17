"""内存索引：遍历 store 所有 md → Object 节点 + 版本聚合 + 边邻接表。

核心不变量（对齐 spec §6.4 与任务简报）：
- 一个 md = 一个 ``(id, version)`` 节点；同 id 多版本 = 多节点 + ``versions[]`` 聚合。
- ``resolve_node(id, None)`` → **该 id 最新现存版本**（语义化取最大；不是网元最新；
  若 id 仅存于旧版本，落到旧版本，不返回 None / 不 404）。
- ``resolve_node(id, version=X)`` → (id, X) 存在则返回，否则 None（API 将 404）。
- ``in_edges(to_id)`` → **按 to_id 收集所有指向它的边（版本无关）**；签名只取 to_id。
- ``to_id`` 完全不存在（不在 versions 字典里）→ 悬空边告警（不阻断构建）。
"""
from collections import defaultdict
from typing import Optional

from .edges import parse_edges
from .logical_id import split_id
from .md_parser import parse_md
from .models import Object, Edge
from .registry import Registry
from .store import Store
from .version import latest_version


class Index:
    def __init__(self):
        # (id, version) -> Object。跨 NF 类 version 为 None，键里也是 None。
        self.nodes: dict = {}
        # id -> [versions]（同 id 多版本聚合；跨 NF 类为 [None]）
        self.versions: dict = {}
        # (id, version) -> [Edge]；出边邻接表
        self.out: dict = defaultdict(list)
        self.dangling = False

    @classmethod
    def build(cls, store: Store, registry: Registry) -> "Index":
        idx = cls()
        files = store.list_md()
        total = len(files)
        print(f"[index] 开始解析 {total} 个 md…", flush=True)
        # 第 1 趟：建节点 + 聚合 versions + 收集原始边
        for i, rel in enumerate(files, 1):
            if total >= 2000 and i % 2000 == 0:
                print(f"[index] 已解析 {i}/{total}…", flush=True)
            try:
                text = store.read(rel)
                fm, body, edge_sec = parse_md(text)
            except Exception:
                # 单文件解析失败不阻塞整库索引
                continue
            id_ = fm.get("id")
            typ = fm.get("type")
            if not id_ or not typ or not registry.known(typ):
                # 缺 id/type 或类型未注册 → 不作为图谱对象索引
                continue
            # split_id 失败（非 2/3 段）也跳过
            try:
                nf, _typ_seg, _local = split_id(id_)
            except ValueError:
                continue
            version = fm.get("version")
            scope = registry.get(typ)["scope"]
            obj = Object(
                id=id_,
                type=typ,
                layer=registry.layer_of(typ),
                scope=scope,
                version=version,
                versions=[],
                frontmatter=fm,
                body_md=body,
                raw_md=text,
                source_path=rel,
                nf=nf,
                domain=fm.get("domain"),
                scenario=fm.get("scenario"),
            )
            key = (id_, version)
            idx.nodes[key] = obj
            idx.versions.setdefault(id_, [])
            if version not in idx.versions[id_]:
                idx.versions[id_].append(version)
            # 出边（## 边 显式；正文 [[ ]] 是 Agent 跳转引用，不建边）
            for e in parse_edges(edge_sec, from_id=id_, from_version=version):
                idx.out[key].append(e)
        # 把聚合后的 versions 列表回填到每个节点
        for key, obj in idx.nodes.items():
            obj.versions = sorted(idx.versions[obj.id])
        # 第 2 趟：悬空检测（to_id 完全不存在于任何已索引 id → 悬空）
        for edges in idx.out.values():
            for e in edges:
                if e.to not in idx.versions:
                    idx.dangling = True
                    break
            if idx.dangling:
                break
        return idx

    @classmethod
    def load_from_db(cls, db, registry: Registry) -> "Index":
        """从 SQLite 加载内存（启动 + 写操作 reload 用，毫秒~百毫秒级）。

        替代 build 的全量 parse md；DB 是 ``migrate.build_index_db`` / ``Service.reindex_path``
        维护的解析结果缓存。内存结构与 build 一致（nodes/versions/out/dangling）。
        """
        from .repos import objects_repo, edges_repo
        idx = cls()
        for row in objects_repo.load_all(db):
            obj = Object(
                id=row["id"], type=row["type"], layer=row["layer"], scope=row["scope"],
                version=row["version"], versions=[],
                frontmatter=row["frontmatter"], body_md=row["body_md"], raw_md=row["raw_md"],
                source_path=row["source_path"], nf=row["nf"],
                domain=row["domain"], scenario=row["scenario"],
            )
            key = (obj.id, obj.version)
            idx.nodes[key] = obj
            idx.versions.setdefault(obj.id, [])
            if obj.version not in idx.versions[obj.id]:
                idx.versions[obj.id].append(obj.version)
        # 回填 versions 列表（与 build 一致）
        for key, obj in idx.nodes.items():
            obj.versions = sorted(idx.versions[obj.id])
        for row in edges_repo.load_all(db):
            e = Edge(from_id=row["from_id"], from_version=row["from_version"],
                     relation=row["relation"], to=row["to"])
            idx.out[(e.from_id, e.from_version)].append(e)
        drow = db.execute("SELECT value FROM meta WHERE key='dangling'").fetchone()
        idx.dangling = bool(drow and drow["value"] == "True")
        return idx

    # ---------- 节点查询 ----------

    def node(self, id_: str, version: Optional[str]) -> Optional[Object]:
        return self.nodes.get((id_, version))

    def versions_of(self, id_: str) -> list:
        return self.versions.get(id_, [])

    def latest_version_of_id(self, id_: str) -> Optional[str]:
        return latest_version(self.versions_of(id_))

    def latest_node_of_id(self, id_: str) -> Optional[Object]:
        """该 id 语义最新版本的节点（跨 NF 类 version=None 合法）。"""
        return self.node(id_, self.latest_version_of_id(id_))

    def latest_version_of_nf(self, nf: str) -> Optional[str]:
        """该 nf 名下所有节点的版本集合中最新者（语义化排序）。"""
        vs = {obj.version for obj in self.nodes.values() if obj.nf == nf and obj.version is not None}
        return latest_version(list(vs)) if vs else None

    def resolve_node(self, id_: str, version: Optional[str]) -> Optional[Object]:
        """版本解析（spec §6.4）。

        - 显式 version=X：返回 (id, X) 节点；不存在 → None（API 将 404 + 列出可用版本）。
        - version=None：返回 **该 id 最新现存版本**（语义化取最大；id 仅存旧版本则落到
          旧版本，不返回 None、不 404）。这与"网元最新"不同：某 id 若没跟上网元最新版本，
          不会被误判 404。
        - 跨 NF 类 version 恒为 None：versions=[None]，latest=None 是合法版本，照常返回节点。
        """
        if version is not None:
            return self.node(id_, version)
        vs = self.versions_of(id_)
        if not vs:
            # id 完全不存在于索引 → None（区别于跨 NF 类的 versions=[None]）
            return None
        v = self.latest_version_of_id(id_)  # 跨 NF 类为 None（合法）
        return self.node(id_, v)

    # ---------- 邻接查询 ----------

    def out_edges(self, id_: str, version: Optional[str]) -> list:
        return self.out.get((id_, version), [])

    def in_edges(self, to_id: str) -> list:
        """反链：按 to_id 收集所有指向它的边（版本无关）。

        签名只取 ``to_id``——边本身存储为 ``(from, relation, to_id 版本无关)``，
        展示时再按 §6.4 解析到具体版本节点。
        """
        return [e for edges in self.out.values() for e in edges if e.to == to_id]

    def has_dangling(self) -> bool:
        return self.dangling

    # ---------- /stats 辅助 ----------

    def nfs(self) -> set:
        return {obj.nf for obj in self.nodes.values() if obj.nf}

    def versions_per_nf(self) -> dict:
        m = defaultdict(set)
        for obj in self.nodes.values():
            if obj.nf and obj.version is not None:
                m[obj.nf].add(obj.version)
        return {k: sorted(v) for k, v in m.items()}
