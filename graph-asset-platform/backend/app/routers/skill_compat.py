"""SKILL 兼容双接口（2026-09-03 恢复，用户决策：与 MCP 两套并行）。

- 2026-08-24 MCP 服务化时删除了 ``POST /api/v1/domains`` 与 ``POST /api/v1/md``
  （e4922b4）；为兼容存量 Agent/SKILL 配置，按**原契约**恢复（请求/响应/
  版本解析语义逐行取自删除前代码，仅去掉已整体移除的 X-User-Id operator）。
- 权限与 MCP 一致：skill（``can_skill`` 或 ``can_frontend``，admin 全权）——
  见 middleware/auth.py ``_need_perm`` 的路径分支。
- 打点与取用统计无缝：level=object、caller=skill、endpoint=/domains|/md，
  与 MCP 行（mcp:get_domains|mcp:get_md）在运维页"知识取用频次"合并计数。
- 新接入仍推荐 MCP（/mcp 另有 search_objects/search_md/get_object 三工具）。
"""
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ..service import get_service
from ..telemetry.recorder import record
from ..version import is_newer

router = APIRouter()


@router.post("/domains")
def list_domains_with_md(request: Request):
    """一次性返回全部业务域的完整 md（``[{id, name, md}, ...]``）。

    业务域是用户最优先的业务归属定位层——数量少（跨 NF 类，version 恒 null），
    Agent 入口直接取全部域 md。其他层级仍按 ``POST /md`` 沿 ``[[ID]]`` 引用下钻。
    """
    idx = get_service().index
    latest: dict = {}
    for (id_, _ver), obj in idx.nodes.items():
        if obj.type != "BusinessDomain":
            continue
        cur = latest.get(id_)
        if cur is None or is_newer(obj.version, cur.version):
            latest[id_] = obj
    out = [
        {"id": id_, "name": obj.frontmatter.get("name"), "md": obj.raw_md}
        for id_, obj in latest.items()
    ]
    for item in out:
        record("/domains", item["id"], "BusinessDomain",
               user=request.state.user, caller=request.state.caller,
               level="object")
    return out


# ---------- /md (batch) ----------

class BatchMdRequest(BaseModel):
    """批量取 md 请求体（Agent 友好，供 SKILL 逐层批次调用）。

    - ``ids``：1~N 个对象 id（版本无关逻辑 ID，可含 ``@`` 与空格）。
    - ``version``：可选全局版本；不传 → 每个 id 各自取**最新现存版本**。
      某 id 不在该版本 → 该 id 计错并回带 ``available_versions``，不影响其余 id。
    """
    ids: list[str] = Field(..., min_length=1)
    version: Optional[str] = None


@router.post("/md")
def batch_md(req: BatchMdRequest, request: Request):
    """批量取多个对象的原始 markdown。

    复用单对象版本解析（``Index.resolve_node``）：不传 version 落到该 id 最新
    现存版本；版本不匹配不整体报错，而是该 id 计错并回带可用版本，其余 id 照常
    返回。响应为 ``{id: {version, md} | {error, available_versions}}``——每个 id
    恰好一个条目，便于 Agent 遍历。
    """
    idx = get_service().index
    out: dict = {}
    # dict.fromkeys 去重并保序；同 id 重复请求只算一次。
    for id_ in dict.fromkeys(req.ids):
        available = idx.versions_of(id_)
        if not available:
            out[id_] = {"error": "对象不存在", "available_versions": []}
            continue
        obj = idx.resolve_node(id_, req.version)
        if obj is None:
            # id 存在但指定版本缺失 → 回带可用版本，供 Agent 改版本重试
            out[id_] = {
                "error": f"版本不存在: {id_}@{req.version}",
                "available_versions": available,
            }
            continue
        out[id_] = {"version": obj.version, "md": obj.raw_md}
        record("/md", id_, obj.type, user=request.state.user,
               caller=request.state.caller, level="object")
    return out
