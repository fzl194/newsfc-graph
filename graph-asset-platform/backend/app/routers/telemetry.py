"""telemetry router：SKILL 取用统计/明细导出（受鉴权中间件保护，需 can_frontend）。"""
from fastapi import APIRouter, Query

from ..telemetry.aggregator import aggregate_stats, list_skill_usage

router = APIRouter()


@router.get("/telemetry/stats")
def telemetry_stats(days: int = Query(default=30, ge=1, le=365)):
    """返回最近 days 天的 SKILL 取用频次聚合：{total, by_type, top_ids, timeline, by_user}。"""
    return aggregate_stats(days)


@router.get("/telemetry/skill-usage")
def telemetry_skill_usage(
    since: str = Query(default="", description="ISO8601 UTC 游标；空=全量起点。透传上批 next_since 做增量轮询"),
    limit: int = Query(default=1000, ge=1, le=10000, description="单批最大行数"),
):
    """SKILL 取用明细增量流（供外部系统对接）。

    口径同 stats（level=object + caller=skill + endpoint∈{/md,/domains}），返回原始明细而非聚合：
    {events:[{ts, endpoint, obj_id, obj_type, user, operator}], next_since, has_more}。
    消费方把本批 next_since 作为下次 since 原样回传，即可增量推进（next_since 为不透明游标）。
    """
    return list_skill_usage(since, limit)
