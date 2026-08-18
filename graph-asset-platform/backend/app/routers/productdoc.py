"""productdoc router：上传产品文档 .hwics → 异步构建四类图谱资产。

- ``POST /import/product-doc``：中间件门控 ``upload`` 权限（/api/v1/import*），此处再
  二次校验 ``assets``（构建写入资产库，与 /fs 写一致）。表单：nf / version / force /
  file(.hwics)。重复上传同 nf+version 默认 409（带已有计数），``force=true`` 覆盖重建。
  立即返回 job_id，后台线程执行 ``pipeline.runner``（分步进度）。
- ``GET /import/jobs`` / ``GET /import/jobs/{id}```：job 列表与详情（前端轮询）。

产物：assets/{Command,ConfigObject,License,Feature}/{nf}/{version}/（进图谱）+
output/{nf}_{version}/（原始导出 md，不进图谱，前端「原始产品文档」tab 浏览）。
"""
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile

from .. import jobs
from ..pipeline.runner import existing_layer_counts, run_product_doc_import
from ..users.service import check_perm
from ..telemetry.recorder import record

router = APIRouter()

_ALLOWED_UPLOAD_SUFFIXES = {".hwics", ".hdx", ".zip"}


def _require_assets(request: Request) -> None:
    """构建直接写资产库：与 /fs 写端点一致要求 can_assets（中间件已验 upload）。"""
    user = getattr(request.state, "user_obj", None)
    if not user or not check_perm(user, "assets"):
        raise HTTPException(status_code=403, detail="需要资产权限（can_assets）")


@router.post("/import/product-doc")
async def upload_product_doc(
    request: Request,
    background: BackgroundTasks,
    nf: str = Form(...),
    version: str = Form(...),
    force: bool = Form(False),
    file: UploadFile = File(...),
):
    nf, version = nf.strip(), version.strip()
    if not nf or not version:
        raise HTTPException(status_code=400, detail="nf 与 version 必填")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=400, detail=f"仅支持产品文档归档（{'/'.join(sorted(_ALLOWED_UPLOAD_SUFFIXES))}）")

    _require_assets(request)

    # 重复上传：默认拒 + 可选覆盖（用户决策 2026-08-18）
    existing = existing_layer_counts(nf, version)
    if existing and not force:
        raise HTTPException(
            status_code=409,
            detail={"message": f"网元 {nf} 版本 {version} 已有图谱资产，勾选「覆盖重建」后重试",
                    "existing": existing})

    # 上传落临时文件（runner 结束（成败皆）负责清理）
    data = await file.read()
    fd, tmp = tempfile.mkstemp(prefix="pdoc_up_", suffix=suffix or ".hwics")
    os.close(fd)
    try:
        Path(tmp).write_bytes(data)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise

    job = jobs.create_job(kind="product_doc", nf=nf, version=version)
    background.add_task(run_product_doc_import, job.job_id, Path(tmp), nf, version, force)
    record("/import/product-doc", f"{nf}@{version}", "", user=request.state.user,
           caller=request.state.caller, level="object",
           operator=getattr(request.state, "operator", ""))
    return {"job_id": job.job_id, "force": force, "existing": existing}


@router.get("/import/jobs")
def list_jobs():
    return [j.summary() for j in jobs.list_jobs()]


@router.get("/import/jobs/{job_id}")
def get_job(job_id: str):
    j = jobs.get_job(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail=f"job 不存在: {job_id}")
    return j.summary()
