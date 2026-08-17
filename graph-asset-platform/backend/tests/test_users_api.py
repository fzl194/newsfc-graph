"""users router 测试：login（公开）+ CRUD。权限矩阵测试在 Task 5（中间件）后补。"""
import json
from fastapi.testclient import TestClient


def _seed_users(tmp_path, monkeypatch, users):
    from app.users import store as users_store
    for u in users:
        users_store.add_user(u)


ADMIN = {"username": "admin", "key": "gap_admin", "can_frontend": True, "can_upload": True, "can_test": True, "can_skill": True, "is_admin": True}
SKILL_ONLY = {"username": "sa", "key": "gap_sa", "can_skill": True}


def test_login_success(tmp_path, monkeypatch, tmp_data_dir):
    _seed_users(tmp_path, monkeypatch, [ADMIN])
    from app.main import app
    with TestClient(app) as c:
        r = c.post("/api/v1/users/login", json={"username": "admin", "key": "gap_admin"})
        assert r.status_code == 200
        assert r.json()["is_admin"] is True


def test_login_wrong_creds(tmp_path, monkeypatch, tmp_data_dir):
    _seed_users(tmp_path, monkeypatch, [ADMIN])
    from app.main import app
    with TestClient(app) as c:
        assert c.post("/api/v1/users/login", json={"username": "admin", "key": "wrong"}).status_code == 401


def test_login_no_frontend_perm(tmp_path, monkeypatch, tmp_data_dir):
    _seed_users(tmp_path, monkeypatch, [SKILL_ONLY])
    from app.main import app
    with TestClient(app) as c:
        # sa 只有 can_skill，不能登录前端
        assert c.post("/api/v1/users/login", json={"username": "sa", "key": "gap_sa"}).status_code == 403


def test_admin_can_list_and_create(tmp_path, monkeypatch, tmp_data_dir):
    _seed_users(tmp_path, monkeypatch, [ADMIN])
    from app.main import app
    with TestClient(app) as c:
        h = {"X-API-Key": "gap_admin"}
        assert c.get("/api/v1/users", headers=h).status_code == 200
        r = c.post("/api/v1/users", json={"username": "new", "can_skill": True}, headers=h)
        assert r.status_code == 200
        assert r.json()["key"].startswith("sk-")


def test_admin_can_view_activity(tmp_path, monkeypatch, tmp_data_dir):
    _seed_users(tmp_path, monkeypatch, [ADMIN])
    from app.main import app
    with TestClient(app) as c:
        r = c.get("/api/v1/users/admin/activity?days=7", headers={"X-API-Key": "gap_admin"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)
