"""stats router：三视图统计（命令/特性/业务图谱）+ MOP 动网变更场景统计。

挂在 ``/api/v1/stats`` 下（auth 中间件 Others→frontend 权限）。与 assets.py 的
旧 ``GET /stats`` 并存——旧端点供 AppHeader/LayerNav/UploadView 复用，勿删。
导出端点在本前缀下（``/api/v1/stats/export``），避开 ``/api/v1/export`` 的
upload 权限分支。

2026-09-02 改版（用户反馈）：
- 卡片摘要与表格**分离**：summary 端点受视图级筛选；表端点各自独立筛选 +
  服务端分页/排序（/command/knowledge、/command/rules、/feature/matrix）。
- 视图级筛选收窄：命令=物理网元+版本+逻辑网元；特性=物理网元+版本；业务=无。
- ``GET /mop``：MOP 动网变更场景统计（Excel 底表，不走库）；``PUT /mop/source``
  （仅 admin，raw body 传文件字节——免 python-multipart 依赖）。
- 前端导出入口已隐藏（用户决策），``/export`` 后端保留待后续启用。
"""
import time

from fastapi import APIRouter, HTTPException, Query, Request, Response

from ..stats import export as export_mod
from ..stats import mop as mop_mod
from ..stats.core import (
    business_overview, command_knowledge, command_rules, command_summary,
    feature_matrix, feature_summary, filters_options, get_conn, parse_filters,
    view_payload,
)

router = APIRouter()


def _f(nfs: str = "", versions: str = "", logical_ne: str = "",
       object_types: str = "", relations: str = "", rule_types: str = "",
       domain: str = "", scenario: str = "", solution: str = "",
       overseas: bool = False):
    return parse_filters(
        nfs=nfs, versions=versions, logical_ne=logical_ne,
        object_types=object_types, relations=relations, rule_types=rule_types,
        domain=domain, scenario=scenario, solution=solution, overseas=overseas)


@router.get("/filters")
def get_filters():
    """筛选下拉选项 + 导入表行数（0/缺失 → 前端提示规则表未导入）。"""
    return filters_options(get_conn())


# ---------- 命令图谱 ----------

@router.get("/command/summary")
def stats_command_summary(nfs: str = "", versions: str = "", logical_ne: str = "",
                          overseas: bool = False):
    return command_summary(get_conn(), _f(nfs, versions, logical_ne,
                                          overseas=overseas))


@router.get("/command/knowledge")
def stats_command_knowledge(nfs: str = "", versions: str = "",
                            overseas: bool = False,
                            page: int = 1, size: int = 20, sort: str = "-total"):
    return command_knowledge(get_conn(), _f(nfs, versions, overseas=overseas),
                             page, size, sort)


@router.get("/command/rules")
def stats_command_rules(nfs: str = "", versions: str = "", logical_ne: str = "",
                        rule_types: str = "", mode: str = "ne_version",
                        overseas: bool = False,
                        page: int = 1, size: int = 20, sort: str = "-rule"):
    return command_rules(get_conn(), _f(nfs, versions, logical_ne,
                                        rule_types=rule_types, overseas=overseas),
                         mode, page, size, sort)


# ---------- 特性图谱 ----------

@router.get("/feature/summary")
def stats_feature_summary(nfs: str = "", versions: str = "", overseas: bool = False):
    return feature_summary(get_conn(), _f(nfs, versions, overseas=overseas))


@router.get("/feature/matrix")
def stats_feature_matrix(nfs: str = "", versions: str = "", overseas: bool = False,
                         page: int = 1, size: int = 20, sort: str = "-fk"):
    return feature_matrix(get_conn(), _f(nfs, versions, overseas=overseas),
                          page, size, sort)


# ---------- 业务图谱（无筛选）----------

@router.get("/business/overview")
def stats_business_overview():
    return business_overview(get_conn())


# ---------- MOP 动网变更场景统计 ----------

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


# ---------- 导出（前端入口已隐藏，端点保留）----------

_EXPORT_FORMATS = {
    "csv": ("text/csv; charset=utf-8", ".csv"),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "md": ("text/markdown; charset=utf-8", ".md"),
}


@router.get("/export")
def stats_export(view: str = Query(...),
                 format: str = Query("csv"),
                 nfs: str = "", versions: str = "", logical_ne: str = "",
                 object_types: str = "", relations: str = "", rule_types: str = "",
                 domain: str = "", scenario: str = "", solution: str = "",
                 overseas: bool = False):
    """当前筛选结果导出（汇总+明细；与视图端点同参数同数据）。"""
    meta = _EXPORT_FORMATS.get(format)
    if meta is None or view not in ("command", "feature", "business"):
        raise HTTPException(status_code=400, detail=(
            f"view 须为 command/feature/business，format 须为 "
            f"{'/'.join(_EXPORT_FORMATS)}"))
    f = _f(nfs, versions, logical_ne, object_types, relations, rule_types,
           domain, scenario, solution, overseas)
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
