"""mcp_tools 表 + meta.mcp_instructions 读写（admin 前端可配）。

v13（三工具重构 2026-09-08）语义：
- ``visibility`` 三态：visible（tools/list 展示 + 可直调）/ hidden（不展示 +
  可直调——旧客户端缓存 schema 仍可调）/ disabled（不展示 + TOOL_DISABLED）。
  ``enabled`` 物理列仅供旧数据迁移读取，新代码一律以 visibility 判定。
- ``description`` 物理列存 **supplemental_description**（补充说明）：生效描述 =
  canonical（代码 docstring）+ 管理员补充——只能追加，不能覆盖接口契约（§9.2）。
- 服务总体说明（meta.mcp_instructions）同语义：生效 = canonical + 补充。
  旧全文覆盖值已由 v13 迁移备份到 mcp_instructions_legacy_backup。

MCP 请求路径每请求调用 ``get_all``（几行 SELECT，成本可忽略）——无缓存、
无失效问题；调用方（mcp_server）须自行兜异常（配置读取失败不影响工具结果）。
"""
import sqlite3
from datetime import datetime, timezone

INSTRUCTIONS_META_KEY = "mcp_instructions"
INSTRUCTIONS_LEGACY_BACKUP_KEY = "mcp_instructions_legacy_backup"

VISIBILITIES = ("visible", "hidden", "disabled")


def get_all(conn: sqlite3.Connection) -> dict:
    """{tool_name: {visibility, description}}（仅含已配置过的行）。"""
    rows = conn.execute(
        "SELECT tool_name, visibility, description FROM mcp_tools"
    ).fetchall()
    return {r["tool_name"]: {"visibility": r["visibility"],
                             "description": r["description"] or ""}
            for r in rows}


def upsert(conn: sqlite3.Connection, *, tool_name: str, visibility: str,
           description: str, updated_by: str) -> None:
    """单工具配置写入（调用方 commit）。enabled 列同步旧语义
    （disabled=0，其余=1）——老代码/报表读 enabled 仍一致。"""
    conn.execute(
        "INSERT INTO mcp_tools(tool_name, enabled, description, visibility, "
        "updated_at, updated_by) VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(tool_name) DO UPDATE SET "
        "enabled=excluded.enabled, description=excluded.description, "
        "visibility=excluded.visibility, "
        "updated_at=excluded.updated_at, updated_by=excluded.updated_by",
        (tool_name, 0 if visibility == "disabled" else 1, description or "",
         visibility,
         datetime.now(timezone.utc).isoformat(timespec="seconds"), updated_by),
    )


def get_instructions(conn: sqlite3.Connection) -> str:
    r = conn.execute(
        "SELECT value FROM meta WHERE key=?", (INSTRUCTIONS_META_KEY,)
    ).fetchone()
    return r["value"] if r else ""


def set_instructions(conn: sqlite3.Connection, text: str) -> None:
    """''=无补充（纯 canonical）。调用方 commit。"""
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (INSTRUCTIONS_META_KEY, text or ""),
    )
