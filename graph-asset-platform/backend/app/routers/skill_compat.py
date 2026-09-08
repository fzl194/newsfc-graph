"""SKILL 兼容双接口（薄 adapter；业务实现走 graph_query 共享核心）。

- 2026-09-08 三工具重构（M1）：/domains、/md 与 MCP get_domains/get_md 调用
  同一 ``get_domains_core`` / ``get_md_core``——业务数据、版本解析、护栏
  （ids 1~100、响应 2MB）、错误不分叉（需求 §10）；本文件只做协议包装与打点。
- 请求体手动解析（extra=forbid + 统一 INVALID_ARGUMENT envelope 422），
  不走 FastAPI 默认 RequestValidationError 形态（需求 §5.2：REST 图谱路由
  错误体固定为 ``{"error": {GraphError}}``）。
- 归因参数与 MCP 同名且必填：``AGENT_USERNAME`` / ``AGENT_SESSION_ID`` 落
  telemetry 的 ``operator`` / ``session_id`` 专列，不重复写入 params。
- 权限与 MCP 一致：skill（``can_skill`` 或 ``can_frontend``，admin 全权）；
  401/403 的 error envelope 由 AuthMiddleware 对两路径分支输出。
"""
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..attribution import telemetry_attribution
from ..graph_query import contracts as gq
from ..graph_query import read as graph_read
from ..telemetry.recorder import record

router = APIRouter()
_REST_CALLER = "skill"


def _error_response(error: gq.GraphError) -> JSONResponse:
    """REST 图谱路由错误体：{"error": {GraphError}} + HTTP_STATUS 映射（§5.2）。"""
    return JSONResponse(status_code=gq.HTTP_STATUS.get(error.code, 500),
                        content={"error": error.model_dump()})


async def _parse_body(request: Request, model_cls):
    """JSON body → Pydantic 模型（extra=forbid）。失败统一 INVALID_ARGUMENT 422。"""
    try:
        body = await request.json()
    except Exception:
        raise gq.err(gq.INVALID_ARGUMENT, "请求体须为 JSON 对象")
    try:
        return model_cls.model_validate(body)
    except ValidationError as e:
        details = [{"field": ".".join(str(x) for x in x["loc"]),
                    "message": x["msg"]} for x in e.errors()]
        raise gq.err(gq.INVALID_ARGUMENT, "请求参数校验失败", errors=details)


def _record_call(endpoint: str, request: Request, operator: str, session_id: str,
                 params: dict, result: dict) -> None:
    """调用级行（底表默认口径）：一次 HTTP 请求记一条 level=tool 行（与 MCP 工具
    行同构——params/result 摘要与 MCP 对齐，仅 caller/endpoint 不同，§8.6）。"""
    record(endpoint, user=request.state.user, caller=_REST_CALLER,
           level="tool", **telemetry_attribution(operator, session_id),
           params=json.dumps(params, ensure_ascii=False),
           result=json.dumps(result, ensure_ascii=False))


@router.post("/domains")
async def list_domains_with_md(request: Request):
    """一次性返回全部业务域的完整 md（``[{id, type, name, version, md, references}]``）。

    业务域是用户最优先的业务归属定位层——数量少（跨 NF 类，version 恒 null），
    Agent 入口直接取全部域 md。其他层级仍按 ``POST /md`` 沿 ``[[ID]]`` 引用下钻。
    """
    req = None
    try:
        req = await _parse_body(request, gq.RestDomainsRequest)
        items = graph_read.get_domains_core()
    except gq.GraphQueryError as e:
        _record_error("/domains", request, req, e)
        return _error_response(e.error)
    except Exception as e:  # noqa: BLE001 详细异常只进服务端日志
        print(f"[skill_compat] INTERNAL_ERROR /domains: {e!r}", flush=True)
        _record_error("/domains", request, req, e)
        return _error_response(gq.GraphError(
            code=gq.INTERNAL_ERROR, message=gq.INTERNAL_ERROR_MESSAGE))
    attribution = telemetry_attribution(req.AGENT_USERNAME, req.AGENT_SESSION_ID)
    # 调用级 1 行（底表默认口径）+ 对象级每域 1 行（运维页统计热榜用）
    _record_call("/domains", request, req.AGENT_USERNAME, req.AGENT_SESSION_ID,
                 params={}, result={"domains": len(items)})
    for item in items:
        record("/domains", item.id, "BusinessDomain",
               user=request.state.user, caller=_REST_CALLER,
               level="object", **attribution)
    return [item.model_dump() for item in items]


def _record_error(endpoint: str, request: Request, req, e: Exception) -> None:
    """失败也留痕（与 MCP tool 行同构）：解析成功后的失败记 1 条 error tool 行。
    body 解析失败（无归因可用）不记——与 MCP SDK 参数校验失败不落 tool 行一致。
    message 只回业务错误文本——未知异常统一 "internal error"（str(e) 可能含
    SQL/路径，不落 telemetry/运维页，安全审查 M1）。"""
    if req is None:
        return
    if isinstance(e, gq.GraphQueryError):
        message = e.error.message
        code = e.error.code
    else:
        message = "internal error"
        code = gq.INTERNAL_ERROR
    result = {"error": {"code": code, "message": message[:200]}}
    if endpoint == "/md" and isinstance(req, gq.RestMdRequest):
        # 规范化 ids（trim 去重）——与 MCP get_md 失败路径同口径
        norm_ids = [k for k in dict.fromkeys((i or "").strip() for i in req.ids) if k]
        params = {"ids": norm_ids, "version": req.version}
    else:
        params = {}
    _record_call(endpoint, request, req.AGENT_USERNAME, req.AGENT_SESSION_ID,
                 params=params, result=result)


@router.post("/md")
async def batch_md(request: Request):
    """批量取多个对象的原始 markdown（与 MCP get_md 完全同构，§10）。

    响应 ``{id: MdSuccess | MdFailure}``（动态 ID map）：成功项含完整元数据 +
    md + references；失败项含 error_code/requested_version/available_versions，
    单项失败不影响其余 id。护栏与 MCP 相同：ids 1~100（去重后）、响应 ≤2MB，
    超限整单失败（413 RESULT_TOO_LARGE）。
    """
    req = None
    try:
        req = await _parse_body(request, gq.RestMdRequest)
        result_map, summary = graph_read.get_md_core(req.ids, req.version)
    except gq.GraphQueryError as e:
        _record_error("/md", request, req, e)
        return _error_response(e.error)
    except Exception as e:  # noqa: BLE001 详细异常只进服务端日志
        print(f"[skill_compat] INTERNAL_ERROR /md: {e!r}", flush=True)
        _record_error("/md", request, req, e)
        return _error_response(gq.GraphError(
            code=gq.INTERNAL_ERROR, message=gq.INTERNAL_ERROR_MESSAGE))
    attribution = telemetry_attribution(req.AGENT_USERNAME, req.AGENT_SESSION_ID)
    # 护栏已过 → 成功 id 逐个留取用点（失败 id 不写 object 行，§8.6）
    for id_, item in result_map.items():
        if item["ok"]:
            record("/md", id_, item["type"], user=request.state.user,
                   caller=_REST_CALLER, level="object", **attribution)
    _record_call("/md", request, req.AGENT_USERNAME, req.AGENT_SESSION_ID,
                 params={"ids": summary["ids"], "version": summary["version"]},
                 result={"ok": summary["ok"], "failed": summary["failed"],
                         "failed_ids": summary["failed_ids"],
                         "bytes": summary["bytes"]})
    return result_map
