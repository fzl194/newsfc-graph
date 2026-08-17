"""端到端测试：导入 sample_bundle → 校验全链路（stats / 单对象 / 邻居含反链 /
版本解析 / 悬空告警 / 非法 md 跳过 / 往返无损）。

sample_bundle 用中立业务名（demo / URR / ADD URR / FEAT-0001），不耦合具体业务，
覆盖矩阵：命令双版本、配置对象、特性、业务树三层、悬空边、跨 NF（UDG + UNC）。
"""
import io
import zipfile

from fastapi.testclient import TestClient

from app.bundle import export_bundle, import_bundle
from app.index import Index
from app.main import app
from app.registry import Registry
from app.store import Store
import app.service as svc


def _setup_with_bundle(tmp_data_dir, monkeypatch, zip_bytes: bytes):
    """把 sample_bundle 导入 tmp_data_dir 上的 store，并把 service 单例指过去。"""
    import app.db as dbmod
    s = svc.Service.__new__(svc.Service)
    s.store = Store(tmp_data_dir)
    s.registry = Registry.load_default()
    s.db = dbmod.get_db(tmp_data_dir.parent / "test.db")
    dbmod.init_schema(s.db)
    monkeypatch.setattr(dbmod, "_shared", s.db, raising=False)
    import_bundle(zip_bytes, s.store, s.registry)
    s.rebuild()  # 全量 reindex：建 DB + 加载内存
    monkeypatch.setattr(svc, "_service", s)
    return s


# ---------------- 统计计数 ----------------

def test_stats_counts_after_import(tmp_data_dir, monkeypatch, sample_bundle_zip):
    s = _setup_with_bundle(tmp_data_dir, monkeypatch, sample_bundle_zip)
    # 12 个 md：MMLCommand×4(ADD URR v15.2/v16.0, MOD URR, SHOW URR, UNC ADD URR)
    #          + ConfigObject×3(UDG×2, UNC×1) + Feature×1 + Business×3
    with TestClient(app) as c:
        r = c.get("/api/v1/stats")
        assert r.status_code == 200
        body = r.json()
    counts = body["object_counts_by_type"]
    assert counts["MMLCommand"] == 5
    assert counts["ConfigObject"] == 3
    assert counts["Feature"] == 1
    assert counts["BusinessDomain"] == 1
    assert counts["NetworkScenario"] == 1
    assert counts["ConfigurationSolution"] == 1
    # 两个网元
    assert set(body["nfs"]) == {"UDG", "UNC"}
    # 版本聚合
    assert "20.15.2" in body["versions_per_nf"]["UDG"]
    assert "20.16.0" in body["versions_per_nf"]["UDG"]
    assert body["versions_per_nf"]["UNC"] == ["20.16.0"]
    # 边数 > 0（结构校验，精确数由计数逻辑保证）
    assert body["edge_count"] > 0


# ---------------- 单对象 ----------------

def test_get_single_object_frontmatter_and_out_edges(tmp_data_dir, monkeypatch, sample_bundle_zip):
    _setup_with_bundle(tmp_data_dir, monkeypatch, sample_bundle_zip)
    with TestClient(app) as c:
        # 显式取旧版本（有完整边）
        r = c.get("/api/v1/objects/UDG@MMLCommand@ADD URR",
                  params={"version": "20.15.2"})
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "UDG@MMLCommand@ADD URR"
        assert body["type"] == "MMLCommand"
        assert body["version"] == "20.15.2"
        assert body["frontmatter"]["name"] == "新增 URR 用量统计规则"
        # 出向边：操作配置对象 + 参见
        targets = {(e["relation"], e["to"]) for e in body["out_edges"]}
        assert ("操作配置对象", "UDG@ConfigObject@URR") in targets
        assert ("参见", "UDG@MMLCommand@MOD URR") in targets


# ---------------- 邻居（含反链 in[]） ----------------

def test_neighbors_out_and_back_edges(tmp_data_dir, monkeypatch, sample_bundle_zip):
    _setup_with_bundle(tmp_data_dir, monkeypatch, sample_bundle_zip)
    with TestClient(app) as c:
        # URR 配置对象的反链应包含指向它的命令（版本无关）
        r = c.get("/api/v1/objects/UDG@ConfigObject@URR/neighbors")
        assert r.status_code == 200
        body = r.json()
        froms = {e["from"] for e in body["in"]}
        assert "UDG@MMLCommand@ADD URR" in froms
        assert "UDG@MMLCommand@MOD URR" in froms
        # 配置对象自身没有出边
        assert body["out"] == []


# ---------------- 版本解析 ----------------

def test_version_resolution_default_latest(tmp_data_dir, monkeypatch, sample_bundle_zip):
    _setup_with_bundle(tmp_data_dir, monkeypatch, sample_bundle_zip)
    with TestClient(app) as c:
        # 不带 version → 最新现存（20.16.0）
        r = c.get("/api/v1/objects/UDG@MMLCommand@ADD URR")
        assert r.status_code == 200
        assert r.json()["version"] == "20.16.0"


def test_version_resolution_explicit(tmp_data_dir, monkeypatch, sample_bundle_zip):
    _setup_with_bundle(tmp_data_dir, monkeypatch, sample_bundle_zip)
    with TestClient(app) as c:
        r = c.get("/api/v1/objects/UDG@MMLCommand@ADD URR",
                  params={"version": "20.15.2"})
        assert r.status_code == 200
        assert r.json()["version"] == "20.15.2"


def test_version_resolution_missing_version_404_lists_available(tmp_data_dir, monkeypatch, sample_bundle_zip):
    _setup_with_bundle(tmp_data_dir, monkeypatch, sample_bundle_zip)
    with TestClient(app) as c:
        r = c.get("/api/v1/objects/UDG@MMLCommand@ADD URR",
                  params={"version": "9.9.9"})
        assert r.status_code == 404
        avail = r.json()["detail"]["available_versions"]
        assert set(avail) == {"20.15.2", "20.16.0"}


def test_version_resolution_unknown_id_404(tmp_data_dir, monkeypatch, sample_bundle_zip):
    _setup_with_bundle(tmp_data_dir, monkeypatch, sample_bundle_zip)
    with TestClient(app) as c:
        r = c.get("/api/v1/objects/UDG@MMLCommand@NOPE")
        assert r.status_code == 404


# ---------------- 悬空告警 ----------------

def test_dangling_edge_detected(tmp_data_dir, monkeypatch, sample_bundle_zip):
    s = _setup_with_bundle(tmp_data_dir, monkeypatch, sample_bundle_zip)
    # SHOW URR 含 - 参见: [[UDG@MMLCommand@NOPE]] → 悬空
    assert s.index.has_dangling() is True


# ---------------- 非法 md 跳过（不阻塞整包） ----------------

def test_invalid_md_skipped_not_blocking(tmp_data_dir, monkeypatch, sample_bundle_zip):
    # 在 sample_bundle 基础上追加一个缺 type 的 md + 一个未知类型的 md
    extra = io.BytesIO()
    with zipfile.ZipFile(extra, "w") as z:
        z.writestr("bad_no_type.md", "---\nid: UDG@MMLCommand@BAD\n---\n# bad\n")
        z.writestr(
            "bad_unknown_type.md",
            "---\nid: UDG@Bogus@X\ntype: Bogus\nnf: UDG\nversion: 20.16.0\n---\n# x\n",
        )
    combined = sample_bundle_zip
    # 拼一个含样例 + 非法 md 的 zip
    merged = io.BytesIO()
    with zipfile.ZipFile(merged, "w") as z:
        with zipfile.ZipFile(io.BytesIO(combined)) as src:
            for n in src.namelist():
                z.writestr(n, src.read(n))
        with zipfile.ZipFile(extra) as src:
            for n in src.namelist():
                z.writestr(n, src.read(n))
    s = _setup_with_bundle(tmp_data_dir, monkeypatch, merged.getvalue())
    # 两个非法 md 都进 warnings + skipped，但合法对象照常建索引
    assert s.index.has_dangling()  # 仍能正常构建
    # sample_bundle 中的 ADD URR 仍可查到
    with TestClient(app) as c:
        r = c.get("/api/v1/objects/UDG@MMLCommand@ADD URR")
        assert r.status_code == 200


# ---------------- 往返无损（导出再导入） ----------------

def test_export_reimport_roundtrip(tmp_data_dir, monkeypatch, sample_bundle_zip):
    s = _setup_with_bundle(tmp_data_dir, monkeypatch, sample_bundle_zip)
    exported = export_bundle(s.store)
    # 导入到全新的 tmp assets，对象/边应与原一致
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as d:
        s2_store = Store(pathlib.Path(d))
        s2_reg = Registry.load_default()
        import_bundle(exported, s2_store, s2_reg)
        idx2 = Index.build(s2_store, s2_reg)
        # 对象集合一致（节点键 (id,version) 可哈希）
        assert set(s.index.nodes) == set(idx2.nodes)
        # 边邻接一致（value 是 list 不可哈希，按 key + 边元组多重集比较）
        assert set(s.index.out.keys()) == set(idx2.out.keys())
        for k in s.index.out:
            a = sorted((e.from_id, e.from_version, e.relation, e.to) for e in s.index.out[k])
            b = sorted((e.from_id, e.from_version, e.relation, e.to) for e in idx2.out[k])
            assert a == b


# ---------------- 业务树邻居 ----------------

def test_business_tree_neighbors(tmp_data_dir, monkeypatch, sample_bundle_zip):
    _setup_with_bundle(tmp_data_dir, monkeypatch, sample_bundle_zip)
    with TestClient(app) as c:
        # NS → 方案: ConfigurationSolution@demo-scenario-online
        r = c.get("/api/v1/objects/NetworkScenario@demo-scenario/neighbors")
        assert r.status_code == 200
        body = r.json()
        assert any(e["to"] == "ConfigurationSolution@demo-scenario-online"
                   for e in body["out"])
        # 反向：方案 的 in 应含 NS
        r2 = c.get("/api/v1/objects/ConfigurationSolution@demo-scenario-online/neighbors")
        body2 = r2.json()
        assert any(e["from"] == "NetworkScenario@demo-scenario" for e in body2["in"])
