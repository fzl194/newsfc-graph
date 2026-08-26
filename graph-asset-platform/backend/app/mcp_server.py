"""MCP 服务（Streamable HTTP，同进程挂载 /mcp；CR：MCP 服务化 2026-08-24）。

设计要点（docs/需求分析与实施计划-MCP服务化-2026-08-24.md）：
- 5 工具：get_domains / get_md / search_objects / search_md / get_object——
  SKILL 旧两接口（POST /domains、POST /md，步骤③删除）的能力继承 +
  search_md 正文召回新能力（FTS5）。
- 上下文参数 AGENT_USERNAME / AGENT_SESSION_ID：Agent 从沙箱环境变量
  ``_AGENT_USERNAME`` / ``_AGENT_SESSION_ID`` 读取后传入（打点归因，不影响结果；
  SDK 禁止下划线前缀参数名，故工具参数名去掉前导下划线）。
- 鉴权：纯 ASGI 中间件（X-API-Key → skill 权限）——**不用 BaseHTTPMiddleware**
  （其对 SSE 流式响应有缓冲/挂起的历史问题，对抗审查 A1）。
- stateless_http + json_response：无会话状态累积（免 TTL/清理，审查 A3 简化），
  响应纯 JSON（TestClient/普通 HTTP 客户端直测）。
- 打点三层：request 级（鉴权后立即记，caller=mcp，审查 A2）/ tool 级（每调用，
  审查 B3）/ object 级（get_md 每 id、get_domains 每域——取用统计口径）。
"""
from typing import Annotated, Optional

import json

from pydantic import Field

from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.server import Context
from mcp.server.transport_security import TransportSecuritySettings

from .objects_search import list_objects_rows
from .routers.objects import _dump, _dump_edge, _resolve
from .service import get_service
from .telemetry.recorder import record
from .users.service import authenticate, check_perm
from .version import is_newer

# get_md 护栏（对抗审查 F1：防单次 tool result 撑爆 Agent 上下文）
MAX_IDS_PER_CALL = 100
MAX_TOTAL_BYTES = 2 * 1024 * 1024  # 2MB

_CTX = ("【必传】当前使用者工号：每次调用从环境变量 _AGENT_USERNAME 读取后传入。"
        "仅用于平台取用统计与追溯，不影响调用结果。")
_CTX_SID = ("【必传】当前会话ID：每次调用从环境变量 _AGENT_SESSION_ID 读取后传入。"
            "仅用于平台取用统计与追溯，不影响调用结果。")

# 服务总体说明默认值（admin 可在 mcp_tools 配置覆盖，''=用本默认）
DEFAULT_INSTRUCTIONS = (
    "三层电信图谱（业务层→任务层→特性层→命令层）查询服务。"
    "推荐入口：get_domains 锁定业务域 → 读 md 提取 [[ID]] 引用 → get_md 逐层下钻；"
    "不确定对象 ID 时先用 search_md 按业务关键词召回。"
)


# ---------- 工具配置动态生效（admin 前端可配，2026-08-25） ----------

def _load_config_safe() -> dict:
    """读 mcp_tools 配置；任何异常回退空配置（全启用+默认描述）——配置面故障
    绝不影响工具结果（与打点同哲学）。每请求读 DB（5 行 SELECT，成本可忽略）。"""
    try:
        from .db import get_shared_db
        from .repos import mcp_tools_repo
        return mcp_tools_repo.get_all(get_shared_db())
    except Exception:  # noqa: BLE001
        return {}


class _ConfigurableFastMCP(FastMCP):
    """tools/list 过滤禁用 + 描述覆盖；直连调用禁用拦截（决策：隐藏+拦截）。

    必须子类覆写：``__init__`` 注册的是 bound method，事后 monkey-patch 无效。
    描述覆盖只改**返回的 MCPTool 副本**（super().list_tools 每次从注册表重建），
    注册表 Tool 对象保持 docstring 默认——清空覆盖即回默认，无需恢复逻辑。
    """

    async def list_tools(self):
        tools = await super().list_tools()
        cfg = _load_config_safe()
        out = []
        for t in tools:
            c = cfg.get(t.name)
            if c is not None and not c["enabled"]:
                continue  # 禁用 → 隐藏（Agent 看不到）
            d = (c or {}).get("description") or ""
            if d:
                t.description = d  # 完全替换（决策）；pydantic 模型可变
            out.append(t)
        return out

    async def call_tool(self, name: str, arguments: dict, **kwargs):
        c = _load_config_safe().get(name)
        if c is not None and not c["enabled"]:
            # ToolError → MCP isError=true，中文原文透传给 Agent
            raise ToolError(f"工具 {name} 已被管理员禁用，如有需要请联系平台管理员开启")
        return await super().call_tool(name, arguments, **kwargs)


mcp = _ConfigurableFastMCP(
    "graph-asset-platform",
    instructions=DEFAULT_INSTRUCTIONS,
    streamable_http_path="/",   # 挂载于 FastAPI /mcp 之下，最终端点即 /mcp
    stateless_http=True,        # 无会话状态（免 TTL/孤儿清理）
    json_response=True,         # 响应纯 JSON（非 SSE 流）
    # 内网服务 + 平台自带 KEY 鉴权（ASGI 层），关闭 SDK 的 DNS rebinding Host 校验
    # （生产若暴露公网应改配 allowed_hosts 而非关闭）
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


# ---------- 身份与打点 ----------

def _identity(ctx: Context) -> str:
    """从 MCP 请求头解析 KEY 属主用户名（ASGI 鉴权门已拦截未授权；此处仅取归因）。"""
    try:
        req = ctx.request_context.request
        key = req.headers.get("x-api-key", "") if req is not None else ""
        u = authenticate(key)
        return (u or {}).get("username", "")
    except Exception:  # noqa: BLE001 打点归因绝不影响工具结果
        return ""


_PARAMS_MAX = 2048  # 入参/出参摘要截断上限（观测载荷不与业务等量级）


def _j(v) -> str:
    """入参/出参 → JSON 字符串（超长截断；序列化失败返回空串不阻断）。"""
    try:
        s = json.dumps(v, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return ""
    return s if len(s) <= _PARAMS_MAX else s[:_PARAMS_MAX] + "…(截断)"


def _record_tool(name: str, *, user: str, operator: str, session_id: str,
                 params: Optional[dict] = None, result: Optional[dict] = None) -> None:
    """tool 级打点（2026-08-24 用户决策：输入输出都记录）。

    params=业务入参（上下文参数已有专列不重复）；result=**结构化摘要**而非原始
    载荷（md 全文本在 objects 表，append-only 打点表不存大字段）。
    """
    record(f"mcp:{name}", user=user, caller="mcp", level="tool",
           operator=operator, session_id=session_id,
           params=_j(params or {}), result=_j(result or {}))


def _err_summary(e: Exception) -> dict:
    return {"error": str(e)[:300]}


# ---------- 工具 ----------

@mcp.tool()
def get_domains(AGENT_USERNAME: Annotated[str, Field(description=_CTX)], AGENT_SESSION_ID: Annotated[str, Field(description=_CTX_SID)], ctx: Context = None) -> dict:
    """获取三层图谱全部业务域（BusinessDomain）的完整 markdown。

    业务域是业务归属的顶层定位层，是任何查询的推荐第一步：先调本工具，按用户需求
    关键词锁定业务域，再从域 md 的 [[NetworkScenario@*]] 引用下钻场景/方案。
    返回量小（业务域数量少），可放心全量读取。返回 {domains: [{id, name, md}]}。

    Args:
        AGENT_USERNAME: 当前使用者工号（从环境变量 _AGENT_USERNAME 读取传入）
        AGENT_SESSION_ID: 当前会话ID（从环境变量 _AGENT_SESSION_ID 读取传入）
    """
    user = _identity(ctx)
    params: dict = {}
    try:
        idx = get_service().index
        latest: dict = {}
        for (id_, _v), obj in idx.nodes.items():
            if obj.type != "BusinessDomain":
                continue
            cur = latest.get(id_)
            if cur is None or is_newer(obj.version, cur.version):
                latest[id_] = obj
        out = [{"id": id_, "name": obj.frontmatter.get("name"), "md": obj.raw_md}
               for id_, obj in latest.items()]
        for item in out:  # object 级：每域一行（取用统计口径）
            record("mcp:get_domains", item["id"], "BusinessDomain", user=user,
                   caller="mcp", level="object", operator=AGENT_USERNAME,
                   session_id=AGENT_SESSION_ID)
        _record_tool("get_domains", user=user, operator=AGENT_USERNAME,
                     session_id=AGENT_SESSION_ID, params=params,
                     result={"domains": len(out), "ids": [d["id"] for d in out[:30]]})
        # 包一层 dict：裸 list 会被 SDK 拆成逐元素 content，形态不稳定
        return {"domains": out}
    except Exception as e:  # noqa: BLE001 失败也留痕后原样抛出（转 MCP isError）
        _record_tool("get_domains", user=user, operator=AGENT_USERNAME,
                     session_id=AGENT_SESSION_ID, params=params, result=_err_summary(e))
        raise


@mcp.tool()
def get_md(ids: list[str], AGENT_USERNAME: Annotated[str, Field(description=_CTX)], AGENT_SESSION_ID: Annotated[str, Field(description=_CTX_SID)],
           version: Optional[str] = None, ctx: Context = None) -> dict:
    """按逻辑 ID 批量获取图谱对象的完整 markdown（含 frontmatter + 正文 + ## 边段）。

    ID 格式：业务层 2 段 {Type}@{slug}（如 NetworkScenario@charging）；NF 类 3 段
    {nf}@{Type}@{name}（如 UDG@AtomTask@SET UPDEFAULTQUOTA，name 可含空格）。
    不传 version 则每个 id 各取最新现存版本。部分失败容错：不存在/版本缺失的 id
    单独计错并回带 available_versions，其余 id 照常返回。读完 md 后应提取全文
    [[ID]] 引用继续下钻。单次最多 100 个 id 且响应总量 ≤2MB，超限报错请分批。

    Args:
        ids: 对象逻辑 ID 列表（1~100 个）
        AGENT_USERNAME: 当前使用者工号（从环境变量 _AGENT_USERNAME 读取传入）
        AGENT_SESSION_ID: 当前会话ID（从环境变量 _AGENT_SESSION_ID 读取传入）
        version: 可选全局版本；不传 = 每个 id 各取最新现存版本
    """
    user = _identity(ctx)
    uniq = list(dict.fromkeys(ids))  # 去重保序
    params: dict = {"ids": uniq, "version": version}
    try:
        if not (1 <= len(uniq) <= MAX_IDS_PER_CALL):
            raise ValueError(f"ids 数量须在 1~{MAX_IDS_PER_CALL}，当前 {len(uniq)}——请分批调用")
        idx = get_service().index
        out: dict = {}
        total = 0
        failed_ids: list = []
        for id_ in uniq:
            available = idx.versions_of(id_)
            if not available:
                out[id_] = {"error": "对象不存在", "available_versions": []}
                failed_ids.append(id_)
                continue
            obj = idx.resolve_node(id_, version)
            if obj is None:
                out[id_] = {"error": f"版本不存在: {id_}@{version}", "available_versions": available}
                failed_ids.append(id_)
                continue
            total += len(obj.raw_md.encode("utf-8"))
            if total > MAX_TOTAL_BYTES:
                raise RuntimeError(
                    f"响应总量超 {MAX_TOTAL_BYTES // 1024 // 1024}MB 上限（已处理 "
                    f"{len(out)} 个 id）——请分批调用，每批 ≤50 个 id")
            out[id_] = {"version": obj.version, "md": obj.raw_md}
            record("mcp:get_md", id_, obj.type, user=user, caller="mcp", level="object",
                   operator=AGENT_USERNAME, session_id=AGENT_SESSION_ID)
        _record_tool("get_md", user=user, operator=AGENT_USERNAME, session_id=AGENT_SESSION_ID,
                     params=params,
                     result={"ok": len(uniq) - len(failed_ids), "failed": len(failed_ids),
                             "failed_ids": failed_ids[:20], "bytes": total})
        return out
    except Exception as e:  # noqa: BLE001 失败也留痕后原样抛出
        _record_tool("get_md", user=user, operator=AGENT_USERNAME, session_id=AGENT_SESSION_ID,
                     params=params, result=_err_summary(e))
        raise


@mcp.tool()
def search_objects(AGENT_USERNAME: Annotated[str, Field(description=_CTX)], AGENT_SESSION_ID: Annotated[str, Field(description=_CTX_SID)], q: Optional[str] = None,
                   layer: Optional[str] = None, type: Optional[str] = None,
                   nf: Optional[str] = None, version: Optional[str] = None,
                   domain: Optional[str] = None, scenario: Optional[str] = None,
                   page: int = 1, size: int = 50, ctx: Context = None) -> dict:
    """按关键词搜索图谱对象的元数据（匹配 id / name / name_zh，不搜正文）。

    支持按层（命令层/特性层/任务层/业务层）、类型、网元、版本、业务域过滤。
    用于：已知大致名称/编号时定位对象 ID，或浏览某层某网元的对象清单。
    要搜正文内容请用 search_md。

    Args:
        AGENT_USERNAME: 当前使用者工号（从环境变量 _AGENT_USERNAME 读取传入）
        AGENT_SESSION_ID: 当前会话ID（从环境变量 _AGENT_SESSION_ID 读取传入）
        q: 关键词（id/name/name_zh 子串，不区分大小写）
        layer: UI 层过滤（命令层/特性层/任务层/业务层）
        type: 单类型过滤（优先于 layer，如 MMLCommand）
        nf: 网元过滤（如 UDG）
        version: 版本精确匹配
        domain: 业务域过滤
        scenario: 场景过滤
        page: 页码（默认 1）
        size: 页大小（默认 50）
    """
    user = _identity(ctx)
    params = {k: v for k, v in {"q": q, "layer": layer, "type": type, "nf": nf,
                                "version": version, "domain": domain,
                                "scenario": scenario, "page": page, "size": size}.items()
              if v is not None}
    try:
        rows, total = list_objects_rows(q=q, layer=layer, type=type, nf=nf, version=version,
                                        domain=domain, scenario=scenario)
        start = (page - 1) * size
        page_rows = rows[start:start + size]
        _record_tool("search_objects", user=user, operator=AGENT_USERNAME,
                     session_id=AGENT_SESSION_ID, params=params,
                     result={"total": total, "returned": len(page_rows),
                             "top_ids": [r["id"] for r in page_rows[:10]]})
        return {"total": total, "rows": page_rows}
    except Exception as e:  # noqa: BLE001
        _record_tool("search_objects", user=user, operator=AGENT_USERNAME,
                     session_id=AGENT_SESSION_ID, params=params, result=_err_summary(e))
        raise


@mcp.tool()
def search_md(q: str, AGENT_USERNAME: Annotated[str, Field(description=_CTX)], AGENT_SESSION_ID: Annotated[str, Field(description=_CTX_SID)],
              layer: Optional[str] = None, type: Optional[str] = None,
              nf: Optional[str] = None, version: Optional[str] = None,
              limit: int = 20, offset: int = 0, ctx: Context = None) -> dict:
    """全文搜索图谱所有对象的 markdown 正文，按相关度排序返回高亮摘要片段。

    用于：①用户意图式召回——不确定对象 ID 时按业务关键词找相关 md；②查某个
    参数/命令/特性名出现在哪些对象里。返回片段摘要而非全文，选中后用 get_md
    取完整 md。支持层/类型/网元/版本过滤。默认只搜每个对象的最新版本。

    Args:
        q: 正文关键词（≥3 字符走相关度排序；更短按字面匹配）
        AGENT_USERNAME: 当前使用者工号（从环境变量 _AGENT_USERNAME 读取传入）
        AGENT_SESSION_ID: 当前会话ID（从环境变量 _AGENT_SESSION_ID 读取传入）
        layer: UI 层过滤（命令层/特性层/任务层/业务层）
        type: 单类型过滤（优先于 layer）
        nf: 网元过滤
        version: 版本锁定（不传 = 只搜每个对象最新版本）
        limit: 返回条数（默认 20）
        offset: 偏移（默认 0）
    """
    user = _identity(ctx)
    params = {k: v for k, v in {"q": q, "layer": layer, "type": type, "nf": nf,
                                "version": version, "limit": limit,
                                "offset": offset}.items() if v is not None}
    try:
        res = get_service().search_md(q, layer=layer, type=type, nf=nf, version=version,
                                      limit=limit, offset=offset)
        _record_tool("search_md", user=user, operator=AGENT_USERNAME,
                     session_id=AGENT_SESSION_ID, params=params,
                     result={"total": res["total"], "returned": len(res["hits"]),
                             "top_ids": [h["id"] for h in res["hits"][:10]]})
        return res
    except Exception as e:  # noqa: BLE001
        _record_tool("search_md", user=user, operator=AGENT_USERNAME,
                     session_id=AGENT_SESSION_ID, params=params, result=_err_summary(e))
        raise


@mcp.tool()
def get_object(id: str, AGENT_USERNAME: Annotated[str, Field(description=_CTX)], AGENT_SESSION_ID: Annotated[str, Field(description=_CTX_SID)],
               version: Optional[str] = None, ctx: Context = None) -> dict:
    """获取单个图谱对象的结构化详情：frontmatter 元数据、正文、出边列表。

    需要看对象的关联关系（如某 FeatureTask 引用了哪些命令）时用。
    ⚠ 出边仅含 curated 边（## 边段声明的显式边），完备遍历必须读 md 全文提取
    [[ID]] 引用。要完整原文用 get_md。

    Args:
        id: 对象逻辑 ID
        AGENT_USERNAME: 当前使用者工号（从环境变量 _AGENT_USERNAME 读取传入）
        AGENT_SESSION_ID: 当前会话ID（从环境变量 _AGENT_SESSION_ID 读取传入）
        version: 版本锁定（不传 = 最新现存版本；版本缺失回带可用版本列表）
    """
    user = _identity(ctx)
    params = {k: v for k, v in {"id": id, "version": version}.items() if v is not None}
    try:
        obj = _resolve(id, version)
        idx = get_service().index
        out = {
            **_dump(obj),
            "versions": idx.versions_of(obj.id),
            "out_edges": [_dump_edge(e) for e in idx.out_edges(obj.id, obj.version)],
        }
        _record_tool("get_object", user=user, operator=AGENT_USERNAME,
                     session_id=AGENT_SESSION_ID, params=params,
                     result={"type": obj.type, "version": obj.version,
                             "out_edges": len(out["out_edges"])})
        return out
    except Exception as e:  # noqa: BLE001
        _record_tool("get_object", user=user, operator=AGENT_USERNAME,
                     session_id=AGENT_SESSION_ID, params=params, result=_err_summary(e))
        raise


# ---------- 配置快照与总体说明应用 ----------

# 默认描述快照（注册表 Tool 的 docstring 描述；GET /mcp-tools 的 default_description
# 数据源）。放在全部 @mcp.tool() 注册之后。
_DEFAULT_DESCRIPTIONS = {t.name: t.description
                         for t in mcp._tool_manager.list_tools()}


def apply_instructions(text: str) -> None:
    """应用总体说明覆盖（''=恢复默认）。stateless 模式每请求经
    ``create_initialization_options()`` 读 ``_mcp_server.instructions``——改即生效。"""
    mcp._mcp_server.instructions = text or DEFAULT_INSTRUCTIONS  # SDK 无公开 setter（1.27.1）


# ---------- 纯 ASGI 鉴权（审查 A1：BaseHTTPMiddleware 对 SSE 流有缓冲/挂起风险） ----------

class MCPAuthMiddleware:
    """X-API-Key 鉴权 + 请求级打点（鉴权通过后立即记，不等响应完成——审查 A2）。

    纯 ASGI 实现：只读 header，不缓冲 body、不包装响应流。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                   for k, v in scope.get("headers", [])}
        user = authenticate(headers.get("x-api-key", ""))
        if user is None:
            await JSONResponse(status_code=401,
                               content={"detail": "missing or invalid api key"}
                               )(scope, receive, send)
            return
        if not check_perm(user, "skill"):
            await JSONResponse(status_code=403,
                               content={"detail": "permission denied"}
                               )(scope, receive, send)
            return
        # /mcp 请求级打点已移除（2026-08-26 打点瘦身·方案B）：无任何消费方；
        # 取用观测由 tool 级（mcp_server 工具装饰器内）+ object 级承担
        await self.app(scope, receive, send)


# ---------- 可重建挂载（SDK 限制：session manager 的 run() 仅可进一次/实例） ----------

class _RebuildableMCPMount:
    """lifespan 启动时 ``rebuild_session_manager()`` 重建；本包装器实时跟随当前 app。

    测试（TestClient 每用例启停 lifespan）与生产（单次启停）都需要：同一 FastMCP
    实例的工具注册不变，仅 session manager 换新。
    """

    def __init__(self, mcp_instance):
        self._mcp = mcp_instance
        self._app = None

    def rebuild(self) -> None:
        self._mcp._session_manager = None  # SDK 无公开重置口（1.27.1）
        self._app = self._mcp.streamable_http_app()

    async def __call__(self, scope, receive, send):
        if self._app is None:
            self.rebuild()
        await self._app(scope, receive, send)


_mount = _RebuildableMCPMount(mcp)


class _RootPathASGI:
    """配合 FastAPI ``Route("/mcp")`` 挂载：子 app 以根路由注册，改写子路径为 "/"。

    （Starlette ``Mount("/mcp")`` 对无尾斜杠的精确路径匹配不到——子路径为空串，
    子 app 的 Route("/") 不命中；显式 Route + 路径改写彻底避开该坑。）
    """

    def __init__(self, inner):
        self._inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "path": "/"}
        await self._inner(scope, receive, send)


asgi_app = MCPAuthMiddleware(_RootPathASGI(_mount))


def rebuild_session_manager():
    """lifespan 启动时调用：重建 session manager 并返回（供 ``async with .run()``）。"""
    _mount.rebuild()
    return mcp.session_manager
