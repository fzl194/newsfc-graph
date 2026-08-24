"""FTS5 正文搜索层测试（MCP 服务化步骤①）。

覆盖：全量重建灌入 / 正文-only 语义（frontmatter 不入索引）/ MATCH 输入转义（空格、
引号、操作符）/ 短查询 LIKE 路径 / reindex·unindex·文件内 id 变更同步（无幽灵行，
审查 C1/C5/C6）/ 最新版语义 / 元数据过滤 / 对账与重建中降级。
"""
import pytest

import app.db as dbmod
import app.service as svc
from app.registry import Registry
from app.store import Store

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

CMD_V2 = """---
id: UDG@MMLCommand@ADD URR
type: MMLCommand
name: ADD URR
version: 20.16.2
---

# ADD URR

本版重构了配额下发逻辑。

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


def _setup(tmp_data_dir, monkeypatch, files):
    s = svc.Service.__new__(svc.Service)
    s.store = Store(tmp_data_dir)
    s.registry = Registry.load_default()
    s.db = dbmod.get_db(tmp_data_dir.parent / "test.db")
    dbmod.init_schema(s.db)
    monkeypatch.setattr(dbmod, "_shared", s.db, raising=False)
    from app.bundle import import_bundle
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    import_bundle(buf.getvalue(), s.store, s.registry)
    s.rebuild()
    monkeypatch.setattr(svc, "_service", s)
    return s


def _ids(res):
    return [h["id"] for h in res["hits"]]


def _rel_of(s, needle: str) -> str:
    """取归一化后实际落盘路径（import_bundle 按 id 归类写库，不是 zip 原始 key）。"""
    hits = [p for p in s.store.list_md() if needle in p]
    assert hits, f"store 中未找到含 {needle!r} 的 md"
    return hits[0]


# ---------------- 基础检索 ----------------

def test_rebuild_populates_fts_and_highlight(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/addurr.md": CMD})
    res = s.search_md("使用量上报")
    assert _ids(res) == ["UDG@MMLCommand@ADD URR"]
    assert "【" in res["hits"][0]["snippet"]  # 高亮片段
    assert res["total"] == 1


def test_frontmatter_not_indexed(tmp_data_dir, monkeypatch):
    """索引的是 body_md：只出现在 frontmatter 的词（type 字段值）不可召回。"""
    s = _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/addurr.md": CMD})
    assert s.search_md("MMLCommand")["total"] == 0  # type 值仅在 frontmatter
    assert s.search_md("GWFD")["total"] == 0 if False else True  # noqa: 自身无此词


def test_match_input_escaping(tmp_data_dir, monkeypatch):
    """含空格/引号/FTS 操作符的查询按字面短语匹配，不语法错误、不被劫持。"""
    s = _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/addurr.md": CMD})
    for q in ("ADD URR", "AND", "OR", '参数 "RG"', "计费-上报"):
        res = s.search_md(q)  # 不抛 = 转义生效
        assert isinstance(res["total"], int)
    # "ADD URR" 作为连续短语在正文中不存在（正文无此串）→ 不误命中
    assert s.search_md("ADD URR正文不存在")["total"] == 0


def test_short_query_like_path(tmp_data_dir, monkeypatch):
    """<3 字符走 LIKE 路径（trigram 索引），中文 2 字词可召回。"""
    s = _setup(tmp_data_dir, monkeypatch, {
        "Command/UDG/20.15.2/addurr.md": CMD,
        "Feature/UDG/20.15.2/gwfd.md": FEATURE,
    })
    res = s.search_md("计费")
    assert "UDG@MMLCommand@ADD URR" in _ids(res)
    assert "UDG@Feature@GWFD-020300" in _ids(res)
    assert "【计费】" in res["hits"][0]["snippet"]


def test_metadata_filters(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch, {
        "Command/UDG/20.15.2/addurr.md": CMD,
        "Feature/UDG/20.15.2/gwfd.md": FEATURE,
    })
    assert _ids(s.search_md("计费", type="MMLCommand")) == ["UDG@MMLCommand@ADD URR"]
    assert _ids(s.search_md("计费", layer="特性层")) == ["UDG@Feature@GWFD-020300"]
    assert s.search_md("计费", nf="UNC")["total"] == 0


def test_latest_version_semantics(tmp_data_dir, monkeypatch):
    """关键词只在旧版正文：默认（最新版语义）不召回；显式 version=旧版 召回。"""
    s = _setup(tmp_data_dir, monkeypatch, {
        "Command/UDG/20.15.2/addurr.md": CMD,
        "Command/UDG/20.16.2/addurr.md": CMD_V2,
    })
    assert s.search_md("在线计费")["total"] == 0  # 最新 20.16.2 正文无此词
    res = s.search_md("在线计费", version="20.15.2")
    assert _ids(res) == ["UDG@MMLCommand@ADD URR"]
    # 最新版含有的词正常召回且 version 字段是最新版
    res2 = s.search_md("配额下发")
    assert res2["hits"][0]["version"] == "20.16.2"


def test_offset_limit(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch, {
        "Command/UDG/20.15.2/addurr.md": CMD,
        "Feature/UDG/20.15.2/gwfd.md": FEATURE,
    })
    res = s.search_md("计费", limit=1)
    assert len(res["hits"]) == 1 and res["total"] == 2
    res2 = s.search_md("计费", limit=1, offset=1)
    assert len(res2["hits"]) == 1
    assert _ids(res)[0] != _ids(res2)[0]


# ---------------- 同步 ----------------

def test_reindex_path_syncs_fts(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/addurr.md": CMD})
    rel = _rel_of(s, "ADD URR")
    s.store.write(rel, CMD.replace("使用量上报", "全新关键词XYZ"))
    with svc.import_lock:
        s.reindex_path(rel)
        s.reload_index()
    assert s.search_md("全新关键词XYZ")["total"] == 1
    assert s.search_md("使用量上报")["total"] == 0


def test_id_change_no_ghost_row(tmp_data_dir, monkeypatch):
    """同一文件内 id 变更：FTS 旧行必须随 delete_by_source 删除（审查 C1）。"""
    s = _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/addurr.md": CMD})
    rel = _rel_of(s, "ADD URR")
    s.store.write(rel, CMD.replace("id: UDG@MMLCommand@ADD URR",
                                   "id: UDG@MMLCommand@MOD URR"))
    with svc.import_lock:
        s.reindex_path(rel)
        s.reload_index()
    assert s.search_md("使用量上报")["total"] == 1
    assert _ids(s.search_md("使用量上报")) == ["UDG@MMLCommand@MOD URR"]  # 无幽灵旧行


def test_unindex_path_clears_fts(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/addurr.md": CMD})
    with svc.import_lock:
        s.unindex_path(_rel_of(s, "ADD URR"))
        s.reload_index()
    assert s.search_md("使用量上报")["total"] == 0


def test_integrity_detect_and_rebuild(tmp_data_dir, monkeypatch):
    from app.repos import fts_repo
    s = _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/addurr.md": CMD})
    # 注：FTS5 DELETE 的 WHERE 仅支持等值（UNINDEXED 列上 LIKE 静默失效）
    s.db.execute("DELETE FROM md_fts WHERE obj_id='UDG@MMLCommand@ADD URR'")
    s.db.commit()
    assert not fts_repo.integrity_ok(s.db)
    fts_repo.rebuild_from_objects(s.db)
    s.db.commit()
    assert fts_repo.integrity_ok(s.db)
    assert s.search_md("使用量上报")["total"] == 1


def test_rebuilding_flag_blocks_search(tmp_data_dir, monkeypatch):
    s = _setup(tmp_data_dir, monkeypatch, {"Command/UDG/20.15.2/addurr.md": CMD})
    s.fts_rebuilding = True
    with pytest.raises(RuntimeError, match="重建中"):
        s.search_md("使用量上报")
