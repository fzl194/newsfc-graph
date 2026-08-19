"""productdoc router：两步流水线端点（上传页签三模式的后两模式）。

步骤① ``POST /import/product-doc``：上传 .hwics → **只解压转换留存**（output 包）。
步骤② ``POST /import/mine``：从已解压包挖掘图谱资产（模式+目录+范围）。
辅助：``GET /import/modes``（模式下拉）、``GET /import/bundles``（包列表）、
``GET /import/bundles/{nf}/{version}/locate``（定位推荐+候选）、
jobs 列表/详情/删除。

权限：中间件门控 upload（/api/v1/import*，=上传页签）；两类任务均**二次校验
assets**（解压写 output 属数据目录、挖掘直接写资产库——与既有纵深防御一致）。
安全底线（评审清单 2026-08-19 批准）：D1 nf/version 白名单；D4 流式落盘+2GB 上限；
D6 各类任务互斥锁（检查→登记原子化）。
"""
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from .. import config, jobs
from ..pipeline import bundles, modes as modes_reg
from ..pipeline.runner import (
    expand_scope, locate_candidates, run_extract, run_mine)
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
    """上传产品文档归档 → 异步**解压转换留存**（不构建；构建走 /import/mine）。"""
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


# ---------- 步骤②：图谱挖掘 ----------

@router.get("/import/modes")
def list_modes():
    """解析模式下拉（注册表枚举；新模式注册即出现）。"""
    return modes_reg.list_modes()


@router.get("/import/bundles")
def list_bundles():
    """已解压产品文档包列表（抽取页数据源；含 legacy 旧格式）。"""
    return bundles.list_bundles()


@router.get("/import/bundles/{nf}/{version}/locate")
def locate(nf: str, version: str, request: Request, mode: str = "5gc"):
    """包内源目录定位：自动推荐 + 全部候选（用户确认/改选，防猜错）。"""
    _check_names(nf, version)
    _require_assets(request)
    bundle = bundles.get_bundle(nf, version)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"产品文档包不存在: {nf}_{version}")
    m = modes_reg.get_mode(mode)
    if m is None:
        raise HTTPException(status_code=400, detail=f"解析模式不存在: {mode}")
    return locate_candidates(bundles.bundle_dir(nf, version), m, nf)


class MineIn(BaseModel):
    nf: str
    version: str
    mode: str = "5gc"
    dirs: dict[str, str] = {}                 # 角色→包内相对路径（来自 locate 候选）
    scope: list[str] = ["Command", "ConfigObject", "License", "Feature"]
    force: bool = False


@router.post("/import/mine")
def mine(req: MineIn, request: Request, background: BackgroundTasks):
    """从已解压包挖掘。门槛：包必须解压完成（用户约束 2026-08-19）；
    依赖强制：勾选层的 needs 层资产不存在时自动补选（响应带 scope + notes）。"""
    nf, version = req.nf.strip(), req.version.strip()
    _check_names(nf, version)
    _require_assets(request)
    mode_id = req.mode or "5gc"
    scope = req.scope or ["Command", "ConfigObject", "License", "Feature"]
    dirs = req.dirs or {}
    force = req.force

    m = modes_reg.get_mode(mode_id)
    if m is None:
        raise HTTPException(status_code=400,
                            detail=f"解析模式不存在: {mode_id}")
    valid_layers = {b.layer for b in m.builders}
    bad = [s for s in scope if s not in valid_layers]
    if bad:
        raise HTTPException(status_code=400, detail=f"无效抽取范围: {bad}（可选 {sorted(valid_layers)}）")
    bundle = bundles.get_bundle(nf, version)
    if bundle is None:
        raise HTTPException(status_code=404,
                            detail=f"产品文档包 {nf}_{version} 不存在——请先在上传页完成解压")
    if bundle["status"] != "done":
        raise HTTPException(status_code=400,
                            detail=f"包 {nf}_{version} 未解压完成（{bundle['status']}）")

    # 依赖强制（服务端权威；前端同规则锁 UI）
    final_scope, added_notes = expand_scope(scope, m, nf, version)

    if not jobs.acquire_mutex("product_doc_mine"):
        running = jobs.has_processing("product_doc_mine")
        raise HTTPException(
            status_code=409,
            detail={"message": "已有挖掘任务在跑"
                    + (f"（{running.nf} {running.version} · {running.job_id}）" if running else ""),
                    "job_id": running.job_id if running else ""})
    try:
        job = jobs.create_job(kind="product_doc_mine", nf=nf, version=version)
        background.add_task(_run_mine_and_release, job.job_id, nf, version,
                            mode_id, dirs, final_scope, force)
    except Exception:
        jobs.release_mutex("product_doc_mine")
        raise
    record("/import/mine", f"{nf}@{version}", "", user=request.state.user,
           caller=request.state.caller, level="object",
           operator=getattr(request.state, "operator", ""))
    return {"job_id": job.job_id, "scope": final_scope, "notes": added_notes,
            "force": force}


def _run_mine_and_release(job_id, nf, version, mode_id, dirs, scope, force) -> None:
    try:
        run_mine(job_id, nf, version, mode_id, dirs, scope, force)
    finally:
        jobs.release_mutex("product_doc_mine")


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
    """删除历史任务（完成/失败可删；解析进行中不可删——用户决策）。"""
    _require_assets(request)
    j = jobs.get_job(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail=f"job 不存在: {job_id}")
    if j.status == "processing":
        raise HTTPException(status_code=400, detail="任务解析进行中，不允许删除")
    if not jobs.delete_job(job_id):
        raise HTTPException(status_code=500, detail="删除失败")
    record("/import/jobs/delete", job_id, "", user=request.state.user,
           caller=request.state.caller, level="object",
           operator=getattr(request.state, "operator", ""))
    return {"ok": True, "job_id": job_id}
