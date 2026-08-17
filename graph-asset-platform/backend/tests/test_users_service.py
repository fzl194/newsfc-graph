"""users.service 测试：gen_key 唯一、authenticate、check_perm 矩阵、create/reset/delete。"""


def _seed(tmp_path, monkeypatch, users):
    from app.users import store as users_store
    for u in users:
        users_store.add_user(u)


def test_gen_key_unique_and_format(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, [{"username": "a", "key": "sk-old"}])
    from app.users.service import gen_key
    k = gen_key()
    assert k.startswith("sk-") and len(k) == 21 and k != "sk-old"


def test_authenticate_by_key(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, [{"username": "u", "key": "k1", "can_skill": True}])
    from app.users.service import authenticate
    assert authenticate("k1")["username"] == "u"
    assert authenticate("nope") is None


def test_check_perm_matrix():
    from app.users.service import check_perm
    admin = {"is_admin": True}
    fe = {"can_frontend": True}
    fe_up = {"can_frontend": True, "can_upload": True}
    fe_test = {"can_frontend": True, "can_test": True}
    sk = {"can_skill": True}
    assets = {"can_assets": True}
    plain = {}
    # admin 全权
    assert all(check_perm(admin, p) for p in ("frontend", "assets", "upload", "test", "skill", "admin"))
    # can_frontend：前端✓，但 upload/test/assets✗（需额外 flag）
    assert check_perm(fe, "frontend") and not check_perm(fe, "upload") and not check_perm(fe, "test")
    assert not check_perm(fe, "assets")
    # can_frontend+can_upload：upload✓，test✗，assets 仍✗（upload 不再授予 /fs）
    assert check_perm(fe_up, "upload") and not check_perm(fe_up, "test") and not check_perm(fe_up, "assets")
    # can_frontend+can_test：test✓，upload✗
    assert check_perm(fe_test, "test") and not check_perm(fe_test, "upload")
    # 无 can_frontend 但有 can_upload：upload✗（依赖 can_frontend）
    assert not check_perm({"can_upload": True}, "upload")
    # can_assets：assets✓（独立，不依赖 can_frontend），前端✗
    assert check_perm(assets, "assets") and not check_perm(assets, "frontend")
    # can_skill：skill✓，前端✗
    assert check_perm(sk, "skill") and not check_perm(sk, "frontend")
    assert not check_perm(plain, "frontend")


def test_create_user_returns_key_and_rejects_dup(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, [{"username": "u", "key": "k"}])
    from app.users.service import create_user
    import pytest
    u = create_user("new", can_frontend=True, can_skill=False)
    assert u["key"].startswith("sk-") and u["can_frontend"] is True
    with pytest.raises(ValueError):
        create_user("u", can_frontend=False, can_skill=False)


def test_init_schema_migrates_can_assets(tmp_path):
    """旧 v1 users 表（无 can_assets）→ init_schema 补列 + admin 回填，普通用户为 0。"""
    from app.db import get_db, init_schema
    db = get_db(tmp_path / "old.db")
    db.execute(
        "CREATE TABLE users(username TEXT PRIMARY KEY, key TEXT, can_frontend INT, "
        "can_upload INT, can_test INT, can_skill INT, is_admin INT, created_at TEXT)"
    )
    db.execute("INSERT INTO users VALUES('admin','k',1,1,1,1,1,'')")
    db.execute("INSERT INTO users VALUES('fe','k2',1,0,0,0,0,'')")
    init_schema(db)  # 幂等迁移
    cols = {r[1] for r in db.execute("PRAGMA table_info(users)")}
    assert "can_assets" in cols
    rows = {r["username"]: r["can_assets"] for r in db.execute("SELECT username, can_assets FROM users")}
    assert rows == {"admin": 1, "fe": 0}


def test_reset_key_and_set_perms(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, [{"username": "u", "key": "k", "can_frontend": False}])
    from app.users.service import reset_key, set_perms
    from app.users.store import find_by_name
    new_k = reset_key("u")
    assert new_k and new_k != "k"
    set_perms("u", can_frontend=True, can_upload=False, can_test=False, can_skill=True, is_admin=False)
    assert find_by_name("u")["can_frontend"] is True


def test_set_perms_roundtrip_all_flags(tmp_path, monkeypatch):
    """set_perms 6 个权限位往返（防位置参数顺序写错）。"""
    _seed(tmp_path, monkeypatch, [{"username": "u", "key": "k"}])
    from app.users.service import set_perms
    from app.users.store import find_by_name
    set_perms("u", can_frontend=True, can_upload=True, can_test=False, can_skill=True, is_admin=False)
    u = find_by_name("u")
    assert u["can_frontend"] is True
    assert u["can_upload"] is True
    assert u["can_test"] is False
    assert u["can_skill"] is True
    assert u["is_admin"] is False
