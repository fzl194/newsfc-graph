"""打点独立连接 + reindex 提交防御回归（内网挖掘任务失败根因，2026-08-25）。

现场：挖掘「增量索引」步（reindex_prefixes 逐文件 delete+insert+commit，后台线程）
期间，前端轮询任务状态 → 中间件每个请求写一条 request 级打点并 commit——两者
共用共享连接时，打点线程抢先 commit 掉挖掘线程的事务 → 后者 commit 报
``cannot commit - no transaction is active``，任务失败。

修复：① recorder 独立连接（生产形态）；② service._commit 容忍被抢先提交。
"""
import io
import sqlite3
import threading
import time
import zipfile

import pytest

import app.db as dbmod
import app.service as svc
import app.telemetry.recorder as tel_recorder
from app.registry import Registry
from app.store import Store


def _mk_cmd(i: int) -> str:
    return f"""---
id: UDG@MMLCommand@CMD{i:03d}
type: MMLCommand
name: CMD{i:03d}
version: 20.15.2
---

命令 {i} 正文：配额与用量上报。
"""


def _setup(tmp_data_dir, monkeypatch, n=40):
    s = svc.Service.__new__(svc.Service)
    s.store = Store(tmp_data_dir)
    s.registry = Registry.load_default()
    s.db = dbmod.get_db(tmp_data_dir.parent / "test.db")
    dbmod.init_schema(s.db)
    monkeypatch.setattr(dbmod, "_shared", s.db, raising=False)
    monkeypatch.setattr(svc, "_service", s)
    s.index = svc.Index.load_from_db(s.db, s.registry)
    from app.bundle import import_bundle
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(n):
            z.writestr(f"Command/UDG/20.15.2/cmd{i:03d}.md", _mk_cmd(i))
    import_bundle(buf.getvalue(), s.store, s.registry)
    s.rebuild()
    s.fts_rebuilding = False
    return s


def test_reindex_survives_concurrent_telemetry(tmp_data_dir, monkeypatch):
    """生产形态回归：打点走独立连接，重索引期间高频打点不再打断事务。"""
    s = _setup(tmp_data_dir, monkeypatch, n=40)
    # 复现生产布局：打点用「同库文件的第二个连接」（覆盖 conftest 的注入）
    tel_conn = dbmod.get_db(tmp_data_dir.parent / "test.db")
    monkeypatch.setattr(tel_recorder, "_conn", tel_conn, raising=False)

    stop = threading.Event()

    def hammer():
        # 频率校准：≈1000 打点/秒——远超真实轮询（任务面板 ~1 次/秒），但避免
        # 零间歇死循环在 Windows 写锁无公平仲裁下把另一写者饿超 busy_timeout
        # （>5s locked 属病态压力非生产行为，曾致本用例偶发失败）
        while not stop.is_set():
            tel_recorder.record("/api/v1/import/jobs/poll", user="admin", caller="web")
            time.sleep(0.001)

    t = threading.Thread(target=hammer, daemon=True)
    t.start()
    try:
        with svc.import_lock:  # 挖掘线程同款持锁姿势
            ix = s.reindex_prefixes(["Command/UDG/20.15.2"])
    finally:
        stop.set()
        t.join(timeout=5)

    assert ix["indexed"] == 40 and ix["removed"] == 0
    # 索引完整（对象/FTS 对账）+ 打点行落库且经共享连接可见
    assert s.db.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 40
    from app.repos import fts_repo
    assert fts_repo.integrity_ok(s.db)
    assert s.db.execute(
        "SELECT COUNT(*) FROM telemetry WHERE endpoint='/api/v1/import/jobs/poll'"
    ).fetchone()[0] > 0


def test_commit_tolerates_stolen_transaction():
    """被并发写者抢先提交（no transaction）→ 跳过不炸；其他 OperationalError 原样抛。"""

    class FakeDB:
        def __init__(self, err: str):
            self.err = err
            self.n = 0

        def commit(self):
            self.n += 1
            raise sqlite3.OperationalError(self.err)

    stolen = FakeDB("cannot commit - no transaction is active")
    svc._commit(stolen)
    assert stolen.n == 1  # 调了一次 commit，吞掉

    locked = FakeDB("database is locked")
    with pytest.raises(sqlite3.OperationalError):
        svc._commit(locked)


class _OKDB:
    n = 0

    def commit(self):
        self.n += 1


def test_commit_passes_through_normal():
    db = _OKDB()
    svc._commit(db)
    assert db.n == 1
