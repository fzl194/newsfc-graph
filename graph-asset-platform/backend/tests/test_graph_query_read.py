"""graph_query 共享读取核心单元测试（M1，2026-09-08 三工具重构）。

覆盖（需求 §6/§8/§15.5 部分）：
- extract_references：全文 [[ID]] 提取，去重保序；
- get_domains_core：最新版聚合、按 id 升序、references、version null；
- get_md_core：去重保序/trim、部分失败（OBJECT_NOT_FOUND / VERSION_NOT_FOUND）、
  versionless 对象 versions=[]、护栏（ids 1~100、响应 2MB 含边界）。
"""
import io
import json
import zipfile

import pytest

import app.db as dbmod
import app.service as svc
from app.index import Index
from app.registry import Registry
from app.store import Store

from app.graph_query import contracts as gq
from app.graph_query.read import extract_references, get_domains_core, get_md_core

CMD_V1 = """---
id: alpha@MMLCommand@ADD DEMO
type: MMLCommand
version: 20.15.2
name: add demo command
---

# ADD DEMO

正文提及 [[alpha@ConfigObject@DEMO_OBJ]] 与重复引用 [[alpha@ConfigObject@DEMO_OBJ]]。

## 边

- 操作配置对象: [[alpha@ConfigObject@DEMO_OBJ]]
"""

CMD_V2 = """---
id: alpha@MMLCommand@ADD DEMO
type: MMLCommand
version: 20.16.0
name: add demo command v2
---

# ADD DEMO v2（新版正文）
"""

CFG = """---
id: alpha@ConfigObject@DEMO_OBJ
type: ConfigObject
version: 20.15.2
---

# DEMO_OBJ
"""

DOMAIN_B = """---
id: BusinessDomain@billing
type: BusinessDomain
name: 计费
domain: billing
---

计费域正文，引用 [[NetworkScenario@charging]]。
"""

DOMAIN_A = """---
id: BusinessDomain@awareness
type: BusinessDomain
name: 业务感知
domain: awareness
---

业务感知域正文，引用 [[NetworkScenario@charging]] 与 [[BusinessDomain@billing]]。
"""


def _setup(tmp_data_dir, monkeypatch, files):
    s = svc.Service.__new__(svc.Service)
    s.store = Store(tmp_data_dir)
    s.registry = Registry.load_default()
    s.db = dbmod.get_db(tmp_data_dir.parent / "test.db")
    dbmod.init_schema(s.db)
    monkeypatch.setattr(dbmod, "_shared", s.db, raising=False)
    from app.bundle import import_bundle
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    import_bundle(buf.getvalue(), s.store, s.registry)
    s.rebuild()
    s.fts_rebuilding = False
    monkeypatch.setattr(svc, "_service", s)
    return s


ALL = {"a.md": CMD_V1, "v2.md": CMD_V2, "cfg.md": CFG,
       "db.md": DOMAIN_B, "da.md": DOMAIN_A}


# ---------------- extract_references ----------------

def test_extract_references_dedup_and_order():
    md = "见 [[B@X]] 与 [[A@Y]]；重复 [[B@X]]；空白 [[  ]]；嵌套内容 [[C@Z ]] 尾部。"
    assert extract_references(md) == ["B@X", "A@Y", "C@Z"]


def test_extract_references_empty_body():
    assert extract_references("") == []
    assert extract_references(None) == []


# ---------------- get_domains_core ----------------

def test_get_domains_core_sorted_latest_references(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, ALL)
    items = get_domains_core()
    # 按 id 升序（MCP/REST 共享排序）
    assert [d.id for d in items] == ["BusinessDomain@awareness", "BusinessDomain@billing"]
    a = items[0]
    assert a.type == "BusinessDomain"
    assert a.name == "业务感知"
    assert a.version is None  # 跨 NF 类 version null
    assert a.references == ["NetworkScenario@charging", "BusinessDomain@billing"]
    assert "业务感知" in a.md


# ---------------- get_md_core ----------------

def test_get_md_core_success_fields(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, ALL)
    result, summary = get_md_core(["alpha@MMLCommand@ADD DEMO"])
    item = result["alpha@MMLCommand@ADD DEMO"]
    assert item["ok"] is True
    assert item["id"] == "alpha@MMLCommand@ADD DEMO"
    assert item["type"] == "MMLCommand"
    assert item["name"] == "add demo command v2"  # 不传 version → 最新 20.16.0
    assert item["nf"] == "alpha"
    assert item["version"] == "20.16.0"
    assert item["versions"] == ["20.15.2", "20.16.0"]
    assert "ADD DEMO v2" in item["md"]
    assert item["references"] == []
    assert summary["ok"] == 1 and summary["failed"] == 0
    assert summary["bytes"] > 0


def test_get_md_core_explicit_old_version(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, ALL)
    result, _ = get_md_core(["alpha@MMLCommand@ADD DEMO"], version="20.15.2")
    item = result["alpha@MMLCommand@ADD DEMO"]
    assert item["version"] == "20.15.2"
    # references 从完整 raw_md 提取（含 ## 边段；同 ID 引用去重）
    assert item["references"] == ["alpha@ConfigObject@DEMO_OBJ"]


def test_get_md_core_object_not_found(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, ALL)
    result, summary = get_md_core(["nope@MMLCommand@X"])
    item = result["nope@MMLCommand@X"]
    assert item["ok"] is False
    assert item["error_code"] == gq.OBJECT_NOT_FOUND
    assert item["error"] == "对象不存在"
    assert item["available_versions"] == []
    assert summary["failed"] == 1 and summary["failed_ids"] == ["nope@MMLCommand@X"]


def test_get_md_core_version_not_found(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, ALL)
    result, _ = get_md_core(["alpha@MMLCommand@ADD DEMO"], version="19.0.0")
    item = result["alpha@MMLCommand@ADD DEMO"]
    assert item["ok"] is False
    assert item["error_code"] == gq.VERSION_NOT_FOUND
    assert item["error"].startswith("版本不存在")
    assert item["requested_version"] == "19.0.0"
    assert set(item["available_versions"]) == {"20.15.2", "20.16.0"}


def test_get_md_core_versionless_object_versions_empty(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, ALL)
    result, _ = get_md_core(["BusinessDomain@billing"])
    item = result["BusinessDomain@billing"]
    assert item["ok"] is True
    assert item["version"] is None
    assert item["versions"] == []  # 无版本对象不得返回 [null]
    assert item["domain"] == "billing"


def test_get_md_core_dedup_trim_order(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, ALL)
    result, _ = get_md_core([
        "  alpha@ConfigObject@DEMO_OBJ  ",  # trim 后规范 key
        "alpha@ConfigObject@DEMO_OBJ",      # 重复（trim 后）只保留首个位置
        "BusinessDomain@billing",
    ])
    assert list(result.keys()) == ["alpha@ConfigObject@DEMO_OBJ", "BusinessDomain@billing"]


def test_get_md_core_blank_id_rejected(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, ALL)
    with pytest.raises(gq.GraphQueryError) as ei:
        get_md_core(["   "])
    assert ei.value.error.code == gq.INVALID_ARGUMENT


def test_get_md_core_blank_version_rejected(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, ALL)
    with pytest.raises(gq.GraphQueryError) as ei:
        get_md_core(["alpha@ConfigObject@DEMO_OBJ"], version="   ")
    assert ei.value.error.code == gq.INVALID_ARGUMENT


def test_get_md_core_ids_cap(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, ALL)
    with pytest.raises(gq.GraphQueryError) as ei:
        get_md_core([f"x@y@{i}" for i in range(101)])
    assert ei.value.error.code == gq.INVALID_ARGUMENT
    assert "100" in ei.value.error.message


def test_get_md_core_empty_ids_rejected(tmp_data_dir, monkeypatch):
    _setup(tmp_data_dir, monkeypatch, ALL)
    with pytest.raises(gq.GraphQueryError) as ei:
        get_md_core([])
    assert ei.value.error.code == gq.INVALID_ARGUMENT


def test_get_md_core_byte_cap_boundaries(tmp_data_dir, monkeypatch):
    """2MB 护栏：恰好等于上限成功；多 1 byte 整单失败（RESULT_TOO_LARGE）。"""
    s = _setup(tmp_data_dir, monkeypatch, {"a.md": CMD_V1, "v2.md": CMD_V2, "cfg.md": CFG})
    result, _ = get_md_core(["alpha@MMLCommand@ADD DEMO"])
    exact_bytes = len(json.dumps(result, ensure_ascii=False,
                                 separators=(",", ":")).encode("utf-8"))
    monkeypatch.setattr(gq, "MAX_TOTAL_BYTES", exact_bytes)
    r2, summary2 = get_md_core(["alpha@MMLCommand@ADD DEMO"])
    assert r2["alpha@MMLCommand@ADD DEMO"]["ok"] is True
    monkeypatch.setattr(gq, "MAX_TOTAL_BYTES", exact_bytes - 1)
    with pytest.raises(gq.GraphQueryError) as ei:
        get_md_core(["alpha@MMLCommand@ADD DEMO"])
    assert ei.value.error.code == gq.RESULT_TOO_LARGE
    assert "分批" in ei.value.error.message
    assert ei.value.error.details["bytes"] == exact_bytes
    assert ei.value.error.details["limit"] == exact_bytes - 1
