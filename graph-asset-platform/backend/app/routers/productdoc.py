"""productdoc router：两步流水线端点（上传页签三模式的后两模式）。

步骤① ``POST /import/product-doc``：上传 .hwics → **只解压转换留存**（output 包）。
步骤② **抽取任务**（2026-08-26 任务化+入图闸门重构）：
- ``GET /import/extractors``：抽取器下拉（注册表枚举，含 needs/roles）；
- ``GET /import/target-assets``：目标 (nf,version) 四层资产存在性（依赖检查 UI）；
- ``GET /import/bundles[...]``：包列表 / 包内目录定位（按目标网元名匹配）；
- ``POST /import/extract``：发起任务（依赖**阻断** 400 / 同目标 awaiting 409）→
  后台沙箱构建 → awaiting；
- ``POST /import/extract/{job}/confirm|cancel``：闸门三选（覆盖/只新增/撤销）；
- ``POST /import/extract/{job}/revert``：按任务移除本次产出（sha 守卫）；
- jobs 列表/详情/删除。

权限：中间件门控 upload（/api/v1/import*，=上传页签）；写端点均**二次校验
assets**（解压写 output 属数据目录、抽取/闸门/回退直接写资产库——与既有纵深一致）。
安全底线（评审清单 2026-08-19 沿用）：D1 nf/version 白名单；D4 流式落盘+2GB 上限；
D6 各类任务互斥锁（检查→登记原子化）。
"""
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from .. import config, jobs
from ..pipeline import bundles, gate
from ..pipeline import extractors as extractors_reg
from ..pipeline.runner import locate_candidates, run_extract, run_mine
from ..repos import extract_files_repo
from ..telemetry.recorder import record
from ..users.service import check_perm

router = APIRouter()

_ALLOWED_UPLOAD_SUFFIXES = {".hwics", ".hdx", ".zip"}
_MAX_UPLOAD_BYTES = 2 * 1024 ** 3   # 2GB（D4；真实归档实测 277MB）
_CHUNK = 8 * 1024 * 1024


def _require_assets(request: Request) -> None:
    """写数据/资产库：二次校验 can_assets（中间件已验 upload）。"""
    user = getattr(request.state, "user_obj", None)
    if not user or not check_perm(user, "assets"):
        raise HTTPException(status_code=403, detail="需要资产权限（can_assets）")


def _check_names(nf: str, version: str) -> None:
    """D1：nf/version 白名单（拼 output/assets 路径前的第一道闸）。"""
    if not bundles.is_valid_name(nf) or not bundles.is_valid_name(version):
        raise HTTPException(
            status_code=400,
            detail=f"非法网元/版本命名：nf={nf!r} version={version!r}"
                   f"（仅允许字母数字 _ . -，长度≤32）")


# ---------- 步骤①：上传解压 ----------

@router.post("/import/product-doc")
async def upload_product_doc(
    request: Request,
    background: BackgroundTasks,
    nf: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
):
    """上传产品文档归档 → 异步**解压转换留存**（不构建；抽取走 /import/extract）。"""
    nf, version = nf.strip(), version.strip()
    _check_names(nf, version)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"仅支持产品文档归档（{'/'.join(sorted(_ALLOWED_UPLOAD_SUFFIXES))}）")
    _require_assets(request)

    if not jobs.acquire_mutex("product_doc_extract"):  # D6：同类单任务
        raise HTTPException(status_code=409, detail="已有解压任务在跑，完成后再试")
    try:
        # D4：流式落盘（8MB 分块）+ 2GB 上限；放 DATA_DIR 同盘（同盘 move 瞬时，
        # 且规避 exporter 跨盘 relpath——见 runner 注释）
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".pdoc_up_", suffix=suffix or ".hwics",
                                   dir=str(config.DATA_DIR))
        total = 0
        try:
            with os.fdopen(fd, "wb") as f:
                while True:
                    chunk = await file.read(_CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > _MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=f"文件超过上限 {_MAX_UPLOAD_BYTES // 1024 // 1024 // 1024}GB")
                    f.write(chunk)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise

        job = jobs.create_job(kind="product_doc_extract", nf=nf, version=version)
        background.add_task(_run_extract_and_release, job.job_id, Path(tmp), nf, version,
                            getattr(request.state, "user", ""))
    except Exception:
        jobs.release_mutex("product_doc_extract")
        raise
    record("/import/product-doc", f"{nf}@{version}", "", user=request.state.user,
           caller=request.state.caller, level="object",
           operator=getattr(request.state, "operator", ""))
    return {"job_id": job.job_id, "nf": nf, "version": version, "size": total}


def _run_extract_and_release(job_id: str, tmp: Path, nf: str, version: str, by: str) -> None:
    """后台包装：执行完（成败皆）释放该类互斥锁。"""
    try:
        run_extract(job_id, tmp, nf, version, uploaded_by=by)
    finally:
        jobs.release_mutex("product_doc_extract")


# ---------- 步骤②：抽取任务（沙箱→闸门） ----------

@router.get("/import/extractors")
def list_extractors():
    """抽取器下拉（注册表枚举；新抽取器注册即出现）。needs=阻断依赖层。"""
    return extractors_reg.list_extractors()


@router.get("/import/target-assets")
def target_assets(nf: str, version: str, request: Request):
    """目标 (nf,version) 四层资产存在性——前端实时依赖检查（缺层禁提交）。"""
    _check_names(nf, version)
    _require_assets(request)
    return bundles.assets_flags(nf, version)


@router.get("/import/bundles")
def list_bundles():
    """已解压产品文档包列表（抽取页数据源；含 legacy 旧格式）。"""
    return bundles.list_bundles()


@router.get("/import/bundles/{nf}/{version}/locate")
def locate(nf: str, version: str, request: Request,
           extractor: str = "cmd", target_nf: str = ""):
    """包内源目录定位：自动推荐 + 全部候选（用户确认/改选，防猜错）。
    target_nf=**目标网元**（默认同包名）——逻辑网元名与包名不同时仍能严格匹配。"""
    _check_names(nf, version)
    _require_assets(request)
    bundle = bundles.get_bundle(nf, version)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"产品文档包不存在: {nf}_{version}")
    x = extractors_reg.get_extractor(extractor)
    if x is None:
        raise HTTPException(status_code=400, detail=f"抽取器不存在: {extractor}")
    return locate_candidates(bundles.bundle_dir(nf, version), x,
                             (target_nf or nf).strip())


class ExtractIn(BaseModel):
    bundle_nf: str
    bundle_version: str
    target_nf: str
    target_version: str
    extractor: str
    # 角色→包内相对路径（来自 locate 候选/逐层浏览）。mml 支持 list（多目录，
    # 构建器要求全部目录单次调用传入——跨批参见边才不丢）
    dirs: dict[str, "str | list[str]"] = {}


@router.post("/import/extract")
def extract(req: ExtractIn, request: Request, background: BackgroundTasks):
    """发起抽取任务：依赖**阻断**（缺层 400 报明细，不自动补齐——人来编排
    「先命令后特性」）；**全流程串行**（2026-08-27 用户决策）：存在未完结抽取
    任务（抽取中/待确认/入库中）即 409——上一任务入库完结或撤销后再发下一个。"""
    bnf, bver = req.bundle_nf.strip(), req.bundle_version.strip()
    tnf, tver = req.target_nf.strip(), req.target_version.strip()
    _check_names(bnf, bver)
    _check_names(tnf, tver)
    _require_assets(request)

    x = extractors_reg.get_extractor(req.extractor)
    if x is None:
        raise HTTPException(status_code=400, detail=f"抽取器不存在: {req.extractor}")
    bundle = bundles.get_bundle(bnf, bver)
    if bundle is None:
        raise HTTPException(status_code=404,
                            detail=f"产品文档包 {bnf}_{bver} 不存在——请先在上传页完成解压")
    if bundle["status"] != "done":
        raise HTTPException(status_code=400,
                            detail=f"包 {bnf}_{bver} 未解压完成（{bundle['status']}）")

    # 依赖阻断（服务端权威；前端同规则预检禁提交）
    missing = [L for L in x.needs
               if not bundles.assets_flags(tnf, tver).get(L)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"message": f"目标 {tnf}@{tver} 缺少依赖层资产: {'+'.join(missing)}"
                              f"——请先完成对应抽取任务（本任务不自动补齐依赖）",
                    "missing": missing})

    def _role_vals(role: str) -> list:
        v = req.dirs.get(role) or []
        return v if isinstance(v, list) else [v]
    lack_roles = [r for r in x.required_roles
                  if not [p for p in _role_vals(r) if p and p.strip()]]
    if lack_roles:
        raise HTTPException(
            status_code=400,
            detail=f"抽取器「{x.name}」必须选择源目录角色: {'、'.join(lack_roles)}")

    clash = jobs.pending_for("product_doc_mine")
    if clash is not None:
        state = "待入库确认" if clash.status == "awaiting" else "执行中（抽取/入库/回退）"
        raise HTTPException(
            status_code=409,
            detail={"message": f"存在未完结的抽取任务（{state} · {clash.job_id}）"
                              f"——全流程串行：先完成确认/撤销或等其结束",
                    "job_id": clash.job_id})
    if not jobs.acquire_mutex("product_doc_mine"):
        running = jobs.has_processing("product_doc_mine")
        raise HTTPException(
            status_code=409,
            detail={"message": "已有抽取任务在跑"
                    + (f"（{running.nf} {running.version} · {running.job_id}）" if running else ""),
                    "job_id": running.job_id if running else ""})
    try:
        job = jobs.create_job(kind="product_doc_mine", nf=tnf, version=tver)
        spec = {"bundle_nf": bnf, "bundle_version": bver,
                "target_nf": tnf, "target_version": tver,
                "extractor": req.extractor, "dirs": dict(req.dirs)}
        background.add_task(_run_mine_and_release, job.job_id, spec)
    except Exception:
        jobs.release_mutex("product_doc_mine")
        raise
    record("/import/extract", f"{tnf}@{tver}", "", user=request.state.user,
           caller=request.state.caller, level="object",
           operator=getattr(request.state, "operator", ""))
    return {"job_id": job.job_id, "target_nf": tnf, "target_version": tver,
            "extractor": req.extractor}


def _run_mine_and_release(job_id: str, spec: dict) -> None:
    """后台包装：沙箱构建→awaiting 后即释放互斥（闸门等待不占锁；确认/撤销/
    回退端点各自短取锁）。"""
    try:
        run_mine(job_id, spec)
    finally:
        jobs.release_mutex("product_doc_mine")


def _get_mine_job_or_404(job_id: str):
    j = jobs.get_job(job_id)
    if j is None or j.kind != "product_doc_mine":
        raise HTTPException(status_code=404, detail=f"抽取任务不存在: {job_id}")
    return j


class ConfirmIn(BaseModel):
    action: str  # overwrite | new_only


@router.post("/import/extract/{job_id}/confirm")
def confirm(job_id: str, req: ConfirmIn, request: Request, background: BackgroundTasks):
    """闸门确认——**后台异步执行**（2026-08-27 用户反馈改版：不阻塞前台，同步
    端点在千文件拷贝+重索引期间挂着 HTTP 请求易超时）。立即返回，任务转
    processing(stage=applying)，完成转 done。执行失败自动回 awaiting 可重试/
    撤销（清单先行设计使重试安全）。action=overwrite|new_only。"""
    _require_assets(request)
    if req.action not in ("overwrite", "new_only"):
        raise HTTPException(status_code=400, detail="action 仅支持 overwrite | new_only")
    j = _get_mine_job_or_404(job_id)
    if j.status != "awaiting":
        raise HTTPException(status_code=409,
                            detail=f"任务状态为 {j.status}，仅待确认（awaiting）任务可确认")
    if not jobs.acquire_mutex("product_doc_mine"):
        raise HTTPException(status_code=409, detail="已有抽取任务在执行（抽取/入库/回退），稍后再试")
    try:
        steps = list(j.steps or []) + [{"name": "入库", "status": "processing", "detail": ""}]
        jobs.update_job(job_id, status="processing",
                        result={**(j.result or {}), "stage": "applying"},
                        steps=steps)
        background.add_task(_apply_and_release, job_id, req.action)
    except Exception:
        jobs.release_mutex("product_doc_mine")
        raise
    record("/import/extract/confirm", job_id, "", user=request.state.user,
           caller=request.state.caller, level="object",
           operator=getattr(request.state, "operator", ""))
    return {"ok": True, "job_id": job_id, "stage": "applying"}


def _apply_and_release(job_id: str, action: str) -> None:
    """后台包装：执行入库（成败皆释放互斥）。失败回 awaiting（清单先行+sha 守卫
    使重试自愈；亦可撤销——cancel 会按清单回滚已落盘部分）。"""
    try:
        gate.apply_gate(job_id, action)
    except Exception as e:  # noqa: BLE001
        j = jobs.get_job(job_id)
        res = dict((j.result if j else None) or {})
        res["confirm_error"] = str(e)
        jobs.update_job(job_id, status="awaiting", result=res,
                        warnings=[*((j.warnings if j else None) or []),
                                  f"入库执行失败：{e}——可重试确认或撤销"])
    finally:
        jobs.release_mutex("product_doc_mine")


@router.post("/import/extract/{job_id}/cancel")
def cancel(job_id: str, request: Request):
    """闸门撤销：沙箱全删（含按清单回滚失败确认已落盘的部分），任务终态 cancelled。
    同步端点（正常秒级——仅清理；部分回滚仅在确认失败后才发生）。"""
    _require_assets(request)
    j = _get_mine_job_or_404(job_id)
    if j.status != "awaiting":
        raise HTTPException(status_code=409,
                            detail=f"任务状态为 {j.status}，仅待确认（awaiting）任务可撤销")
    if not jobs.acquire_mutex("product_doc_mine"):
        raise HTTPException(status_code=409, detail="已有抽取任务在执行，稍后撤销")
    try:
        gate.cancel_gate(job_id)
    finally:
        jobs.release_mutex("product_doc_mine")
    record("/import/extract/cancel", job_id, "", user=request.state.user,
           caller=request.state.caller, level="object",
           operator=getattr(request.state, "operator", ""))
    return {"ok": True, "job_id": job_id}


@router.post("/import/extract/{job_id}/revert")
def revert(job_id: str, request: Request, background: BackgroundTasks):
    """按任务移除本次抽取内容——**后台异步执行**（同确认）：新增→软删进回收站；
    覆盖→还原旧版备份；sha 守卫跳过已被后续任务改动的文件。失败回 done 带告警
    可重发起（每文件守卫使重发起安全）。"""
    _require_assets(request)
    j = _get_mine_job_or_404(job_id)
    if j.status != "done":
        raise HTTPException(status_code=400,
                            detail=f"仅已完成任务可回退（当前 {j.status}）")
    if (j.result or {}).get("reverted_at"):
        raise HTTPException(status_code=400, detail="该任务已回退过")
    if extract_files_repo.count_for_job(_svc_db(), job_id) == 0:
        raise HTTPException(status_code=400,
                            detail="该任务无产物清单（旧任务或空产出），无法回退")
    if not jobs.acquire_mutex("product_doc_mine"):
        raise HTTPException(status_code=409, detail="已有抽取任务在执行，稍后回退")
    try:
        steps = list(j.steps or []) + [{"name": "回退", "status": "processing", "detail": ""}]
        jobs.update_job(job_id, status="processing",
                        result={**(j.result or {}), "stage": "reverting"},
                        steps=steps)
        background.add_task(_revert_and_release, job_id,
                            getattr(request.state, "user", ""))
    except Exception:
        jobs.release_mutex("product_doc_mine")
        raise
    record("/import/extract/revert", job_id, "", user=request.state.user,
           caller=request.state.caller, level="object",
           operator=getattr(request.state, "operator", ""))
    return {"ok": True, "job_id": job_id, "stage": "reverting"}


def _revert_and_release(job_id: str, by: str) -> None:
    """后台包装：执行回退（成败皆释放互斥）。失败回 done 带告警。"""
    try:
        gate.revert_job(job_id, deleted_by=by)
    except Exception as e:  # noqa: BLE001
        j = jobs.get_job(job_id)
        res = dict((j.result if j else None) or {})
        res["revert_error"] = str(e)
        jobs.update_job(job_id, status="done", result=res,
                        warnings=[*((j.warnings if j else None) or []),
                                  f"回退执行失败：{e}——可重新发起「移除产出」"])
    finally:
        jobs.release_mutex("product_doc_mine")


def _svc_db():
    from ..service import get_service
    return get_service().db


# ---------- 任务历史 ----------

@router.get("/import/jobs")
def list_jobs():
    """历史任务（DB 持久化，跨重启；按 started_at 倒序，默认 100 条）。"""
    return [j.summary() for j in jobs.list_jobs()]


@router.get("/import/jobs/{job_id}")
def get_job(job_id: str):
    j = jobs.get_job(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail=f"job 不存在: {job_id}")
    return j.summary()


@router.delete("/import/jobs/{job_id}")
def delete_job(job_id: str, request: Request):
    """删除历史任务（完成/失败/已撤销可删；进行中/待确认不可删——用户决策）。
    删除抽取任务连带清沙箱备份与产物清单（**回退权随之丧失**）。"""
    _require_assets(request)
    j = jobs.get_job(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail=f"job 不存在: {job_id}")
    if j.status in ("processing", "awaiting"):
        state = "解析进行中" if j.status == "processing" else "待闸门确认"
        raise HTTPException(status_code=400, detail=f"任务{state}，不允许删除")
    if not jobs.delete_job(job_id):
        raise HTTPException(status_code=500, detail="删除失败")
    if j.kind == "product_doc_mine":
        # 与 confirm/revert 互斥（评审修复 2026-08-26）：防止回退进行中清掉 originals
        if not jobs.acquire_mutex("product_doc_mine"):
            raise HTTPException(status_code=409, detail="抽取任务闸门操作进行中，稍后删除")
        try:
            gate.cleanup(job_id)  # originals 备份（回退权丧失——UI 删除确认提示）
            try:
                extract_files_repo.delete_for_job(_svc_db(), job_id)
                _svc_db().commit()
            except Exception as e:  # noqa: BLE001 清单清理失败不阻断删任务，但留痕
                print(f"[jobs] 删除任务 {job_id} 时清理产物清单失败: {e}", flush=True)
        finally:
            jobs.release_mutex("product_doc_mine")
    record("/import/jobs/delete", job_id, "", user=request.state.user,
           caller=request.state.caller, level="object",
           operator=getattr(request.state, "operator", ""))
    return {"ok": True, "job_id": job_id}
