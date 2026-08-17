"""测试索引：扫描 platform-data/tests/ 构建 cases/runs/reviews 内存索引。

新文件夹模型（spec §3）：
- TestCase = 文件夹 ``cases/{域}/{场景}/TestCase@{slug}/``：意图 md 必须（stem=文件夹名），
  其余文件（inputs/、references/、附件…）全可选。
- Run = 文件夹 ``runs/{用例ID}/Run@{runid}/``：产出任意、``Run@{runid}.md`` 可选（元数据）、
  ``reviews/`` 子目录嵌审查。
- Review = md 文件 ``runs/{用例ID}/{RunID}/reviews/Review@{slug}.md``。

只依赖**路径+文件夹/文件名**做识别/分组；YAML 缺失一律降级。无隐藏文件——文件夹内所有
文件都进 ``files``（用例）/``artifacts``（运行），可查看。
"""
from dataclasses import dataclass, field
from pathlib import Path

from .models import Review, Run, TestCase
from .parser import extract_problems, parse_md


@dataclass
class TestIndex:
    cases: dict = field(default_factory=dict)            # id → TestCase
    runs: dict = field(default_factory=dict)             # id → Run
    reviews: dict = field(default_factory=dict)          # id → Review
    runs_by_case: dict = field(default_factory=dict)     # case_id → [run_id]
    reviews_by_run: dict = field(default_factory=dict)   # run_id → [review_id]
    warnings: list = field(default_factory=list)

    @classmethod
    def build(cls, store) -> "TestIndex":
        idx = cls()
        root = store.root
        cases_root = root / "cases"
        runs_root = root / "runs"

        # --- TestCase 文件夹 ---
        if cases_root.exists():
            for d in sorted(p for p in cases_root.rglob("TestCase@*") if p.is_dir()):
                try:
                    idx._add_case(store, d)
                except Exception as e:  # noqa: BLE001
                    idx.warnings.append(f"用例解析失败 {d.name}: {e}")

        # --- Run 文件夹（必须直接位于 runs/{用例ID}/ 下，即相对 runs 深度恰为 2 段）---
        if runs_root.exists():
            for d in sorted(p for p in runs_root.rglob("Run@*") if p.is_dir()):
                if len(d.relative_to(runs_root).parts) != 2:
                    continue  # 不是 runs/{用例ID}/{RunID}/ 结构，跳过
                try:
                    idx._add_run(store, d)
                except Exception as e:  # noqa: BLE001
                    idx.warnings.append(f"运行解析失败 {d.name}: {e}")

        for rid, run in idx.runs.items():
            idx.runs_by_case.setdefault(run.case, []).append(rid)
        for rvid, rv in idx.reviews.items():
            idx.reviews_by_run.setdefault(rv.run, []).append(rvid)
        return idx

    @classmethod
    def load_from_db(cls, db) -> "TestIndex":
        """从 test_* 表加载内存（替代 build 的 parse；启动 + 写操作 reload 用）。"""
        import json
        from ..repos import tests_repo
        from .models import TestCase, Run, Review, Problem
        idx = cls()
        data = tests_repo.load_all(db)
        case_files, run_artifacts, review_problems = {}, {}, {}
        for a in data["artifacts"]:
            if a["owner_type"] == "case":
                case_files.setdefault(a["owner_id"], []).append(a["path"])
            elif a["owner_type"] == "run":
                run_artifacts.setdefault(a["owner_id"], []).append(a["path"])
        for p in data["problems"]:
            review_problems.setdefault(p["review_id"], []).append(p)
        for c in data["cases"]:
            fm = json.loads(c["frontmatter_json"]) if c["frontmatter_json"] else {}
            idx.cases[c["id"]] = TestCase(
                id=c["id"], domain=c["domain"], scenario=c["scenario"], name=c["name"],
                frontmatter=fm, body_md=c["body_md"], raw_md=c["raw_md"],
                source_path=c["source_path"], files=case_files.get(c["id"], []),
            )
        for r in data["runs"]:
            fm = json.loads(r["frontmatter_json"]) if r["frontmatter_json"] else {}
            idx.runs[r["id"]] = Run(
                id=r["id"], case=r["case_id"], name=r["name"], runner=r["runner"],
                run_at=r["run_at"], status=r["status"],
                artifacts=run_artifacts.get(r["id"], []),
                frontmatter=fm, body_md=r["body_md"], raw_md=r["raw_md"],
                source_path=r["source_path"],
            )
        for rv in data["reviews"]:
            fm = json.loads(rv["frontmatter_json"]) if rv["frontmatter_json"] else {}
            probs = [Problem(
                description=p["description"],
                attribution=json.loads(p["attribution_json"] or "[]"),
                objects=json.loads(p["objects_json"] or "[]"),
            ) for p in review_problems.get(rv["id"], [])]
            idx.reviews[rv["id"]] = Review(
                id=rv["id"], run=rv["run_id"], reviewer=rv["reviewer"],
                reviewed_at=rv["reviewed_at"], verdict=rv["verdict"],
                problems=probs, frontmatter=fm, body_md=rv["body_md"],
                raw_md=rv["raw_md"], source_path=rv["source_path"],
            )
        for rid, run in idx.runs.items():
            idx.runs_by_case.setdefault(run.case, []).append(rid)
        for rvid, rv in idx.reviews.items():
            idx.reviews_by_run.setdefault(rv.run, []).append(rvid)
        return idx

    # ---------- builders ----------

    def _add_case(self, store, case_dir: Path) -> None:
        cid = case_dir.name
        rel = case_dir.relative_to(store.root).as_posix()
        parts = rel.split("/")
        after = parts[1:-1]  # cases/ 与用例文件夹之间的目录段
        domain = after[0] if len(after) >= 1 else "未分类"
        scenario = after[1] if len(after) >= 2 else ""

        frontmatter: dict = {}
        body = ""
        raw = ""
        intent_rel = f"{rel}/{cid}.md"
        if store.exists(intent_rel):
            raw = store.read(intent_rel)
            fm, body, _ = parse_md(raw)
            frontmatter = fm

        # 文件夹内所有文件（相对用例文件夹），排除意图 md 本身
        files = []
        for f in case_dir.rglob("*"):
            if f.is_file():
                fr = f.relative_to(case_dir).as_posix()
                if fr != f"{cid}.md":
                    files.append(fr)

        self.cases[cid] = TestCase(
            id=cid, domain=domain, scenario=scenario,
            name=_name(frontmatter, body, cid),
            frontmatter=frontmatter, body_md=body, raw_md=raw,
            source_path=rel, files=files,
        )

    def _add_run(self, store, run_dir: Path) -> None:
        rid = run_dir.name
        case_id = run_dir.parent.name
        rel = run_dir.relative_to(store.root).as_posix()

        frontmatter: dict = {}
        body = ""
        raw = ""
        runner = run_at = status = ""
        meta_rel = f"{rel}/{rid}.md"
        if store.exists(meta_rel):
            raw = store.read(meta_rel)
            fm, body, _ = parse_md(raw)
            frontmatter = fm
            runner = str(fm.get("runner") or "")
            run_at = str(fm.get("run_at") or "")
            status = str(fm.get("status") or "")

        # 运行文件夹内所有文件（相对运行文件夹），排除 Run@id.md 与 reviews/ 子目录
        artifacts = []
        reviews_dir = run_dir / "reviews"
        for f in run_dir.rglob("*"):
            if not f.is_file():
                continue
            fr = f.relative_to(run_dir).as_posix()
            if fr == f"{rid}.md" or fr.startswith("reviews/"):
                continue
            artifacts.append(fr)

        name = str(frontmatter.get("name") or f"Run {run_at}".strip() or rid)
        self.runs[rid] = Run(
            id=rid, case=case_id, name=name, runner=runner, run_at=run_at,
            status=status, artifacts=artifacts, frontmatter=frontmatter,
            body_md=body, raw_md=raw, source_path=rel,
        )

        # 审查：嵌在 reviews/ 子目录
        if reviews_dir.exists():
            for rf in sorted(reviews_dir.glob("*.md")):
                self._add_review(store, rf, rid)

    def _add_review(self, store, rf: Path, run_id: str) -> None:
        rvid = rf.stem
        rel = rf.relative_to(store.root).as_posix()
        raw = store.read(rel)
        fm, body, _ = parse_md(raw)
        self.reviews[rvid] = Review(
            id=rvid, run=run_id,
            reviewer=str(fm.get("reviewer") or ""),
            reviewed_at=str(fm.get("reviewed_at") or ""),
            verdict=str(fm.get("verdict") or ""),
            problems=extract_problems(body),
            frontmatter=fm, body_md=body, raw_md=raw, source_path=rel,
        )


def _name(fm: dict, body: str, fallback_id: str) -> str:
    """fm.name → 正文首 H1 → id。"""
    n = fm.get("name")
    if n:
        return str(n)
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s.lstrip("# ").strip()
    return fallback_id
