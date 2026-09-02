"""SKILL 兼容双接口（2026-09-03 恢复，与 MCP 并行）——契约回归。

语义逐行对齐 e4922b4 删除前的旧测试：/domains 返回全部业务域最新 md；
/md 批量取 md（不传 version→最新现存；版本缺失→该 id 计错回带可用版本，
不影响其余 id）。权限=skill（与 MCP 一致：can_skill ∨ can_frontend，admin 全权）。
"""
from fastapi.testclient import TestClient

from app.main import app
from tests.test_api_objects import _setup, CMD_EDGES, CMD_V2, CFG

BIZ = (
    "---\n"
    "id: alpha@BusinessDomain@demo\n"
    "type: BusinessDomain\n"
    "domain: demo\n"
    "---\n"
    "# 业务感知\n"
)

client = TestClient(app)


def _seed(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch,
           {"cmd.md": CMD_EDGES, "v2.md": CMD_V2, "cfg.md": CFG, "biz.md": BIZ})


def test_domains_returns_all_business_domain_md(tmp_data_dir, monkeypatch):
    _seed(tmp_data_dir, monkeypatch)
    r = client.post("/api/v1/domains")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    d = body[0]
    assert d["id"] == "alpha@BusinessDomain@demo"
    assert "业务感知" in d["md"]
    assert "name" in d  # 旧契约 frontmatter.get("name")，无 name 字段时为 None


def test_md_batch_latest_version(tmp_data_dir, monkeypatch):
    """不传 version → 各 id 最新现存版本 + 原始 md。"""
    _seed(tmp_data_dir, monkeypatch)
    r = client.post("/api/v1/md", json={
        "ids": ["alpha@MMLCommand@ADD DEMO", "alpha@ConfigObject@DEMO_OBJ"]})
    assert r.status_code == 200, r.text
    body = r.json()
    # CMD 有 20.15.2+20.16.0，不传 version → 最新 20.16.0
    cmd = body["alpha@MMLCommand@ADD DEMO"]
    assert cmd["version"] == "20.16.0"
    assert "ADD DEMO" in cmd["md"]
    assert "DEMO_OBJ" in body["alpha@ConfigObject@DEMO_OBJ"]["md"]


def test_md_version_missing_and_nonexistent(tmp_data_dir, monkeypatch):
    """版本缺失→该 id 计错回带 available_versions；不存在 id→对象不存在；互不影响。"""
    _seed(tmp_data_dir, monkeypatch)
    r = client.post("/api/v1/md", json={
        "ids": ["alpha@MMLCommand@ADD DEMO", "nope@MMLCommand@X"],
        "version": "20.15.2"})
    body = r.json()
    ok = body["alpha@MMLCommand@ADD DEMO"]
    assert ok["version"] == "20.15.2" and "ADD DEMO" in ok["md"]
    miss = body["nope@MMLCommand@X"]
    assert miss["error"] == "对象不存在" and miss["available_versions"] == []
    # 版本不存在场景
    r2 = client.post("/api/v1/md", json={
        "ids": ["alpha@MMLCommand@ADD DEMO"], "version": "19.0.0"})
    m = r2.json()["alpha@MMLCommand@ADD DEMO"]
    assert m["error"].startswith("版本不存在")
    assert set(m["available_versions"]) == {"20.15.2", "20.16.0"}


def test_md_dedup_same_id(tmp_data_dir, monkeypatch):
    """同 id 重复请求只算一次条目（dict.fromkeys 去重保序）。"""
    _seed(tmp_data_dir, monkeypatch)
    r = client.post("/api/v1/md", json={
        "ids": ["alpha@ConfigObject@DEMO_OBJ", "alpha@ConfigObject@DEMO_OBJ"]})
    assert list(r.json().keys()) == ["alpha@ConfigObject@DEMO_OBJ"]


def test_skill_perm_same_as_mcp(tmp_data_dir, monkeypatch):
    """权限=skill：can_skill ∨ can_frontend 放行（admin 全权）；两者皆无 → 403。"""
    _seed(tmp_data_dir, monkeypatch)
    from app.middleware import auth as auth_mod

    def _as(user):
        monkeypatch.setattr(auth_mod, "authenticate", lambda key: user)
        return (client.post("/api/v1/domains").status_code,
                client.post("/api/v1/md", json={"ids": ["alpha@ConfigObject@DEMO_OBJ"]}).status_code)

    assert _as({"username": "sk", "can_skill": True}) == (200, 200)
    assert _as({"username": "fe", "can_frontend": True}) == (200, 200)
    assert _as({"username": "none", "can_assets": True}) == (403, 403)
