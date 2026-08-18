"""ImportJob：异步导入后台任务的状态载体（内存缓存 + platform.db 持久化）。

v2（2026-08-18，产品文档导入需求）：
- **历史持久化**：job 全量写 ``import_jobs`` 表（create/update 落库），后端重启后
  ``GET /import/jobs`` 仍能列出全部历史，前端刷新/重开页面不丢任务。
- **单任务互斥**：产品文档构建同时只允许一个在跑——router 层用
  ``has_processing('product_doc')`` 拒新（409）。
- **重启清账**：``sweep_interrupted()``（lifespan 启动时调）把上个进程遗留的
  processing 标记 failed——后台线程随进程消亡，不能装作还在跑；已写入的半成品
  资产保留，覆盖重建可续。
- 内存 ``_registry`` 仅是**活动缓存**（processing 实时读，避免每步查询）；
  终态与历史以 DB 为准。``delete_job`` 仅允许非 processing（解析进行中不可删）。
"""
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

from .db import get_shared_db


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
    # 产品文档导入扩展字段（v2）；旧 import job 无这些字段，summary() 向后兼容
    kind: str = "import"            # import | product_doc
    nf: str = ""
    version: str = ""
    steps: list = field(default_factory=list)    # [{name, status, detail}]
    result: dict = field(default_factory=dict)   # 构建产物计数（命名避开 summary() 方法）

    def summary(self) -> dict:
        return asdict(self)


_registry: dict[str, ImportJob] = {}
_lock = threading.Lock()


def _persist(j: ImportJob) -> None:
    """落库（UPSERT）。持久化失败不阻断任务推进——内存态仍在，仅历史缺失。"""
    try:
        db = get_shared_db()
        db.execute(
            "INSERT OR REPLACE INTO import_jobs(job_id,kind,nf,version,status,added,"
            "steps,result,warnings,error,started_at,finished_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (j.job_id, j.kind, j.nf, j.version, j.status, j.added,
             json.dumps(j.steps, ensure_ascii=False),
             json.dumps(j.result, ensure_ascii=False),
             json.dumps(j.warnings, ensure_ascii=False),
             j.error, j.started_at, j.finished_at))
        db.commit()
    except sqlite3.Error:
        pass


def _from_row(r: sqlite3.Row) -> ImportJob:
    return ImportJob(
        job_id=r["job_id"], kind=r["kind"], nf=r["nf"] or "", version=r["version"] or "",
        status=r["status"], added=r["added"] or 0,
        steps=json.loads(r["steps"] or "[]"),
        result=json.loads(r["result"] or "{}"),
        warnings=json.loads(r["warnings"] or "[]"),
        error=r["error"] or "", started_at=r["started_at"], finished_at=r["finished_at"] or 0.0,
    )


def create_job(kind: str = "import", nf: str = "", version: str = "") -> ImportJob:
    """新建一个 processing 状态的 job 并登记（内存 + DB）。"""
    j = ImportJob(job_id=uuid.uuid4().hex[:12], kind=kind, nf=nf, version=version)
    with _lock:
        _registry[j.job_id] = j
    _persist(j)
    return j


def update_job(jid: str, **kw) -> None:
    """增量更新 job 字段（内存 + 落库）；status 转为 done/failed 时记录 finished_at。"""
    with _lock:
        j = _registry.get(jid)
        if j is None:
            return
        for k, v in kw.items():
            setattr(j, k, v)
        if kw.get("status") in ("done", "failed"):
            j.finished_at = time.time()
        snapshot = asdict(j)
    # 快照后落库（锁外执行 DB IO；registry 是唯一写方，快照一致性够用）
    _persist(ImportJob(**snapshot))


def get_job(jid: str) -> Optional[ImportJob]:
    with _lock:
        j = _registry.get(jid)
    if j is not None:
        return j
    try:
        row = get_shared_db().execute(
            "SELECT * FROM import_jobs WHERE job_id=?", (jid,)).fetchone()
    except sqlite3.Error:
        return None
    return _from_row(row) if row else None


def list_jobs(limit: int = 100) -> list:
    """按 started_at 倒序的历史任务（DB 为准；registry 内的活动对象覆盖同 id 行，
    保证 processing 步骤实时）。"""
    try:
        rows = get_shared_db().execute(
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
    # registry 里可能有未落库成功的（持久化失败容忍）——补上，保持倒序
    seen = {r["job_id"] for r in rows}
    extra = [j for jid, j in reg.items() if jid not in seen]
    out.extend(sorted(extra, key=lambda j: j.started_at, reverse=True))
    return out[:limit]


def delete_job(jid: str) -> bool:
    """删除历史任务（**仅非 processing**——解析进行中不可删）。不存在 → False；
    processing → False（调用方据此 400）。"""
    with _lock:
        j = _registry.get(jid)
    if j is not None and j.status == "processing":
        return False
    try:
        cur = get_shared_db().execute("DELETE FROM import_jobs WHERE job_id=?", (jid,))
        get_shared_db().commit()
    except sqlite3.Error:
        return False
    if cur.rowcount == 0 and j is None:
        return False
    with _lock:
        _registry.pop(jid, None)
    return True


def has_processing(kind: str) -> Optional[ImportJob]:
    """指定 kind 是否有 processing 任务（单任务互斥用）。registry 优先，DB 兜底。"""
    with _lock:
        for j in _registry.values():
            if j.kind == kind and j.status == "processing":
                return j
    try:
        row = get_shared_db().execute(
            "SELECT * FROM import_jobs WHERE kind=? AND status='processing' "
            "ORDER BY started_at DESC LIMIT 1", (kind,)).fetchone()
    except sqlite3.Error:
        return None
    return _from_row(row) if row else None


def sweep_interrupted() -> int:
    """启动清账：上个进程遗留的 processing → failed（后台线程已随进程消亡）。
    幂等；返回清账条数。"""
    try:
        db = get_shared_db()
        cur = db.execute(
            "UPDATE import_jobs SET status='failed', finished_at=?, "
            "error=COALESCE(NULLIF(error,''), '后端重启，任务中断：后台线程已消亡；"
            "已写入的资产保留，可覆盖重建续跑') WHERE status='processing'",
            (time.time(),))
        db.commit()
    except sqlite3.Error:
        return 0
    return cur.rowcount
