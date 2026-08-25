"""mcp_tools router：MCP 工具配置（admin）——启用开关 + 描述覆盖 + 服务总体说明。

配置全局生效（2026-08-25 用户决策），存 platform.db（mcp_tools 表 + meta.mcp_instructions）。
生效机制（mcp_server._ConfigurableFastMCP）：
- enabled=0 → tools/list 隐藏 + 直连调用中文报错（决策：隐藏+拦截）
- description 非空 → 完全替换 docstring 默认（决策）；''=恢复默认
- instructions 非空 → 完全替换；''=恢复默认
保存即生效（enabled/description 每请求读 DB；instructions 改即生效），无需重启。
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import mcp_server
from ..db import get_shared_db
from ..repos import mcp_tools_repo
from ..service import import_lock
from ..users.service import check_perm

# 长度上限（审查：防 admin 误存超大文本 → tools/list/initialize 响应膨胀）
_MAX_DESC = 2000
_MAX_INSTRUCTIONS = 10000

router = APIRouter()


def _require_admin(request: Request) -> None:
    """配置面仅 admin（endpoint 级校验，与 admin.py 同款；中间件已验 KEY）。"""
    user = getattr(request.state, "user_obj", None)
    if not user or not check_perm(user, "admin"):
        raise HTTPException(status_code=403, detail="需要 admin 权限")


def _snapshot() -> dict:
    """注册表（代码事实）∪ DB 行（配置覆盖）→ 前端全量视图。"""
    cfg = mcp_tools_repo.get_all(get_shared_db())
    tools = []
    for t in mcp_server.mcp._tool_manager.list_tools():  # 注册顺序
        c = cfg.get(t.name) or {}
        tools.append({
            "name": t.name,
            "enabled": c.get("enabled", True),
            "description": c.get("description", ""),
            "default_description": mcp_server._DEFAULT_DESCRIPTIONS.get(t.name, ""),
        })
    return {
        "tools": tools,
        "instructions": mcp_tools_repo.get_instructions(get_shared_db()),
        "default_instructions": mcp_server.DEFAULT_INSTRUCTIONS,
    }


@router.get("/mcp-tools")
def get_config(request: Request):
    _require_admin(request)
    return _snapshot()


class ToolCfgIn(BaseModel):
    name: str
    enabled: bool = True
    description: str = Field(default="", max_length=_MAX_DESC)


class ConfigIn(BaseModel):
    tools: Optional[List[ToolCfgIn]] = None
    instructions: Optional[str] = Field(default=None, max_length=_MAX_INSTRUCTIONS)


@router.patch("/mcp-tools")
def patch_config(req: ConfigIn, request: Request):
    """保存配置（全量或部分）。未知工具名 400；返回保存后全量（同 GET）。"""
    _require_admin(request)
    known = set(mcp_server._DEFAULT_DESCRIPTIONS)
    if req.tools is not None:
        bad = [t.name for t in req.tools if t.name not in known]
        if bad:
            raise HTTPException(status_code=400,
                                detail=f"未知工具名: {bad}（可选 {sorted(known)}）")
    conn = get_shared_db()
    by = getattr(request.state, "user", "")
    # 多行写 + meta 写共一个事务，持共享写锁（与 fs/jobs 写路径同约定，审查修正）；
    # 去首尾空白：纯空白描述/说明视同清空（回默认）
    with import_lock:
        if req.tools:
            for t in req.tools:
                mcp_tools_repo.upsert(conn, tool_name=t.name, enabled=t.enabled,
                                      description=t.description.strip(), updated_by=by)
        if req.instructions is not None:
            mcp_tools_repo.set_instructions(conn, req.instructions.strip())
        conn.commit()
    # commit 成功后才应用到内存（审查修正：防 DB 写失败时内存与 DB 漂移）
    if req.instructions is not None:
        mcp_server.apply_instructions(req.instructions.strip())
    return _snapshot()
