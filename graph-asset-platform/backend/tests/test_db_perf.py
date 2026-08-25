"""增量索引性能基建回归（2026-08-25）：source_path 索引 + md_fts_map + WAL NORMAL。

背景：reindex_path 每文件两个全表扫——objects 按 source_path（无索引）、md_fts 按
UNINDEXED 列（含全部正文页）——批量增量索引 O(N²)；且每文件 commit 在
synchronous=FULL 下逐条 fsync。本文件用确定性断言（EXPLAIN QUERY PLAN / PRAGMA /
行数对账）锁定三项基建不被回归。
"""
from app import db as dbmod
from app.repos import fts_repo


def test_objects_source_path_index_used(tmp_path):
    """v7 索引存在且 delete_by_source 走索引查找（SEARCH 非 SCAN）。"""
    conn = dbmod.get_db(tmp_path / "t.db")
    dbmod.init_schema(conn)
    names = {r["name"] for r in conn.execute("PRAGMA index_list(objects)")}
    assert "idx_objects_source" in names
    plan = [dict(r)["detail"] for r in conn.execute(
        "EXPLAIN QUERY PLAN SELECT id, version FROM objects WHERE source_path=?",
        ("x",))]
    assert any("SEARCH objects" in d and "idx_objects_source" in d for d in plan)
    assert not any(d.startswith("SCAN objects") for d in plan)


def test_wal_synchronous_normal(tmp_path):
    """WAL + synchronous=NORMAL（免逐条 fsync；断电才可能丢最近提交）。"""
    conn = dbmod.get_db(tmp_path / "t.db")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    # SQLite: 0=OFF 1=NORMAL 2=FULL
    assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1


# ---------- md_fts_map：按 rowid 删 ----------

def test_fts_upsert_delete_via_map(tmp_path):
    conn = dbmod.get_db(tmp_path / "t.db")
    dbmod.init_schema(conn)
    fts_repo.upsert(conn, obj_id="A@1", version="1.0", body="正文甲")
    fts_repo.upsert(conn, obj_id="A@1", version="1.0", body="正文甲改")  # 同键重写
    assert conn.execute("SELECT COUNT(*) FROM md_fts").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM md_fts_map").fetchone()[0] == 1
    # 行内容是新写的（map 路径删旧插新正确）
    assert "改" in conn.execute("SELECT body FROM md_fts").fetchone()[0]
    # 删：fts 与 map 同清
    fts_repo.delete(conn, "A@1", "1.0")
    assert conn.execute("SELECT COUNT(*) FROM md_fts").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM md_fts_map").fetchone()[0] == 0
    # 删不存在的键：无异常
    fts_repo.delete(conn, "A@1", "1.0")
    fts_repo.delete_many(conn, [("B@2", None), ("C@3", "9")])


def test_fts_delete_fallback_for_legacy_rows(tmp_path):
    """map 缺失的存量/直写行 → 回退全扫删（正确性网底）。"""
    conn = dbmod.get_db(tmp_path / "t.db")
    dbmod.init_schema(conn)
    conn.execute(
        "INSERT INTO md_fts(obj_id, version, body) VALUES(?,?,?)",
        ("LEGACY@0", "", "旧正文"))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM md_fts_map").fetchone()[0] == 0
    fts_repo.delete(conn, "LEGACY@0", None)
    assert conn.execute("SELECT COUNT(*) FROM md_fts").fetchone()[0] == 0


def test_fts_map_backfill_on_init(tmp_path):
    """存量库（md_fts 有行、map 空）→ init_schema 一次性回填。"""
    conn = dbmod.get_db(tmp_path / "t.db")
    dbmod.init_schema(conn)
    for i in range(3):
        conn.execute(
            "INSERT INTO md_fts(obj_id, version, body) VALUES(?,?,?)",
            (f"L@{i}", "", f"正文{i}"))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM md_fts_map").fetchone()[0] == 0
    dbmod.init_schema(conn)  # 幂等重跑 → 触发回填
    assert conn.execute("SELECT COUNT(*) FROM md_fts_map").fetchone()[0] == 3
    fts_repo.delete(conn, "L@1", None)  # 回填后走 rowid 快路径
    assert conn.execute("SELECT COUNT(*) FROM md_fts").fetchone()[0] == 2


def test_fts_rebuild_repopulates_map(tmp_path):
    conn = dbmod.get_db(tmp_path / "t.db")
    dbmod.init_schema(conn)
    conn.execute(
        "INSERT INTO objects(id, version, type, layer, scope, nf, domain, scenario,"
        " source_path, name, frontmatter_json, body_md, raw_md, mtime)"
        " VALUES('A@1','','T','L','S','nf','','','a.md','','{}','正文','r',1.0)")
    n = fts_repo.rebuild_from_objects(conn)
    assert n == 1
    assert conn.execute("SELECT COUNT(*) FROM md_fts_map").fetchone()[0] == 1
    assert fts_repo.integrity_ok(conn)
    fts_repo.delete(conn, "A@1", None)  # 重建后 map 可用
    assert conn.execute("SELECT COUNT(*) FROM md_fts").fetchone()[0] == 0
