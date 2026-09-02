"""统计页总览配置（stats_overview.json：手动维护 + 管理员页编辑）测试。"""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_SAMPLE = {
    "description": "三层图谱建设进展总览（手动维护）。",
    "updated_at": "2026-09-03",
    "cards": [
        {"title": "命令图谱", "accent": "#4f46e5", "metrics": [
            {"label": "知识条数", "value": 126880},
            {"label": "覆盖率", "value": "81.8%", "progress": 81.8},
        ]},
        {"title": "特性图谱", "metrics": [
            {"label": "覆盖特性编号", "value": "1,139", "progress": 60.0},
        ]},
        {"title": "业务图谱", "metrics": []},
    ],
}


def test_overview_missing(tmp_data_dir):
    d = client.get("/api/v1/stats/overview")
    assert d.status_code == 200
    assert d.json() == {"available": False, "config": None}


def test_overview_file_loaded(tmp_data_dir):
    (tmp_data_dir.parent / "stats_overview.json").write_text(
        json.dumps(_SAMPLE, ensure_ascii=False), encoding="utf-8")
    d = client.get("/api/v1/stats/overview")
    assert d.json()["available"] is True
    cfg = d.json()["config"]
    assert cfg["cards"][0]["title"] == "命令图谱"
    assert cfg["cards"][0]["metrics"][1]["progress"] == 81.8
    assert cfg["cards"][2]["metrics"] == []


def test_overview_invalid_file(tmp_data_dir):
    (tmp_data_dir.parent / "stats_overview.json").write_text(
        "{bad json", encoding="utf-8")
    d = client.get("/api/v1/stats/overview")
    assert d.json()["available"] is False
    assert "无效" in d.json()["error"]


def test_overview_save_admin_and_validate(tmp_data_dir, monkeypatch):
    # 非 admin 403
    from app.middleware import auth as auth_mod
    monkeypatch.setattr(auth_mod, "authenticate", lambda key: {
        "username": "u", "can_frontend": True})
    r = client.put("/api/v1/stats/overview", json=_SAMPLE)
    assert r.status_code == 403
    # admin 保存：非法结构 400
    monkeypatch.setattr(auth_mod, "authenticate", lambda key: {
        "username": "admin", "is_admin": True})
    bad = client.put("/api/v1/stats/overview", json={"cards": [{"title": ""}]})
    assert bad.status_code == 400
    bad2 = client.put("/api/v1/stats/overview", json={
        "cards": [{"title": "x", "metrics": [{"label": "a", "value": 1, "progress": 120}]}]})
    assert bad2.status_code == 400
    # 合法保存：回读一致 + 盘上文件规整（未知键被剔除、updated_by 记录）
    ok = client.put("/api/v1/stats/overview", json={
        **_SAMPLE, "junk": "unknown-key"})
    assert ok.status_code == 200
    assert ok.json()["config"]["updated_by"] == "admin"
    assert "junk" not in ok.json()["config"]
    loaded = client.get("/api/v1/stats/overview").json()
    assert loaded["available"] is True
    assert len(loaded["config"]["cards"]) == 3
