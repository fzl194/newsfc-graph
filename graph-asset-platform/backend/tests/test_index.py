from app.store import Store
from app.index import Index
from app.registry import Registry


def _cmd(store, id_, version, body_edges=""):
    nf, typ, _ = id_.split("@", 2)
    md = (
        f"---\n"
        f"id: {id_}\n"
        f"type: {typ}\n"
        f"nf: {nf}\n"
        f"version: {version}\n"
        f"---\n"
        f"# {id_}\n"
        f"{body_edges}"
    )
    store.write(f"Command/{nf}/{version}/{id_}.md", md)


def _cfg(store, id_, version):
    nf, typ, _ = id_.split("@", 2)
    md = (
        f"---\n"
        f"id: {id_}\n"
        f"type: {typ}\n"
        f"nf: {nf}\n"
        f"version: {version}\n"
        f"---\n"
        f"# {id_}\n"
    )
    store.write(f"ConfigObject/{nf}/{version}/{id_}.md", md)


# ---------- 节点 + 版本聚合 ----------

def test_nodes_and_versions(tmp_data_dir):
    s = Store(tmp_data_dir)
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2")
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.16.0")   # 同 id 两版本
    idx = Index.build(s, Registry.load_default())
    # 两个节点（一个 md = 一个 (id,version) 节点）
    assert idx.node("UDG@MMLCommand@ADD URR", "20.15.2") is not None
    assert idx.node("UDG@MMLCommand@ADD URR", "20.16.0") is not None
    # versions 聚合
    vs = idx.versions_of("UDG@MMLCommand@ADD URR")
    assert set(vs) == {"20.15.2", "20.16.0"}
    # 节点上的 versions 字段也已回填
    n = idx.node("UDG@MMLCommand@ADD URR", "20.15.2")
    assert set(n.versions) == {"20.15.2", "20.16.0"}


def test_node_unknown_id_returns_none(tmp_data_dir):
    s = Store(tmp_data_dir)
    idx = Index.build(s, Registry.load_default())
    assert idx.node("UDG@MMLCommand@NOPE", "20.15.2") is None
    assert idx.versions_of("UDG@MMLCommand@NOPE") == []


# ---------- 版本解析 ----------

def test_latest_version_of_id(tmp_data_dir):
    s = Store(tmp_data_dir)
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.9.10")
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2")
    idx = Index.build(s, Registry.load_default())
    assert idx.latest_version_of_id("UDG@MMLCommand@ADD URR") == "20.15.2"


def test_latest_version_of_nf(tmp_data_dir):
    s = Store(tmp_data_dir)
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.9.10")
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2")
    idx = Index.build(s, Registry.load_default())
    assert idx.latest_version_of_nf("UDG") == "20.15.2"


def test_default_resolves_latest_existing(tmp_data_dir):
    s = Store(tmp_data_dir)
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2")
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.16.0")
    idx = Index.build(s, Registry.load_default())
    # 不指定版本 → 该 id 最新现存版本
    n = idx.resolve_node("UDG@MMLCommand@ADD URR", version=None)
    assert n is not None
    assert n.version == "20.16.0"


def test_default_when_id_only_at_old_version(tmp_data_dir):
    # UDG 有更新版本（OTHER@20.16.0），但 ADD URR 只在 20.15.2 →
    # 默认不 404、不落到网元最新，而是落到该 id 最新现存 20.15.2
    s = Store(tmp_data_dir)
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2")
    _cmd(s, "UDG@MMLCommand@OTHER", "20.16.0")
    idx = Index.build(s, Registry.load_default())
    n = idx.resolve_node("UDG@MMLCommand@ADD URR", version=None)
    assert n is not None and n.version == "20.15.2"


def test_resolve_node_explicit_version(tmp_data_dir):
    s = Store(tmp_data_dir)
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2")
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.16.0")
    idx = Index.build(s, Registry.load_default())
    assert idx.resolve_node("UDG@MMLCommand@ADD URR", version="20.15.2").version == "20.15.2"
    # 指定不存在版本 → None（API 将 404）
    assert idx.resolve_node("UDG@MMLCommand@ADD URR", version="9.9.9") is None


def test_resolve_node_unknown_id_returns_none(tmp_data_dir):
    s = Store(tmp_data_dir)
    idx = Index.build(s, Registry.load_default())
    assert idx.resolve_node("UDG@MMLCommand@NOPE", version=None) is None


# ---------- 出边 / 反链 ----------

def test_out_edges(tmp_data_dir):
    s = Store(tmp_data_dir)
    edges_md = "## 边\n- 操作配置对象: [[UDG@ConfigObject@URR]]\n"
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2", edges_md)
    _cfg(s, "UDG@ConfigObject@URR", "20.15.2")
    idx = Index.build(s, Registry.load_default())
    out = idx.out_edges("UDG@MMLCommand@ADD URR", "20.15.2")
    assert any(e.to == "UDG@ConfigObject@URR" for e in out)
    assert any(e.relation == "操作配置对象" for e in out)


def test_in_edges_version_agnostic_by_to_id(tmp_data_dir):
    # 反链签名只取 to_id，与查看哪个版本节点无关、与目标节点版本无关
    s = Store(tmp_data_dir)
    edges_md = "## 边\n- 操作配置对象: [[UDG@ConfigObject@URR]]\n"
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2", edges_md)
    _cfg(s, "UDG@ConfigObject@URR", "20.15.2")
    idx = Index.build(s, Registry.load_default())
    back = idx.in_edges("UDG@ConfigObject@URR")
    assert any(e.from_id == "UDG@MMLCommand@ADD URR" for e in back)


def test_in_edges_collects_across_versions(tmp_data_dir):
    # 两个不同版本的源都指向同一 to_id → in_edges 全收
    s = Store(tmp_data_dir)
    edges_md = "## 边\n- 操作配置对象: [[UDG@ConfigObject@URR]]\n"
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2", edges_md)
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.16.0", edges_md)
    _cfg(s, "UDG@ConfigObject@URR", "20.15.2")
    idx = Index.build(s, Registry.load_default())
    back = idx.in_edges("UDG@ConfigObject@URR")
    from_versions = {e.from_version for e in back}
    assert from_versions == {"20.15.2", "20.16.0"}


def test_in_edges_empty(tmp_data_dir):
    s = Store(tmp_data_dir)
    _cfg(s, "UDG@ConfigObject@URR", "20.15.2")
    idx = Index.build(s, Registry.load_default())
    assert idx.in_edges("UDG@ConfigObject@URR") == []


# ---------- 悬空 ----------

def test_dangling_edge_detected(tmp_data_dir):
    s = Store(tmp_data_dir)
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2",
         "## 边\n- 参见: [[UDG@MMLCommand@NOPE]]\n")
    idx = Index.build(s, Registry.load_default())
    assert idx.has_dangling()   # 目标不存在 → 悬空


def test_no_dangling_when_target_exists(tmp_data_dir):
    s = Store(tmp_data_dir)
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2",
         "## 边\n- 参见: [[UDG@MMLCommand@MOD URR]]\n")
    _cmd(s, "UDG@MMLCommand@MOD URR", "20.15.2")
    idx = Index.build(s, Registry.load_default())
    assert not idx.has_dangling()


# ---------- 网元/版本聚合辅助（给 /stats 用） ----------

def test_nfs(tmp_data_dir):
    s = Store(tmp_data_dir)
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2")
    _cfg(s, "UDG@ConfigObject@URR", "20.15.2")
    idx = Index.build(s, Registry.load_default())
    assert idx.nfs() == {"UDG"}


def test_versions_per_nf(tmp_data_dir):
    s = Store(tmp_data_dir)
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2")
    _cmd(s, "UDG@MMLCommand@OTHER", "20.16.0")
    idx = Index.build(s, Registry.load_default())
    vpm = idx.versions_per_nf()
    assert set(vpm["UDG"]) == {"20.15.2", "20.16.0"}


# ---------- 容错：缺 id / 未知类型不崩溃 ----------

def test_skips_md_without_id_or_unknown_type(tmp_data_dir):
    s = Store(tmp_data_dir)
    # 无 id
    s.write("Command/UDG/20.15.2/no_id.md",
            "---\ntype: MMLCommand\nversion: 20.15.2\n---\nno id\n")
    # 未知类型
    s.write("Command/UDG/20.15.2/unknown.md",
            "---\nid: UDG@WTF@x\ntype: WTF\nversion: 20.15.2\n---\nx\n")
    # 有效
    _cmd(s, "UDG@MMLCommand@ADD URR", "20.15.2")
    idx = Index.build(s, Registry.load_default())
    assert idx.node("UDG@MMLCommand@ADD URR", "20.15.2") is not None
    # 无 id / 未知类型的节点不进索引
    assert len(idx.nodes) == 1


def test_cross_nf_object_indexed(tmp_data_dir):
    s = Store(tmp_data_dir)
    md = (
        "---\n"
        "id: BusinessDomain@demo\n"
        "type: BusinessDomain\n"
        "domain: demo\n"
        "---\n# demo\n"
    )
    s.write("Business/demo/BusinessDomain@demo.md", md)
    idx = Index.build(s, Registry.load_default())
    n = idx.node("BusinessDomain@demo", None)
    assert n is not None
    assert n.scope == "cross"
    assert n.domain == "demo"
    assert n.version is None
