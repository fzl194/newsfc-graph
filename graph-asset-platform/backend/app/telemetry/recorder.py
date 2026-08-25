"""打点记录器：请求路径只入队，专职线程批量写 telemetry 表。观测用，绝不阻断业务。

演进史（每一版都是内网现场逼出来的）：
- v1 共享连接：与挖掘 reindex 线程跨线程互踩事务 → ``no transaction is active``
  （挖掘任务失败），改独立连接。
- v2 独立连接+同步写：仍有两个问题（2026-08-25 内网：telemetry record failed:
  database is locked + 前端卡）：① 挖掘流式写 WAL 写锁，打点 INSERT 忙等
  busy_timeout=5s——而中间件在 **async dispatch 里同步调 record**，等于阻塞
  事件循环最多 5s，整个后端所有请求一起冻住；② 打点连接被事件循环线程与
  线程池端点线程并发使用——又是跨线程连接竞争。
- v3（本版）队列 + 单写线程：record() 只入队（微秒级，永不阻塞、永不抛）；
  专职 daemon 线程独占连接，攒批（≤200 条/事务）落库，失败丢弃 + warning。
  顺带消灭 ②（单线程独占连接）。测试用 ``flush()`` 等队列清空后断言。

原 jsonl 文件仅作首次迁移源（``migrate_telemetry``），之后不再读写。
"""
import atexit
import logging
import sqlite3
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from ..db import DB_PATH, init_schema
from ..repos import telemetry_repo

logger = logging.getLogger(__name__)

# 有界队列：极端积压时丢最旧（打点是观测数据，可丢不可阻）
_MAX_QUEUE = 10000
_BATCH = 200

_queue: "deque[tuple]" = deque(maxlen=_MAX_QUEUE)
_pending = 0            # 已入队未落库计数（flush 判据）
_wakeup = threading.Condition()
_writer_started = False
_writer_start_lock = threading.Lock()

_conn: Optional[sqlite3.Connection] = None  # 仅写线程使用；测试 monkeypatch 注入


def _get_conn() -> sqlite3.Connection:
    """惰性独立连接（同库文件；WAL 多连接并发写由 busy_timeout 串行化）。"""
    global _conn
    if _conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")  # 与 db.get_db 同策略（WAL 免逐条 fsync）
        conn.execute("PRAGMA busy_timeout=5000")
        init_schema(conn)  # 幂等：telemetry 表等确保存在（正常时共享连接已建）
        _conn = conn
    return _conn


def _ensure_writer() -> None:
    global _writer_started
    if _writer_started:
        return
    with _writer_start_lock:
        if _writer_started:
            return
        t = threading.Thread(target=_writer_loop, daemon=True, name="telemetry-writer")
        t.start()
        _writer_started = True


def _writer_loop() -> None:
    while True:
        with _wakeup:
            while not _queue:
                _wakeup.wait()
            batch = []
            while _queue and len(batch) < _BATCH:
                batch.append(_queue.popleft())
        if not batch:
            continue
        _write_batch(batch)
        with _wakeup:
            global _pending
            _pending -= len(batch)  # 失败也已出队（丢弃语义），flush 不必等重试
            _wakeup.notify_all()


def _write_batch(batch: list) -> None:
    """攒批单事务落库；失败整批丢弃 + warning（绝不重试阻塞队列）。"""
    try:
        conn = _get_conn()  # 每批解析：测试 monkeypatch _conn 后写线程随之切换
        with conn:  # 事务块（异常回滚）
            for row in batch:
                telemetry_repo.insert(conn, **row)
    except Exception as e:  # noqa: BLE001 — 观测用，绝不阻断业务
        logger.warning("telemetry record failed (dropped %d rows): %s", len(batch), e)


def record(endpoint: str, id_: str = "", type_: str = "", *, user: str = "",
           caller: str = "", level: str = "request", operator: str = "",
           session_id: str = "", params: str = "", result: str = "") -> None:
    """追加一条打点：仅入队（微秒级，不碰 DB、不阻塞、不抛）。

    level: request/object/tool；operator: 调用者工号（MCP 工具参数 AGENT_USERNAME）；
    session_id: 会话ID（MCP 工具参数 AGENT_SESSION_ID）；
    params/result: tool 级的入参与出参摘要（调用方序列化好的 JSON 字符串，截断 2KB）。
    """
    try:
        with _wakeup:
            global _pending
            _pending += 1
            _queue.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": level, "caller": caller, "endpoint": endpoint,
                "obj_id": id_, "obj_type": type_, "user": user, "operator": operator,
                "session_id": session_id, "params": params, "result": result,
            })
            _wakeup.notify()
        _ensure_writer()
    except Exception as e:  # noqa: BLE001 — 入队本身几乎不可能失败，兜底
        logger.warning("telemetry enqueue failed: %s", e)


def flush(timeout: float = 5.0) -> bool:
    """等已入队的全部落库（_pending 归零；测试断言前用）。超时返回 False。"""
    import time
    deadline = time.monotonic() + timeout
    with _wakeup:
        while _pending > 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            _wakeup.wait(remaining)
    return True


atexit.register(lambda: flush(timeout=1.0))
