"""telemetry router：SKILL 取用统计/明细导出（受鉴权中间件保护，需 can_frontend）。"""
from fastapi import APIRouter, Query

from ..telemetry.aggregator import aggregate_stats, list_skill_usage

router = APIRouter()


@router.get("/telemetry/stats")
def telemetry_stats(days: int = Query(default=30, ge=1, le=365),
                    start: str = Query(default="", description="时间窗起点（ISO8601 或纯日期 YYYY-MM-DD）；给了 start/end 则优先于 days"),
                    end: str = Query(default="", description="时间窗终点（ISO8601 或纯日期，纯日期=含当天到 23:59:59）")):
    """返回 SKILL 取用频次聚合：{total, by_type, top_ids, timeline, by_user}。
    时间范围：start/end 优先；否则近 days 天。"""
    return aggregate_stats(days, start, end)


@router.get("/telemetry/skill-usage")
def telemetry_skill_usage(
    since: str = Query(default="", description="ISO8601 UTC 游标；空=全量起点。透传上批 next_since 做增量轮询"),
    limit: int = Query(default=1000, ge=1, le=10000, description="单批最大行数"),
    start: str = Query(default="", description="时间窗起点（ISO8601 或纯日期；首轮 since 空时生效）"),
    end: str = Query(default="", description="时间窗终点（ISO8601 或纯日期=含当天）；翻页全程生效"),
):
    """SKILL 取用明细增量流（供外部系统对接）。

    口径同 stats（level=object + caller∈{skill,mcp} + endpoint∈取用四端点），返回原始明细而非聚合：
    {events:[{ts, endpoint, obj_id, obj_type, user, operator, session_id}], next_since, has_more}。
    消费方把本批 next_since 作为下次 since 原样回传，即可增量推进（next_since 为不透明游标）。
    时间窗用法（2026-09-03）：?start=2026-09-01&end=2026-09-02 首轮拉取，翻页时
    原样回传 next_since 并**继续携带 start/end**（end 上界全程生效）。
    """
    return list_skill_usage(since, limit, start, end)
