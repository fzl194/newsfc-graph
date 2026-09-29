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
    files_repo.remove_prefix(conn_db, "Command/UDG")
    assert _count(conn_db, "files") == 1  # 只剩 Command/
    assert _count(conn_db, "files_fts") == 1


def test_rebuild_all_skips_dotfiles_and_includes_dirs(conn_db, store):
    store.write("Command/a.md", "a")
    (store.root / ".hidden").write_text("x", encoding="utf-8")
    (store.root / "Command" / ".h").write_text("y", encoding="utf-8")
    n = files_repo.rebuild_all(conn_db, store)
    assert n == 2  # Command/ 目录行 + a.md；点文件全跳过
    rows = {r["path"]: r for r in conn_db.execute("SELECT * FROM files")}
    assert rows["Command"]["is_dir"] == 1
    assert rows["Command"]["ext"] == ""


def test_integrity_ok_detects_drift(conn_db, store):
    store.write("a.md", "a")
    files_repo.rebuild_all(conn_db, store)
    assert files_repo.integrity_ok(conn_db)
    conn_db.execute("DELETE FROM files WHERE path='a.md'")  # 制造漂移
    conn_db.commit()
    assert not files_repo.integrity_ok(conn_db)
