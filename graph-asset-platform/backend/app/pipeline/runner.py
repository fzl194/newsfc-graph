"""产品文档导入编排：.hwics → 四类图谱资产 + 原始 md 留存。

由 ``routers/productdoc.py`` 在后台线程调用（job 状态经 ``app.jobs`` 推进，前端轮询）。

流程（构建顺序 = 规范《图谱边定义.md》§0，commands 必须先于 features——
特性层「使用命令」边校验依赖已建 Command 资产）：
  1. 临时目录解压 .hwics（html 中间态）→ exporter 转 md → ``output/{nf}_{version}/`` 留存
     （output/ 在 GAP_DATA_DIR 下、不进数据库不进图谱；html 随临时目录删除：md 留、html 删）
  2. rglob 定位 mml/feature/license 目录（UDG/UNC 目录层级不同，nf 优先 + 通配兜底）
  3. force 覆盖：先清理 assets 四类层目录（Task/Business 不参与）
  4. build_commands → build_configobjects → build_licenses → build_features（subprocess）
  5. svc.rebuild() 重建图谱索引；manifest 计数汇总进 job.summary
失败语义：已写入的部分保留（重跑即覆盖），job 标 failed + 定位到步骤；临时目录必清理。
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .. import config, jobs

HERE = Path(__file__).resolve().parent
GRAPH_LAYERS = ("Command", "ConfigObject", "Feature", "License")


def existing_layer_counts(nf: str, version: str) -> dict[str, int]:
    """同 nf+version 已有图谱资产 md 计数（重复上传判定 / 覆盖提示）。"""
    out: dict[str, int] = {}
    for layer in GRAPH_LAYERS:
        d = config.ASSETS_DIR / layer / nf / version
        if d.is_dir():
            out[layer] = sum(1 for _ in d.rglob("*.md"))
    return out


def locate_dirs(export_root: Path, nf: str) -> dict[str, Path]:
    """导出树中定位 mml/feature/license 源目录。**严格 nf 匹配**（不做通配兜底——
    通配会把 UDG 归档错标成 UNC 等跨网元错位）。找不到 → ValueError。"""

    def find(*patterns: str) -> Path | None:
        for pat in patterns:
            cands = [p for p in export_root.rglob(pat) if p.is_dir()]
            if cands:
                return cands[0]
        return None

    found = {
        "mml": find(f"{nf} MML命令"),
        "feature": find(f"{nf}特性指南"),
        "license": find(f"{nf} License描述"),
    }
    missing = [k for k, v in found.items() if v is None]
    if missing:
        raise ValueError(
            f"导出目录中未找到 {','.join(missing)} 源目录（按 {nf} 严格匹配）——"
            f"请确认 .hwics 是 {nf} 的产品文档归档，且网元/版本填写正确")
    return found  # type: ignore[return-value]


def _load_exporter():
    """按路径加载拷贝版 exporter（不污染 sys.path；依赖 chardet/bs4）。"""
    spec = importlib.util.spec_from_file_location("pipeline_exporter", HERE / "exporter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(script: Path, *args: object) -> str:
    proc = subprocess.run(
        [sys.executable, str(script), *[str(a) for a in args]],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = ((proc.stderr or "") + (proc.stdout or ""))[-2000:]
        raise RuntimeError(f"{script.name} 构建失败 (code {proc.returncode}):\n{tail}")
    return proc.stdout or ""


def _manifest(layer: str, nf: str, version: str) -> dict:
    p = config.ASSETS_DIR / layer / nf / version / "_build_manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def run_product_doc_import(job_id: str, hwics_path: Path, nf: str,
                           version: str, force: bool) -> None:
    """后台执行体：完成或失败后写终态；hwics_path 由调用方落在临时文件，本函数负责清理。"""
    steps: list[dict] = []
    warnings: list[str] = []

    def step(name: str, status: str = "processing", detail: str = "") -> None:
        for s in steps:
            if s["name"] == name:
                s.update(status=status, detail=detail)
                break
        else:
            steps.append({"name": name, "status": status, "detail": detail})
        jobs.update_job(job_id, steps=list(steps))

    try:
        # 1. 解压导出（html 中间态在临时目录，结束即删；md 留存 output/）
        step("解压导出", detail=f"{nf} {version}")
        export_target = config.OUTPUT_DIR / f"{nf}_{version}"
        if export_target.exists():
            shutil.rmtree(export_target)  # 同 nf+version 旧导出一并覆盖
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            exp = _load_exporter()
            with tempfile.TemporaryDirectory(prefix="pdoc_") as td:
                up = Path(td) / hwics_path.name
                shutil.move(str(hwics_path), str(up))
                extracted = exp.extract_hdx_file(str(up))  # 解到 td 内 → 随 td 删除
                exp.main_from_extracted(extracted, str(export_target))
        finally:
            # 兜底：调用方临时文件若未被 move 走（如解压前抛错）也清掉
            hwics_path.unlink(missing_ok=True)
        md_count = sum(1 for _ in export_target.rglob("*.md"))
        step("解压导出", "done", f"md {md_count} 篇留存 → output/{nf}_{version}/（html 已清理）")

        # 版本一致性提示（导出根目录名通常含版本号）
        prod_dirs = [p.name for p in export_target.iterdir() if p.is_dir()]
        if prod_dirs and version not in " ".join(prod_dirs):
            warnings.append(f"导出目录名 {prod_dirs} 未含版本 {version}，请核对")

        # 2. 定位源目录
        step("定位源目录")
        dirs = locate_dirs(export_target, nf)
        step("定位源目录", "done",
             f"mml/feature/license 已定位（{dirs['mml'].name} 等）")

        # 3. 覆盖清理（force）
        if force:
            step("覆盖清理")
            removed = 0
            for layer in GRAPH_LAYERS:
                d = config.ASSETS_DIR / layer / nf / version
                if d.exists():
                    removed += sum(1 for _ in d.rglob("*.md"))
                    shutil.rmtree(d)
            step("覆盖清理", "done", f"已清理旧资产 {removed} 个 md")

        # 4-7. 四类构建（§0 顺序）
        step("命令层", detail="build_commands（参见边全文锚定）")
        _run(HERE / "command" / "build_commands.py",
             "--nf", nf, "--version", version,
             "--mml-dir", dirs["mml"], "--storage", config.ASSETS_DIR)
        m_cmd = _manifest("Command", nf, version)
        step("命令层", "done", f"命令 {m_cmd.get('command_count', '?')} 个")

        step("配置对象层")
        _run(HERE / "command" / "build_configobjects.py",
             "--nf", nf, "--version", version, "--storage", config.ASSETS_DIR)
        m_cfg = _manifest("ConfigObject", nf, version)
        step("配置对象层", "done", f"配置对象 {m_cfg.get('object_count', '?')} 个")

        step("License 层")
        _run(HERE / "feature" / "build_licenses.py",
             "--nf", nf, "--version", version,
             "--license-dir", dirs["license"], "--feature-dir", dirs["feature"],
             "--storage", config.ASSETS_DIR)
        m_lic = _manifest("License", nf, version)
        step("License 层", "done", f"License {m_lic.get('license_count', '?')} 个")

        step("特性层", detail="build_features（依赖特性/使用命令边）")
        _run(HERE / "feature" / "build_features.py",
             "--nf", nf, "--version", version,
             "--feature-dir", dirs["feature"], "--storage", config.ASSETS_DIR)
        m_feat = _manifest("Feature", nf, version)
        step("特性层", "done",
             f"特性 {m_feat.get('feature_count', '?')} / 文档 {m_feat.get('doc_count', '?')}")

        # 8. 重建图谱索引
        step("重建索引")
        from ..service import get_service, import_lock  # 延迟导入避免环
        with import_lock:
            get_service().rebuild()
        step("重建索引", "done")

        summary = {
            "commands": m_cmd.get("command_count"),
            "config_objects": m_cfg.get("object_count"),
            "licenses": m_lic.get("license_count"),
            "features": m_feat.get("feature_count"),
            "feature_docs": m_feat.get("doc_count"),
            "export_md": md_count,
            "use_command_edges": m_feat.get("use_command_edges"),
            "dep_dangling_dropped": m_feat.get("dep_dangling_dropped"),
        }
        jobs.update_job(job_id, status="done", result=summary,
                        added=summary["commands"] or 0, warnings=warnings)
    except Exception as e:  # noqa: BLE001 —— job 终态必须覆盖一切异常
        if hwics_path.exists():
            hwics_path.unlink(missing_ok=True)
        jobs.update_job(job_id, status="failed",
                        error=f"{type(e).__name__}: {e}", warnings=warnings)
