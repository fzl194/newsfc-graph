"""多版本端到端测试：版本切换可见性 / 语义版本排序 / SKILL 接口（/md /domains）
多版本取数 / 打点 / 搜索（含中文名 name_zh）。

回归背景（2026-08-14 修复）：list_objects 曾先按 id 聚合「最新版本」再按 version
过滤，导致选旧版本时同 id 的对象全部不可见（前端切版本「啥都看不到」）。
语义排序回归：字符串比较会误判 "20.9.10" > "20.15.2"。

语料（自定义 zip，不耦合 sample_bundle）：
- UDG ACT DEMO：同 id 双版本 20.15.2 / 20.16.2，两版本出边不同
- UDG OLD ONLY：仅 20.15.2
- UNC SEM TRAP：20.9.10 + 20.15.2（语义陷阱：字符串比较会选错最新）
- UDG ConfigObject@URR：边目标（跨版本共用）
- BusinessDomain@demo：/domains 用（version 恒 null）
"""
import io
import zipfile

from fastapi.testclient import TestClient

from app.bundle import import_bundle
from app.main import app
from app.registry import Registry
from app.store import Store
import app.service as svc

ACT_DEMO = "UDG@MMLCommand@ACT DEMO"
OLD_ONLY = "UDG@MMLCommand@OLD ONLY"
SEM_TRAP = "UNC@MMLCommand@SEM TRAP"


def _cmd_md(id_: str, version: str, name_zh: str, edge: tuple | None = None) -> str:
    lines = [
        "---",
        f"id: {id_}",
        "type: MMLCommand",
        f"name: {id_.split('@')[-1]}",
        f"name_zh: {name_zh}",
        "nf: " + id_.split("@", 1)[0],
        f"version: {version}",
        "status: active",
        "---",
        f"# {id_}",
        "",
        f"{name_zh}（{version}）。",
        "",
        "## 边",
    ]
    if edge is not None:
        lines.append(f"- {edge[0]}: [[{edge[1]}]]")
    return "\n".join(lines) + "\n"


def _e2e_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Command/UDG/20.15.2/UDG@MMLCommand@ACT DEMO.md",
                   _cmd_md(ACT_DEMO, "20.15.2", "演示命令", ("操作配置对象", "UDG@ConfigObject@URR")))
        z.writestr("Command/UDG/20.16.2/UDG@MMLCommand@ACT DEMO.md",
                   _cmd_md(ACT_DEMO, "20.16.2", "演示命令", ("参见", OLD_ONLY)))
        z.writestr("Command/UDG/20.15.2/UDG@MMLCommand@OLD ONLY.md",
                   _cmd_md(OLD_ONLY, "20.15.2", "仅旧版本"))
        z.writestr("Command/UNC/20.9.10/UNC@MMLCommand@SEM TRAP.md",
                   _cmd_md(SEM_TRAP, "20.9.10", "语义陷阱"))
        z.writestr("Command/UNC/20.15.2/UNC@MMLCommand@SEM TRAP.md",
                   _cmd_md(SEM_TRAP, "20.15.2", "语义陷阱"))
        z.writestr(
            "ConfigObject/UDG/20.15.2/UDG@ConfigObject@URR.md",
            "---\nid: UDG@ConfigObject@URR\ntype: ConfigObject\nname: URR\n"
            "name_zh: 用量统计规则\nnf: UDG\nversion: 20.15.2\n---\n# URR\n",
        )
        z.writestr(
            "Business/demo/BusinessDomain@demo.md",
            "---\nid: BusinessDomain@demo\ntype: BusinessDomain\nname: demo域\n"
            "name_zh: 演示业务域\ndomain: demo\n---\n# demo\n业务域正文。\n",
        )
    return buf.getvalue()


def _setup(tmp_data_dir, monkeypatch):
    """导入多版本语料到 tmp store，service 单例指向它。"""
    import app.db as dbmod
    s = svc.Service.__new__(svc.Service)
    s.store = Store(tmp_data_dir)
    s.registry = Registry.load_default()
    s.db = dbmod.get_db(tmp_data_dir.parent / "test.db")
    dbmod.init_schema(s.db)
    monkeypatch.setattr(dbmod, "_shared", s.db, raising=False)
    import_bundle(_e2e_zip(), s.store, s.registry)
    s.rebuild()
    monkeypatch.setattr(svc, "_service", s)
    return s


# ---------------- 版本切换可见性（核心回归） ----------------

def test_old_version_list_visible(tmp_data_dir, monkeypatch):
    """选旧版本 20.15.2 → 同 id 双版本对象仍可见（修复前为 0 行）。"""
    _setup(tmp_data_dir, monkeypatch)
    with TestClient(app) as c:
        r = c.get("/api/v1/objects", params={"nf": "UDG", "version": "20.15.2"})
        assert r.status_code == 200
        ids = {row["id"] for row in r.json()}
        assert ACT_DEMO in ids          # 双版本对象在旧版本可见
        assert OLD_ONLY in ids          # 仅旧版本对象
        # 新版本过滤：OLD ONLY 消失，ACT DEMO 仍在
        r2 = c.get("/api/v1/objects", params={"nf": "UDG", "version": "20.16.2"})
        ids2 = {row["id"] for row in r2.json()}
        assert ACT_DEMO in ids2
        assert OLD_ONLY not in ids2


def test_no_version_list_merges_versions(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    with TestClient(app) as c:
        r = c.get("/api/v1/objects", params={"nf": "UDG"})
        row = next(x for x in r.json() if x["id"] == ACT_DEMO)
        assert set(row["versions"]) == {"20.15.2", "20.16.2"}


# ---------------- 语义版本排序 ----------------

def test_semantic_latest_not_string_compare(tmp_data_dir, monkeypatch):
    """20.9.10 vs 20.15.2：语义最新是 20.15.2（字符串比较会错选 20.9.10）。"""
    _setup(tmp_data_dir, monkeypatch)
    with TestClient(app) as c:
        r = c.get(f"/api/v1/objects/{SEM_TRAP}")
        assert r.status_code == 200
        assert r.json()["version"] == "20.15.2"
        # /md 不带 version 同样落语义最新
        r2 = c.post("/api/v1/md", json={"ids": [SEM_TRAP]})
        assert r2.status_code == 200
        assert r2.json()[SEM_TRAP]["version"] == "20.15.2"


# ---------------- 单对象 / 邻居的版本维度 ----------------

def test_object_and_neighbors_per_version(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    with TestClient(app) as c:
        # 旧版本出边 → ConfigObject
        r = c.get(f"/api/v1/objects/{ACT_DEMO}", params={"version": "20.15.2"})
        assert r.status_code == 200
        assert r.json()["version"] == "20.15.2"
        targets = {e["to"] for e in r.json()["out_edges"]}
        assert targets == {"UDG@ConfigObject@URR"}
        # 新版本出边 → OLD ONLY（版本间边不同）
        r2 = c.get(f"/api/v1/objects/{ACT_DEMO}", params={"version": "20.16.2"})
        assert {e["to"] for e in r2.json()["out_edges"]} == {OLD_ONLY}
        # neighbors 同样按版本取边
        n = c.get(f"/api/v1/objects/{ACT_DEMO}/neighbors", params={"version": "20.15.2"})
        assert {e["to"] for e in n.json()["out"]} == {"UDG@ConfigObject@URR"}
        # 错版本 → 404 + available_versions
        bad = c.get(f"/api/v1/objects/{ACT_DEMO}", params={"version": "9.9.9"})
        assert bad.status_code == 404
        assert set(bad.json()["detail"]["available_versions"]) == {"20.15.2", "20.16.2"}


# ---------------- SKILL /md 多版本 ----------------

def test_skill_md_both_versions_and_latest(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    with TestClient(app) as c:
        # 指定旧版本
        r = c.post("/api/v1/md", json={"ids": [ACT_DEMO], "version": "20.15.2"})
        body = r.json()[ACT_DEMO]
        assert body["version"] == "20.15.2"
        assert "20.15.2" in body["md"]
        # 指定新版本
        r2 = c.post("/api/v1/md", json={"ids": [ACT_DEMO], "version": "20.16.2"})
        assert r2.json()[ACT_DEMO]["version"] == "20.16.2"
        # 不带 version → 最新
        r3 = c.post("/api/v1/md", json={"ids": [ACT_DEMO]})
        assert r3.json()[ACT_DEMO]["version"] == "20.16.2"
        # 错版本 → 单 id 计错回带可用版本，其余 id 不受影响
        # （ACT_DEMO 有 20.16.2 照常返回；OLD_ONLY 仅有 20.15.2 → 计错）
        r4 = c.post("/api/v1/md", json={"ids": [ACT_DEMO, OLD_ONLY], "version": "20.16.2"})
        out = r4.json()
        assert out[ACT_DEMO]["version"] == "20.16.2"
        assert "available_versions" in out[OLD_ONLY]
        assert out[OLD_ONLY].get("error")
        assert set(out[OLD_ONLY]["available_versions"]) == {"20.15.2"}


# ---------------- SKILL /domains ----------------

def test_skill_domains_returns_md(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    with TestClient(app) as c:
        r = c.post("/api/v1/domains")
        assert r.status_code == 200
        domains = r.json()
        demo = next(d for d in domains if d["id"] == "BusinessDomain@demo")
        assert "业务域正文" in demo["md"]


# ---------------- 打点（caller=skill + operator） ----------------

def test_telemetry_records_skill_calls(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    from app.middleware import auth
    skill_user = {"username": "agent01", "key": "sk", "can_frontend": False,
                  "can_assets": False, "can_upload": False, "can_test": False,
                  "can_skill": True, "is_admin": False}
    admin = {"username": "admin", "key": "x", "can_frontend": True, "can_assets": True,
             "can_upload": True, "can_test": True, "can_skill": True, "is_admin": True}
    headers = {"X-API-Key": "sk", "X-User-Id": "EMP-777"}
    with TestClient(app) as c:
        monkeypatch.setattr(auth, "authenticate", lambda key: skill_user)
        r = c.post("/api/v1/md", json={"ids": [ACT_DEMO]}, headers=headers)
        assert r.status_code == 200
        c.post("/api/v1/domains", headers=headers)
        # 回到 admin 读打点（skill 用户无 frontend 权限读不了 telemetry）
        monkeypatch.setattr(auth, "authenticate", lambda key: admin)
        usage = c.get("/api/v1/telemetry/skill-usage").json()
        events = usage["events"]
        md_ev = [e for e in events if e["endpoint"] == "/md" and e.get("obj_id") == ACT_DEMO]
        assert md_ev, f"/md 打点缺失: {events}"
        assert md_ev[0]["operator"] == "EMP-777"
        assert md_ev[0]["user"] == "agent01"
        # skill-usage 流本身就是 caller=skill 口径（字段不重复携带 caller）
        assert any(e["endpoint"] == "/domains" and e["operator"] == "EMP-777" for e in events)
        stats = c.get("/api/v1/telemetry/stats").json()
        assert stats["total"] >= 2


# ---------------- 搜索 + 总数头 ----------------

def test_search_matches_name_zh_and_total_header(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    with TestClient(app) as c:
        # 中文名（name_zh）命中
        r = c.get("/api/v1/objects", params={"nf": "UDG", "q": "演示命令"})
        ids = {row["id"] for row in r.json()}
        assert ACT_DEMO in ids
        assert r.headers.get("X-Total-Count") == str(len(r.json()))
        # id 子串命中
        r2 = c.get("/api/v1/objects", params={"q": "OLD ONLY"})
        assert OLD_ONLY in {row["id"] for row in r2.json()}
        # total 是分页前的总数：size=1 时 total 仍为全集
        r3 = c.get("/api/v1/objects", params={"nf": "UDG", "size": 1})
        assert len(r3.json()) == 1
        assert int(r3.headers["X-Total-Count"]) > 1
