"""objects router 测试：/objects /objects/{id} /neighbors /md /subgraph。

测试隔离 + 中立命名（demo/alpha/beta），不耦合具体业务。
v2：所有请求带 admin KEY（_setup seed admin 到 tmp users.json）。
"""
import io
import zipfile

from fastapi.testclient import TestClient

from app.index import Index
from app.main import app
from app.registry import Registry
from app.store import Store
import app.service as svc

# 测试用 admin（_setup seed 到 tmp users.json）
_ADMIN = {"username": "admin", "key": "gap_test_admin", "can_frontend": True, "can_upload": True, "can_test": True, "can_skill": True, "is_admin": True}
H = {"X-API-Key": "gap_test_admin"}

# MMLCommand（注册表内建类型）+ 一条指向 ConfigObject 的边
CMD_EDGES = (
    "---\n"
    "id: alpha@MMLCommand@ADD DEMO\n"
    "type: MMLCommand\n"
    "nf: alpha\n"
    "version: 20.15.2\n"
    "name: add demo command\n"
    "---\n"
    "# ADD DEMO\n"
    "## 边\n"
    "- 操作配置对象: [[alpha@ConfigObject@DEMO_OBJ]]\n"
)
# 同 id 的另一版本（测版本解析）
CMD_V2 = (
    "---\n"
    "id: alpha@MMLCommand@ADD DEMO\n"
    "type: MMLCommand\n"
    "nf: alpha\n"
    "version: 20.16.0\n"
    "---\n"
    "# ADD DEMO v2\n"
)
CFG = (
    "---\n"
    "id: alpha@ConfigObject@DEMO_OBJ\n"
    "type: ConfigObject\n"
    "nf: alpha\n"
    "version: 20.15.2\n"
    "object_kind: profile\n"
    "---\n"
    "# DEMO_OBJ\n"
)


def _setup(tmp_data_dir, monkeypatch, files):
    import app.db as dbmod
    s = svc.Service.__new__(svc.Service)
    s.store = Store(tmp_data_dir)
    s.registry = Registry.load_default()
    s.db = dbmod.get_db(tmp_data_dir.parent / "test.db")
    dbmod.init_schema(s.db)
    monkeypatch.setattr(dbmod, "_shared", s.db, raising=False)
    # 通过 import_bundle 走归类合并（与真实 /import 同路径）
    from app.bundle import import_bundle
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    import_bundle(buf.getvalue(), s.store, s.registry)
    s.rebuild()  # 全量 reindex：建 DB + 加载内存
    monkeypatch.setattr(svc, "_service", s)
    # seed admin 到 DB（users 表；_shared 由 _setup 上面已 monkeypatch 指向 tmp）
    from app.users import store as users_store
    users_store.add_user(_ADMIN)
    return s


# ---------------- /objects ----------------

def test_list_objects_filter_type(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_EDGES, "b.md": CFG})
    with TestClient(app) as c:
        r = c.get("/api/v1/objects", params={"type": "MMLCommand"}, headers=H)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["id"] == "alpha@MMLCommand@ADD DEMO"
        assert "20.15.2" in rows[0]["versions"]


def test_list_objects_search_q(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_EDGES})
    with TestClient(app) as c:
        # name 含 "add demo"
        r = c.get("/api/v1/objects", params={"q": "add demo"}, headers=H)
        rows = r.json()
        assert any(o["id"] == "alpha@MMLCommand@ADD DEMO" for o in rows)
        # 无关关键字 → 空
        r2 = c.get("/api/v1/objects", params={"q": "zzznope"}, headers=H)
        assert r2.json() == []


def test_list_objects_dedups_versions(tmp_data_dir, monkeypatch):
    # 同 id 两版本 → 列表里只出现一行，versions 聚合两条
    _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_EDGES, "v2.md": CMD_V2})
    with TestClient(app) as c:
        rows = c.get("/api/v1/objects", params={"type": "MMLCommand"}, headers=H).json()
        assert len(rows) == 1
        assert set(rows[0]["versions"]) == {"20.15.2", "20.16.0"}


# ---------------- /objects/{id} ----------------

def test_get_object_default_latest_version(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_EDGES, "v2.md": CMD_V2})
    with TestClient(app) as c:
        r = c.get("/api/v1/objects/alpha@MMLCommand@ADD DEMO", headers=H)  # 不带版本 → 最新
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == "20.16.0"  # 语义化排序最新
        assert set(body["versions"]) == {"20.15.2", "20.16.0"}
        # out_edges 来自最新版本（v2 无边 → 空）；这里只校验结构存在
        assert isinstance(body["out_edges"], list)


def test_get_object_explicit_version_with_out_edges(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_EDGES, "b.md": CFG})
    with TestClient(app) as c:
        r = c.get("/api/v1/objects/alpha@MMLCommand@ADD DEMO",
                  params={"version": "20.15.2"}, headers=H)
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == "20.15.2"
        assert len(body["out_edges"]) == 1
        assert body["out_edges"][0]["to"] == "alpha@ConfigObject@DEMO_OBJ"
        assert body["out_edges"][0]["relation"] == "操作配置对象"


def test_get_object_missing_version_404_lists_available(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_EDGES})
    with TestClient(app) as c:
        r = c.get("/api/v1/objects/alpha@MMLCommand@ADD DEMO",
                  params={"version": "9.9.9"}, headers=H)
        assert r.status_code == 404
        body = r.json()
        # spec §8.2：列出可用版本
        assert "20.15.2" in body["detail"]["available_versions"]


def test_get_object_unknown_id_404(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_EDGES})
    with TestClient(app) as c:
        r = c.get("/api/v1/objects/alpha@MMLCommand@NOPE", headers=H)
        assert r.status_code == 404


# ---------------- /neighbors ----------------

def test_neighbors_out_and_in(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_EDGES, "b.md": CFG})
    with TestClient(app) as c:
        # out: ADD DEMO → DEMO_OBJ
        r = c.get("/api/v1/objects/alpha@MMLCommand@ADD DEMO/neighbors", headers=H)
        assert r.status_code == 200
        body = r.json()
        assert body["center"]["id"] == "alpha@MMLCommand@ADD DEMO"
        assert any(e["to"] == "alpha@ConfigObject@DEMO_OBJ" for e in body["out"])

        # in: DEMO_OBJ 的反链指向 ADD DEMO（版本无关）
        r2 = c.get("/api/v1/objects/alpha@ConfigObject@DEMO_OBJ/neighbors", headers=H)
        body2 = r2.json()
        assert any(e["from"] == "alpha@MMLCommand@ADD DEMO" for e in body2["in"])


# ---------------- /md ----------------

def test_md_raw(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_EDGES})
    with TestClient(app) as c:
        r = c.get("/api/v1/objects/alpha@MMLCommand@ADD DEMO/md", headers=H)
        assert r.status_code == 200
        assert "text/markdown" in r.headers["content-type"]
        assert "ADD DEMO" in r.text
        assert "## 边" in r.text  # raw_md 是原始全文


# ---------------- /subgraph ----------------

def test_subgraph_one_hop(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_EDGES, "b.md": CFG})
    with TestClient(app) as c:
        r = c.get("/api/v1/subgraph",
                  params={"center": "alpha@MMLCommand@ADD DEMO", "hops": 1}, headers=H)
        assert r.status_code == 200
        body = r.json()
        ids = {n["id"] for n in body["nodes"]}
        assert "alpha@MMLCommand@ADD DEMO" in ids
        assert "alpha@ConfigObject@DEMO_OBJ" in ids
        assert any(e["to"] == "alpha@ConfigObject@DEMO_OBJ" for e in body["edges"])


def test_subgraph_unknown_center_404(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_EDGES})
    with TestClient(app) as c:
        r = c.get("/api/v1/subgraph", params={"center": "alpha@MMLCommand@NOPE"}, headers=H)
        assert r.status_code == 404


def test_list_objects_filter_by_ui_layer(tmp_data_dir, monkeypatch):
    """/objects?layer=命令层 返回 MMLCommand + ConfigObject，不含 Feature/Business。"""
    feat = (
        "---\n"
        "id: alpha@Feature@F-1\n"
        "type: Feature\n"
        "nf: alpha\n"
        "version: 20.15.2\n"
        "---\n"
        "# F-1\n"
    )
    _setup(tmp_data_dir, monkeypatch, {"cmd.md": CMD_EDGES, "cfg.md": CFG, "feat.md": feat})
    with TestClient(app) as c:
        rows = c.get("/api/v1/objects", params={"layer": "命令层"}, headers=H).json()
        types = {r["type"] for r in rows}
        assert types == {"MMLCommand", "ConfigObject"}
        # 特性层过滤
        rows_f = c.get("/api/v1/objects", params={"layer": "特性层"}, headers=H).json()
        assert {r["type"] for r in rows_f} == {"Feature"}
        # layer 与 nf+version 组合过滤
        rows_v = c.get("/api/v1/objects",
                       params={"layer": "命令层", "nf": "alpha",
                               "version": "20.15.2"}, headers=H).json()
        ids = {r["id"] for r in rows_v}
        assert "alpha@MMLCommand@ADD DEMO" in ids
        assert "alpha@ConfigObject@DEMO_OBJ" in ids


# ---------------- 旧 SKILL 两接口已删（MCP 服务化 2026-08-24） ----------------
# POST /domains 与 POST /md 的能力由 MCP 工具 get_domains / get_md 继承
# （语义测试见 test_mcp.py；版本解析矩阵见 test_e2e_versions.py）。

def test_skill_compat_endpoints_restored(tmp_data_dir, monkeypatch):
    """SKILL 兼容双接口已恢复（2026-09-03，与 MCP 并行；权限=skill）。
    契约回归（版本解析/批量语义/权限矩阵）见 test_skill_compat.py。"""
    _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_EDGES})
    with TestClient(app) as c:
        assert c.post("/api/v1/md", json={"ids": ["x"]}, headers=H).status_code == 200
        assert c.post("/api/v1/domains", headers=H).status_code == 200


# ---------------- 业务层 scenario / type 过滤 ----------------

_BD = (
    "---\n"
    "id: BusinessDomain@demo\n"
    "type: BusinessDomain\n"
    "domain: demo\n"
    "name: 演示域\n"
    "---\n"
    "# demo domain\n"
)
_NS = (
    "---\n"
    "id: NetworkScenario@demo-scenario\n"
    "type: NetworkScenario\n"
    "domain: demo\n"
    "scenario: demo-scenario\n"
    "---\n"
    "# demo-scenario\n"
)
_CS = (
    "---\n"
    "id: ConfigurationSolution@demo-scenario-online\n"
    "type: ConfigurationSolution\n"
    "domain: demo\n"
    "scenario: demo-scenario\n"
    "---\n"
    "# online\n"
)


def test_list_objects_business_scenario_and_type_filter(tmp_data_dir, monkeypatch):
    """业务层：scenario 过滤、type 过滤、ObjectRow 返 scenario 字段。"""
    _setup(tmp_data_dir, monkeypatch, {"bd.md": _BD, "ns.md": _NS, "cs.md": _CS})
    with TestClient(app) as c:
        # 业务层全量 = BD + NS + CS
        rows = c.get("/api/v1/objects", params={"layer": "业务层"}, headers=H).json()
        ids = {r["id"] for r in rows}
        assert ids == {"BusinessDomain@demo", "NetworkScenario@demo-scenario",
                       "ConfigurationSolution@demo-scenario-online"}
        # ObjectRow 带 scenario（NS/CS 有值；BD 无场景为 None）
        by_id = {r["id"]: r for r in rows}
        assert by_id["NetworkScenario@demo-scenario"]["scenario"] == "demo-scenario"
        assert by_id["BusinessDomain@demo"]["scenario"] is None
        # scenario 过滤 → 只剩该场景下 NS+CS（BD 无场景被排除）
        rows_sc = c.get("/api/v1/objects",
                        params={"layer": "业务层", "scenario": "demo-scenario"}, headers=H).json()
        ids_sc = {r["id"] for r in rows_sc}
        assert ids_sc == {"NetworkScenario@demo-scenario",
                          "ConfigurationSolution@demo-scenario-online"}
        assert "BusinessDomain@demo" not in ids_sc
        # type 过滤：只 BD
        rows_bd = c.get("/api/v1/objects",
                        params={"layer": "业务层", "type": "BusinessDomain"}, headers=H).json()
        assert {r["id"] for r in rows_bd} == {"BusinessDomain@demo"}


def test_stats_per_domain_scenario(tmp_data_dir, monkeypatch):
    """/stats 聚合 per_domain 与 per_domain_scenario（供前端域/场景下拉）。"""
    _setup(tmp_data_dir, monkeypatch, {"bd.md": _BD, "ns.md": _NS, "cs.md": _CS})
    with TestClient(app) as c:
        s = c.get("/api/v1/stats", headers=H).json()
        # demo 域共 3 对象
        assert s["per_domain"]["demo"] == 3
        # demo 域下 demo-scenario 场景共 2 对象（NS+CS；BD 无场景不计入）
        assert s["per_domain_scenario"]["demo"]["demo-scenario"] == 2
        # 业务层计数 = 3
        assert s["per_layer"]["业务层"] == 3


def test_list_objects_graph_layer_alias(tmp_data_dir, monkeypatch):
    """三图谱层别名（2026-09-03，仅图谱浏览页使用；旧 4 层名不动）：
    业务图谱 = 任务层 + 业务层联合；命令图谱/特性图谱与旧层等价。"""
    feat = (
        "---\n"
        "id: alpha@Feature@F-1\n"
        "type: Feature\n"
        "nf: alpha\n"
        "version: 20.15.2\n"
        "---\n"
        "# F-1\n"
    )
    atom = (
        "---\n"
        "id: alpha@AtomTask@T-1\n"
        "type: AtomTask\n"
        "nf: alpha\n"
        "---\n"
        "# T-1\n"
    )
    biz = (
        "---\n"
        "id: alpha@BusinessDomain@D-1\n"
        "type: BusinessDomain\n"
        "domain: demo\n"
        "---\n"
        "# D-1\n"
    )
    _setup(tmp_data_dir, monkeypatch,
           {"cmd.md": CMD_EDGES, "cfg.md": CFG, "feat.md": feat,
            "atom.md": atom, "biz.md": biz})
    with TestClient(app) as c:
        rows = c.get("/api/v1/objects", params={"layer": "业务图谱"}, headers=H).json()
        types = {r["type"] for r in rows}
        assert types == {"AtomTask", "BusinessDomain"}  # 不含命令/特性
        rows2 = c.get("/api/v1/objects", params={"layer": "命令图谱"}, headers=H).json()
        assert {r["type"] for r in rows2} == {"MMLCommand", "ConfigObject"}
        rows3 = c.get("/api/v1/objects", params={"layer": "特性图谱"}, headers=H).json()
        assert {r["type"] for r in rows3} == {"Feature"}
