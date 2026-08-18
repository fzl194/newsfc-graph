"""产品文档导入 + 原始文档浏览 + 图片服务 测试。

- pipeline.runner 的纯函数（定位/计数）用 tmp 目录树直测（UDG/UNC 两种层级）；
- POST /import/product-doc 的重复 409 / 后缀 400 / 成功建 job（runner 打桩）；
- /docs/*（output 只读浏览：children 同构 / 图片白名单 / 路径越界）；
- /fs/raw（资产图片：白名单 / 越界 / 404）。
完整 pipeline（真实 .hwics → 四层构建）不在单测覆盖，验收走手工上传。
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline import runner as pl
from app.store import Store

client = TestClient(app)


# ---------- locate_dirs（UDG / UNC 两种目录层级 + nf 优先 + 兜底 + 缺失） ----------

def _make_tree(base: Path, style: str) -> Path:
    """造最小导出树。UDG: 特性部署/特性指南/...；UNC: 网络部署/特性部署/...。"""
    root = base / "export"
    if style == "udg":
        (root / "Prod_CH_20.15.2" / "OM参考" / "命令" / "UDG MML命令").mkdir(parents=True)
        (root / "Prod_CH_20.15.2" / "特性部署" / "特性指南" / "UDG特性指南").mkdir(parents=True)
        (root / "Prod_CH_20.15.2" / "特性部署" / "特性指南" / "UDG License描述").mkdir(parents=True)
    else:
        (root / "Prod" / "OM参考" / "命令" / "UNC MML命令").mkdir(parents=True)
        (root / "Prod" / "网络部署" / "特性部署" / "UNC特性指南").mkdir(parents=True)
        (root / "Prod" / "网络部署" / "特性部署" / "UNC License描述").mkdir(parents=True)
    return root


class TestLocateDirs:
    def test_udg_layout_strict(self, tmp_path):
        root = _make_tree(tmp_path, "udg")
        dirs, warns = pl.locate_dirs(root, "UDG")
        assert dirs["mml"].name == "UDG MML命令"
        assert dirs["feature"].name == "UDG特性指南"
        assert dirs["license"].name == "UDG License描述"
        assert warns == []

    def test_unc_layout_strict(self, tmp_path):
        root = _make_tree(tmp_path, "unc")
        dirs, warns = pl.locate_dirs(root, "UNC")
        assert dirs["mml"].name == "UNC MML命令"
        assert dirs["feature"].name == "UNC特性指南"
        assert warns == []

    def test_renamed_dir_unique_fallback(self, tmp_path):
        """目录名不带 nf（命名变化）→ 泛匹配唯一候选可用 + 警告。"""
        root = tmp_path / "export"
        (root / "P" / "OM参考" / "命令" / "云核心网MML命令").mkdir(parents=True)
        (root / "P" / "特性指南目录A").mkdir(parents=True)
        (root / "P" / "License描述目录B").mkdir(parents=True)
        dirs, warns = pl.locate_dirs(root, "UDG")
        assert dirs["mml"].name == "云核心网MML命令"
        assert len(warns) == 3  # 三类都走了兜底

    def test_multiple_candidates_raises(self, tmp_path):
        """同关键词多目录且都不含 nf → 无法判定，报错列出候选。"""
        root = tmp_path / "export"
        (root / "A" / "甲MML命令").mkdir(parents=True)
        (root / "B" / "乙MML命令").mkdir(parents=True)
        (root / "C" / "UDG特性指南").mkdir(parents=True)
        (root / "C" / "UDG License描述").mkdir(parents=True)
        with pytest.raises(ValueError, match="候选"):
            pl.locate_dirs(root, "UDG")

    def test_missing_raises(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(ValueError, match="定位失败"):
            pl.locate_dirs(empty, "UDG")


class TestExistingLayerCounts:
    def test_counts(self, tmp_data_dir, monkeypatch):
        import app.config as config
        monkeypatch.setattr(config, "ASSETS_DIR", tmp_data_dir)
        d = tmp_data_dir / "Command" / "UDG" / "20.15.2"
        d.mkdir(parents=True)
        (d / "a.md").write_text("x", encoding="utf-8")
        (d / "b.md").write_text("x", encoding="utf-8")
        counts = pl.existing_layer_counts("UDG", "20.15.2")
        assert counts == {"Command": 2}


# ---------- POST /import/product-doc ----------

class TestUploadEndpoint:
    def test_reject_bad_suffix(self):
        r = client.post("/api/v1/import/product-doc",
                        data={"nf": "UDG", "version": "20.15.2"},
                        files={"file": ("doc.exe", b"xx")})
        assert r.status_code == 400
        assert "产品文档归档" in r.text

    def test_reject_duplicate_without_force(self, tmp_data_dir, monkeypatch):
        import app.config as config
        monkeypatch.setattr(config, "ASSETS_DIR", tmp_data_dir)
        d = tmp_data_dir / "Command" / "UDG" / "20.15.2"
        d.mkdir(parents=True)
        (d / "a.md").write_text("x", encoding="utf-8")
        r = client.post("/api/v1/import/product-doc",
                        data={"nf": "UDG", "version": "20.15.2"},
                        files={"file": ("doc.hwics", b"PK")})
        assert r.status_code == 409
        assert r.json()["detail"]["existing"] == {"Command": 1}

    def test_creates_job_and_runs_stub(self, tmp_data_dir, monkeypatch):
        import app.config as config
        from app import jobs as jobs_mod
        monkeypatch.setattr(config, "ASSETS_DIR", tmp_data_dir)
        seen = {}

        def stub_run(job_id, hwics_path, nf, version, force):
            seen.update(job_id=job_id, path=hwics_path, nf=nf, version=version, force=force)
            Path(hwics_path).unlink(missing_ok=True)
            jobs_mod.update_job(job_id, status="done", result={"commands": 3})

        import app.routers.productdoc as pd
        monkeypatch.setattr(pd, "run_product_doc_import", stub_run)
        r = client.post("/api/v1/import/product-doc",
                        data={"nf": "UDG", "version": "20.15.2"},
                        files={"file": ("doc.hwics", b"PK-zip-bytes")})
        assert r.status_code == 200
        jid = r.json()["job_id"]
        assert seen["nf"] == "UDG" and seen["force"] is False
        j = client.get(f"/api/v1/import/jobs/{jid}")
        assert j.status_code == 200
        assert j.json()["status"] == "done"
        assert j.json()["kind"] == "product_doc"
        assert j.json()["result"]["commands"] == 3

    def test_force_allows_duplicate(self, tmp_data_dir, monkeypatch):
        import app.config as config
        monkeypatch.setattr(config, "ASSETS_DIR", tmp_data_dir)
        d = tmp_data_dir / "Command" / "UDG" / "20.15.2"
        d.mkdir(parents=True)
        (d / "a.md").write_text("x", encoding="utf-8")

        import app.routers.productdoc as pd
        from app import jobs as jobs_mod

        def stub(job_id, hwics_path, nf, version, force):
            Path(hwics_path).unlink(missing_ok=True)
            jobs_mod.update_job(job_id, status="done")

        monkeypatch.setattr(pd, "run_product_doc_import", stub)
        r = client.post("/api/v1/import/product-doc",
                        data={"nf": "UDG", "version": "20.15.2", "force": "true"},
                        files={"file": ("doc.hwics", b"PK")})
        assert r.status_code == 200
        assert r.json()["force"] is True


# ---------- /docs/*（output 只读浏览） ----------

class TestDocsRouter:
    @pytest.fixture(autouse=True)
    def _output(self, tmp_path, monkeypatch):
        import app.config as config
        out = tmp_path / "platform-data" / "output" / "UDG_20.15.2" / "Prod"
        out.mkdir(parents=True)
        monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "platform-data" / "output")
        (out / "cmd.md").write_text("# 命令\n![](x.assets/a.png)\n", encoding="utf-8")
        (out / "x.assets").mkdir()
        (out / "x.assets" / "a.png").write_bytes(b"\x89PNG-fake")
        self.out_root = tmp_path / "platform-data" / "output"

    def test_children_shape(self):
        r = client.get("/api/v1/docs/children")
        assert r.status_code == 200
        top = r.json()
        assert top and top[0]["name"] == "UDG_20.15.2" and top[0]["is_dir"] is True
        r2 = client.get("/api/v1/docs/children",
                        params={"path": "UDG_20.15.2/Prod"})
        names = {x["name"] for x in r2.json()}
        assert {"cmd.md", "x.assets"} <= names

    def test_file_text(self):
        r = client.get("/api/v1/docs/file", params={"path": "UDG_20.15.2/Prod/cmd.md"})
        assert r.status_code == 200
        assert "命令" in r.text

    def test_raw_image_ok(self):
        r = client.get("/api/v1/docs/raw",
                       params={"path": "UDG_20.15.2/Prod/x.assets/a.png"})
        assert r.status_code == 200
        assert r.content == b"\x89PNG-fake"

    def test_raw_rejects_non_image(self):
        r = client.get("/api/v1/docs/raw", params={"path": "UDG_20.15.2/Prod/cmd.md"})
        assert r.status_code == 400

    def test_traversal_rejected(self):
        r = client.get("/api/v1/docs/file",
                       params={"path": "../../users.json"})
        assert r.status_code in (400, 404)


# ---------- /fs/raw（资产图片服务） ----------

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
        (img_dir / "note.txt").write_text("x", encoding="utf-8")

    def test_image_served(self):
        r = client.get("/api/v1/fs/raw",
                       params={"path": "Command/UDG/20.15.2/assets/pic.png"})
        assert r.status_code == 200
        assert r.content == b"\x89PNG-asset"

    def test_non_image_rejected(self):
        r = client.get("/api/v1/fs/raw",
                       params={"path": "Command/UDG/20.15.2/assets/note.txt"})
        assert r.status_code == 400

    def test_missing_404(self):
        r = client.get("/api/v1/fs/raw", params={"path": "Command/UDG/20.15.2/assets/nope.png"})
        assert r.status_code == 404

    def test_traversal_rejected(self):
        r = client.get("/api/v1/fs/raw", params={"path": "../../platform.db"})
        assert r.status_code in (400, 404)


# ---------- job 持久化 / 单任务互斥 / 删除 / 重启清账 ----------

class TestJobPersistenceAndMutex:
    @pytest.fixture(autouse=True)
    def _clean_registry(self):
        """jobs._registry 是模块级单例，跨测试残留会误触发互斥——逐测清空。"""
        from app import jobs as jobs_mod
        jobs_mod._registry.clear()
        yield
        jobs_mod._registry.clear()

    def _post(self, **kw):
        return client.post(
            "/api/v1/import/product-doc",
            data={"nf": kw.get("nf", "UDG"), "version": kw.get("version", "20.15.2"),
                  **({"force": "true"} if kw.get("force") else {})},
            files={"file": ("doc.hwics", b"PK")})

    def test_mutex_rejects_new_while_processing(self):
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc", nf="UDG", version="20.15.2")
        r = self._post()
        assert r.status_code == 409
        assert "已有构建任务在跑" in r.text
        jobs_mod.update_job(j.job_id, status="done")
        # 完成后放行（runner 打桩避免真跑）
        import app.routers.productdoc as pd
        orig = pd.run_product_doc_import
        pd.run_product_doc_import = lambda *a, **k: None
        try:
            r2 = self._post()
            assert r2.status_code == 200
        finally:
            pd.run_product_doc_import = orig

    def test_delete_rejected_while_processing(self):
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc", nf="UDG", version="20.15.2")
        r = client.delete(f"/api/v1/import/jobs/{j.job_id}")
        assert r.status_code == 400
        assert "进行中" in r.text

    def test_delete_done_ok(self):
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc", nf="UDG", version="20.15.2")
        jobs_mod.update_job(j.job_id, status="done", result={"commands": 5})
        r = client.delete(f"/api/v1/import/jobs/{j.job_id}")
        assert r.status_code == 200
        assert client.get(f"/api/v1/import/jobs/{j.job_id}").status_code == 404

    def test_history_survives_restart(self):
        """registry 清空（模拟重启后缓存丢失）→ 历史从 DB 读回。"""
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc", nf="UNC", version="20.15.2")
        jobs_mod.update_job(j.job_id, status="done",
                            steps=[{"name": "解压导出", "status": "done", "detail": "md 1 篇"}],
                            result={"commands": 13073})
        jobs_mod._registry.clear()
        got = jobs_mod.get_job(j.job_id)
        assert got is not None and got.status == "done"
        assert got.result["commands"] == 13073
        assert got.steps[0]["name"] == "解压导出"
        listed = {x.job_id for x in jobs_mod.list_jobs()}
        assert j.job_id in listed

    def test_sweep_interrupted_marks_failed(self):
        from app import jobs as jobs_mod
        j = jobs_mod.create_job(kind="product_doc", nf="UDG", version="20.15.2")
        jobs_mod._registry.clear()  # 模拟：DB 留 processing，进程已死
        n = jobs_mod.sweep_interrupted()
        assert n >= 1
        got = jobs_mod.get_job(j.job_id)
        assert got.status == "failed"
        assert "重启" in got.error
