"""打点聚合（SQL）：stats（SKILL 取用聚合，按小时桶）+ skill_usage（SKILL 取用明细流）+ activity（用户请求轨迹）。

原 jsonl 全表扫改为 SQL WHERE/GROUP BY（telemetry 表 + 复合索引）。算法口径不变。
"""
from ..db import get_shared_db
from ..repos import telemetry_repo


def aggregate_stats(days: int = 30, start: str = "", end: str = "") -> dict:
    """caller=skill + level=object + endpoint∈{/md,/domains}；timeline 按小时。
    start/end（ISO8601 或纯日期）优先于 days（2026-09-03 时间窗对接）。"""
    return telemetry_repo.aggregate_stats(get_shared_db(), days, start, end)


def list_skill_usage(since: str = "", limit: int = 1000,
                     start: str = "", end: str = "") -> dict:
    """SKILL 取用明细增量流（原始事件 + next_since 游标 + has_more）。"""
    return telemetry_repo.list_skill_usage(get_shared_db(), since, limit, start, end)


def aggregate_activity(username: str, days: int = 30) -> list:
    """某 user 的 request 级轨迹，按 ts 倒序。"""
    return telemetry_repo.aggregate_activity(get_shared_db(), username, days)
