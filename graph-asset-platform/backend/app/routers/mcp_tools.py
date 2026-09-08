"""mcp_tools router：MCP 工具配置（admin）——visibility 三态 + 补充说明 + 总体说明补充。

v13（三工具重构 M3，2026-09-08）：
- 主字段 ``visibility``（visible/hidden/disabled）+ ``supplemental_description``
  （物理列复用旧 ``description``，仅 API/UI 改名——语义从“覆盖”变“追加”）。
- 旧 API 兼容（§11.1）：GET 返回 ``enabled = visibility != 'disabled'``；旧 PATCH
  ``enabled=true/false``：公开工具 → visible/disabled；legacy 工具 →
  hidden/disabled（旧客户端 re-enable 只到 hidden——回滚可见须显式
  ``visibility=visible``）。``description`` 字段继续作为补充说明的兼容别名。
- instructions 语义=补充说明（canonical 在代码，§9.3）。

配置全局生效，存 platform.db。保存即生效（visibility/description 每请求读 DB；
instructions 改即生效），无需重启。
"""
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import mcp_server
from ..db import get_shared_db
from ..repos import mcp_tools_repo
from ..service import import_lock
from ..users.service import check_perm

# 长度上限（防 admin 误存超大文本 → tools/list/initialize 响应膨胀）
_MAX_DESC = 2000
_MAX_INSTRUCTIONS = 10000

# 拿锁等待上限：挖掘增量索引/批量上传/启动对账持 import_lock 可达分钟级——
# UI 保存无限等只表现为转圈，限时失败给提示
_LOCK_WAIT_SECONDS = 5.0

router = APIRouter()

# legacy 三工具（旧 PATCH enabled=true 只到 hidden；显式 visibility=visible
# 才重新出现在 tools/list——回滚通道）
_LEGACY_TOOLS = {"search_objects", "search_md", "get_object"}


def _require_admin(request: Request) -> None:
    """配置面仅 admin（endpoint 级校验，与 admin.py 同款；中间件已验 KEY）。"""
    user = getattr(request.state, "user_obj", None)
    if not user or not check_perm(user, "admin"):
        raise HTTPException(status_code=403, detail="需要 admin 权限")


def _snapshot() -> dict:
    """注册表（代码事实）∪ DB 行（配置）→ 前端全量视图。"""
    cfg = mcp_tools_repo.get_all(get_shared_db())
    tools = []
    for t in mcp_server.mcp._tool_manager.list_tools():  # 注册顺序
        c = cfg.get(t.name) or {}
        supp = c.get("description", "")
        vis = c.get("visibility", "visible")
        tools.append({
            "name": t.name,
            "visibility": vis,
            "enabled": vis != "disabled",  # 旧前端兼容（§11.1）
            "supplemental_description": supp,
            "description": supp,  # 旧 PATCH/前端兼容别名
            "default_description": mcp_server._DEFAULT_DESCRIPTIONS.get(t.name, ""),
            "is_legacy": t.name in _LEGACY_TOOLS,
        })
    return {
        "tools": tools,
        "instructions": mcp_tools_repo.get_instructions(get_shared_db()),
        "default_instructions": mcp_server.DEFAULT_INSTRUCTIONS,
        "instructions_legacy_backup": _backup_instructions(),
    }


def _backup_instructions() -> str:
    from ..repos.mcp_tools_repo import INSTRUCTIONS_LEGACY_BACKUP_KEY
    r = get_shared_db().execute(
        "SELECT value FROM meta WHERE key=?", (INSTRUCTIONS_LEGACY_BACKUP_KEY,)
    ).fetchone()
    return r["value"] if r else ""


@router.get("/mcp-tools")
def get_config(request: Request):
    _require_admin(request)
    return _snapshot()


class ToolCfgIn(BaseModel):
    """visibility 显式优先；enabled 为旧客户端兼容字段。"""
    name: str
    visibility: Optional[Literal["visible", "hidden", "disabled"]] = None
    enabled: Optional[bool] = None
    description: str = Field(default="", max_length=_MAX_DESC)  # 兼容别名=补充说明
    supplemental_description: Optional[str] = Field(default=None, max_length=_MAX_DESC)


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
    # 多行写 + meta 写共一个事务，持共享写锁（与 fs/jobs 写路径同约定）；
    # 去首尾空白：纯空白描述/说明视同清空。
    # 限时拿锁：批量任务（挖掘/上传/对账）持锁期间不无限等——超时 409 给提示
    if not import_lock.acquire(timeout=_LOCK_WAIT_SECONDS):
        raise HTTPException(
            status_code=409,
            detail="图谱索引正被批量任务占用（挖掘/上传/启动对账），请稍后重试")
    try:
        if req.tools:
            for t in req.tools:
                if t.visibility is not None:
                    vis = t.visibility
                elif t.enabled is not None:
                    # 旧 PATCH 兼容映射（§11.1）：legacy 的 enable 只到 hidden
                    if t.enabled:
                        vis = "hidden" if t.name in _LEGACY_TOOLS else "visible"
                    else:
                        vis = "disabled"
                else:
                    c = mcp_tools_repo.get_all(conn).get(t.name) or {}
                    vis = c.get("visibility", "visible")
                supp = (t.supplemental_description
                        if t.supplemental_description is not None else t.description)
                mcp_tools_repo.upsert(conn, tool_name=t.name, visibility=vis,
                                      description=supp.strip(), updated_by=by)
        if req.instructions is not None:
            mcp_tools_repo.set_instructions(conn, req.instructions.strip())
        conn.commit()
    finally:
        import_lock.release()
    # commit 成功后才应用到内存（防 DB 写失败时内存与 DB 漂移）
    if req.instructions is not None:
        mcp_server.apply_instructions(req.instructions.strip())
    return _snapshot()
