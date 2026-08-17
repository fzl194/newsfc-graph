"""assets router 测试：/export /stats。

旧的 /import /imports 端点已移除（改由 fs router 的 /fs/upload 承担）；建数据
改用 ``import_bundle`` 库函数（仍保留，供测试与脚本复用）。

测试隔离：monkeypatch 把 service 单例指向 tmp_data_dir 上的 store。
"""
import io
import zipfile

from fastapi.testclient import TestClient

from app.bundle import import_bundle
from app.index import Index
from app.main import app
from app.registry import Registry
from app.store import Store
import app.service as svc

CMD = (
    "---\n"
    "id: alpha@MMLCommand@ADD DEMO\n"
    "type: MMLCommand\n"
    "nf: alpha\n"
    "version: 20.15.2\n"
    "---\n"
    "# ADD DEMO\n"
)


def _zip_bytes(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    buf.seek(0)
    return buf.getvalue()


def _setup_service(tmp_data_dir, monkeypatch):
    """把全局单例重定向到 tmp_data_dir 上的空 store + 空 tmp DB，返回 service。"""
    import app.db as dbmod
    s = svc.Service.__new__(svc.Service)
    s.store = Store(tmp_data_dir)
    s.registry = Registry.load_default()
    s.db = dbmod.get_db(tmp_data_dir.parent / "test.db")
    dbmod.init_schema(s.db)
    monkeypatch.setattr(dbmod, "_shared", s.db, raising=False)
    s.index = Index.load_from_db(s.db, s.registry)
    monkeypatch.setattr(svc, "_service", s)
    return s


def _seed(s, files: dict) -> None:
    """用 import_bundle 库函数批量建数据到 service 的 store + 重建索引。"""
    import_bundle(_zip_bytes(files), s.store, s.registry)
    s.rebuild()


def test_export_returns_zip(tmp_data_dir, monkeypatch):
    s = _setup_service(tmp_data_dir, monkeypatch)
    _seed(s, {"a.md": CMD})
    with TestClient(app) as c:
        r = c.get("/api/v1/export")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/zip")
        assert "attachment" in r.headers.get("content-disposition", "")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        assert "Command/alpha/20.15.2/alpha@MMLCommand@ADD DEMO.md" in names


def test_export_filter_nf_excludes_other(tmp_data_dir, monkeypatch):
    s = _setup_service(tmp_data_dir, monkeypatch)
    beta = (CMD.replace("alpha@MMLCommand@ADD DEMO", "beta@MMLCommand@ADD DEMO")
                .replace("nf: alpha", "nf: beta"))
    _seed(s, {"a.md": CMD, "b.md": beta})
    with TestClient(app) as c:
        r = c.get("/api/v1/export", params={"nf": "alpha"})
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        assert any("alpha" in n for n in names)
        assert all("beta" not in n for n in names)


# 多类型样例（命令层 + 特性层 + 业务层）测 /stats UI 层聚合
CMD2 = (
    "---\n"
    "id: alpha@MMLCommand@ADD CMD2\n"
    "type: MMLCommand\n"
    "nf: alpha\n"
    "version: 20.15.2\n"
    "---\n"
    "# ADD CMD2\n"
)
CFG2 = (
    "---\n"
    "id: alpha@ConfigObject@OBJ2\n"
    "type: ConfigObject\n"
    "nf: alpha\n"
    "version: 20.15.2\n"
    "object_kind: profile\n"
    "---\n"
    "# OBJ2\n"
)
FEAT = (
    "---\n"
    "id: alpha@Feature@F-100\n"
    "type: Feature\n"
    "nf: alpha\n"
    "version: 20.15.2\n"
    "---\n"
    "# F-100\n"
)
BD = (
    "---\n"
    "id: BusinessDomain@demo\n"
    "type: BusinessDomain\n"
    "domain: demo\n"
    "---\n"
    "# Demo Domain\n"
)


def test_stats_ui_layer_aggregation(tmp_data_dir, monkeypatch):
    """/stats per_layer 按 UI 层（4 个 Tab）聚合；ConfigObject 与 MMLCommand 合入命令层。"""
    s = _setup_service(tmp_data_dir, monkeypatch)
    _seed(s, {"cmd.md": CMD, "cmd2.md": CMD2, "cfg.md": CFG2,
              "feat.md": FEAT, "bd.md": BD})
    with TestClient(app) as c:
        out = c.get("/api/v1/stats").json()
        per_layer = out["per_layer"]
        assert set(per_layer.keys()) >= {"命令层", "特性层", "业务层"}
        assert per_layer["命令层"] == 3
        assert per_layer["特性层"] == 1
        assert per_layer["业务层"] == 1
        assert out["per_layer_per_nf"]["命令层"]["alpha"] == 3
        assert out["per_layer_per_nf_per_version"]["命令层"]["alpha"]["20.15.2"] == 3
        assert out["per_domain"]["demo"] == 1
