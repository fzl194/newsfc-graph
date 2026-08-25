"""打点记录器：INSERT 到 telemetry 表（DB）。观测用，绝不阻断业务。

原 jsonl 文件仅作首次迁移源（``migrate_telemetry``），之后不再读写。

**独立 SQLite 连接**（2026-08-25）：原走共享连接 ``get_shared_db()``——request 级
打点随每个 API 请求高频 INSERT+commit，与挖掘后台线程 ``reindex_prefixes`` 逐文件
事务在**同一连接**上跨线程互踩：打点线程抢先 commit 掉对方开着的唯一事务，对方
commit 时报 ``cannot commit - no transaction is active``（内网挖掘任务在「增量
索引」步失败根因）。改为独立连接 + WAL + busy_timeout（与 ``jobs._conn`` 同款）。
测试经 monkeypatch ``telemetry.recorder._conn`` 注入 tmp 连接。
"""
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from ..db import DB_PATH, init_schema
from ..repos import telemetry_repo

logger = logging.getLogger(__name__)

_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    """惰性独立连接（同库文件；WAL 多连接并发写由 busy_timeout 串行化）。"""
    global _conn
    if _conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        init_schema(conn)  # 幂等：telemetry 表等确保存在（正常时共享连接已建）
        _conn = conn
    return _conn


def record(endpoint: str, id_: str = "", type_: str = "", *, user: str = "",
           caller: str = "", level: str = "request", operator: str = "",
           session_id: str = "", params: str = "", result: str = "") -> None:
    """追加一条打点。失败吞掉 + log，不抛。

    level: request/object/tool；operator: 调用者工号（MCP 工具参数 AGENT_USERNAME）；
    session_id: 会话ID（MCP 工具参数 AGENT_SESSION_ID）；
    params/result: tool 级的入参与出参摘要（调用方序列化好的 JSON 字符串，截断 2KB）。
    """
    try:
        conn = _get_conn()
        telemetry_repo.insert(
            conn,
            ts=datetime.now(timezone.utc).isoformat(),
            level=level, caller=caller, endpoint=endpoint,
            obj_id=id_, obj_type=type_, user=user, operator=operator,
            session_id=session_id, params=params, result=result,
        )
        conn.commit()
    except Exception as e:  # noqa: BLE001 — 观测用，绝不阻断业务
        logger.warning("telemetry record failed: %s", e)
