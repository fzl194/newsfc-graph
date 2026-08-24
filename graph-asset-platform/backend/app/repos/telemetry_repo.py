"""telemetry 表：append-only INSERT + 聚合查询（替代 jsonl 全表扫）。

level=object（取用统计：SKILL 旧接口 + MCP 工具）+ level=request（请求轨迹，
activity 统计）+ level=tool（MCP 工具调用级，含 search 类可观测，MCP 服务化
2026-08-24）。ts 存 ISO8601 UTC 字符串（字典序 = 时间序，cutoff 用字符串比较）。
"""
import sqlite3
from datetime import datetime, timedelta, timezone

# 取用统计口径：SKILL 旧两接口（历史行）+ MCP 对应工具（新行）——无缝衔接
_STATS_ENDPOINTS = ("/md", "/domains", "mcp:get_md", "mcp:get_domains")
_STATS_CALLERS = ("skill", "mcp")


def insert(conn: sqlite3.Connection, *, ts: str, level: str, caller: str,
           endpoint: str, obj_id: str, obj_type: str, user: str, operator: str,
           session_id: str = "") -> None:
    conn.execute(
        "INSERT INTO telemetry(ts, level, caller, endpoint, obj_id, obj_type, user, "
        "operator, session_id) VALUES(?,?,?,?,?,?,?,?,?)",
        (ts, level, caller, endpoint, obj_id, obj_type, user, operator, session_id),
    )


def _cutoff_iso(days: int):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat() if days > 0 else None


def aggregate_stats(conn: sqlite3.Connection, days: int = 30) -> dict:
    """level=object + caller∈{skill,mcp} + endpoint∈取用口径，按 type/id/user/
    operator/session + 小时桶。小时桶在 Python 算（SQLite strftime 不认 ISO 带时区 T 格式）。

    占位符动态生成（对抗审查 B4：SQL `IN (?,?)` 写死与 _STATS_ENDPOINTS 扩容不匹配）。
    """
    ep_ph = ",".join("?" * len(_STATS_ENDPOINTS))
    ca_ph = ",".join("?" * len(_STATS_CALLERS))
    sql = (f"SELECT obj_type, obj_id, user, operator, session_id, ts FROM telemetry "
           f"WHERE level='object' AND caller IN ({ca_ph}) AND endpoint IN ({ep_ph})")
    params = [*list(_STATS_CALLERS), *list(_STATS_ENDPOINTS)]
    c = _cutoff_iso(days)
    if c:
        sql += " AND ts >= ?"
        params.append(c)
    by_type, by_id, id_type, by_user, by_operator, by_hour, sessions = {}, {}, {}, {}, {}, {}, set()
    for r in conn.execute(sql, params).fetchall():
        t = r["obj_type"] or "?"
        i = r["obj_id"] or "?"
        u = r["user"] or "?"
        by_type[t] = by_type.get(t, 0) + 1
        by_id[i] = by_id.get(i, 0) + 1
        id_type[i] = t
        by_user[u] = by_user.get(u, 0) + 1
        op = r["operator"] or ""
        if op:
            by_operator[op] = by_operator.get(op, 0) + 1
        sid = r["session_id"] or ""
        if sid:
            sessions.add(sid)
        try:
            dt = datetime.fromisoformat((r["ts"] or "").replace("Z", "+00:00"))
            hour = dt.strftime("%m-%d %H:00")
            by_hour[hour] = by_hour.get(hour, 0) + 1
        except ValueError:
            continue
    top_ids = sorted(by_id.items(), key=lambda x: -x[1])[:20]
    timeline = [{"date": d, "count": n} for d, n in sorted(by_hour.items())]
    return {
        "total": sum(by_type.values()),
        "by_type": by_type,
        "top_ids": [{"id": i, "type": id_type.get(i, "?"), "count": c} for i, c in top_ids],
        "timeline": timeline,
        "by_user": by_user,
        "by_operator": by_operator,
        "by_session": len(sessions),
    }


def _parse_cursor(since: str) -> tuple[str, int]:
    """拆 next_since 游标：'ts|rowid' → (ts, rowid)；纯 ISO → (ts, 0) 表示含边界起点。"""
    if "|" in since:
        ts, _, rid = since.partition("|")
        try:
            return ts, int(rid)
        except ValueError:
            return ts, 0
    return since, 0


def list_skill_usage(conn: sqlite3.Connection, since: str = "", limit: int = 1000) -> dict:
    """取用明细增量流（与 ``aggregate_stats`` 同口径，返回原始明细行）。

    ts 存 ISO8601 UTC，字典序=时间序。游标语义（next_since 不透明，消费方原样回传）：
      - since 留空 → 全量起点；
      - 纯 ISO8601 → ``ts >= 该时间``（含边界起点，便于按时间引导/过滤）；
      - 'ts|rowid' → ``(ts, rowid)`` 精确推进位，跨同 ts 行不卡死、不重复。
    取 limit+1 行判断 has_more，返回前 limit 行；无行时 next_since 回填 since。
    """
    ep_ph = ",".join("?" * len(_STATS_ENDPOINTS))
    ca_ph = ",".join("?" * len(_STATS_CALLERS))
    where = [f"level='object'", f"caller IN ({ca_ph})", f"endpoint IN ({ep_ph})"]
    params = [*list(_STATS_CALLERS), *list(_STATS_ENDPOINTS)]
    if since:
        cur_ts, cur_rowid = _parse_cursor(since)
        if cur_rowid > 0:
            where.append("((ts > ?) OR (ts = ? AND rowid > ?))")
            params += [cur_ts, cur_ts, cur_rowid]
        else:
            where.append("ts >= ?")
            params.append(cur_ts)
    sql = ("SELECT ts, endpoint, obj_id, obj_type, user, operator, session_id, rowid FROM telemetry "
           "WHERE " + " AND ".join(where) + " ORDER BY ts ASC, rowid ASC LIMIT ?")
    params.append(limit + 1)
    rows = conn.execute(sql, params).fetchall()
    returned = rows[:limit]
    events = [{"ts": r["ts"], "endpoint": r["endpoint"], "obj_id": r["obj_id"],
               "obj_type": r["obj_type"], "user": r["user"], "operator": r["operator"],
               "session_id": r["session_id"] or ""}
              for r in returned]
    next_since = f"{returned[-1]['ts']}|{returned[-1]['rowid']}" if returned else (since or "")
    return {"events": events, "next_since": next_since, "has_more": len(rows) > limit}


def aggregate_activity(conn: sqlite3.Connection, username: str, days: int = 30) -> list:
    sql = ("SELECT ts, endpoint, caller, operator FROM telemetry "
           "WHERE user=? AND level='request'")
    params = [username]
    c = _cutoff_iso(days)
    if c:
        sql += " AND ts >= ?"
        params.append(c)
    sql += " ORDER BY ts DESC"
    return [{"ts": r["ts"], "endpoint": r["endpoint"], "caller": r["caller"],
             "operator": r["operator"]} for r in conn.execute(sql, params).fetchall()]
