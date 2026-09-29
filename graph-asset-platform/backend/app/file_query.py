"""search_files 核心（spec 2026-09-29 §4.3）——文件名搜索 / 目录浏览（find/ls 语义）。

与 graph_query 平行的共享核心：MCP search_files 与 REST POST /files 调用同一
``search_files_core``，错误/护栏不分叉。不搜内容（内容搜索是 search_graph 职责）。

游标=上一页最后一条 path（keyset，path ASC 确定性排序）：深翻页 O(1)、不受并发
增删的页错位影响。total 精确到 ``TOTAL_CAP``（10000），超过置 ``total_is_bounded``。

2 字符 query 走 trigram **加速 LIKE**（SQLite >= 3.45 对 2 字符 LIKE 模式给出索引
计划，3.45.3 实证；低版本为 name 语料扫描——语义正确、速度尽力）。⚠️ 前缀短语
``MATCH '"xx"*'`` 已实证否决（FTS5 trigram MATCH 需 >=3 字符，spec D6 修订）。
"""
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .graph_query.contracts import INVALID_ARGUMENT, INVALID_FILTER, err
from .repos.graph_search_repo import normalize_search_text
from .service import get_service

TOTAL_CAP = 10_000
MAX_QUERY_LEN = 80


def _like_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _glob_escape(prefix: str) -> str:
    """GLOB 元字符转义（[ ] * ? → 字符类）。"""
    out = []
    for ch in prefix:
        out.append(f"[{ch}]" if ch in "[]*?" else ch)
    return "".join(out)


def _fts_phrase(q: str) -> str:
    return '"' + q.replace('"', '""') + '"'


def search_files_core(*, query: Optional[str] = None, path: Optional[str] = None,
                      ext: Optional[str] = None, recursive: bool = False,
                      limit: int = 100, after: Optional[str] = None) -> dict:
    """→ SearchFilesResponse 同构 dict（MCP 包模型 / REST 直返，两边 wire 一致）。"""
    svc = get_service()
    conn = svc.db

    # ---- 校验 ----
    norm_query = normalize_search_text(query) if query else ""
    if query is not None and not norm_query:
        raise err(INVALID_ARGUMENT, "query 不能为空白")
    if norm_query and len(norm_query) < 2:
        raise err(INVALID_ARGUMENT,
                  "文件名搜索词规范化后至少 2 个字符（1 字符无法走索引且无意义）")
    if len(norm_query) > MAX_QUERY_LEN:
        raise err(INVALID_ARGUMENT, f"query 规范化后最长 {MAX_QUERY_LEN} 字符")
    ext_n = (ext or "").strip().lstrip(".").lower() or None
    path_n = (path or "").strip().strip("/") or None
    if not (norm_query or path_n or ext_n):
        raise err(INVALID_ARGUMENT,
                  "query / path / ext 至少给一个：query=按文件名搜；path=列目录；"
                  "组合=交集")
    if path_n is not None:
        ok = conn.execute("SELECT 1 FROM files WHERE path=? AND is_dir=1",
                          (path_n,)).fetchone()
        if ok is None:
            raise err(INVALID_FILTER,
                      f"path 不存在或不是目录: {path_n}（首启建册期间可能未建全，"
                      f"稍后重试或联系管理员执行 files-reindex）",
                      field="path", value=path_n)
    if not isinstance(limit, int) or not (1 <= limit <= 500):
        raise err(INVALID_ARGUMENT, "limit 须在 1~500")

    # ---- WHERE 组装 ----
    where: list = []
    params: list = []
    join_fts = bool(norm_query)
    if norm_query:
        if len(norm_query) >= 3:
            where.append("files_fts MATCH ?")
            params.append(f"name : {_fts_phrase(norm_query)}")
        else:  # 2 字符 → trigram 加速 LIKE（>=3.45 索引支持；低版本 name 语料扫描）
            where.append("files_fts.name LIKE ? ESCAPE '\\'")
            params.append(f"%{_like_escape(norm_query)}%")
    if path_n is not None:
        base = _glob_escape(path_n) + "/"
        where.append("files.path GLOB ?")
        params.append(base + "*")
        if recursive:
            where.append("files.is_dir = 0")  # find -type f 语义
        else:
            where.append("files.path NOT GLOB ?")  # 排除更深层 → 直接子项
            params.append(base + "*/*")
    if ext_n is not None:
        where.append("files.ext = ?")
        params.append(ext_n)
    if after:
        where.append("files.path > ?")
        params.append(after)
    where_sql = " AND ".join(where) if where else "1=1"
    from_sql = ("FROM files JOIN files_fts ON files_fts.path = files.path"
                if join_fts else "FROM files")

    # ---- 计数（封顶） ----
    cnt = conn.execute(
        f"SELECT COUNT(*) FROM (SELECT 1 {from_sql} WHERE {where_sql} "
        f"LIMIT {TOTAL_CAP + 1})", params).fetchone()[0]

    # ---- 取页（limit+1 探 has_more） ----
    rows = conn.execute(
        f"SELECT files.path, files.name, files.ext, files.is_dir, files.size, "
        f"files.mtime, o.id AS obj_id, o.version AS o_version {from_sql} "
        f"LEFT JOIN objects o ON o.source_path = files.path "
        f"WHERE {where_sql} ORDER BY files.path LIMIT ?",
        [*params, limit + 1]).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]

    files = []
    for r in rows:
        is_dir = bool(r["is_dir"])
        has_obj = (not is_dir) and r["obj_id"] is not None
        files.append({
            "path": r["path"], "name": r["name"], "ext": r["ext"],
            "is_dir": is_dir, "size": r["size"],
            "mtime": (datetime.fromtimestamp(r["mtime"], tz=timezone.utc)
                      .isoformat(timespec="seconds") if r["mtime"] else None),
            # 键恒在（目录/非对象文件为 None）——MCP/REST wire 同构
            "obj_id": r["obj_id"] if has_obj else None,
            "version": (r["o_version"] or None) if has_obj else None,
        })
    applied = {k: v for k, v in {
        "query": query, "path": path_n, "ext": ext_n,
        "recursive": True if (recursive and path_n) else None}.items()
        if v is not None}
    return {
        "files": files, "total": min(cnt, TOTAL_CAP),
        "total_is_bounded": cnt > TOTAL_CAP,
        "has_more": has_more,
        "next_cursor": rows[-1]["path"] if has_more and rows else None,
        "index_building": bool(getattr(svc, "files_building", False)),
        "applied_filters": applied,
    }
