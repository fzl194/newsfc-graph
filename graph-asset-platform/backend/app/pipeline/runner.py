"""两步流水线编排（2026-08-19 重构，用户决策拆分）：

- 步骤① ``run_extract``（上传页·产品文档解压）：.hwics → 解压（html 临时态）→
  转 md → ``output/{nf}_{version}/`` 留存（**只留 md + bundle.json**，html/原件随
  临时目录删除；原子替换失败不动旧包）。
- 步骤② ``run_mine``（上传页·自动抽取）：包须解压完成（门槛）→ 用户确认的源目录
  （候选来自 ``locate_candidates``，只能选服务端枚举项）→ 范围勾选（依赖强制补齐）
  → 按模式注册表调度构建器（``two_pass`` 修 D5 force 剥引用）→ ``svc.rebuild()``。

安全底线（评审清单 2026-08-18，2026-08-19 批准随重构实施）：
D1 命名白名单+目录祖先校验；D14 版本不一致阻断；D16 子进程 PID 记录（sweep 终止）；
D17 zip namelist 预检；D20 摘要=四层之和+manifest 缺失告警。
构建脚本为规范拷贝件（字节一致），全部经 subprocess 隔离运行（两份同名 _common 平面导入）。
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .. import config, jobs
from . import bundles
from . import modes as modes_reg

HERE = Path(__file__).resolve().parent
GRAPH_LAYERS = ("Command", "ConfigObject", "Feature", "License")

# 挖掘范围 → 产物层（范围勾选即层选择；配置对象层随命令层走同目录计数）
_UPLOAD_MAX_BYTES = 2 * 1024 ** 3  # 2GB（router 侧强制，D4）


# ---------- 公共 ----------

def _load_exporter():
    """按路径加载拷贝版 exporter（不污染 sys.path；依赖 chardet/bs4）。
    **必须注册进 sys.modules**：exporter 顶部的 @dataclass 按 __module__ 名查
    sys.modules 解析字符串注解，未注册会 AttributeError: NoneType.__dict__。"""
    spec = importlib.util.spec_from_file_location("pipeline_exporter", HERE / "exporter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return mod


def _zip_precheck(hwics_path: Path) -> None:
    """D17：解压前预检 zip 成员（绝对路径/`..`/反斜杠穿越——exporter 是权威拷贝
    不能改，编排层负责不喂危险归档）。"""
    with zipfile.ZipFile(hwics_path) as z:
        for n in z.namelist():
            if n.startswith(("/", "\\")) or (len(n) > 1 and n[1] == ":"):
                raise ValueError(f"归档含绝对路径成员: {n}")
            parts = PurePosixName(n)
            if ".." in parts:
                raise ValueError(f"归档含路径穿越成员: {n}")


def PurePosixName(n: str) -> list:
    return [p for p in n.replace("\\", "/").split("/") if p]


def _extract_version_hint(root: Path) -> str:
    """从导出根的产品目录名抽版本号（如 UDG_Product_Documentation_CH_20.15.2 → 20.15.2）。"""
    pat = re.compile(r"\d+\.\d+(?:\.\d+)*")
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        m = pat.search(d.name)
        if m:
            return m.group(0)
    return ""


def _run(script: Path, *args: object, job_id: str = "") -> str:
    """subprocess 跑构建脚本；PID 记入 job（D16：进程被杀后 sweep 可终止孤儿树）。"""
    proc = subprocess.Popen(
        [sys.executable, str(script), *[str(a) for a in args]],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace")
    if job_id:
        j = jobs.get_job(job_id)
        if j is not None:
            jobs.update_job(job_id, child_pids=(j.child_pids or []) + [proc.pid])
    out, err = proc.communicate()
    if job_id:
        j = jobs.get_job(job_id)
        if j is not None:
            jobs.update_job(job_id, child_pids=[p for p in (j.child_pids or []) if p != proc.pid])
    if proc.returncode != 0:
        tail = ((err or "") + (out or ""))[-2000:]
        raise RuntimeError(f"{script.name} 构建失败 (code {proc.returncode}):\n{tail}")
    return out or ""


def _fail(job_id: str, hwics_or_none: Path | None, e: Exception) -> None:
    if hwics_or_none is not None:
        hwics_or_none.unlink(missing_ok=True)
    jobs.update_job(job_id, status="failed",
                    error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-3000:]}")


# ---------- 步骤② 定位（推荐 + 候选，人工确认；架构性缓解 D11/D1） ----------

def locate_candidates(export_root: Path, mode: "modes_reg.ModeDef", nf: str) -> dict:
    """按模式关键词扫描包内源目录候选。

    每角色返回 {recommended: 相对路径|None, candidates: [相对路径], note}；
    recommended 仅供前端默认选中——最终由用户从 candidates 改选（防猜错）。
    """
    root = export_root.resolve()
    out: dict[str, dict] = {}
    nf_cf = nf.casefold()
    for role, kws in mode.keywords.items():
        kw_cfs = [k.casefold() for k in kws]
        hits: dict[Path, bool] = {}  # path -> strict?
        for p in root.rglob("*"):
            if not p.is_dir():
                continue
            name_cf = p.name.casefold()
            kw_hit = any(k in name_cf for k in kw_cfs)
            if not kw_hit:
                continue
            strict = nf_cf in name_cf
            hits[p] = hits.get(p, False) or strict
        cands = sorted(hits, key=lambda p: (len(p.parts), p.name))  # 浅层优先、短名优先
        stricts = [p for p in cands if hits[p]]
        recommended = stricts[0] if stricts else (cands[0] if len(cands) == 1 else None)
        rel = lambda p: p.relative_to(root).as_posix()  # noqa: E731
        note = ""
        if recommended is None and cands:
            note = f"发现 {len(cands)} 个候选目录，请人工选择"
        if recommended is not None and not hits.get(recommended):
            note = "目录名未含网元（非标准命名），请确认选择"
        out[role] = {
            "recommended": rel(recommended) if recommended else None,
            "candidates": [rel(p) for p in cands[:30]],
            "note": note,
        }
    return out


def validate_selected_dirs(bundle_root: Path, selected: dict) -> dict:
    """用户提交的目录选择校验：必须在包内且真实存在（防注入；D1 纵深）。"""
    root = bundle_root.resolve()
    out: dict[str, Path] = {}
    for role, rel in selected.items():
        p = (root / rel).resolve()
        if p != root and root not in p.parents:
            raise ValueError(f"目录越界: {role}={rel}")
        if not p.is_dir():
            raise ValueError(f"目录不存在: {role}={rel}")
        out[role] = p
    return out


def layer_assets_exist(layer: str, nf: str, version: str) -> bool:
    d = config.ASSETS_DIR / layer / nf / version
    return d.is_dir() and any(d.rglob("*.md"))


def expand_scope(scope: list, mode: "modes_reg.ModeDef", nf: str, version: str) -> tuple:
    """范围×依赖强制（用户决策 2026-08-19）：勾选层的 needs 层若资产不存在，
    自动补选并锁定（返回 final + 补选说明）。资产已存在则不强制（增量挖掘）。"""
    final = set(scope)
    added: list[str] = []
    for b in mode.builders:
        if b.layer not in final:
            continue
        for dep in b.needs:
            if dep not in final and not layer_assets_exist(dep, nf, version):
                final.add(dep)
                added.append(f"{b.layer} 依赖 {dep}（该层资产不存在，已自动补选）")
    ordered = [b.layer for b in mode.builders if b.layer in final]
    return ordered, added


# ---------- 步骤① 解压转换留存 ----------

def run_extract(job_id: str, hwics_path: Path, nf: str, version: str,
                uploaded_by: str = "") -> None:
    """后台执行体：解压 → 转换 → md 留存 + bundle.json（原子替换）。"""
    steps: list = []
    warnings: list = []

    def step(name: str, status: str = "processing", detail: str = "") -> None:
        for s in steps:
            if s["name"] == name:
                s.update(status=status, detail=detail)
                break
        else:
            steps.append({"name": name, "status": status, "detail": detail})
        jobs.update_job(job_id, steps=list(steps))

    if not (bundles.is_valid_name(nf) and bundles.is_valid_name(version)):  # D1 双保险
        jobs.update_job(job_id, status="failed",
                        error=f"非法网元/版本命名：nf={nf!r} version={version!r}"
                              f"（白名单 ^[A-Za-z0-9_][A-Za-z0-9_.-]{{0,31}}$）")
        hwics_path.unlink(missing_ok=True)
        return

    try:
        step("预检", detail=str(hwics_path.name))
        _zip_precheck(hwics_path)                                        # D17
        sha = bundles.file_sha256(hwics_path)                            # 追溯元信息
        step("预检", "done", "归档结构/哈希 OK")

        tmp_out = bundles.tmp_bundle_dir(nf, version)
        if tmp_out.exists():
            shutil.rmtree(tmp_out)
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        exp = _load_exporter()
        convert_fail: list = []
        try:
            with tempfile.TemporaryDirectory(prefix=".pdoc_", dir=str(config.DATA_DIR)) as td:
                up = Path(td) / hwics_path.name
                shutil.move(str(hwics_path), str(up))
                extracted = exp.extract_hdx_file(str(up))  # html 解到 td 内 → 随 td 删除
                # D14：版本一致性（抽目录名版本 vs 表单；不一致即阻断，防止版本分裂）
                hint = _extract_version_hint(Path(extracted))
                if hint and hint != version:
                    raise ValueError(
                        f"归档版本为 {hint}，与填写的 {version} 不符——请用版本 {hint} 重新上传")
                step("解压导出", "done", f"html 就绪（版本识别 {hint or '未识别'}）")
                step("转换 md")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):  # 捕获 exporter 逐文件失败行（长路径等）
                    exp.main_from_extracted(extracted, str(tmp_out))
                convert_fail = [ln for ln in buf.getvalue().splitlines()
                                if ln.startswith("转换失败")][:20]
                warnings.extend(convert_fail)
                jobs.update_job(job_id, warnings=list(warnings))
        finally:
            hwics_path.unlink(missing_ok=True)

        md_count = sum(1 for _ in tmp_out.rglob("*.md"))
        step("转换 md", "done", f"md {md_count} 篇"
             + (f"；⚠ {len(convert_fail)} 篇转换失败（多为超长路径，详见警告）" if convert_fail else ""))

        step("留存登记")
        meta = {
            "nf": nf, "version": version, "status": "done",
            "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "uploaded_by": uploaded_by,
            "source_name": hwics_path.name, "source_sha256": sha,
            "exporter": "product_doc_md_exporter_optimized:" + bundles.file_sha256(
                HERE / "exporter.py")[:8],
            "md_count": md_count, "convert_failed": len(convert_fail),
            "mode_id": "",
        }
        bundles.write_meta(tmp_out, meta)
        bundles.atomic_replace(nf, version, tmp_out)                    # D10：成功才替换
        step("留存登记", "done", f"output/{nf}_{version}/（旧包已进回收站如有）")

        jobs.update_job(job_id, status="done",
                        result={"md_count": md_count, "convert_failed": len(convert_fail),
                                "bundle": f"{nf}_{version}"},
                        added=md_count, warnings=warnings)
    except Exception as e:  # noqa: BLE001
        _fail(job_id, hwics_path if hwics_path.exists() else None, e)
        # 转换失败时清理半成品 tmp（正式包未动——原子替换语义）
        t = bundles.tmp_bundle_dir(nf, version)
        if t.exists():
            shutil.rmtree(t, ignore_errors=True)


# ---------- 步骤② 图谱挖掘 ----------

def run_mine(job_id: str, nf: str, version: str, mode_id: str,
             selected_dirs: dict, scope: list, force: bool) -> None:
    """后台执行体：门槛校验 → 目录校验 → 依赖强制 → force 清理（按勾选层）→
    按模式构建器调度 → two_pass 二遍 → rebuild → 四层摘要（D20）。"""
    steps: list = []
    warnings: list = []

    def step(name: str, status: str = "processing", detail: str = "") -> None:
        for s in steps:
            if s["name"] == name:
                s.update(status=status, detail=detail)
                break
        else:
            steps.append({"name": name, "status": status, "detail": detail})
        jobs.update_job(job_id, steps=list(steps))

    try:
        # 门槛（用户约束：解压完成才能挖）
        bundle = bundles.get_bundle(nf, version)
        if bundle is None:
            raise ValueError(f"产品文档包 {nf}_{version} 不存在——请先在上传页完成解压")
        if bundle["status"] != "done":
            raise ValueError(f"包 {nf}_{version} 状态为 {bundle['status']}，未就绪")

        mode = modes_reg.get_mode(mode_id)
        if mode is None:
            raise ValueError(f"解析模式不存在: {mode_id}（可选 {list(modes_reg.MODES)}）")

        step("校验", detail=f"{mode.name} · 范围 {'+'.join(scope)}")
        root = bundles.bundle_dir(nf, version)
        dirs = validate_selected_dirs(root, selected_dirs)               # D1 纵深
        final_scope, added = expand_scope(scope, mode, nf, version)      # 依赖强制
        if added:
            warnings.extend(added)
            jobs.update_job(job_id, warnings=list(warnings))
        step("校验", "done", f"范围 {final_scope}" + ("；依赖已自动补选" if added else ""))

        # force：只清勾选层（依赖强制后的 final）
        if force:
            step("覆盖清理")
            removed = 0
            for layer in final_scope:
                d = config.ASSETS_DIR / layer / nf / version
                if d.exists():
                    removed += sum(1 for _ in d.rglob("*.md"))
                    shutil.rmtree(d)
            step("覆盖清理", "done", f"已清理旧资产 {removed} 个 md")

        counts: dict[str, int] = {}

        def run_builder(b: "modes_reg.Builder", label: str) -> None:
            step(label)
            args: list = ["--nf", nf, "--version", version, "--storage", config.ASSETS_DIR]
            for role, flags in (b.src_args or {}).items():
                if role in dirs:
                    for f in flags:
                        args += [f, dirs[role]]
            _run(HERE / b.script, *args, job_id=job_id)
            m = _manifest(b.layer, nf, version)
            counts[b.layer] = m.get(_COUNT_KEY.get(b.layer, ""), 0) or 0
            step(label, "done", f"{b.layer} {counts[b.layer]} 个"
                 + ("" if m else "；⚠ manifest 缺失"))                   # D20
            if not m:
                warnings.append(f"{b.layer} 构建后 manifest 缺失（计数未知，请核查）")
                jobs.update_job(job_id, warnings=list(warnings))

        for b in mode.builders:
            if b.layer in final_scope:
                run_builder(b, f"构建 {b.layer}")

        # D5 修复：Feature 重建后 Command 层特性引用此前被剥（feature_codes 空）→
        # two_pass 模式第二遍补 Command/ConfigObject（幂等）
        if mode.two_pass and "Feature" in final_scope and "Command" in final_scope:
            for b in mode.builders:
                if b.layer in ("Command", "ConfigObject") and b.layer in final_scope:
                    run_builder(b, f"第二遍 {b.layer}（补特性引用）")

        # 增量索引（与 fs 写端点同一套 reindex 语义）：只重索引本次勾选层目录 +
        # 清理前缀下已消失的旧文件（force 清理产生的空洞）——秒级、规模无关
        step("增量索引")
        from ..service import get_service, import_lock
        with import_lock:
            ix = get_service().reindex_prefixes(
                [f"{layer}/{nf}/{version}" for layer in final_scope])
        step("增量索引", "done",
             f"重索引 {ix['indexed']} / 清理 {ix['removed']}（增量，秒级）")

        # 更新包元信息（记录最近挖掘模式）
        meta = bundles.read_meta(bundles.bundle_dir(nf, version)) or {}
        meta["mode_id"] = mode.id
        meta["mined_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        bundles.write_meta(bundles.bundle_dir(nf, version), meta)

        jobs.update_job(job_id, status="done",
                        result={"layers": counts, "total": sum(counts.values()),
                                "bundle": f"{nf}_{version}", "mode": mode.name},
                        added=sum(counts.values()), warnings=warnings)
    except Exception as e:  # noqa: BLE001
        _fail(job_id, None, e)


_COUNT_KEY = {"Command": "command_count", "ConfigObject": "object_count",
              "License": "license_count", "Feature": "feature_count"}


def _manifest(layer: str, nf: str, version: str) -> dict:
    p = config.ASSETS_DIR / layer / nf / version / "_build_manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
