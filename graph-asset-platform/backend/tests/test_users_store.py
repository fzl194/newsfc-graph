"""users.store 测试：users.json 读写、按 key/name 查、增删改。"""
import json


def _use_tmp_users(tmp_path, monkeypatch):
    """重置 _shared 到独立 tmp DB（隔离每个 test_users_store 测试）。"""
    import app.db as dbmod
    db = dbmod.get_db(tmp_path / "test.db")
    dbmod.init_schema(db)
    monkeypatch.setattr(dbmod, "_shared", db, raising=False)
    return db


def test_load_empty_when_absent(tmp_path, monkeypatch):
    _use_tmp_users(tmp_path, monkeypatch)
    from app.users.store import list_users
    assert list_users() == []


def test_add_and_find_by_key(tmp_path, monkeypatch):
    _use_tmp_users(tmp_path, monkeypatch)
    from app.users.store import add_user, find_by_key
    add_user({"username": "admin", "key": "gap_abc", "can_frontend": True})
    u = find_by_key("gap_abc")
    assert u is not None and u["username"] == "admin"
    assert find_by_key("nope") is None


def test_find_by_name_and_update_and_delete(tmp_path, monkeypatch):
    _use_tmp_users(tmp_path, monkeypatch)
    from app.users.store import add_user, find_by_name, update_user, delete_user
    add_user({"username": "u1", "key": "k1", "can_skill": True})
    assert find_by_name("u1") is not None
    updated = update_user("u1", {"can_frontend": True})
    assert updated["can_frontend"] is True
    assert delete_user("u1") is True
    assert find_by_name("u1") is None
    assert delete_user("u1") is False  # 已删


def test_persists_to_disk(tmp_path, monkeypatch):
    db = _use_tmp_users(tmp_path, monkeypatch)
    from app.users.store import add_user
    add_user({"username": "x", "key": "kx"})
    # 验证 DB 持久化（直接查 users 表）
    from app.repos import users_repo
    assert users_repo.find_by_name(db, "x") is not None
