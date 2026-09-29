"""files 户口册 repo 单元测试（spec §4.1/§4.2）。"""
import pytest

from app.repos import files_repo


@pytest.fixture
def conn_db(tmp_data_dir):
    import app.db as dbmod
    conn = dbmod.get_db(tmp_data_dir.parent / "t.db")
    dbmod.init_schema(conn)
    return conn


@pytest.fixture
def store(tmp_data_dir):
    from app.store import Store
    return Store(tmp_data_dir)


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_upsert_and_remove_roundtrip(conn_db, store):
    store.write("Command/UDG/20.15.2/x.md", "hello")
    files_repo.upsert_from_disk(conn_db, store, "Command/UDG/20.15.2/x.md")
    row = conn_db.execute("SELECT * FROM files WHERE path=?",
                          ("Command/UDG/20.15.2/x.md",)).fetchone()
    assert row["name"] == "x.md" and row["ext"] == "md" and row["is_dir"] == 0
    assert row["size"] == 5
    assert _count(conn_db, "files_fts") == 1
    # FTS 名字已规范化：不同大小写可命中
    assert conn_db.execute(
        "SELECT 1 FROM files_fts WHERE files_fts MATCH 'name : \"x.md\"'").fetchone()
    files_repo.remove_path(conn_db, "Command/UDG/20.15.2/x.md")
    assert _count(conn_db, "files") == 0 and _count(conn_db, "files_fts") == 0
    assert _count(conn_db, "files_fts_map") == 0  # map 同步清（无幽灵）


def test_upsert_from_disk_missing_removes_row(conn_db, store):
    files_repo.upsert_entry(conn_db, path="gone.md", name="gone.md", ext="md",
                            is_dir=0, size=1, mtime=0.0)
    files_repo.upsert_from_disk(conn_db, store, "gone.md")  # 磁盘不存在 → 删行
    assert _count(conn_db, "files") == 0


def test_remove_prefix_removes_subtree_and_self(conn_db, store):
    store.makedirs("Command/UDG/20.15.2")
    store.write("Command/UDG/20.15.2/a.md", "a")
    store.write("Command/UDG/20.15.2/sub/b.md", "b")
    files_repo.upsert_tree(conn_db, store, "Command")
    # Command 自身 + UDG + 20.15.2 + a.md + sub + b.md = 6
    assert _count(conn_db, "files") == 6
    # 目录 ext 恒 ''（schema 注释）：点名目录（版本号 20.15.2）不得算出 '2'
    row = conn_db.execute(
        "SELECT * FROM files WHERE path='Command/UDG/20.15.2'").fetchone()
    assert row["is_dir"] == 1 and row["ext"] == ""
    files_repo.remove_prefix(conn_db, "Command/UDG")
    assert _count(conn_db, "files") == 1  # 只剩 Command/
    assert _count(conn_db, "files_fts") == 1


def test_rebuild_all_skips_dotfiles_and_includes_dirs(conn_db, store):
    store.write("Command/a.md", "a")
    store.makedirs("Command/UDG/20.15.2")  # 含点号的目录名（版本目录）
    (store.root / ".hidden").write_text("x", encoding="utf-8")
    (store.root / "Command" / ".h").write_text("y", encoding="utf-8")
    n = files_repo.rebuild_all(conn_db, store)
    assert n == 4  # Command/ + UDG/ + 20.15.2/ 目录行 + a.md；点文件全跳过
    rows = {r["path"]: r for r in conn_db.execute("SELECT * FROM files")}
    assert rows["Command"]["is_dir"] == 1
    assert rows["Command"]["ext"] == ""
    assert rows["Command/UDG/20.15.2"]["ext"] == ""  # 目录 ext 恒 ''（非 '2'）


def test_reupsert_map_hit_keeps_single_fts_row(conn_db, store):
    store.write("a.md", "a")
    files_repo.upsert_from_disk(conn_db, store, "a.md")
    files_repo.upsert_from_disk(conn_db, store, "a.md")  # map 命中 → rowid 删旧行
    assert _count(conn_db, "files") == 1
    assert _count(conn_db, "files_fts") == 1
    assert _count(conn_db, "files_fts_map") == 1


def test_reupsert_map_miss_fallback_no_ghost(conn_db, store):
    store.write("a.md", "a")
    files_repo.upsert_from_disk(conn_db, store, "a.md")
    conn_db.execute("DELETE FROM files_fts_map WHERE path='a.md'")  # 模拟 map 行丢失
    conn_db.commit()
    files_repo.upsert_from_disk(conn_db, store, "a.md")  # map-miss → path 回退删
    assert _count(conn_db, "files_fts") == 1  # 不留重复（幽灵）行
    assert files_repo.integrity_ok(conn_db)
    # 重复感知对账：EXCEPT 集合语义查不出重复行，COUNT 感知须能查出
    conn_db.execute("INSERT INTO files_fts(path, name) VALUES('a.md', 'a.md')")
    conn_db.commit()
    assert not files_repo.integrity_ok(conn_db)


def test_upsert_from_disk_rejects_and_heals_dotfiles(conn_db, store):
    store.write("a/.secret.md", "s")
    files_repo.upsert_from_disk(conn_db, store, "a/.secret.md")  # 单路径入口拦截
    assert _count(conn_db, "files") == 0
    # 自愈：已在册的点文件（历史脏数据）同样被清，FTS/map 无残留
    files_repo.upsert_entry(conn_db, path="a/.secret.md", name=".secret.md",
                            ext="md", is_dir=0, size=1, mtime=0.0)
    files_repo.upsert_from_disk(conn_db, store, "a/.secret.md")
    assert _count(conn_db, "files") == 0
    assert _count(conn_db, "files_fts") == 0
    assert _count(conn_db, "files_fts_map") == 0


def test_integrity_ok_detects_drift(conn_db, store):
    store.write("a.md", "a")
    files_repo.rebuild_all(conn_db, store)
    assert files_repo.integrity_ok(conn_db)
    conn_db.execute("DELETE FROM files WHERE path='a.md'")  # 制造漂移
    conn_db.commit()
    assert not files_repo.integrity_ok(conn_db)


def _bare_service(tmp_data_dir):
    """__new__ 装配（同 test_fs._setup 形态），返回 service。"""
    import app.service as svc_mod
    from app.store import Store
    import app.db as dbmod
    from app.registry import Registry
    s = svc_mod.Service.__new__(svc_mod.Service)
    s.store = Store(tmp_data_dir)
    s.db = dbmod.get_db(tmp_data_dir.parent / "t.db")
    dbmod.init_schema(s.db)
    s.registry = Registry.load_default()
    return s


def test_rebuild_populates_files(tmp_data_dir):
    s = _bare_service(tmp_data_dir)
    s.store.write("Command/a.md", "a")
    s.rebuild()  # 应连带重建 files 户口册
    assert s.db.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 2
    assert s.index is not None  # Index.load_from_db 走通


def test_files_bootstrap_async(tmp_data_dir):
    s = _bare_service(tmp_data_dir)
    s.store.write("Feature/x/概述.md", "f")
    s.files_building = True
    s._files_bootstrap_async()  # 同步直调（后台线程跑的就是这个函数体）
    assert s.files_building is False
    # Feature + x + 概述.md = 3 行
    assert s.db.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 3
