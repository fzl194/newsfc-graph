"""stats router：三视图统计（命令/特性/业务图谱）+ MOP 动网变更场景统计。

挂在 ``/api/v1/stats`` 下（auth 中间件 Others→frontend 权限）。与 assets.py 的
旧 ``GET /stats`` 并存——旧端点供 AppHeader 旁路组件复用，勿删。

2026-09-02 晚改版（用户反馈"筛选仍然很卡"）：三视图数据全部走 **cache.py 预聚合
缓存**（启动预热 + ``POST /cache/refresh`` 重建，筛选在内存聚合上做行级过滤，
不再打百万行 SQL）。MOP 底表独立（文件随时换，不走缓存）。导出端点保留
（前端入口隐藏），仍直查 DB（导出是低频操作）。
"""
import time

from fastapi import APIRouter, HTTPException, Query, Request, Response

from ..stats import cache as stats_cache
from ..stats import export as export_mod
from ..stats import mop as mop_mod
from ..stats.core import get_conn, parse_filters, view_payload

router = APIRouter()


def _f(nfs: str = "", versions: str = "", logical_ne: str = "",
       rule_types: str = "", overseas: bool = False):
    return parse_filters(nfs=nfs, versions=versions, logical_ne=logical_ne,
                         rule_types=rule_types, overseas=overseas)


@router.get("/filters")
def get_filters():
    """筛选下拉选项 + 导入表行数 + 缓存状态（前端轮询 building）。"""
    return stats_cache.filters_options()


@router.post("/cache/refresh")
def refresh_cache():
    """「更新缓存」按钮：触发后台重建（构建期间继续服务旧数据，完成原子换新）。"""
    started = stats_cache.refresh_async()
    return {"ok": True, "started": started, **stats_cache.status()}


# ---------- 命令图谱 ----------

@router.get("/command/summary")
def stats_command_summary(nfs: str = "", versions: str = "", logical_ne: str = "",
                          overseas: bool = False):
    return stats_cache.command_summary(_f(nfs, versions, logical_ne, overseas=overseas))


@router.get("/command/knowledge")
def stats_command_knowledge(nfs: str = "", versions: str = "",
                            overseas: bool = False,
                            page: int = 1, size: int = 20, sort: str = "-total"):
    return stats_cache.command_knowledge(_f(nfs, versions, overseas=overseas),
                                         page, size, sort)


@router.get("/command/rules")
def stats_command_rules(nfs: str = "", versions: str = "", logical_ne: str = "",
                        rule_types: str = "", mode: str = "ne_version",
                        overseas: bool = False,
                        page: int = 1, size: int = 20, sort: str = "-count"):
    return stats_cache.command_rules(
        _f(nfs, versions, logical_ne, rule_types=rule_types, overseas=overseas),
        mode, page, size, sort)


# ---------- 特性图谱 ----------

@router.get("/feature/summary")
def stats_feature_summary(nfs: str = "", versions: str = "", overseas: bool = False):
    return stats_cache.feature_summary(_f(nfs, versions, overseas=overseas))


@router.get("/feature/matrix")
def stats_feature_matrix(nfs: str = "", versions: str = "", overseas: bool = False,
                         page: int = 1, size: int = 20, sort: str = "-fk"):
    return stats_cache.feature_matrix(_f(nfs, versions, overseas=overseas),
                                      page, size, sort)


# ---------- 业务图谱（无筛选）----------

@router.get("/business/overview")
def stats_business_overview():
    return stats_cache.business_overview()


# ---------- MOP 动网变更场景统计（文件底表，不走缓存）----------

@router.get("/mop")
def stats_mop(level: int = 1):
    return mop_mod.aggregate(level)


@router.put("/mop/source")
async def stats_mop_upload(request: Request, filename: str = Query(...)):
    """上传/替换 MOP 底表（仅 admin）。body = 文件原始字节（前端 Blob 直传）。"""
    user = getattr(request.state, "user_obj", None) or {}
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可上传 MOP 底表")
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件超过 20MB 上限")
    try:
        return mop_mod.save_source(filename, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ---------- 导出（前端入口已隐藏，端点保留；低频 → 直查不走缓存）----------

_EXPORT_FORMATS = {
    "csv": ("text/csv; charset=utf-8", ".csv"),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "md": ("text/markdown; charset=utf-8", ".md"),
}


@router.get("/export")
def stats_export(view: str = Query(...),
                 format: str = Query("csv"),
                 nfs: str = "", versions: str = "", logical_ne: str = "",
                 rule_types: str = "", overseas: bool = False):
    """当前筛选结果导出（汇总+明细）。"""
    meta = _EXPORT_FORMATS.get(format)
    if meta is None or view not in ("command", "feature", "business"):
        raise HTTPException(status_code=400, detail=(
            f"view 须为 command/feature/business，format 须为 "
            f"{'/'.join(_EXPORT_FORMATS)}"))
    from ..stats.core import parse_filters as pf
    f = pf(nfs=nfs, versions=versions, logical_ne=logical_ne,
           rule_types=rule_types, overseas=overseas)
    sections = export_mod.sections_for(view, view_payload(get_conn(), view, f))
    media_type, ext = meta
    filename = f"stats-{view}-{time.strftime('%Y%m%d')}{ext}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if format == "xlsx":
        return Response(export_mod.render_xlsx(sections),
                        media_type=media_type, headers=headers)
    text = export_mod.render_csv(sections) if format == "csv" \
        else export_mod.render_md(sections)
    if format == "csv":
        text = "﻿" + text  # BOM：Excel 直接双击打开不乱码
    return Response(text, media_type=media_type, headers=headers)
