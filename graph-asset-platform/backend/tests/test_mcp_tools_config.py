"""MCP 工具配置测试（admin GET/PATCH /mcp-tools + 动态生效，2026-08-25）。

覆盖：权限（401/403/admin）、禁用语义（tools/list 隐藏 + 直连调用中文报错——
决策「隐藏+拦截」）、描述完全替换与恢复默认、总体说明（instructions）覆盖与
恢复、重启后配置恢复（lifespan 启动应用）。
"""
import io
import zipfile

import app.db as dbmod
import app.service as svc
from app.registry import Registry
from app.store import Store

ACC = {"Accept": "application/json, text/event-stream"}

CMD = """---
id: UDG@MMLCommand@ADD URR
type: MMLCommand
name: ADD URR
version: 20.15.2
---

在线计费的使用量上报规则配置命令。
"""

ALL_TOOLS = {"get_domains", "get_md", "search_objects", "search_md", "get_object"}


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
    add_user({"username": "web1", "key": "gap_web", "can_frontend": True})
    return s


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _get_cfg(c, key="gap_admin"):
    r = c.get("/api/v1/mcp-tools", headers={"X-API-Key": key})
    return r


def _patch_cfg(c, body, key="gap_admin"):
    return c.patch("/api/v1/mcp-tools", headers={"X-API-Key": key}, json=body)


def _tools_list(c, key="gap_admin"):
    r = c.post("/mcp", headers={"X-API-Key": key, **ACC},
               json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 200, r.text
    return r.json()["result"]["tools"]


def _init(c, key="gap_admin"):
    r = c.post("/mcp", headers={"X-API-Key": key, **ACC},
               json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                "clientInfo": {"name": "t", "version": "0"}}})
    assert r.status_code == 200, r.text
    return r.json()["result"]


def _call(c, name, arguments, sid=1):
    r = c.post("/mcp", headers={"X-API-Key": "gap_admin", **ACC},
               json={"jsonrpc": "2.0", "id": sid, "method": "tools/call",
                     "params": {"name": name, "arguments": arguments}})
    assert r.status_code == 200, r.text
    return r.json()["result"]


_CTX = {"AGENT_USERNAME": "00234567", "AGENT_SESSION_ID": "sess-1"}


# ---------------- 权限 ----------------

def test_get_config_permissions(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    with _client() as c:
        # 无 KEY → 401（中间件）
        assert _get_cfg(c, key="").status_code == 401
        # 无 frontend → 403（中间件）
        assert _get_cfg(c, key="gap_assets_only").status_code == 403
        # frontend 非 admin → 403（端点二次校验）
        r = _get_cfg(c, key="gap_web")
        assert r.status_code == 403
        assert "admin" in r.json()["detail"]
        # admin → 200：5 工具全启用 + 默认描述/说明齐全
        r = _get_cfg(c)
        assert r.status_code == 200
        body = r.json()
        assert {t["name"] for t in body["tools"]} == ALL_TOOLS
        assert all(t["enabled"] for t in body["tools"])
        assert all(t["description"] == "" for t in body["tools"])
        assert all(t["default_description"] for t in body["tools"])
        assert body["instructions"] == ""
        assert "三层电信图谱" in body["default_instructions"]


# ---------------- 禁用：隐藏 + 拦截 ----------------

def test_disable_hides_from_list_and_blocks_call(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/a.md": CMD})
    with _client() as c:
        r = _patch_cfg(c, {"tools": [{"name": "search_md", "enabled": False}]})
        assert r.status_code == 200
        # 保存后返回全量：search_md disabled，其余不变
        by = {t["name"]: t for t in r.json()["tools"]}
        assert by["search_md"]["enabled"] is False
        assert by["get_md"]["enabled"] is True
        # tools/list 隐藏（Agent 看不到）
        names = {t["name"] for t in _tools_list(c)}
        assert names == ALL_TOOLS - {"search_md"}
        # 直连调用 → isError + 中文禁用提示（兜底，防绕过）
        res = _call(c, "search_md", {**_CTX, "q": "计费"})
        assert res["isError"] is True
        assert "已被管理员禁用" in res["content"][0]["text"]
        # 其余工具照常
        res2 = _call(c, "get_md", {**_CTX, "ids": ["UDG@MMLCommand@ADD URR"]})
        assert res2["isError"] is False
        assert "在线计费" in res2["content"][0]["text"]
        # 重新启用 → 恢复
        _patch_cfg(c, {"tools": [{"name": "search_md", "enabled": True}]})
        assert {t["name"] for t in _tools_list(c)} == ALL_TOOLS


# ---------------- 描述：完全替换 + 恢复默认 ----------------

def test_description_override_and_reset(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    with _client() as c:
        _patch_cfg(c, {"tools": [{"name": "get_md", "enabled": True,
                                  "description": "定制描述：专用于计费场景查询"}]})
        t = next(t for t in _tools_list(c) if t["name"] == "get_md")
        assert t["description"] == "定制描述：专用于计费场景查询"
        # 清空 → 恢复 docstring 默认
        _patch_cfg(c, {"tools": [{"name": "get_md", "enabled": True, "description": ""}]})
        t2 = next(t for t in _tools_list(c) if t["name"] == "get_md")
        body = _get_cfg(c).json()
        default = next(t for t in body["tools"] if t["name"] == "get_md")["default_description"]
        assert t2["description"] == default
        assert "批量获取" in t2["description"]


# ---------------- 总体说明：覆盖 + 恢复 ----------------

def test_instructions_override_and_reset(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    with _client() as c:
        assert _init(c)["instructions"] != "定制总体说明ABC"
        _patch_cfg(c, {"instructions": "定制总体说明ABC"})
        assert _init(c)["instructions"] == "定制总体说明ABC"
        # 清空 → 恢复默认（保存即生效，无需重启）
        _patch_cfg(c, {"instructions": ""})
        assert _init(c)["instructions"] != "定制总体说明ABC"
        assert "三层电信图谱" in _init(c)["instructions"]


def test_instructions_survive_restart(tmp_data_dir, monkeypatch):
    """重启语义：lifespan 启动时从 DB 恢复说明覆盖（enabled/description 每请求读
    DB 天然恢复）。新 TestClient 上下文 = 完整 lifespan 启停。"""
    _setup(tmp_data_dir, monkeypatch)
    with _client() as c:
        _patch_cfg(c, {"instructions": "重启后仍生效的说明"})
        _patch_cfg(c, {"tools": [{"name": "search_objects", "enabled": False}]})
    with _client() as c:
        assert _init(c)["instructions"] == "重启后仍生效的说明"
        assert "search_objects" not in {t["name"] for t in _tools_list(c)}


# ---------------- 入参校验 ----------------

def test_whitespace_only_values_reset_to_default(tmp_data_dir, monkeypatch):
    """纯空白描述/说明去空白后视同清空 → 回默认（审查修正）。"""
    _setup(tmp_data_dir, monkeypatch)
    with _client() as c:
        r = _patch_cfg(c, {"tools": [{"name": "get_md", "description": "   "}],
                           "instructions": "   "})
        assert r.status_code == 200
        by = {t["name"]: t for t in r.json()["tools"]}
        assert by["get_md"]["description"] == ""   # 已按默认存回
        t = next(t for t in _tools_list(c) if t["name"] == "get_md")
        assert "批量获取" in t["description"]       # 生效层面也是默认
        assert "三层电信图谱" in _init(c)["instructions"]


def test_patch_unknown_tool_rejected(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch)
    with _client() as c:
        r = _patch_cfg(c, {"tools": [{"name": "no_such_tool", "enabled": True}]})
        assert r.status_code == 400
        assert "no_such_tool" in r.json()["detail"]
        # 无效请求不落库
        assert {t["name"] for t in _tools_list(c)} == ALL_TOOLS
