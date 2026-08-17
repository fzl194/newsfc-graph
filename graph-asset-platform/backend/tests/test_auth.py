"""鉴权中间件测试（v2 用户体系）：KEY 反查用户 + 权限 + login 豁免 + 取消旁路 + 打点①。
每 test 加 tmp_data_dir 避免 lifespan 建真实索引。"""
import json
from fastapi.testclient import TestClient


def _seed(tmp_path, monkeypatch, users):
    # users 已迁 SQLite；seed 到 DB（_shared 由 conftest _empty_service 指向 tmp）
    from app.users import store as users_store
    for u in users:
        users_store.add_user(u)


ADMIN = {"username": "admin", "key": "gap_admin", "can_frontend": True, "can_upload": True, "can_test": True, "can_skill": True, "is_admin": True}
FE = {"username": "fe", "key": "gap_fe", "can_frontend": True}
SK = {"username": "sk", "key": "gap_sk", "can_skill": True}


def test_no_key_401(tmp_path, monkeypatch, tmp_data_dir):
    _seed(tmp_path, monkeypatch, [ADMIN])
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/v1/names").status_code == 401


def test_wrong_key_401(tmp_path, monkeypatch, tmp_data_dir):
    _seed(tmp_path, monkeypatch, [ADMIN])
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/v1/names", headers={"X-API-Key": "wrong"}).status_code == 401


def test_login_exempt_from_auth(tmp_path, monkeypatch, tmp_data_dir):
    """login 豁免鉴权：空 users 也能调 login（凭证错 → 401，但不是「未带KEY」401）。"""
    _seed(tmp_path, monkeypatch, [])
    from app.main import app
    with TestClient(app) as c:
        r = c.post("/api/v1/users/login", json={"username": "x", "key": "y"})
        assert r.status_code == 401


def test_empty_users_401_all(tmp_path, monkeypatch, tmp_data_dir):
    _seed(tmp_path, monkeypatch, [])
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/v1/names", headers={"X-API-Key": "any"}).status_code == 401


def test_skill_user_can_md_but_not_objects(tmp_path, monkeypatch, tmp_data_dir):
    _seed(tmp_path, monkeypatch, [SK])
    from app.main import app
    with TestClient(app) as c:
        h = {"X-API-Key": "gap_sk"}
        # /md 允许（id 不存在 → 200 含 error，非 403）
        assert c.post("/api/v1/md", json={"ids": ["x"]}, headers=h).status_code == 200
        assert c.get("/api/v1/objects", headers=h).status_code == 403


def test_frontend_user_can_objects(tmp_path, monkeypatch, tmp_data_dir):
    _seed(tmp_path, monkeypatch, [FE])
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/v1/objects", headers={"X-API-Key": "gap_fe"}).status_code == 200


def test_admin_can_users(tmp_path, monkeypatch, tmp_data_dir):
    _seed(tmp_path, monkeypatch, [ADMIN])
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/v1/users", headers={"X-API-Key": "gap_admin"}).status_code == 200


def test_frontend_user_cannot_users(tmp_path, monkeypatch, tmp_data_dir):
    _seed(tmp_path, monkeypatch, [FE])
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/v1/users", headers={"X-API-Key": "gap_fe"}).status_code == 403


# ---------------- assets / upload / test 权限 ----------------

def test_frontend_without_assets_denied_fs(tmp_path, monkeypatch, tmp_data_dir):
    """can_frontend（无 can_assets）→ /fs/* 全 403（新模型：/fs 专属 can_assets）。"""
    _seed(tmp_path, monkeypatch, [FE])
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/v1/fs/children", headers={"X-API-Key": "gap_fe"}).status_code == 403
        assert c.post("/api/v1/fs/mkdir", json={"path": "x"},
                      headers={"X-API-Key": "gap_fe"}).status_code == 403


def test_assets_user_can_fs_write(tmp_path, monkeypatch, tmp_data_dir):
    """can_assets → /fs 读写通过；can_frontend+can_upload 但无 can_assets → 403。"""
    _seed(tmp_path, monkeypatch, [
        {"username": "am", "key": "gap_am", "can_assets": True},
        {"username": "up", "key": "gap_up", "can_frontend": True, "can_upload": True},
    ])
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/v1/fs/children", headers={"X-API-Key": "gap_am"}).status_code == 200
        assert c.post("/api/v1/fs/mkdir", json={"path": "x"},
                      headers={"X-API-Key": "gap_am"}).status_code != 403
        # upload 权限不再授予 /fs
        assert c.post("/api/v1/fs/mkdir", json={"path": "y"},
                      headers={"X-API-Key": "gap_up"}).status_code == 403


def test_skill_user_cannot_write_assets_nor_tests(tmp_path, monkeypatch, tmp_data_dir):
    """can_skill 用户 → /fs/mkdir 403（中间件 assets 拦截）、/tests 403（需 test）。"""
    _seed(tmp_path, monkeypatch, [SK])
    from app.main import app
    with TestClient(app) as c:
        h = {"X-API-Key": "gap_sk"}
        assert c.post("/api/v1/fs/mkdir", json={"path": "x"}, headers=h).status_code == 403
        assert c.get("/api/v1/tests/cases", headers=h).status_code == 403


def test_x_user_id_recorded_as_operator(tmp_path, monkeypatch, tmp_data_dir):
    """SKILL 调用带 X-User-Id → 打点 operator 记工号（request 级 telemetry 表）。"""
    _seed(tmp_path, monkeypatch, [SK])
    from app.main import app
    with TestClient(app) as c:
        c.post("/api/v1/md", json={"ids": ["x"]}, headers={"X-API-Key": "gap_sk", "X-User-Id": "EMP1024"})
    import app.db as dbmod
    reqs = [dict(r) for r in dbmod.get_shared_db().execute(
        "SELECT * FROM telemetry WHERE level='request' AND endpoint='/api/v1/md'").fetchall()]
    assert reqs and reqs[0]["operator"] == "EMP1024"
    assert reqs[0]["user"] == "sk"
