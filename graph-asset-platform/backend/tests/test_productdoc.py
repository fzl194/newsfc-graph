"""两步流水线测试（2026-08-26 抽取任务化版）：解压留存 / 抽取器注册 / 定位候选 /
抽取任务端点（依赖阻断·同目标守卫·互斥）/ 闸门与回退见 test_extract_gate.py /
任务持久化 / bundles 包管理。完整真实归档流程靠手工验收（见实施计划 §6）。
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline import bundles, runner as pl
from app.pipeline import extractors as ex_reg
from app.store import Store

client = TestClient(app)

MML_REL = "Prod_CH_20.15.2/OM参考/命令/UDG MML命令"
FEAT_REL = "Prod_CH_20.15.2/特性部署/特性指南/UDG特性指南"
LIC_REL = "Prod_CH_20.15.2/特性部署/特性指南/UDG License描述"


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


# ---------- 抽取器注册表 ----------

class TestExtractors:
    def test_three_registered_with_semantics(self):
        ids = {x["id"] for x in ex_reg.list_extractors()}
        assert ids == {"cmd", "license", "feature"}
        feat = ex_reg.get_extractor("feature")
        assert feat.needs == ("Command", "License")      # 阻断依赖
        assert feat.rerun_after                          # 自动重跑命令补引用
        assert [b.layer for b in feat.rerun_after] == ["Command", "ConfigObject"]
        cmd = ex_reg.get_extractor("cmd")
        assert cmd.needs == () and cmd.required_roles == ("mml",)
        assert [b.layer for b in cmd.builders] == ["Command", "ConfigObject"]  # 整体
        lic = ex_reg.get_extractor("license")
        assert lic.required_roles == ("license",)        # feature 角色可选
        assert "feature" in lic.keywords                 # locate 仍可推荐 feature 目录

    def test_endpoint_shape(self):
        r = client.get("/api/v1/import/extractors")
        assert r.status_code == 200
        rows = {x["id"]: x for x in r.json()}
        assert rows["feature"]["needs"] == ["Command", "License"]
        assert rows["feature"]["rerun"] is True
        assert rows["cmd"]["roles"] == ["mml"]
        assert rows["license"]["roles"] == ["license", "feature"]


# ---------- locate_candidates（推荐 + 候选；casefold；目标网元严格匹配） ----------

class TestLocateCandidates:
    CMD = ex_reg.get_extractor("cmd")
    LIC = ex_reg.get_extractor("license")

    def test_udg_layout_recommended(self, tmp_path):
        root = _make_md_tree(tmp_path)
        loc = pl.locate_candidates(root, self.CMD, "UDG")
        assert loc["mml"]["recommended"].endswith("UDG MML命令")
        assert loc["mml"]["note"] == ""
        assert any(c.endswith("UDG MML命令") for c in loc["mml"]["candidates"])

    def test_casefold_nf(self, tmp_path):
        root = _make_md_tree(tmp_path)
        loc = pl.locate_candidates(root, self.CMD, "udg")  # 小写网元也能严格命中
        assert loc["mml"]["recommended"].endswith("UDG MML命令")

    def test_target_nf_strict_beats_bundle_nf(self, tmp_path):
        """包=UDG 但内含 AMF 目录 → 目标网元=AMF 时严格命中 AMF（解耦核心）。"""
        root = _make_md_tree(tmp_path)
        (root / "OM参考" / "命令" / "AMF MML命令").mkdir(parents=True)
        loc = pl.locate_candidates(root, self.CMD, "AMF")
        assert loc["mml"]["recommended"].endswith("AMF MML命令")

    def test_license_extractor_roles(self, tmp_path):
        root = _make_md_tree(tmp_path)
        loc = pl.locate_candidates(root, self.LIC, "UDG")
        assert loc["license"]["recommended"].endswith("UDG License描述")
        assert loc["feature"]["recommended"].endswith("UDG特性指南")

    def test_renamed_unique_loose(self, tmp_path):
        root = tmp_path / "pkg"
        (root / "云核心网MML命令").mkdir(parents=True)
        loc = pl.locate_candidates(root, self.CMD, "UDG")
        assert loc["mml"]["recommended"] is not None and "非标准命名" in loc["mml"]["note"]

    def test_multi_candidates_no_recommend(self, tmp_path):
        root = tmp_path / "pkg"
        (root / "甲MML命令").mkdir(parents=True)
        (root / "乙MML命令").mkdir(parents=True)
        loc = pl.locate_candidates(root, self.CMD, "UDG")
        assert loc["mml"]["recommended"] is None
        assert "人工选择" in loc["mml"]["note"]
        assert len(loc["mml"]["candidates"]) == 2

    def test_validate_selected_dirs_rejects_escape(self, tmp_path):
        root = _make_md_tree(tmp_path)
        with pytest.raises(ValueError, match="越界"):
            pl.validate_selected_dirs(root, {"mml": "../../etc"})
        ok = pl.validate_selected_dirs(root, {"mml": MML_REL})
        assert ok["mml"][0].is_dir()

    def test_validate_normalizes_and_rejects(self, tmp_path):
        root = _make_md_tree(tmp_path)
        ok = pl.validate_selected_dirs(root, {
            "mml": [MML_REL, MML_REL],   # 重复 → 去重
            "feature": FEAT_REL,          # str → 单元素
        })
        assert len(ok["mml"]) == 1 and len(ok["feature"]) == 1
        with pytest.raises(ValueError, match="越界"):
            pl.validate_selected_dirs(root, {"mml": ["../../x"]})


# ---------- 端点：解压（步骤①，与 2026-08-19 版一致） ----------

class TestExtractStep1Endpoint:
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

        def stub(job_id, hwics_path, nf, version, uploaded_by=""):
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


# ---------- 端点：抽取任务（步骤② 校验矩阵；沙箱/闸门/回退全流程见 test_extract_gate） ----------

class TestExtractEndpoint:
    @pytest.fixture(autouse=True)
    def _env(self, tmp_path, tmp_data_dir, monkeypatch):
        import app.config as config
        out = tmp_path / "pd" / "output"
        monkeypatch.setattr(config, "OUTPUT_DIR", out)
        monkeypatch.setattr(config, "DATA_DIR", out.parent)
        monkeypatch.setattr(config, "ASSETS_DIR", tmp_data_dir)
        _make_md_tree(out)  # 一个已解压包（legacy 格式）
        from app import jobs as jobs_mod
        jobs_mod._registry.clear()
        yield
        jobs_mod._registry.clear()
        jobs_mod._db().execute("DELETE FROM import_jobs")
        jobs_mod._db().commit()

    def _extract(self, **over):
        body = {"bundle_nf": "UDG", "bundle_version": "20.15.2",
                "target_nf": "UDG", "target_version": "20.15.2",
                "extractor": "cmd", "dirs": {"mml": MML_REL}}
        body.update(over)
        return client.post("/api/v1/import/extract", json=body)

    def test_bundle_missing_404(self):
        r = self._extract(bundle_nf="NOP")
        assert r.status_code == 404

    def test_bad_extractor_400(self):
        r = self._extract(extractor="ims9")
        assert r.status_code == 400

    def test_feature_dep_block_400_with_missing(self, tmp_data_dir):
        """依赖阻断（用户决策 2026-08-26）：feature 缺 Command/License → 400+明细，
        不自动补齐、无 job 创建。"""
        from app import jobs as jobs_mod
        r = self._extract(extractor="feature", dirs={"feature": FEAT_REL})
        assert r.status_code == 400
        assert r.json()["detail"]["missing"] == ["Command", "License"]
        assert not [j for j in jobs_mod.list_jobs() if j.kind == "product_doc_mine"]

    def test_missing_required_role_400(self):
        r = self._extract(dirs={})  # cmd 必选 mml
        assert r.status_code == 400 and "mml" in r.text

    def test_creates_job_with_target_identity(self, monkeypatch):
        """job.nf/version = **目标**网元（同目标 awaiting 守卫/历史展示依据）；
        包身份在 result（run_mine 写入，stub 这里只验 job 创建）。"""
        import app.routers.productdoc as pd

        def stub(job_id, spec):
            from app import jobs as jobs_mod
            jobs_mod.update_job(job_id, status="awaiting", result={"target_nf": spec["target_nf"]})

        monkeypatch.setattr(pd, "run_mine", stub)
        r = self._extract(target_nf="AMF", target_version="20.15.2")  # 目标≠包名
        assert r.status_code == 200
        jid = r.json()["job_id"]
        j = client.get(f"/api/v1/import/jobs/{jid}").json()
        assert j["nf"] == "AMF" and j["kind"] == "product_doc_mine"

    def test_same_target_awaiting_409(self, monkeypatch):
        from app import jobs as jobs_mod
        import app.routers.productdoc as pd

        def stub(job_id, spec):
            jobs_mod.update_job(job_id, status="awaiting",
                                result={"target_nf": spec["target_nf"]})

        monkeypatch.setattr(pd, "run_mine", stub)
        j = jobs_mod.create_job(kind="product_doc_mine", nf="UDG", version="20.15.2")
        jobs_mod.update_job(j.job_id, status="awaiting")
        r2 = None
        try:
            r = self._extract()                                   # 同目标 → 409
            assert r.status_code == 409 and "待确认" in r.json()["detail"]["message"]
            r2 = self._extract(target_nf="OTHER")                 # 异目标 → 放行（互斥未占）
            assert r2.status_code == 200
        finally:
            jobs_mod.update_job(j.job_id, status="cancelled")
            if r2 is not None and r2.status_code == 200:
                jobs_mod.update_job(r2.json()["job_id"], status="cancelled")
                jobs_mod.delete_job(r2.json()["job_id"])
            jobs_mod.delete_job(j.job_id)

    def test_mutex_rejects_second(self):
        from app import jobs as jobs_mod
        assert jobs_mod.acquire_mutex("product_doc_mine")
        try:
            r = self._extract()
            assert r.status_code == 409
        finally:
            jobs_mod.release_mutex("product_doc_mine")

    def test_target_assets_endpoint(self, tmp_data_dir):
        r = client.get("/api/v1/import/target-assets",
                       params={"nf": "UDG", "version": "20.15.2"})
        assert r.status_code == 200
        assert r.json() == {"Command": False, "ConfigObject": False,
                            "Feature": False, "License": False}
        d = tmp_data_dir / "Command" / "UDG" / "20.15.2"
        d.mkdir(parents=True)
        (d / "x.md").write_text("x", encoding="utf-8")
        r2 = client.get("/api/v1/import/target-assets",
                        params={"nf": "UDG", "version": "20.15.2"})
        assert r2.json()["Command"] is True

    def test_locate_endpoint_with_target_nf(self):
        r = client.get("/api/v1/import/bundles/UDG/20.15.2/locate",
                       params={"extractor": "license", "target_nf": "UDG"})
        assert r.status_code == 200
        loc = r.json()
        assert loc["license"]["recommended"].endswith("UDG License描述")
        assert loc["feature"]["recommended"].endswith("UDG特性指南")

    def test_locate_bad_extractor_400(self):
        r = client.get("/api/v1/import/bundles/UDG/20.15.2/locate",
                       params={"extractor": "nope"})
        assert r.status_code == 400


# ---------- jobs 持久化 / 删除 / 清账（v3：child_pids + 互斥锁；v4：awaiting/cancelled） ----------

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

    def test_delete_rejected_while_awaiting(self):
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc_mine", nf="UDG", version="20.15.2")
        jobs_mod.update_job(j.job_id, status="awaiting")
        assert client.delete(f"/api/v1/import/jobs/{j.job_id}").status_code == 400

    def test_delete_done_ok(self):
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc_mine", nf="UDG", version="20.15.2")
        jobs_mod.update_job(j.job_id, status="done")
        assert client.delete(f"/api/v1/import/jobs/{j.job_id}").status_code == 200
        assert client.get(f"/api/v1/import/jobs/{j.job_id}").status_code == 404

    def test_cancelled_stamps_finished_at(self):
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc_mine", nf="UDG", version="20.15.2")
        jobs_mod.update_job(j.job_id, status="cancelled")
        assert jobs_mod.get_job(j.job_id).finished_at > 0

    def test_history_survives_restart(self):
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc_extract", nf="UDG", version="20.15.2")
        jobs_mod.update_job(j.job_id, status="done", child_pids=[123],
                            result={"md_count": 7})
        jobs_mod._registry.clear()  # 模拟重启（缓存丢失）
        got = jobs_mod.get_job(j.job_id)
        assert got.status == "done" and got.result["md_count"] == 7
        assert got.child_pids == [123]

    def test_awaiting_survives_restart_and_sweep(self, monkeypatch):
        """awaiting 非终态：sweep_interrupted 只清 processing（跨重启存活）。"""
        from app import jobs as jobs_mod
        monkeypatch.setattr(jobs_mod, "_kill_pid_tree", lambda pid: None)
        j = jobs_mod.create_job(kind="product_doc_mine", nf="UDG", version="20.15.2")
        jobs_mod.update_job(j.job_id, status="awaiting")
        jobs_mod._registry.clear()
        jobs_mod.sweep_interrupted()
        got = jobs_mod.get_job(j.job_id)
        assert got is not None and got.status == "awaiting"

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

    def test_legacy_result_rows_render_verbatim(self):
        """旧（modes 时代）done 任务历史行原样返回——前端兼容。"""
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc_mine", nf="UDG", version="20.15.2")
        old = {"layers": {"Command": 3612}, "total": 3612,
               "bundle": "UDG_20.15.2", "mode": "5GC产品文档"}
        jobs_mod.update_job(j.job_id, status="done", result=old)
        row = client.get(f"/api/v1/import/jobs/{j.job_id}").json()
        assert row["result"] == old


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


# ---------- 增量索引（reindex_prefixes：闸门 confirm/revert 共用，规模无关） ----------

CMD_MD = (
    "---\n"
    "id: {nf}@MMLCommand@{name}\n"
    "type: MMLCommand\n"
    "nf: {nf}\n"
    "version: {ver}\n"
    "name: {name}\n"
    "---\n"
    "# {name}\n\n## 边\n（暂无）\n"
)


def _svc(tmp_data_dir, monkeypatch):
    """空图谱 service（tmp store + tmp DB + tmp index），同 conftest 模式。"""
    import app.service as svc
    import app.db as dbmod
    from app.store import Store
    from app.registry import Registry
    from app.index import Index
    s = svc.Service.__new__(svc.Service)
    s.store = Store(tmp_data_dir)
    s.registry = Registry.load_default()
    s.db = dbmod.get_db(tmp_data_dir.parent / "test.db")
    dbmod.init_schema(s.db)
    s.index = Index.load_from_db(s.db, s.registry)
    monkeypatch.setattr(svc, "_service", s)
    return s


class TestReindexPrefixes:
    def test_add_update_remove_scoped(self, tmp_data_dir, monkeypatch):
        s = _svc(tmp_data_dir, monkeypatch)
        d1 = tmp_data_dir / "Command" / "X" / "1.0"
        d2 = tmp_data_dir / "Command" / "Y" / "1.0"
        d1.mkdir(parents=True)
        d2.mkdir(parents=True)
        (d1 / "a.md").write_text(CMD_MD.format(nf="X", ver="1.0", name="ADD A"), encoding="utf-8")
        (d1 / "b.md").write_text(CMD_MD.format(nf="X", ver="1.0", name="ADD B"), encoding="utf-8")
        (d2 / "c.md").write_text(CMD_MD.format(nf="Y", ver="1.0", name="ADD C"), encoding="utf-8")

        r1 = s.reindex_prefixes(["Command/X/1.0"])
        assert r1 == {"indexed": 2, "removed": 0}
        assert s.index.node("X@MMLCommand@ADD A", "1.0") is not None
        assert s.index.node("Y@MMLCommand@ADD C", "1.0") is None  # 前缀外未动

        # b 删除 + a 改名（内容变更）→ 增量反映（indexed=前缀下现存文件数）
        (d1 / "b.md").unlink()
        (d1 / "a.md").write_text(CMD_MD.format(nf="X", ver="1.0", name="ADD A2"), encoding="utf-8")
        r2 = s.reindex_prefixes(["Command/X/1.0"])
        assert r2 == {"indexed": 1, "removed": 1}
        assert s.index.node("X@MMLCommand@ADD A", "1.0") is None
        assert s.index.node("X@MMLCommand@ADD A2", "1.0") is not None

    def test_empty_prefix_guard(self, tmp_data_dir, monkeypatch):
        s = _svc(tmp_data_dir, monkeypatch)
        assert s.reindex_prefixes(["", " / "]) == {"indexed": 0, "removed": 0}
