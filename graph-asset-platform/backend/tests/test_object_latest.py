"""object_latest / graph_search_fts 维护测试（M2，需求 §7.5/§12/§15.5）。

覆盖：幂等回填（无版本空串）、删除最新版降级次新、删除最后版本删行、
ID 改名 old∪new 刷新、reindex_paths chunk、启动对账修复、完整性检查。

注意：bundle 导入会按归类重排路径（Layer/nf/version/id.md）——source_path
从 DB 反查，不能假设 zip 内文件名。
"""
import io
import zipfile

import app.db as dbmod
import app.service as svc
from app.registry import Registry
from app.store import Store

from tests.test_search_graph import ALL, CMD_ADD_URR_V2, UNC_CMD


def _setup(tmp_data_dir, monkeypatch, files=None):
    s = svc.Service.__new__(svc.Service)
    s.store = Store(tmp_data_dir)
    s.registry = Registry.load_default()
    s.db = dbmod.get_db(tmp_data_dir.parent / "test.db")
    dbmod.init_schema(s.db)
    monkeypatch.setattr(dbmod, "_shared", s.db, raising=False)
    from app.bundle import import_bundle
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in (files or ALL).items():
            z.writestr(name, content)
    import_bundle(buf.getvalue(), s.store, s.registry)
    s.rebuild()
    s.fts_rebuilding = False
    monkeypatch.setattr(svc, "_service", s)
    return s


def _latest(s, id_):
    row = s.db.execute("SELECT version FROM object_latest WHERE id=?", (id_,)).fetchone()
    return row["version"] if row else None


def _source_path(s, id_, version=None):
    if version is None:
        return s.db.execute(
            "SELECT source_path FROM objects WHERE id=? LIMIT 1",
            (id_,)).fetchone()[0]
    return s.db.execute(
        "SELECT source_path FROM objects WHERE id=? AND version=? LIMIT 1",
        (id_, version)).fetchone()[0]


def test_backfill_latest_and_versionless_empty_string(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch)
    assert _latest(s, "UDG@MMLCommand@ADD URR") == "20.16.0"
    assert _latest(s, "BusinessDomain@charging-fraud") == ""  # 无版本 → DB 空串
    from app.repos import object_latest_repo
    assert object_latest_repo.integrity_ok(s.db)


def test_delete_latest_downgrades_to_previous(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch)
    rel = _source_path(s, "UDG@MMLCommand@ADD URR", "20.16.0")
    from app.service import import_lock
    with import_lock:
        s.unindex_path(rel)  # 删 20.16.0 那份 md
    s.reload_index()
    assert _latest(s, "UDG@MMLCommand@ADD URR") == "20.15.2"
    from app.graph_query.search import search_graph_core
    out = search_graph_core(terms=["N2接口配置"])
    assert "UDG@MMLCommand@ADD URR" in [h["id"] for h in out["hits"]]  # 旧正文可搜


def test_delete_last_version_removes_latest_row(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch)
    rel = _source_path(s, "UNC@MMLCommand@SET N2MODE")
    from app.service import import_lock
    with import_lock:
        s.unindex_path(rel)
    s.reload_index()
    assert _latest(s, "UNC@MMLCommand@SET N2MODE") is None
    from app.repos import object_latest_repo
    assert object_latest_repo.integrity_ok(s.db)


def test_reindex_rename_refreshes_old_and_new(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch)
    rel = _source_path(s, "UNC@MMLCommand@SET N2MODE")
    new_md = UNC_CMD.replace("SET N2MODE", "SET N3MODE").replace(
        "N2接口配置命令", "N3接口配置命令")
    s.store.abspath(rel).write_text(new_md, encoding="utf-8")
    from app.service import import_lock
    with import_lock:
        s.reindex_path(rel)
    s.reload_index()
    assert _latest(s, "UNC@MMLCommand@SET N2MODE") is None
    assert _latest(s, "UNC@MMLCommand@SET N3MODE") == "23.1.0"
    from app.graph_query.search import search_graph_core
    assert search_graph_core(terms=["N3MODE"])["total"] == 1
    assert search_graph_core(terms=["SET N2MODE"])["total"] == 0


def test_reindex_paths_chunk_consistency(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch)
    rels = [_source_path(s, "UDG@MMLCommand@ADD URR"),
            _source_path(s, "UDG@ConfigObject@AFUSRDETECT"),
            _source_path(s, "UNC@MMLCommand@SET N2MODE")]
    from app.service import import_lock
    with import_lock:
        s.reindex_paths(rels)
    from app.repos import object_latest_repo, graph_search_repo
    assert object_latest_repo.integrity_ok(s.db)
    assert graph_search_repo.integrity_ok(s.db)


def test_startup_reconcile_rebuilds_drifted_tables(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch)
    # 人工制造漂移：删 graph_search_fts 行 + 错误 object_latest
    s.db.execute(
        "DELETE FROM graph_search_fts WHERE obj_id='UNC@MMLCommand@SET N2MODE'")
    s.db.execute(
        "UPDATE object_latest SET version='0.0.1' WHERE id='UDG@MMLCommand@ADD URR'")
    s.db.commit()
    from app.repos import object_latest_repo, graph_search_repo
    assert not graph_search_repo.integrity_ok(s.db)
    assert not object_latest_repo.integrity_ok(s.db)
    s._fts_reconcile_async()  # 同步调用（测试）
    s.reload_index()
    assert graph_search_repo.integrity_ok(s.db)
    assert object_latest_repo.integrity_ok(s.db)
    from app.graph_query.search import search_graph_core
    assert search_graph_core(terms=["N2MODE"])["total"] == 1
