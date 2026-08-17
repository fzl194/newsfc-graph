"""tests router：测试用例管理（数据飞轮·数据层）。

完全独立于 objects/assets 路由——只读写 platform-data/tests/，只调 TestService。
跨子系统"图谱对象名渲染"由前端直接调图谱 /names 完成，本路由不碰图谱。
"""
import io
import secrets
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from ..tests.service import get_test_service, test_lock

router = APIRouter()


# ---------- 序列化辅助 ----------

def _dump_problem(p) -> dict:
    return {"description": p.description, "attribution": list(p.attribution), "objects": list(p.objects)}


def _dump_case(c) -> dict:
    return {
        "id": c.id, "type": "TestCase",
        "domain": c.domain, "scenario": c.scenario, "name": c.name,
        "status": c.frontmatter.get("status", ""),
        "solution": c.frontmatter.get("solution", ""),
        "author": c.frontmatter.get("author", ""),
        "frontmatter": c.frontmatter, "body_md": c.body_md,
        "raw_md": c.raw_md, "source_path": c.source_path,
        "files": c.files,
    }


def _dump_run(r) -> dict:
    return {
        "id": r.id, "type": "Run", "case": r.case, "name": r.name,
        "runner": r.runner, "run_at": r.run_at, "status": r.status,
        "artifacts": r.artifacts, "frontmatter": r.frontmatter,
        "body_md": r.body_md, "raw_md": r.raw_md, "source_path": r.source_path,
    }


def _dump_review(rv) -> dict:
    return {
        "id": rv.id, "type": "Review", "run": rv.run,
        "reviewer": rv.reviewer, "reviewed_at": rv.reviewed_at,
        "verdict": rv.verdict, "problem_count": len(rv.problems),
        "problems": [_dump_problem(p) for p in rv.problems],
        "frontmatter": rv.frontmatter, "body_md": rv.body_md,
        "raw_md": rv.raw_md, "source_path": rv.source_path,
    }


def _latest_verdict_for_run(idx, run_id: str) -> str:
    rids = idx.reviews_by_run.get(run_id, [])
    if not rids:
        return ""
    rv = idx.reviews.get(rids[-1])
    return rv.verdict if rv else ""


# ---------- resolve ----------

def _case(id_: str):
    c = get_test_service().index.cases.get(id_)
    if c is None:
        raise HTTPException(status_code=404, detail=f"用例不存在: {id_}")
    return c


def _run(id_: str):
    r = get_test_service().index.runs.get(id_)
    if r is None:
        raise HTTPException(status_code=404, detail=f"运行不存在: {id_}")
    return r


def _review(id_: str):
    rv = get_test_service().index.reviews.get(id_)
    if rv is None:
        raise HTTPException(status_code=404, detail=f"审查不存在: {id_}")
    return rv


# ---------- /tests/cases ----------

@router.get("/tests/cases")
def list_cases(domain: Optional[str] = None,
               scenario: Optional[str] = None,
               q: Optional[str] = None):
    idx = get_test_service().index
    ql = q.lower() if q else None
    rows = []
    for cid, c in idx.cases.items():
        if domain and c.domain != domain:
            continue
        if scenario and c.scenario != scenario:
            continue
        if ql and ql not in cid.lower() and ql not in c.name.lower():
            continue
        run_ids = idx.runs_by_case.get(cid, [])
        rows.append({
            "id": cid, "name": c.name, "domain": c.domain, "scenario": c.scenario,
            "status": c.frontmatter.get("status", ""),
            "file_count": len(c.files),
            "run_count": len(run_ids),
            "latest_verdict": _latest_verdict_for_run(idx, run_ids[-1]) if run_ids else "",
        })
    rows.sort(key=lambda r: (r["domain"], r["scenario"], r["id"]))
    return rows


@router.get("/tests/cases/{id_}")
def get_case(id_: str):
    idx = get_test_service().index
    c = _case(id_)
    runs = []
    for rid in idx.runs_by_case.get(id_, []):
        r = idx.runs.get(rid)
        if r:
            runs.append({
                "id": r.id, "runner": r.runner, "run_at": r.run_at,
                "status": r.status, "artifact_count": len(r.artifacts),
                "verdict": _latest_verdict_for_run(idx, rid),
                "review_count": len(idx.reviews_by_run.get(rid, [])),
            })
    return {**_dump_case(c), "runs": runs}


# ---------- /tests/runs ----------

@router.get("/tests/runs")
def list_runs(case: Optional[str] = None):
    idx = get_test_service().index
    rows = []
    for rid, r in idx.runs.items():
        if case and r.case != case:
            continue
        rows.append({
            "id": rid, "case": r.case, "runner": r.runner, "run_at": r.run_at,
            "status": r.status, "artifact_count": len(r.artifacts),
            "verdict": _latest_verdict_for_run(idx, rid),
            "review_count": len(idx.reviews_by_run.get(rid, [])),
        })
    rows.sort(key=lambda r: r["run_at"], reverse=True)
    return rows


@router.get("/tests/runs/{id_}")
def get_run(id_: str):
    idx = get_test_service().index
    r = _run(id_)
    reviews = [_dump_review(idx.reviews[rid]) for rid in idx.reviews_by_run.get(id_, [])
               if rid in idx.reviews]
    return {**_dump_run(r), "reviews": reviews}


@router.get("/tests/runs/{id_}/artifact/{name:path}")
def get_artifact(id_: str, name: str):
    """取运行产出原文（config.txt / 方案.md / LLD.md / …，支持嵌套子目录路径）。"""
    svc = get_test_service()
    r = _run(id_)
    if name not in r.artifacts:
        raise HTTPException(status_code=404, detail=f"产出不存在: {name}")
    rel = f"{r.source_path}/{name}"
    text = svc.store.read(rel)
    media = "text/markdown; charset=utf-8" if name.lower().endswith(".md") else "text/plain; charset=utf-8"
    return Response(content=text, media_type=media)


@router.post("/tests/runs")
async def upload_run(
    case: str = Form(...),
    file: UploadFile = File(...),
    slug: str = Form(""),
    name: str = Form(""),
    runner: str = Form(""),
):
    """上传运行结果 zip → 解包成 runs/{用例}/Run@{slug}/。zip 内直接放运行产出文件。

    name/runner 可选，写入运行信息卡（不填则 runner 默认 'upload'）。
    """
    svc = get_test_service()
    if case not in svc.index.cases:
        raise HTTPException(status_code=404, detail=f"用例不存在: {case}")
    case_slug = case.split("@", 1)[1] if "@" in case else case
    ts = datetime.now().strftime("%Y%m%d%H%M")
    with test_lock:
        rid = f"Run@{slug or (case_slug + '-' + ts)}-{secrets.token_hex(2)}"
        run_rel = f"runs/{case}/{rid}"
        data = await file.read()
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="不是合法 zip")
        for zi in zf.infolist():
            if zi.is_dir():
                continue
            n = zi.filename.replace("\\", "/")
            # 路径穿越防护：跳过绝对路径与含 .. 的条目
            if n.startswith("/") or any(seg == ".." for seg in n.split("/")):
                continue
            svc.store.write_bytes(f"{run_rel}/{n}", zf.read(zi))
        # 若 zip 没带 Run@id.md，自动盖一份运行信息卡（name/runner 可由前端填）
        if not svc.store.exists(f"{run_rel}/{rid}.md"):
            meta = {
                "id": rid, "type": "Run", "case": case,
                "run_at": _now(), "runner": runner or "upload", "status": "completed",
            }
            if name:
                meta["name"] = name
            svc.store.write(
                f"{run_rel}/{rid}.md",
                f"---\n{yaml.dump(meta, allow_unicode=True, sort_keys=False)}---\n# {name or rid}\n",
            )
        svc.rebuild()
    r = svc.index.runs.get(rid)
    if r is None:
        raise HTTPException(status_code=400, detail="解压后未识别为运行（检查 zip 结构）")
    return _dump_run(r)


class RunInfoIn(BaseModel):
    name: Optional[str] = None
    runner: Optional[str] = None
    run_at: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@router.patch("/tests/runs/{id_}")
def update_run(id_: str, req: RunInfoIn):
    """编辑运行信息卡（name/runner/run_at/status/notes）。无 md 则创建。"""
    svc = get_test_service()
    with test_lock:
        r = svc.index.runs.get(id_)
        if r is None:
            raise HTTPException(status_code=404, detail=f"运行不存在: {id_}")
        fm = dict(r.frontmatter)
        fm["id"] = id_
        fm["type"] = "Run"
        fm["case"] = r.case
        for k in ("name", "runner", "run_at", "status", "notes"):
            v = getattr(req, k)
            if v is not None:
                fm[k] = v
        meta_rel = f"{r.source_path}/{id_}.md"
        body = r.body_md or f"# {fm.get('name', id_)}"
        svc.store.write(meta_rel, f"---\n{yaml.dump(fm, allow_unicode=True, sort_keys=False)}---\n{body}\n")
        svc.rebuild()
    return _dump_run(svc.index.runs.get(id_))


@router.delete("/tests/runs/{id_}")
def delete_run(id_: str):
    """删运行文件夹（含其 reviews/）。"""
    svc = get_test_service()
    with test_lock:
        r = svc.index.runs.get(id_)
        if r is None:
            raise HTTPException(status_code=404, detail=f"运行不存在: {id_}")
        svc.store.rmtree(r.source_path)
        svc.rebuild()
    return {"ok": True}


@router.get("/tests/runs/{id_}/download")
def download_run(id_: str):
    """打包下载整个运行文件夹（zip，含产出 + reviews/）。"""
    svc = get_test_service()
    r = _run(id_)
    folder = svc.store.abspath(r.source_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in folder.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(folder).as_posix())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{id_}.zip"'},
    )


# ---------- /tests/reviews ----------

@router.get("/tests/reviews")
def list_reviews(run: Optional[str] = None):
    idx = get_test_service().index
    rows = []
    for rvid, rv in idx.reviews.items():
        if run and rv.run != run:
            continue
        rows.append(_dump_review(rv))
    rows.sort(key=lambda r: r["reviewed_at"])
    return rows


@router.get("/tests/reviews/{id_}")
def get_review(id_: str):
    return _dump_review(_review(id_))


# ---------- /tests/stats ----------

@router.get("/tests/stats")
def tests_stats():
    idx = get_test_service().index
    by_domain: dict = {}
    by_domain_scenario: dict = {}
    for c in idx.cases.values():
        by_domain[c.domain] = by_domain.get(c.domain, 0) + 1
        key = f"{c.domain}/{c.scenario}" if c.scenario else c.domain
        by_domain_scenario[key] = by_domain_scenario.get(key, 0) + 1
    verdict_dist: dict = {}
    for rv in idx.reviews.values():
        k = rv.verdict or "未判定"
        verdict_dist[k] = verdict_dist.get(k, 0) + 1
    return {
        "case_count": len(idx.cases),
        "run_count": len(idx.runs),
        "review_count": len(idx.reviews),
        "cases_by_domain": by_domain,
        "cases_by_domain_scenario": by_domain_scenario,
        "verdict_distribution": verdict_dist,
        "warnings": idx.warnings[:20],
    }


# ---------- 写：建用例（Phase 1）----------

def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _render_case_md(fm: dict, intent: str) -> str:
    fm_text = yaml.dump(fm, allow_unicode=True, sort_keys=False)
    body = intent or ""
    if body and not body.startswith("#"):
        body = f"# {fm.get('name', '')}\n\n{body}"
    return f"---\n{fm_text}---\n{body}\n"


def _safe_filename(name: str) -> str:
    """剥掉任何目录成分，只留文件名（防穿越）。"""
    return Path(name).name if name else "unnamed"


@router.post("/tests/cases")
async def create_case(
    name: str = Form(...),
    intent: str = Form(""),
    domain: str = Form(""),
    scenario: str = Form(""),
    solution: str = Form(""),
    slug: str = Form(""),
    status: str = Form("active"),
    author: str = Form(""),
    input_files: List[UploadFile] = File([]),
    reference_files: List[UploadFile] = File([]),
):
    """前端建用例：写意图 md + 可选上传输入/参考配置。建文件夹 cases/{域}/{场景}/TestCase@{slug}/。

    domain/scenario/solution 建议填图谱业务层的值（BusinessDomain 域 / NetworkScenario 场景 /
    ConfigurationSolution 方案 id），前端下拉从图谱只读拉取。
    """
    svc = get_test_service()
    with test_lock:
        domain = (domain or "").strip() or "未分类"
        scenario = (scenario or "").strip()
        solution = (solution or "").strip()
        slug = (slug or "").strip()
        if not slug:
            slug = "case-" + secrets.token_hex(3)
        cid = f"TestCase@{slug}"
        if cid in svc.index.cases:
            raise HTTPException(status_code=400, detail=f"用例已存在: {cid}")

        segs = ["cases", domain]
        if scenario:
            segs.append(scenario)
        segs.append(cid)
        case_rel = "/".join(segs)

        fm = {
            "id": cid, "type": "TestCase", "name": name,
            "domain": domain, "scenario": scenario, "status": status,
            "author": author, "created_at": _today(),
        }
        if solution:
            fm["solution"] = solution
        svc.store.write(f"{case_rel}/{cid}.md", _render_case_md(fm, intent))

        for uf in input_files:
            fn = _safe_filename(uf.filename)
            if not fn:
                continue
            svc.store.write_bytes(f"{case_rel}/inputs/{fn}", await uf.read())
        for uf in reference_files:
            fn = _safe_filename(uf.filename)
            if not fn:
                continue
            svc.store.write_bytes(f"{case_rel}/references/{fn}", await uf.read())

        svc.rebuild()
    return _dump_case(svc.index.cases.get(cid))  # type: ignore[arg-type]


@router.get("/tests/cases/{id_}/download")
def download_case(id_: str):
    """打包下载整个用例文件夹（zip）。"""
    svc = get_test_service()
    c = _case(id_)
    folder = svc.store.abspath(c.source_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in folder.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(folder).as_posix())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{id_}.zip"'},
    )


@router.get("/tests/cases/{id_}/file/{name:path}")
def get_case_file(id_: str, name: str):
    """取用例附件文件内容（供前端 txt 预览）。name 可含子路径如 inputs/x.txt。"""
    svc = get_test_service()
    c = _case(id_)
    if name not in c.files:
        raise HTTPException(status_code=404, detail=f"文件不存在: {name}")
    text = svc.store.read(f"{c.source_path}/{name}")
    media = "text/markdown; charset=utf-8" if name.lower().endswith(".md") else "text/plain; charset=utf-8"
    return Response(content=text, media_type=media)


@router.patch("/tests/cases/{id_}")
async def update_case(
    id_: str,
    name: str = Form(""),
    intent: str = Form(""),
    domain: str = Form(""),
    scenario: str = Form(""),
    solution: str = Form(""),
    status: str = Form(""),
    remove_files: str = Form(""),           # 逗号分隔的待删文件相对路径
    input_files: List[UploadFile] = File([]),
    reference_files: List[UploadFile] = File([]),
):
    """编辑用例：改名/域/场景/方案/状态/意图，增删附件。域或场景变化则移动文件夹。"""
    svc = get_test_service()
    with test_lock:
        c = svc.index.cases.get(id_)
        if c is None:
            raise HTTPException(status_code=404, detail=f"用例不存在: {id_}")
        new_domain = (domain or "").strip() or c.domain
        new_scenario = (scenario or "").strip() if (scenario or "").strip() else c.scenario
        segs = ["cases", new_domain]
        if new_scenario:
            segs.append(new_scenario)
        segs.append(id_)
        case_rel = "/".join(segs)
        if case_rel != c.source_path:
            svc.store.move(c.source_path, case_rel)
        # 删指定附件
        if remove_files:
            for rf in remove_files.split(","):
                rf = rf.strip()
                if rf:
                    try:
                        svc.store.delete(f"{case_rel}/{rf}")
                    except Exception:
                        pass
        # 新上传附件
        for uf in input_files:
            fn = _safe_filename(uf.filename)
            if fn:
                svc.store.write_bytes(f"{case_rel}/inputs/{fn}", await uf.read())
        for uf in reference_files:
            fn = _safe_filename(uf.filename)
            if fn:
                svc.store.write_bytes(f"{case_rel}/references/{fn}", await uf.read())
        # 重写意图 md
        fm = dict(c.frontmatter)
        fm["id"] = id_
        fm["type"] = "TestCase"
        if name:
            fm["name"] = name
        fm["domain"] = new_domain
        fm["scenario"] = new_scenario
        if status:
            fm["status"] = status
        if solution:
            fm["solution"] = solution
        else:
            fm.pop("solution", None)
        svc.store.write(f"{case_rel}/{id_}.md", _render_case_md(fm, intent if intent else c.body_md))
        svc.rebuild()
    return _dump_case(svc.index.cases.get(id_))


@router.delete("/tests/cases/{id_}")
def delete_case(id_: str):
    """删用例文件夹，连带其下所有运行。"""
    svc = get_test_service()
    with test_lock:
        c = svc.index.cases.get(id_)
        if c is None:
            raise HTTPException(status_code=404, detail=f"用例不存在: {id_}")
        svc.store.rmtree(c.source_path)
        for rid in list(svc.index.runs_by_case.get(id_, [])):
            r = svc.index.runs.get(rid)
            if r:
                svc.store.rmtree(r.source_path)
        svc.rebuild()
    return {"ok": True}


# ---------- 写：审查 ----------

class ProblemIn(BaseModel):
    desc: str = ""
    attribution: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)


class ReviewWrite(BaseModel):
    run: str
    reviewer: Optional[str] = None
    verdict: str = "不通过"
    conclusion: Optional[str] = None
    problems: list[ProblemIn] = Field(default_factory=list)


def _run_slug(run_id: str) -> str:
    return run_id.split("@", 1)[1] if "@" in run_id else run_id


def _next_review_id(svc, run_id: str) -> str:
    """runs/{用例}/{run}/reviews/ 下已有审查数 +1。"""
    run = svc.index.runs.get(run_id)
    if run is None:
        # 运行不在索引也允许审查（容忍）；目录用约定
        rev_dir_rel = f"runs/unknown/{run_id}/reviews"
    else:
        rev_dir_rel = f"{run.source_path}/reviews"
    existing = svc.store.list_files(rev_dir_rel)
    n = sum(1 for f in existing if f.endswith(".md"))
    return f"Review@{_run_slug(run_id)}-{n + 1:02d}"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def _render_review_md(rvid: str, run_id: str, reviewer: str,
                      reviewed_at: str, verdict: str,
                      conclusion: str, problems: list) -> str:
    fm = {
        "id": rvid, "type": "Review", "run": run_id,
        "reviewer": reviewer, "reviewed_at": reviewed_at,
        "verdict": verdict, "problem_count": len(problems),
    }
    fm_text = yaml.dump(fm, allow_unicode=True, sort_keys=False)
    lines = [f"# 审查：{run_id}", "", "## 结论", conclusion or verdict, ""]
    if problems:
        lines.append("## 问题清单")
        for i, p in enumerate(problems, 1):
            attr_str = ", ".join(p["attribution"]) if p["attribution"] else ""
            obj_str = " ".join(f"[[{o}]]" for o in p["objects"]) if p["objects"] else ""
            lines += ["", f"### 问题 {i}",
                      f"- 描述: {p['desc']}",
                      f"- 归因: {attr_str}",
                      f"- 涉及对象: {obj_str}"]
    lines += ["", "## 边", f"- 审查对象: [[{run_id}]]", ""]
    return f"---\n{fm_text}---\n" + "\n".join(lines)


def _review_rel(svc, run_id: str, rvid: str) -> str:
    run = svc.index.runs.get(run_id)
    base = run.source_path if run else f"runs/unknown/{run_id}"
    return f"{base}/reviews/{rvid}.md"


@router.post("/tests/reviews")
def create_review(req: ReviewWrite):
    svc = get_test_service()
    with test_lock:
        rvid = _next_review_id(svc, req.run)
        reviewed_at = _now()
        md = _render_review_md(
            rvid, req.run, req.reviewer or "", reviewed_at,
            req.verdict, req.conclusion or "",
            [{"desc": p.desc, "attribution": p.attribution, "objects": p.objects} for p in req.problems],
        )
        svc.store.write(_review_rel(svc, req.run, rvid), md)
        svc.rebuild()
    return _dump_review(svc.index.reviews.get(rvid))


@router.patch("/tests/reviews/{id_}")
def update_review(id_: str, req: ReviewWrite):
    svc = get_test_service()
    with test_lock:
        old = svc.index.reviews.get(id_)
        if old is None:
            raise HTTPException(status_code=404, detail=f"审查不存在: {id_}")
        reviewer = req.reviewer if req.reviewer is not None else old.reviewer
        md = _render_review_md(
            id_, old.run, reviewer, old.reviewed_at,
            req.verdict, req.conclusion or "",
            [{"desc": p.desc, "attribution": p.attribution, "objects": p.objects} for p in req.problems],
        )
        svc.store.write(old.source_path, md)
        svc.rebuild()
    return _dump_review(svc.index.reviews.get(id_))


@router.delete("/tests/reviews/{id_}")
def delete_review(id_: str):
    svc = get_test_service()
    with test_lock:
        old = svc.index.reviews.get(id_)
        if old is None:
            raise HTTPException(status_code=404, detail=f"审查不存在: {id_}")
        svc.store.delete(old.source_path)
        svc.rebuild()
    return {"ok": True}


# ---------- 索引重建（Agent 写完 / UI 刷新调用）----------

@router.post("/tests/reindex")
def reindex():
    with test_lock:
        get_test_service().rebuild()
    idx = get_test_service().index
    return {
        "ok": True,
        "case_count": len(idx.cases),
        "run_count": len(idx.runs),
        "review_count": len(idx.reviews),
        "warnings": idx.warnings[:20],
    }
