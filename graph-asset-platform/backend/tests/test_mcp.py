"""MCP 服务测试（Streamable HTTP /mcp，stateless + json_response）。

覆盖：鉴权（401/403）、tools/list、get_domains / get_md（部分失败容错 + 双护栏）/
search_objects / search_md / get_object、三层打点（request/tool/object +
operator/session_id 上下文参数）与统计口径（caller IN ('skill','mcp')）。

HTTP 直测（TestClient + JSON-RPC）：真实客户端需带 Accept: application/json。
"""
import io
import json
import zipfile

import app.db as dbmod
import app.service as svc
from app.index import Index
from app.registry import Registry
from app.store import Store

ACC = {"Accept": "application/json, text/event-stream"}

CMD = """---
id: UDG@MMLCommand@ADD URR
type: MMLCommand
name: ADD URR
version: 20.15.2
---

# ADD URR

在线计费的使用量上报规则配置命令。参数 RG 表示计费组。

## 边

- 参见 [[UDG@MMLCommand@LST URR]]
"""

FEATURE = """---
id: UDG@Feature@GWFD-020300
type: Feature
name: 在线计费特性
version: 20.15.2
---

特性正文：支持在线计费的配额管理与用量上报。
"""

DOMAIN = """---
id: BusinessDomain@business-awareness
type: BusinessDomain
name: 业务感知
domain: business-awareness
---

业务域正文：流量识别与业务感知，覆盖计费与策略控制场景。
"""


def _setup(tmp_data_dir, monkeypatch, files=None):
    s = svc.Service.__new__(svc.Service)
    s.store = Store(tmp_data_dir)
    s.registry = Registry.load_default()
    s.db = dbmod.get_db(tmp_data_dir.parent / "test.db")
    dbmod.init_schema(s.db)
    monkeypatch.setattr(dbmod, "_shared", s.db, raising=False)
    from app.bundle import import_bundle
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in (files or {}).items():
            z.writestr(name, content)
    import_bundle(buf.getvalue(), s.store, s.registry)
    s.rebuild()
    s.fts_rebuilding = False
    monkeypatch.setattr(svc, "_service", s)
    from app.users.store import add_user
    add_user({"username": "admin", "key": "gap_admin", "can_frontend": True,
              "can_skill": True, "is_admin": True})
    add_user({"username": "ao", "key": "gap_assets_only", "can_assets": True})
    return s


def _client():
    from app.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _call(c, name, arguments, key="gap_admin", sid=1):
    r = c.post("/mcp", headers={"X-API-Key": key, **ACC},
               json={"jsonrpc": "2.0", "id": sid, "method": "tools/call",
                     "params": {"name": name, "arguments": arguments}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("result", {}).get("isError") is False, body
    return json.loads(body["result"]["content"][0]["text"])


def _call_err(c, name, arguments, key="gap_admin"):
    r = c.post("/mcp", headers={"X-API-Key": key, **ACC},
               json={"jsonrpc": "2.0", "id": 99, "method": "tools/call",
                     "params": {"name": name, "arguments": arguments}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["result"]["isError"] is True, body
    return body["result"]["content"][0]["text"]


_CTX = {"AGENT_USERNAME": "00234567", "AGENT_SESSION_ID": "sess-1"}


# ---------------- 鉴权 ----------------

def test_mcp_401_without_key(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    with _client() as c:
        r = c.post("/mcp", headers=ACC, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert r.status_code == 401
        assert "detail" in r.json()  # 401 响应体可读（审查 A4）


def test_mcp_403_without_skill_perm(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    with _client() as c:
        r = c.post("/mcp", headers={"X-API-Key": "gap_assets_only", **ACC},
                   json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert r.status_code == 403


# ---------------- 协议 ----------------

def test_tools_list_returns_5_tools(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    with _client() as c:
        r = c.post("/mcp", headers={"X-API-Key": "gap_admin", **ACC},
                   json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert r.status_code == 200
        names = {t["name"] for t in r.json()["result"]["tools"]}
        assert names == {"get_domains", "get_md", "search_objects", "search_md", "get_object"}
        # 上下文参数必填（required）且 description 指向沙箱环境变量
        get_md = next(t for t in r.json()["result"]["tools"] if t["name"] == "get_md")
        assert "AGENT_USERNAME" in get_md["inputSchema"]["required"]
        assert "_AGENT_USERNAME" in get_md["inputSchema"]["properties"]["AGENT_USERNAME"]["description"]


# ---------------- 工具语义 ----------------

def test_get_domains_returns_md(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch, {"Business/business-awareness/x.md": DOMAIN})
    with _client() as c:
        out = _call(c, "get_domains", dict(_CTX))
    assert [d["id"] for d in out["domains"]] == ["BusinessDomain@business-awareness"]
    assert "业务感知" in out["domains"][0]["md"]
    from app.telemetry.recorder import flush as _tel_flush
    assert _tel_flush()  # 打点异步落库（v3 队列化）
    rows = [dict(r) for r in s.db.execute(
        "SELECT * FROM telemetry WHERE level='object'").fetchall()]
    assert len(rows) == 1
    assert rows[0]["endpoint"] == "mcp:get_domains"
    assert rows[0]["caller"] == "mcp"
    assert rows[0]["operator"] == "00234567"
    assert rows[0]["session_id"] == "sess-1"
    assert rows[0]["user"] == "admin"


def test_get_md_partial_failure_and_version(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/a.md": CMD})
    with _client() as c:
        out = _call(c, "get_md", {**_CTX, "ids": ["UDG@MMLCommand@ADD URR", "no@such@id"]})
    ok = out["UDG@MMLCommand@ADD URR"]
    assert ok["version"] == "20.15.2" and "在线计费" in ok["md"]
    assert out["no@such@id"]["error"] == "对象不存在"
    # version 全局不匹配但 id 存在 → 回带 available_versions（部分失败容错）
    with _client() as c:
        out2 = _call(c, "get_md", {**_CTX, "ids": ["UDG@MMLCommand@ADD URR"], "version": "9.9.9"})
    assert "available_versions" in out2["UDG@MMLCommand@ADD URR"]
    assert "20.15.2" in out2["UDG@MMLCommand@ADD URR"]["available_versions"]


def test_get_md_ids_cap(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/a.md": CMD})
    with _client() as c:
        msg = _call_err(c, "get_md", {**_CTX, "ids": [f"x@y@{i}" for i in range(101)]})
    assert "100" in msg


def test_get_md_byte_cap(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/a.md": CMD,
                                           "Feature/UDG/20.15.2/f.md": FEATURE})
    import app.mcp_server as ms
    monkeypatch.setattr(ms, "MAX_TOTAL_BYTES", 10)
    with _client() as c:
        msg = _call_err(c, "get_md", {**_CTX,
                                      "ids": ["UDG@MMLCommand@ADD URR", "UDG@Feature@GWFD-020300"]})
    assert "分批" in msg


def test_search_objects_over_http(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/a.md": CMD,
                                       "Feature/UDG/20.15.2/f.md": FEATURE})
    with _client() as c:
        out = _call(c, "search_objects", {**_CTX, "q": "urr", "type": "MMLCommand"})
    assert out["total"] == 1
    assert out["rows"][0]["id"] == "UDG@MMLCommand@ADD URR"


def test_search_md_over_http(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/a.md": CMD,
                                       "Feature/UDG/20.15.2/f.md": FEATURE})
    with _client() as c:
        out = _call(c, "search_md", {**_CTX, "q": "计费", "type": "MMLCommand"})
    assert out["total"] == 1
    hit = out["hits"][0]
    assert hit["id"] == "UDG@MMLCommand@ADD URR"
    assert "【" in hit["snippet"]


def test_get_object_over_http(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/a.md": CMD})
    with _client() as c:
        out = _call(c, "get_object", {**_CTX, "id": "UDG@MMLCommand@ADD URR"})
    assert out["type"] == "MMLCommand"
    assert out["versions"] == ["20.15.2"]
    assert isinstance(out["out_edges"], list)
    with _client() as c:
        msg = _call_err(c, "get_object", {**_CTX, "id": "no@such"})
    assert "不存在" in msg


# ---------------- 打点与统计口径 ----------------

def test_telemetry_three_levels_and_stats(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/a.md": CMD,
                                           "Business/business-awareness/x.md": DOMAIN})
    with _client() as c:
        _call(c, "get_md", {**_CTX, "ids": ["UDG@MMLCommand@ADD URR"]})
        _call(c, "search_md", {**_CTX, "q": "计费"}, sid=2)
    from app.telemetry.recorder import flush as _tel_flush
    assert _tel_flush()
    rows = [dict(r) for r in s.db.execute(
        "SELECT level, endpoint, caller, operator, session_id FROM telemetry ORDER BY rowid"
    ).fetchall()]
    levels = {(r["level"], r["endpoint"]) for r in rows}
    assert ("request", "/mcp") in levels                     # request 级
    assert ("tool", "mcp:get_md") in levels                  # tool 级（含 search 类可观测）
    assert ("tool", "mcp:search_md") in levels
    assert ("object", "mcp:get_md") in levels                # object 级（取用统计口径）
    mcp_rows = [r for r in rows if r["level"] == "object"]
    assert all(r["caller"] == "mcp" and r["operator"] == "00234567"
               and r["session_id"] == "sess-1" for r in mcp_rows)
    # 统计聚合：mcp 行进入口径 + by_session 计数
    from app.repos.telemetry_repo import aggregate_stats
    st = aggregate_stats(s.db)
    assert st["total"] >= 1
    assert st["by_session"] >= 1
    # skill 历史行与新 mcp 行同口径并存
    from app.telemetry.recorder import record
    record("/md", "X@1", "Feature", user="sk", caller="skill", level="object")
    assert _tel_flush()
    st2 = aggregate_stats(s.db)
    assert st2["total"] == st["total"] + 1


def test_tool_rows_record_params_and_result(tmp_data_dir, monkeypatch):
    """tool 级行记录入参（params）与出参摘要（result）——用户决策：输入输出都记。"""
    s = _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/a.md": CMD,
                                           "Feature/UDG/20.15.2/f.md": FEATURE})
    with _client() as c:
        _call(c, "get_md", {**_CTX, "ids": ["UDG@MMLCommand@ADD URR", "no@such@id"]})
        _call(c, "search_md", {**_CTX, "q": "计费"}, sid=2)
    from app.telemetry.recorder import flush as _tel_flush
    assert _tel_flush()
    tool_rows = [dict(r) for r in s.db.execute(
        "SELECT endpoint, params, result FROM telemetry WHERE level='tool' ORDER BY rowid"
    ).fetchall()]
    by_ep = {r["endpoint"]: (json.loads(r["params"]), json.loads(r["result"]))
             for r in tool_rows}
    p, r = by_ep["mcp:get_md"]
    assert p == {"ids": ["UDG@MMLCommand@ADD URR", "no@such@id"], "version": None}
    assert r["ok"] == 1 and r["failed"] == 1
    assert r["failed_ids"] == ["no@such@id"]
    assert r["bytes"] > 0
    p2, r2 = by_ep["mcp:search_md"]
    assert p2["q"] == "计费"
    assert r2["total"] == 2 and r2["returned"] == 2
    assert "UDG@MMLCommand@ADD URR" in r2["top_ids"]


def test_tool_row_records_error_result(tmp_data_dir, monkeypatch):
    """护栏触发（ids 超限）→ tool 行 result 记 error 摘要。"""
    s = _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/a.md": CMD})
    with _client() as c:
        _call_err(c, "get_md", {**_CTX, "ids": [f"x@y@{i}" for i in range(101)]})
    from app.telemetry.recorder import flush as _tel_flush
    assert _tel_flush()
    rows = [dict(r) for r in s.db.execute(
        "SELECT params, result FROM telemetry WHERE level='tool' AND endpoint='mcp:get_md'"
    ).fetchall()]
    assert rows
    assert "error" in json.loads(rows[0]["result"])
    assert len(json.loads(rows[0]["params"])["ids"]) == 101
