"""打点记录器：INSERT 到 telemetry 表（DB）。观测用，绝不阻断业务。

原 jsonl 文件仅作首次迁移源（``migrate_telemetry``），之后不再读写。
"""
import logging
from datetime import datetime, timezone

from ..db import get_shared_db
from ..repos import telemetry_repo

logger = logging.getLogger(__name__)


def record(endpoint: str, id_: str = "", type_: str = "", *, user: str = "",
           caller: str = "", level: str = "request", operator: str = "") -> None:
    """追加一条打点。失败吞掉 + log，不抛。

    level: request/object；operator: SKILL 调用者工号（X-User-Id），前端为空。
    """
    try:
        db = get_shared_db()
        telemetry_repo.insert(
            db,
            ts=datetime.now(timezone.utc).isoformat(),
            level=level, caller=caller, endpoint=endpoint,
            obj_id=id_, obj_type=type_, user=user, operator=operator,
        )
        db.commit()
    except Exception as e:  # noqa: BLE001 — 观测用，绝不阻断业务
        logger.warning("telemetry record failed: %s", e)
