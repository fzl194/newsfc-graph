"""ImportJob 注册表：异步导入后台任务的活状态载体（内存）。

``POST /import`` 立即返回 ``job_id``，后台 ``_process_import`` 推进状态；
前端轮询 ``GET /import/jobs/{id}`` 拿 processing → done/failed。

并发安全：``_registry`` + ``_lock`` 保护跨线程读写（BackgroundTasks 在线程池跑）。
模块级单实例：进程内一份 job 表（与 service 单例对齐）。
"""
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional


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
    # 产品文档导入（v0.22 平台）扩展字段；旧 import job 无这些字段，summary() 向后兼容
    kind: str = "import"            # import | product_doc
    nf: str = ""
    version: str = ""
    steps: list = field(default_factory=list)    # [{name, status, detail}]
    result: dict = field(default_factory=dict)   # 构建产物计数（命名避开 summary() 方法）

    def summary(self) -> dict:
        return asdict(self)


_registry: dict[str, ImportJob] = {}
_lock = threading.Lock()


def create_job(kind: str = "import", nf: str = "", version: str = "") -> ImportJob:
    """新建一个 processing 状态的 job 并登记（kind: import | product_doc）。"""
    j = ImportJob(job_id=uuid.uuid4().hex[:12], kind=kind, nf=nf, version=version)
    with _lock:
        _registry[j.job_id] = j
    return j


def get_job(jid: str) -> Optional[ImportJob]:
    with _lock:
        return _registry.get(jid)


def list_jobs() -> list[ImportJob]:
    """按 started_at 倒序，最多 100 条。"""
    with _lock:
        return sorted(
            _registry.values(), key=lambda j: j.started_at, reverse=True
        )[:100]


def update_job(jid: str, **kw) -> None:
    """增量更新 job 字段；status 转为 done/failed 时记录 finished_at。"""
    with _lock:
        j = _registry.get(jid)
        if j is None:
            return
        for k, v in kw.items():
            setattr(j, k, v)
        if kw.get("status") in ("done", "failed"):
            j.finished_at = time.time()
