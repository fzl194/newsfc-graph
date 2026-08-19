"""ImportJob：异步导入任务的状态载体（内存缓存 + platform.db 持久化）。

v3（2026-08-19，两步流水线）：
- kind：``product_doc_extract``（解压转换）/ ``product_doc_mine``（图谱挖掘）；
  两类各自全局单任务互斥、允许并行（用户决策）。
- ``child_pids``：构建子进程 PID 记录——后端被硬杀后孤儿进程继续写资产目录，
  ``sweep_interrupted()`` 启动时按 PID 树终止（评审清单 D16）。
- **独立 SQLite 连接**（评审清单 D7）：后台线程高频落库不再与共享连接跨线程混写；
  WAL 多连接 + busy_timeout。测试通过 monkeypatch ``jobs._conn`` 注入 tmp 连接。
- 历史持久化 / 删除（非 processing）/ 重启清账语义见 v2 注释，不变。
"""
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

from .db import DB_PATH

_KINDS = ("import", "product_doc_extract", "product_doc_mine")


@dataclass
class ImportJob:
    job_id: str
    status: str = "processing"      # processing | done | failed
    added: int = 0
    updated: int = 0
    skipped: int = 0
    warnings: list = field(default_factory=list)
    error: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    kind: str = "import"
    nf: str = ""
    version: str = ""
    steps: list = field(default_factory=list)      # [{name, status, detail}]
    result: dict = field(default_factory=dict)     # 产物计数（命名避开 summary() 方法）
    child_pids: list = field(default_factory=list)  # 运行中子进程 PID（D16 sweep 终止用）

    def summary(self) -> dict:
        return asdict(self)


_registry: dict[str, ImportJob] = {}
_lock = threading.Lock()

# 各类任务的全局互斥锁（检查→登记 原子化，修 TOCTOU；评审清单 D6）
_mutex_locks = {k: threading.Lock() for k in _KINDS}


# ---------- 独立连接（D7） ----------

_conn: "sqlite3.Connection | None" = None

_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS import_jobs(
  job_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
  nf TEXT DEFAULT '', version TEXT DEFAULT '',
  status TEXT NOT NULL, added INTEGER DEFAULT 0,
  steps TEXT DEFAULT '[]', result TEXT DEFAULT '{}', warnings TEXT DEFAULT '[]',
  error TEXT DEFAULT '', started_at REAL NOT NULL, finished_at REAL DEFAULT 0,
  child_pids TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_import_jobs_started ON import_jobs(started_at);
"""


def _db() -> sqlite3.Connection:
    """jobs 专用连接（与 service/telemetry 共享连接隔离）；测试注入 ``jobs._conn``。"""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout=5000")
        _conn.executescript(_TABLE_SQL)
        _conn.commit()
    return _conn


def _persist(j: ImportJob) -> None:
    """落库（UPSERT）。持久化失败记 stderr 不抛——内存态仍在，仅历史缺失。"""
    try:
        db = _db()
        db.execute(
            "INSERT OR REPLACE INTO import_jobs(job_id,kind,nf,version,status,added,"
            "steps,result,warnings,error,started_at,finished_at,child_pids) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (j.job_id, j.kind, j.nf, j.version, j.status, j.added,
             json.dumps(j.steps, ensure_ascii=False),
             json.dumps(j.result, ensure_ascii=False),
             json.dumps(j.warnings, ensure_ascii=False),
             j.error, j.started_at, j.finished_at,
             json.dumps(j.child_pids)))
        db.commit()
    except sqlite3.Error as e:
        print(f"[jobs] 持久化失败 {j.job_id}: {e}", file=sys.stderr)


def _from_row(r: sqlite3.Row) -> ImportJob:
    return ImportJob(
        job_id=r["job_id"], kind=r["kind"], nf=r["nf"] or "", version=r["version"] or "",
        status=r["status"], added=r["added"] or 0,
        steps=json.loads(r["steps"] or "[]"),
        result=json.loads(r["result"] or "{}"),
        warnings=json.loads(r["warnings"] or "[]"),
        error=r["error"] or "", started_at=r["started_at"], finished_at=r["finished_at"] or 0.0,
        child_pids=json.loads(r["child_pids"] or "[]"),
    )


def acquire_mutex(kind: str) -> bool:
    """取该类任务的全局锁（检查→登记 原子段入口）。取不到立即返回 False。"""
    lk = _mutex_locks.get(kind)
    return lk.acquire(blocking=False) if lk else True


def release_mutex(kind: str) -> None:
    lk = _mutex_locks.get(kind)
    if lk:
        try:
            lk.release()
        except RuntimeError:
            pass


def create_job(kind: str = "import", nf: str = "", version: str = "") -> ImportJob:
    """新建 processing 状态的 job（内存 + DB）。调用方应已持有该 kind 的互斥锁。"""
    j = ImportJob(job_id=uuid.uuid4().hex[:12], kind=kind, nf=nf, version=version)
    with _lock:
        _registry[j.job_id] = j
    _persist(j)
    return j


def update_job(jid: str, **kw) -> None:
    with _lock:
        j = _registry.get(jid)
        if j is None:
            return
        for k, v in kw.items():
            setattr(j, k, v)
        if kw.get("status") in ("done", "failed"):
            j.finished_at = time.time()
        snapshot = asdict(j)
    _persist(ImportJob(**snapshot))


def get_job(jid: str) -> Optional[ImportJob]:
    with _lock:
        j = _registry.get(jid)
    if j is not None:
        return j
    try:
        row = _db().execute(
            "SELECT * FROM import_jobs WHERE job_id=?", (jid,)).fetchone()
    except sqlite3.Error:
        return None
    return _from_row(row) if row else None


def list_jobs(limit: int = 100) -> list:
    try:
        rows = _db().execute(
            "SELECT * FROM import_jobs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    except sqlite3.Error:
        rows = []
    with _lock:
        reg = dict(_registry)
    out = []
    for r in rows:
        j = reg.get(r["job_id"])
        out.append(j if j is not None else _from_row(r))
    seen = {r["job_id"] for r in rows}
    extra = [j for jid, j in reg.items() if jid not in seen]
    out.extend(sorted(extra, key=lambda j: j.started_at, reverse=True))
    return out[:limit]


def delete_job(jid: str) -> bool:
    """删除历史任务（**仅非 processing**——解析进行中不可删，用户决策）。"""
    with _lock:
        j = _registry.get(jid)
    if j is not None and j.status == "processing":
        return False
    try:
        db = _db()
        cur = db.execute("DELETE FROM import_jobs WHERE job_id=?", (jid,))
        db.commit()
    except sqlite3.Error:
        return False
    if cur.rowcount == 0 and j is None:
        return False
    with _lock:
        _registry.pop(jid, None)
    return True


def has_processing(kind: str) -> Optional[ImportJob]:
    with _lock:
        for j in _registry.values():
            if j.kind == kind and j.status == "processing":
                return j
    try:
        row = _db().execute(
            "SELECT * FROM import_jobs WHERE kind=? AND status='processing' "
            "ORDER BY started_at DESC LIMIT 1", (kind,)).fetchone()
    except sqlite3.Error:
        return None
    return _from_row(row) if row else None


def _kill_pid_tree(pid: int) -> None:
    """尽力终止进程树（Windows taskkill /T；POSIX SIGKILL）。"""
    if not isinstance(pid, int) or pid <= 0:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, timeout=10)
        else:
            os.kill(pid, signal.SIGKILL)
    except Exception:  # noqa: BLE001 —— 尽力而为，失败不阻断清账
        pass


def sweep_interrupted() -> int:
    """启动清账：①终止上个进程遗留的子进程树（D16）→ ②processing 标记 failed。
    幂等；返回清账条数。"""
    n = 0
    try:
        db = _db()
        rows = db.execute(
            "SELECT job_id, child_pids FROM import_jobs WHERE status='processing'").fetchall()
        for r in rows:
            for pid in json.loads(r["child_pids"] or "[]"):
                _kill_pid_tree(int(pid))
        cur = db.execute(
            "UPDATE import_jobs SET status='failed', finished_at=?, child_pids='[]', "
            "error=COALESCE(NULLIF(error,''), '后端重启，任务中断：后台线程已消亡；"
            "已写入的资产保留，可覆盖重建续跑') WHERE status='processing'",
            (time.time(),))
        db.commit()
        n = cur.rowcount
    except sqlite3.Error:
        return 0
    if n:
        with _lock:
            for j in list(_registry.values()):
                if j.status == "processing":
                    j.status = "failed"
                    j.finished_at = time.time()
    return n
