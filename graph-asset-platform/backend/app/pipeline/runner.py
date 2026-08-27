"""两步流水线编排（2026-08-26 抽取任务化重构，用户决策）：

- 步骤① ``run_extract``（上传页·产品文档解压）：.hwics → 解压（html 临时态）→
  转 md → ``output/{nf}_{version}/`` 留存（**只留 md + bundle.json**，html/原件随
  临时目录删除；原子替换失败不动旧包）。包的 nf/version=物理网元基本信息，
  仅作管理与抽取默认值。
- 步骤② ``run_mine``（上传页·抽取任务）：选包 + **目标网元/版本**（可改——图谱
  逻辑网元名由用户定）+ 单抽取器 → 依赖**阻断**校验 → 沙箱构建（脚本写
  ``.extract_gate/{job_id}/storage/``，预拷目标现有层供跨层读；feature 自动重跑
  命令构建器补引用）→ diff 报告 → ``awaiting`` 等闸门三选（``pipeline/gate.py``：
  覆盖/只新增/撤销 + 按任务回退）。正式资产在 confirm 前零改动。

安全底线（评审清单 2026-08-18/19 沿用）：D1 命名白名单+目录祖先校验；D14 版本
不一致阻断（解压侧）；D16 子进程 PID 记录（sweep 终止）；D17 zip namelist 预检；
D20 摘要=层计数之和+manifest 缺失告警。
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
from ..config import win_long as _win_long  # 超长路径（>260）fs 操作 helper
from . import bundles, gate
from . import extractors as extractors_reg

HERE = Path(__file__).resolve().parent

# 上传上限（router 侧强制，D4）
_UPLOAD_MAX_BYTES = 2 * 1024 ** 3  # 2GB


# ---------- 公共 ----------

def _load_exporter():
    """按路径加载拷贝版 exporter（不污染 sys.path；依赖 chardet/bs4）。
    **必须注册进 sys.modules**：exporter 顶部的 @dataclass 按 __module__ 名查
    sys.modules 解析字符串注解，未注册会 AttributeError: NoneType.__dict__。"""
    spec = importlib.util.spec_from_file_location("pipeline_exporter", HERE / "product_doc_md_exporter_optimized.py")
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


# ---------- 目录定位（推荐 + 候选，人工确认；架构性缓解 D11/D1） ----------

def locate_candidates(export_root: Path, extractor: "extractors_reg.ExtractorDef", nf: str) -> dict:
    """按抽取器关键词扫描包内源目录候选（nf=**目标网元**，非包名——逻辑网元名
    由用户抽取时输入）。

    每角色返回 {recommended: 相对路径|None, candidates: [相对路径], note}；
    recommended 仅供前端默认选中——最终由用户从 candidates 改选（防猜错）。
    """
    root = export_root.resolve()
    # 枚举/rel 一致用长前缀根：普通 rglob 对 >260 目录静默漏扫（定位候选缺失）；
    # relative_to 要求两侧前缀一致，故 rel 也基于 root_long
    root_long = _win_long(root)
    out: dict[str, dict] = {}
    nf_cf = nf.casefold()
    for role, kws in extractor.keywords.items():
        kw_cfs = [k.casefold() for k in kws]
        hits: dict[Path, bool] = {}  # path -> strict?
        for p in root_long.rglob("*"):
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
        rel = lambda p: p.relative_to(root_long).as_posix()  # noqa: E731
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
    """用户提交的目录选择校验：必须在包内且真实存在（防注入；D1 纵深）。

    角色值支持 str | list[str]（命令角色可多目录——新产品文档命令拆分多分册，
    且全部目录须单次调用传入构建器）；返回统一 dict[role, list[Path]]。
    """
    root = bundle_root.resolve()
    out: dict[str, list[Path]] = {}
    for role, val in selected.items():
        vals = val if isinstance(val, list) else [val]
        if role not in out:
            out[role] = []
        for rel in vals:
            p = (root / rel).resolve()
            if p == root:
                raise ValueError(f"目录不能是包根: {role}={rel}")
            if p != root and root not in p.parents:
                raise ValueError(f"目录越界: {role}={rel}")
            # is_dir 用长前缀：>260 的深目录普通 is_dir 静默 False（误报不存在）
            if not _win_long(p).is_dir():
                raise ValueError(f"目录不存在: {role}={rel}")
            if p not in out[role]:
                out[role].append(p)
    return out


def layer_assets_exist(layer: str, nf: str, version: str) -> bool:
    # 长前缀：>260 的层目录普通 rglob 静默漏扫 → 依赖阻断误报缺层（评审修复 2026-08-26）
    d = _win_long(config.ASSETS_DIR / layer / nf / version)
    return d.is_dir() and any(d.rglob("*.md"))


def missing_deps(extractor: "extractors_reg.ExtractorDef", nf: str, version: str) -> list:
    """阻断式依赖检查：目标 (nf,version) 槽位缺的层（用户决策 2026-08-26——
    不自动补齐，人来编排「先命令后特性」）。"""
    return [L for L in extractor.needs if not layer_assets_exist(L, nf, version)]


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
            shutil.rmtree(str(_win_long(tmp_out)))
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        exp = _load_exporter()
        convert_fail: list = []
        # 手管临时目录（不用 TemporaryDirectory）：其 __exit__ 用**普通路径**
        # rmtree——>260 的解压产物（长前缀解压写的）删不掉 → rmdir 报
        # WinError 145「目录不是空的」，把已成功的解压任务标失败（2026-08-25
        # 内网现场）。清理必须走长前缀；ignore_errors 兜底，极端残留由启动
        # sweep_orphan_tmp（同为长前缀版）再扫。
        td = tempfile.mkdtemp(prefix=".pdoc_", dir=str(config.DATA_DIR))
        try:
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
            shutil.rmtree(str(_win_long(Path(td))), ignore_errors=True)

        # 枚举根用长前缀：普通路径 rglob 对 >260 的 md 静默漏扫（统计偏小）
        md_count = sum(1 for _ in _win_long(tmp_out).rglob("*.md"))
        step("转换 md", "done", f"md {md_count} 篇"
             + (f"；⚠ {len(convert_fail)} 篇转换失败（多为超长路径，详见警告）" if convert_fail else ""))

        step("留存登记")
        meta = {
            "nf": nf, "version": version, "status": "done",
            "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "uploaded_by": uploaded_by,
            "source_name": hwics_path.name, "source_sha256": sha,
            "exporter": "product_doc_md_exporter_optimized:" + bundles.file_sha256(
                HERE / "product_doc_md_exporter_optimized.py")[:8],
            "md_count": md_count, "convert_failed": len(convert_fail),
            "mode_id": "",
        }
        bundles.write_meta(tmp_out, meta)
        final_result = {
            "stage": "extract_finalizing", "md_count": md_count,
            "convert_failed": len(convert_fail), "bundle": f"{nf}_{version}",
            "source_sha256": sha,
        }
        # 原子替换前先落耐久 checkpoint；替换后若最终 done 写失败，
        # 可用 bundle.json.source_sha256 对账自动补终态。
        jobs.update_job(job_id, result=final_result, added=md_count, warnings=warnings)
        bundles.atomic_replace(nf, version, tmp_out)                    # D10：成功才替换
        step("留存登记", "done", f"output/{nf}_{version}/（旧包已进回收站如有）")

        jobs.update_job(job_id, status="done",
                        result={**final_result, "stage": "extracted"},
                        added=md_count, warnings=warnings)
    except jobs.JobPersistenceError:
        # 关键状态落库失败不得被业务失败分支覆写；交给包装器/对账。
        raise
    except Exception as e:  # noqa: BLE001
        _fail(job_id, hwics_path if hwics_path.exists() else None, e)
        # 转换失败时清理半成品 tmp（正式包未动——原子替换语义）
        t = bundles.tmp_bundle_dir(nf, version)
        if t.exists():
            shutil.rmtree(str(_win_long(t)), ignore_errors=True)


# ---------- 步骤② 抽取任务（沙箱构建 → 闸门） ----------

def find_last_cmd_dirs(nf: str, version: str) -> "dict | None":
    """最近一次成功 cmd 抽取任务记录的源目录（feature 自动重跑命令构建器用）。
    排除已回退任务；无记录返回 None（旧数据/首抽——调用方 warn+skip）。"""
    for j in jobs.recent_done("product_doc_mine"):
        r = j.result or {}
        if (r.get("script") == "cmd" and r.get("target_nf") == nf
                and r.get("target_version") == version and not r.get("reverted_at")):
            d = r.get("dirs") or {}
            if d.get("mml"):
                return {"bundle_nf": r.get("bundle_nf", ""),
                        "bundle_version": r.get("bundle_version", ""), "dirs": d}
    return None


def _run_builder(job_id: str, b: "extractors_reg.Builder", dirs: dict,
                 nf: str, version: str, storage: Path) -> None:
    """跑单个构建器（规范拷贝件，CLI 编排）：--nf/--version 用**目标**网元，
    --storage 指向沙箱 assets 根。"""
    args: list = ["--nf", nf, "--version", version, "--storage", str(storage)]
    for role, flags in (b.src_args or {}).items():
        for v in dirs.get(role, []):          # 角色值可为多目录（mml 单次全量传入）
            for f in flags:
                args += [f, v]
    _run(HERE / b.script, *args, job_id=job_id)


def run_mine(job_id: str, spec: dict) -> None:
    """后台执行体（抽取任务化 2026-08-26）：

    spec = {bundle_nf, bundle_version, target_nf, target_version, extractor, dirs}。
    校验（包 done/依赖阻断/角色目录）→ 沙箱（预拷目标现有层）→ 主构建器 →
    feature 自动重跑命令构建器（two_pass 跨任务版，用最近成功 cmd 任务的目录）→
    diff 报告 → ``awaiting``（闸门三选走 routers 的 gate 端点；互斥随本函数返回释放）。
    """
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

    bundle_nf = spec.get("bundle_nf", "")
    bundle_version = spec.get("bundle_version", "")
    target_nf = spec.get("target_nf", "")
    target_version = spec.get("target_version", "")

    try:
        # 门槛（用户约束：解压完成才能抽）
        bundle = bundles.get_bundle(bundle_nf, bundle_version)
        if bundle is None:
            raise ValueError(f"产品文档包 {bundle_nf}_{bundle_version} 不存在——请先在上传页完成解压")
        if bundle["status"] != "done":
            raise ValueError(f"包 {bundle_nf}_{bundle_version} 状态为 {bundle['status']}，未就绪")

        ex = extractors_reg.get_extractor(spec.get("extractor", ""))
        if ex is None:
            raise ValueError(f"抽取器不存在: {spec.get('extractor')!r}"
                             f"（可选 {list(extractors_reg.EXTRACTORS)}）")

        step("校验", detail=f"{ex.name} · 目标 {target_nf}@{target_version}")
        dirs = validate_selected_dirs(bundles.bundle_dir(bundle_nf, bundle_version),
                                      spec.get("dirs") or {})            # D1 纵深
        for role in ex.required_roles:
            if not dirs.get(role):
                raise ValueError(f"抽取器「{ex.name}」必须选择源目录角色: {role}")
        # 依赖阻断（权威复检；router 入口已拦一道）
        missing = missing_deps(ex, target_nf, target_version)
        if missing:
            raise ValueError(f"目标 {target_nf}@{target_version} 缺少依赖层资产: "
                             f"{'+'.join(missing)}——请先完成对应抽取任务（不自动补齐）")
        step("校验", "done", f"{ex.name} · 目标 {target_nf}@{target_version}")

        # spec 早写进 result（崩溃可查 + 供 feature 重跑检索最近 cmd 任务）。
        # dirs 存包内相对路径（validate 时重解析重校验——随 DATA_DIR/包替换仍有效）
        bundle_root = bundles.bundle_dir(bundle_nf, bundle_version).resolve()
        rel_dirs = {role: [p.relative_to(bundle_root).as_posix() for p in ps]
                    for role, ps in dirs.items()}
        base_result = {
            "stage": "running", "script": ex.id, "script_name": ex.name,
            "bundle": f"{bundle_nf}_{bundle_version}",
            "bundle_nf": bundle_nf, "bundle_version": bundle_version,
            "target_nf": target_nf, "target_version": target_version,
            "dirs": rel_dirs,
        }
        jobs.update_job(job_id, result=base_result)

        # 沙箱：预拷 reads 并集 ∩ 目标已存在层（分次累积/跨层读闭环）
        step("沙箱准备")
        copy_set = sorted({L for b in (*ex.builders, *ex.rerun_after)
                           for L in b.reads})
        copied = gate.create_sandbox(job_id, copy_set, target_nf, target_version)
        step("沙箱准备", "done", (f"预拷 {len(copied)} 层（{'+'.join(copied)}）"
                                   if copied else "目标槽位为空，全新抽取"))

        storage = gate.gate_storage(job_id)
        written: list = []

        def run_builder(b: "extractors_reg.Builder", label: str, run_dirs: dict) -> None:
            step(label)
            _run_builder(job_id, b, run_dirs, target_nf, target_version, storage)
            if b.layer not in written:
                written.append(b.layer)
            step(label, "done", f"{b.layer} 构建 OK")

        for b in ex.builders:
            run_builder(b, f"构建 {b.layer}", dirs)

        # feature 自动重跑命令构建器（用户决策：保持 two_pass 语义不拆分）——
        # 命令 md 的特性引用只在 Feature 资产已存在时写入；feature 抽取后须
        # 用「最近一次成功 cmd 任务」的源目录重跑命令+配置对象补引用，其
        # Command/ConfigObject 文件变化进入闸门报告供审。
        if ex.rerun_after:
            step("重跑命令（补特性引用）")
            last = find_last_cmd_dirs(target_nf, target_version)
            if last is None:
                msg = (f"未找到 {target_nf}@{target_version} 的命令抽取任务记录"
                       f"（旧数据/首抽）——已跳过命令层特性引用修复，可手动重跑一次命令抽取")
                warnings.append(msg)
                jobs.update_job(job_id, warnings=list(warnings))
                step("重跑命令（补特性引用）", "done", "⚠ 跳过（无命令任务记录）")
            else:
                try:
                    last_dirs = validate_selected_dirs(
                        bundles.bundle_dir(last["bundle_nf"], last["bundle_version"]),
                        last["dirs"])
                    for b in ex.rerun_after:
                        run_builder(b, f"重跑 {b.layer}（补特性引用）", last_dirs)
                    step("重跑命令（补特性引用）", "done",
                         f"按最近 cmd 任务（{last['bundle_nf']}_{last['bundle_version']}）")
                except ValueError as e:
                    warnings.append(f"命令层特性引用修复跳过：{e}")
                    jobs.update_job(job_id, warnings=list(warnings))
                    step("重跑命令（补特性引用）", "done", f"⚠ 跳过（{e}）")

        step("差异报告")
        report = gate.diff_report(job_id, written, target_nf, target_version)
        step("差异报告", "done",
             f"新增 {report['new_total']} · 相同 {report['identical_total']} · 差异 {report['modified_total']}")

        ready_result = {**base_result, **report, "stage": "gate_ready"}
        # diff 已完成的耐久 checkpoint；后一笔 awaiting 失败可在线补齐。
        jobs.update_job(job_id, result=ready_result, warnings=list(warnings))
        jobs.update_job(job_id, status="awaiting",
                        result={**ready_result, "stage": "gate"},
                        warnings=list(warnings))
    except jobs.JobPersistenceError:
        raise
    except Exception as e:  # noqa: BLE001
        gate.cleanup(job_id)  # 失败即清沙箱（正式资产从未被碰）
        _fail(job_id, None, e)
