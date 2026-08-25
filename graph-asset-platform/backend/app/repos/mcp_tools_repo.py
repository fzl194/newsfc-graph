"""mcp_tools 表 + meta.mcp_instructions 读写（admin 前端可配，2026-08-25）。

语义：``enabled=0`` → tools/list 隐藏 + 直连调用拦截（中文报错）；
``description=''`` → 用代码默认（工具 docstring，注册后快照）。
服务总体说明（instructions）存 ``meta`` 表 key=``mcp_instructions``（''=默认）。

MCP 请求路径每请求调用 ``get_all``（5 行 SELECT，成本可忽略）——无缓存、
无失效问题；调用方（mcp_server）须自行兜异常（配置读取失败不影响工具结果）。
"""
import sqlite3
from datetime import datetime, timezone

INSTRUCTIONS_META_KEY = "mcp_instructions"


def get_all(conn: sqlite3.Connection) -> dict:
    """{tool_name: {enabled: bool, description: str}}（仅含已配置过的行）。"""
    rows = conn.execute(
        "SELECT tool_name, enabled, description FROM mcp_tools"
    ).fetchall()
    return {
        r["tool_name"]: {"enabled": bool(r["enabled"]), "description": r["description"] or ""}
        for r in rows
    }


def upsert(conn: sqlite3.Connection, *, tool_name: str, enabled: bool,
           description: str, updated_by: str) -> None:
    """单工具配置写入（调用方 commit）。"""
    conn.execute(
        "INSERT INTO mcp_tools(tool_name, enabled, description, updated_at, updated_by) "
        "VALUES(?,?,?,?,?) "
        "ON CONFLICT(tool_name) DO UPDATE SET "
        "enabled=excluded.enabled, description=excluded.description, "
        "updated_at=excluded.updated_at, updated_by=excluded.updated_by",
        (tool_name, int(enabled), description or "",
         datetime.now(timezone.utc).isoformat(timespec="seconds"), updated_by),
    )


def get_instructions(conn: sqlite3.Connection) -> str:
    r = conn.execute(
        "SELECT value FROM meta WHERE key=?", (INSTRUCTIONS_META_KEY,)
    ).fetchone()
    return r["value"] if r else ""


def set_instructions(conn: sqlite3.Connection, text: str) -> None:
    """''=恢复默认。调用方 commit。"""
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (INSTRUCTIONS_META_KEY, text or ""),
    )
