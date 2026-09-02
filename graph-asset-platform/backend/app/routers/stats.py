"""stats router：三视图统计（命令/特性/业务图谱，统计页重构 2026-09-01）。

挂在 ``/api/v1/stats`` 下（auth 中间件 Others→frontend 权限）。与 assets.py 的
旧 ``GET /stats`` 并存——旧端点供 AppHeader/LayerNav/UploadView 复用，勿删。
导出端点在本前缀下（``/api/v1/stats/export``），避开 ``/api/v1/export`` 的
upload 权限分支。
"""
import time

from fastapi import APIRouter, HTTPException, Query, Response

from ..stats import export as export_mod
from ..stats.core import (
    business_view, command_view, feature_view, filters_options,
    get_conn, parse_filters, view_payload,
)

router = APIRouter()


def _f(nfs: str, versions: str, logical_ne: str, object_types: str,
       relations: str, rule_types: str, domain: str, scenario: str,
       solution: str, overseas: bool):
    return parse_filters(
        nfs=nfs, versions=versions, logical_ne=logical_ne,
        object_types=object_types, relations=relations, rule_types=rule_types,
        domain=domain, scenario=scenario, solution=solution, overseas=overseas)


@router.get("/filters")
def get_filters():
    """筛选下拉选项 + 导入表行数（0/缺失 → 前端提示规则表未导入）。"""
    return filters_options(get_conn())


@router.get("/command")
def stats_command(nfs: str = "", versions: str = "", logical_ne: str = "",
                  object_types: str = "", relations: str = "", rule_types: str = "",
                  domain: str = "", scenario: str = "", solution: str = "",
                  overseas: bool = False):
    return command_view(get_conn(), _f(nfs, versions, logical_ne, object_types,
                                       relations, rule_types, domain, scenario,
                                       solution, overseas))


@router.get("/feature")
def stats_feature(nfs: str = "", versions: str = "", logical_ne: str = "",
                  object_types: str = "", relations: str = "", rule_types: str = "",
                  domain: str = "", scenario: str = "", solution: str = "",
                  overseas: bool = False):
    return feature_view(get_conn(), _f(nfs, versions, logical_ne, object_types,
                                       relations, rule_types, domain, scenario,
                                       solution, overseas))


@router.get("/business")
def stats_business(nfs: str = "", versions: str = "", logical_ne: str = "",
                   object_types: str = "", relations: str = "", rule_types: str = "",
                   domain: str = "", scenario: str = "", solution: str = "",
                   overseas: bool = False):
    return business_view(get_conn(), _f(nfs, versions, logical_ne, object_types,
                                        relations, rule_types, domain, scenario,
                                        solution, overseas))


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
