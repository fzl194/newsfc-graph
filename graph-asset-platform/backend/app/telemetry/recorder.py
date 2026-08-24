"""打点记录器：INSERT 到 telemetry 表（DB）。观测用，绝不阻断业务。

原 jsonl 文件仅作首次迁移源（``migrate_telemetry``），之后不再读写。
"""
import logging
from datetime import datetime, timezone

from ..db import get_shared_db
from ..repos import telemetry_repo

logger = logging.getLogger(__name__)


def record(endpoint: str, id_: str = "", type_: str = "", *, user: str = "",
           caller: str = "", level: str = "request", operator: str = "",
           session_id: str = "", params: str = "", result: str = "") -> None:
    """追加一条打点。失败吞掉 + log，不抛。

    level: request/object/tool；operator: 调用者工号（MCP 工具参数 AGENT_USERNAME）；
    session_id: 会话ID（MCP 工具参数 AGENT_SESSION_ID）；
    params/result: tool 级的入参与出参摘要（调用方序列化好的 JSON 字符串，截断 2KB）。
    """
    try:
        db = get_shared_db()
        telemetry_repo.insert(
            db,
            ts=datetime.now(timezone.utc).isoformat(),
            level=level, caller=caller, endpoint=endpoint,
            obj_id=id_, obj_type=type_, user=user, operator=operator,
            session_id=session_id, params=params, result=result,
        )
        db.commit()
    except Exception as e:  # noqa: BLE001 — 观测用，绝不阻断业务
        logger.warning("telemetry record failed: %s", e)
