"""两步流水线测试（2026-08-19 重构版）：解压留存 / 模式注册 / 定位候选 / 挖掘端点 /
任务持久化与互斥 / bundles 包管理。完整真实归档流程靠手工验收（见实施计划 §6）。
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline import bundles, runner as pl
from app.pipeline.modes import get_mode, list_modes
from app.store import Store

client = TestClient(app)


def _make_md_tree(base: Path) -> Path:
    """UDG 布局最小导出树（mml/feature/license 三目录齐）。"""
    root = base / "UDG_20.15.2" / "Prod_CH_20.15.2"
    (root / "OM参考" / "命令" / "UDG MML命令").mkdir(parents=True)
    (root / "特性部署" / "特性指南" / "UDG特性指南").mkdir(parents=True)
    (root / "特性部署" / "特性指南" / "UDG License描述").mkdir(parents=True)
    return base / "UDG_20.15.2"


# ---------- 命名白名单（D1） ----------

class TestNames:
    def test_valid(self):
        assert bundles.is_valid_name("UDG") and bundles.is_valid_name("20.15.2")
        assert bundles.is_valid_name("a-b_c")

    def test_invalid(self):
        for bad in ("", "../x", "a/b", "a\\b", "..", "a" * 40, ".x", "x y"):
            assert not bundles.is_valid_name(bad), bad


# ---------- bundles（包管理 + 原子替换 + 旧格式兼容 + 孤儿清扫） ----------

class TestBundles:
    @pytest.fixture(autouse=True)
    def _out(self, tmp_path, monkeypatch):
        import app.config as config
        out = tmp_path / "platform-data" / "output"
        out.mkdir(parents=True)
        monkeypatch.setattr(config, "OUTPUT_DIR", out)
        monkeypatch.setattr(config, "DATA_DIR", out.parent)
        self.out = out

    def test_list_legacy(self):
        d = self.out / "UDG_20.15.2"
        d.mkdir()
        (d / "a.md").write_text("x", encoding="utf-8")
        bs = bundles.list_bundles()
        assert len(bs) == 1
        assert bs[0]["legacy"] is True and bs[0]["status"] == "done"
        assert bs[0]["nf"] == "UDG" and bs[0]["version"] == "20.15.2"

    def test_atomic_replace_keeps_old_on_fail(self):
        formal = self.out / "UDG_20.15.2"
        formal.mkdir()
        (formal / "old.md").write_text("old", encoding="utf-8")
        tmp = self.out / ".tmp_UDG_20.15.2"
        tmp.mkdir()
        (tmp / "bundle.json").write_text(json.dumps({"nf": "UDG"}), encoding="utf-8")
        result = bundles.atomic_replace("UDG", "20.15.2", tmp)
        assert (result / "bundle.json").exists()
        # 旧包进回收站
        trash = self.out.parent / ".trash"
        assert trash.is_dir() and any(trash.iterdir())

    def test_sweep_orphan_tmp(self):
        (self.out / ".tmp_UDG_1.0").mkdir()
        (self.out.parent / ".pdoc_xx").mkdir()
        (self.out.parent / ".pdoc_up_y").write_bytes(b"x")
        n = bundles.sweep_orphan_tmp()
        assert n == 3
        assert not (self.out / ".tmp_UDG_1.0").exists()


# ---------- locate_candidates（推荐 + 候选；casefold；多候选/无候选） ----------

class TestLocateCandidates:
    MODE = get_mode("5gc")

    def test_udg_layout_recommended(self, tmp_path):
        root = _make_md_tree(tmp_path)
        loc = pl.locate_candidates(root, self.MODE, "UDG")
        assert loc["mml"]["recommended"].endswith("UDG MML命令")
        assert loc["mml"]["note"] == ""
        assert any(c.endswith("UDG MML命令") for c in loc["mml"]["candidates"])

    def test_casefold_nf(self, tmp_path):
        root = _make_md_tree(tmp_path)
        loc = pl.locate_candidates(root, self.MODE, "udg")  # 小写网元也能严格命中
        assert loc["mml"]["recommended"].endswith("UDG MML命令")

    def test_renamed_unique_loose(self, tmp_path):
        root = tmp_path / "pkg"
        (root / "云核心网MML命令").mkdir(parents=True)
        (root / "特性指南目录A").mkdir(parents=True)
        (root / "目录B License描述").mkdir(parents=True)
        loc = pl.locate_candidates(root, self.MODE, "UDG")
        assert loc["mml"]["recommended"] is not None and "非标准命名" in loc["mml"]["note"]

    def test_multi_candidates_no_recommend(self, tmp_path):
        root = tmp_path / "pkg"
        (root / "甲MML命令").mkdir(parents=True)
        (root / "乙MML命令").mkdir(parents=True)
        (root / "UDG特性指南").mkdir(parents=True)
        (root / "UDG License描述").mkdir(parents=True)
        loc = pl.locate_candidates(root, self.MODE, "UDG")
        assert loc["mml"]["recommended"] is None
        assert "人工选择" in loc["mml"]["note"]
        assert len(loc["mml"]["candidates"]) == 2

    def test_validate_selected_dirs_rejects_escape(self, tmp_path):
        root = _make_md_tree(tmp_path)
        with pytest.raises(ValueError, match="越界"):
            pl.validate_selected_dirs(root, {"mml": "../../etc"})
        ok = pl.validate_selected_dirs(
            root, {"mml": "Prod_CH_20.15.2/OM参考/命令/UDG MML命令"})
        assert ok["mml"].is_dir()


# ---------- expand_scope（范围×依赖强制，用户决策） ----------

class TestExpandScope:
    MODE = get_mode("5gc")

    def test_forces_missing_deps(self, tmp_data_dir, monkeypatch):
        import app.config as config
        monkeypatch.setattr(config, "ASSETS_DIR", tmp_data_dir)  # 无任何已建资产
        final, added = pl.expand_scope(["Feature"], self.MODE, "UDG", "20.15.2")
        assert final == ["Command", "License", "Feature"]  # 按模式序
        assert len(added) == 2

    def test_no_force_when_assets_exist(self, tmp_data_dir, monkeypatch):
        import app.config as config
        monkeypatch.setattr(config, "ASSETS_DIR", tmp_data_dir)
        for layer in ("Command", "License"):
            d = tmp_data_dir / layer / "UDG" / "20.15.2"
            d.mkdir(parents=True)
            (d / "x.md").write_text("x", encoding="utf-8")
        final, added = pl.expand_scope(["Feature"], self.MODE, "UDG", "20.15.2")
        assert final == ["Feature"] and added == []


# ---------- 端点：解压（步骤①） ----------

class TestExtractEndpoint:
    @pytest.fixture(autouse=True)
    def _env(self, tmp_data_dir, monkeypatch):
        import app.config as config
        monkeypatch.setattr(config, "ASSETS_DIR", tmp_data_dir)
        from app import jobs as jobs_mod
        jobs_mod._registry.clear()
        yield
        jobs_mod._registry.clear()

    def _post(self, nf="UDG", version="20.15.2", name="doc.hwics"):
        return client.post("/api/v1/import/product-doc",
                           data={"nf": nf, "version": version},
                           files={"file": (name, b"PK-zip")})

    def test_reject_bad_names(self):
        for nf, ver in (("../x", "1.0"), ("UDG", "a/b"), ("", "1.0")):
            r = self._post(nf=nf, version=ver)
            assert r.status_code in (400, 422), (nf, ver)  # 空值由 FastAPI 422 先拦

    def test_reject_bad_suffix(self):
        r = client.post("/api/v1/import/product-doc",
                        data={"nf": "UDG", "version": "20.15.2"},
                        files={"file": ("doc.exe", b"xx")})
        assert r.status_code == 400

    def test_creates_extract_job_with_stub(self, monkeypatch):
        import app.routers.productdoc as pd
        from app import jobs as jobs_mod
        seen = {}

        def stub(job_id, hwics_path, nf, version, uploaded_by=""):
            seen.update(nf=nf, by=uploaded_by)
            Path(hwics_path).unlink(missing_ok=True)
            jobs_mod.update_job(job_id, status="done", result={"md_count": 3})

        monkeypatch.setattr(pd, "run_extract", stub)
        r = self._post()
        assert r.status_code == 200
        jid = r.json()["job_id"]
        j = client.get(f"/api/v1/import/jobs/{jid}").json()
        assert j["kind"] == "product_doc_extract" and j["status"] == "done"

    def test_mutex_rejects_second(self, monkeypatch):
        from app import jobs as jobs_mod
        assert jobs_mod.acquire_mutex("product_doc_extract")
        try:
            r = self._post()
            assert r.status_code == 409
        finally:
            jobs_mod.release_mutex("product_doc_extract")


# ---------- 端点：挖掘（步骤②） ----------

class TestMineEndpoint:
    @pytest.fixture(autouse=True)
    def _env(self, tmp_path, tmp_data_dir, monkeypatch):
        import app.config as config
        out = tmp_path / "pd" / "output"
        monkeypatch.setattr(config, "OUTPUT_DIR", out)
        monkeypatch.setattr(config, "DATA_DIR", out.parent)
        monkeypatch.setattr(config, "ASSETS_DIR", tmp_data_dir)
        root = _make_md_tree(out)  # 一个已解压包（legacy 格式）
        self.root = root
        from app import jobs as jobs_mod
        jobs_mod._registry.clear()
        yield
        jobs_mod._registry.clear()

    def _mine(self, **over):
        body = {"nf": "UDG", "version": "20.15.2", "mode": "5gc",
                "dirs": {"mml": "Prod_CH_20.15.2/OM参考/命令/UDG MML命令",
                         "feature": "Prod_CH_20.15.2/特性部署/特性指南/UDG特性指南",
                         "license": "Prod_CH_20.15.2/特性部署/特性指南/UDG License描述"},
                "scope": ["Command", "ConfigObject", "License", "Feature"]}
        body.update(over)
        return client.post("/api/v1/import/mine", json=body)

    def test_bundle_missing_404(self):
        r = self._mine(nf="NOP")
        assert r.status_code == 404

    def test_invalid_scope_400(self):
        r = self._mine(scope=["Bogus"])
        assert r.status_code == 400

    def test_bad_mode_400(self):
        r = self._mine(mode="ims9")
        assert r.status_code == 400

    def test_creates_mine_job_with_dependency_notes(self, monkeypatch, tmp_data_dir):
        import app.routers.productdoc as pd
        from app import jobs as jobs_mod
        seen = {}

        def stub(job_id, nf, version, mode_id, dirs, scope, force):
            seen.update(scope=scope, dirs=dirs)
            jobs_mod.update_job(job_id, status="done", result={"layers": {}})

        monkeypatch.setattr(pd, "run_mine", stub)
        r = self._mine(scope=["Feature"])  # 依赖强制：Command/License 资产不存在
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == ["Command", "License", "Feature"]
        assert len(body["notes"]) == 2
        assert seen["scope"][0] == "Command"

    def test_mutex_rejects_second(self):
        from app import jobs as jobs_mod
        assert jobs_mod.acquire_mutex("product_doc_mine")
        try:
            r = self._mine()
            assert r.status_code == 409
        finally:
            jobs_mod.release_mutex("product_doc_mine")

    def test_modes_endpoint(self):
        r = client.get("/api/v1/import/modes")
        assert r.status_code == 200
        assert {"id": "5gc", "name": "5GC产品文档"} in r.json()

    def test_locate_endpoint(self):
        r = client.get("/api/v1/import/bundles/UDG/20.15.2/locate", params={"mode": "5gc"})
        assert r.status_code == 200
        loc = r.json()
        assert loc["mml"]["recommended"].endswith("UDG MML命令")
        assert loc["feature"]["recommended"].endswith("UDG特性指南")


# ---------- jobs 持久化 / 删除 / 清账（v3：child_pids + 互斥锁） ----------

class TestJobPersistence:
    @pytest.fixture(autouse=True)
    def _clean(self):
        from app import jobs as jobs_mod
        jobs_mod._registry.clear()
        yield
        jobs_mod._registry.clear()

    def test_delete_rejected_while_processing(self):
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc_mine", nf="UDG", version="20.15.2")
        assert client.delete(f"/api/v1/import/jobs/{j.job_id}").status_code == 400

    def test_delete_done_ok(self):
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc_mine", nf="UDG", version="20.15.2")
        jobs_mod.update_job(j.job_id, status="done")
        assert client.delete(f"/api/v1/import/jobs/{j.job_id}").status_code == 200
        assert client.get(f"/api/v1/import/jobs/{j.job_id}").status_code == 404

    def test_history_survives_restart(self):
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc_extract", nf="UDG", version="20.15.2")
        jobs_mod.update_job(j.job_id, status="done", child_pids=[123],
                            result={"md_count": 7})
        jobs_mod._registry.clear()  # 模拟重启（缓存丢失）
        got = jobs_mod.get_job(j.job_id)
        assert got.status == "done" and got.result["md_count"] == 7
        assert got.child_pids == [123]

    def test_sweep_marks_failed_and_clears_pids(self, monkeypatch):
        from app import jobs as jobs_mod
        monkeypatch.setattr(jobs_mod, "_kill_pid_tree", lambda pid: None)  # 不真杀
        j = jobs_mod.create_job(kind="product_doc_mine", nf="UDG", version="20.15.2")
        jobs_mod.update_job(j.job_id, child_pids=[4321])
        jobs_mod._registry.clear()
        n = jobs_mod.sweep_interrupted()
        assert n >= 1
        got = jobs_mod.get_job(j.job_id)
        assert got.status == "failed" and "重启" in got.error
        assert got.child_pids == []

    def test_mutex_acquire_release(self):
        from app import jobs as jobs_mod
        assert jobs_mod.acquire_mutex("product_doc_mine")
        assert not jobs_mod.acquire_mutex("product_doc_mine")  # 不可重入
        jobs_mod.release_mutex("product_doc_mine")
        assert jobs_mod.acquire_mutex("product_doc_mine")
        jobs_mod.release_mutex("product_doc_mine")


# ---------- /fs/raw（图片端点） ----------

class TestFsRaw:
    @pytest.fixture(autouse=True)
    def _assets(self, tmp_data_dir, monkeypatch):
        import app.service as svc
        import app.db as dbmod
        from app.registry import Registry
        from app.index import Index
        s = svc.Service.__new__(svc.Service)
        s.store = Store(tmp_data_dir)
        s.registry = Registry.load_default()
        s.db = dbmod.get_db(tmp_data_dir.parent / "test.db")
        dbmod.init_schema(s.db)
        s.index = Index.load_from_db(s.db, s.registry)
        monkeypatch.setattr(svc, "_service", s)
        img_dir = tmp_data_dir / "Command" / "UDG" / "20.15.2" / "assets"
        img_dir.mkdir(parents=True)
        (img_dir / "pic.png").write_bytes(b"\x89PNG-asset")
        (img_dir / "evil.svg").write_bytes(b"<svg/>")
        (img_dir / "note.txt").write_text("x", encoding="utf-8")

    def test_image_served(self):
        r = client.get("/api/v1/fs/raw",
                       params={"path": "Command/UDG/20.15.2/assets/pic.png"})
        assert r.status_code == 200
        assert r.content == b"\x89PNG-asset"

    def test_svg_rejected_d9(self):
        r = client.get("/api/v1/fs/raw",
                       params={"path": "Command/UDG/20.15.2/assets/evil.svg"})
        assert r.status_code == 400

    def test_traversal_rejected(self):
        r = client.get("/api/v1/fs/raw", params={"path": "../../platform.db"})
        assert r.status_code in (400, 404)
