import io
import zipfile

import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """把 app.config.DATA_DIR / ASSETS_DIR 重定向到 tmp_path，返回 assets 目录 Path。"""
    data = tmp_path / "platform-data"
    assets = data / "assets"
    assets.mkdir(parents=True)
    import app.config as config
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "ASSETS_DIR", assets)
    return assets


@pytest.fixture
def sample_bundle_zip() -> bytes:
    """把 tests/fixtures/sample_bundle/ 目录打包成 zip 字节。

    目录布局 = 与统一资产库一致的归一化相对路径（Layer/nf/version/id.md 与
    Business/domain/scenario/id.md），可直接喂给 ``import_bundle``。
    """
    root = FIXTURES_DIR / "sample_bundle"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                rel = p.relative_to(root).as_posix()
                z.writestr(rel, p.read_text(encoding="utf-8"))
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _empty_service_to_avoid_real_index(tmp_data_dir, monkeypatch):
    """所有测试预置空图谱 service（0 对象 + 空 tmp DB），避免 TestClient lifespan 建 real index。
    test_fs/test_api_objects 的 _setup 会覆盖为带数据的 tmp service。"""
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
    monkeypatch.setattr(dbmod, "_shared", s.db, raising=False)  # users/store 共用此连接
    s.index = Index.load_from_db(s.db, s.registry)
    monkeypatch.setattr(svc, "_service", s)
    # jobs 独立连接（生产并发隔离）→ 测试注入同一 tmp 连接
    import app.jobs as jobs_mod
    monkeypatch.setattr(jobs_mod, "_conn", s.db, raising=False)
    # telemetry 独立连接（同上，2026-08-25）→ 测试注入同一 tmp 连接
    import app.telemetry.recorder as tel_recorder
    monkeypatch.setattr(tel_recorder, "_conn", s.db, raising=False)
    # stats 独立只读连接（2026-09-02 重查询不阻塞共享连接）→ 同上注入
    import app.stats.core as stats_core
    monkeypatch.setattr(stats_core, "_conn", s.db, raising=False)


@pytest.fixture(autouse=True)
def _skip_auth_for_pure_graph_tests(monkeypatch, request):
    """纯图谱资产测试（assets/e2e/jobs/store/index/classify 等不测 auth/打点的）
    跳过 auth 中间件，避免 v2 后逐个加 admin KEY。测 auth/打点的模块用真实中间件。"""
    mod = getattr(request.module, "__name__", "") if hasattr(request, "module") else ""
    if any(x in mod for x in ("test_auth", "test_users", "test_api_objects", "test_telemetry", "test_mcp_tools_config")):
        return
    from app.middleware import auth
    _ADMIN = {"username": "admin", "key": "x", "can_frontend": True, "can_upload": True, "can_test": True, "can_skill": True, "is_admin": True}
    monkeypatch.setattr(auth, "authenticate", lambda key: _ADMIN)


@pytest.fixture(autouse=True)
def _tmp_tests_dir(tmp_path, monkeypatch):
    """TESTS_DIR → tmp 空 tests + 重置 _test_service 单例（避免 lifespan 扫真实 tests md）。"""
    tests = tmp_path / "platform-data" / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.config.TESTS_DIR", tests, raising=False)
    monkeypatch.setattr("app.tests.service.TESTS_DIR", tests, raising=False)
    import app.tests.service as tsvc
    monkeypatch.setattr(tsvc, "_test_service", None, raising=False)

