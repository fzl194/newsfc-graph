"""tests 子系统表 CRUD：test_cases / test_runs / test_reviews /
test_review_problems / test_artifacts。

``replace_all``：从内存 TestIndex 全量重建（写操作后调；tests 数据少，全量可接受）。
``load_all``：读全部（启动 ``TestIndex.load_from_db`` 用）。

附件（case files / run artifacts）留磁盘，DB 只登记 path（owner_type/owner_id）。
"""
import json
import sqlite3


def replace_all(conn: sqlite3.Connection, idx) -> None:
    """清 test_* + 从内存 TestIndex 全量写。"""
    # child-first 删除（防 FK CASCADE 顺序问题）
    for t in ("test_review_problems", "test_reviews", "test_runs",
              "test_cases", "test_artifacts"):
        conn.execute(f"DELETE FROM {t}")
    # cases
    for cid, c in idx.cases.items():
        fm = c.frontmatter or {}
        conn.execute(
            "INSERT INTO test_cases(id, domain, scenario, name, status, solution, "
            "author, created_at, body_md, raw_md, source_path, frontmatter_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, c.domain, c.scenario, c.name,
             str(fm.get("status") or ""), str(fm.get("solution") or ""),
             str(fm.get("author") or ""), str(fm.get("created_at") or ""),
             c.body_md, c.raw_md, c.source_path,
             json.dumps(fm, ensure_ascii=False, default=str)),
        )
        for f in c.files:
            conn.execute(
                "INSERT INTO test_artifacts(owner_type, owner_id, path, kind, size) "
                "VALUES(?,?,?,?,?)",
                ("case", cid, f, "file", 0),
            )
    # runs
    for rid, r in idx.runs.items():
        fm = r.frontmatter or {}
        review_ids = idx.reviews_by_run.get(rid, [])
        latest_verdict = ""
        if review_ids:
            rv = idx.reviews.get(review_ids[-1])
            if rv:
                latest_verdict = rv.verdict
        conn.execute(
            "INSERT INTO test_runs(id, case_id, name, runner, run_at, status, "
            "latest_verdict, body_md, raw_md, source_path, frontmatter_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (rid, r.case, r.name, r.runner, r.run_at, r.status, latest_verdict,
             r.body_md, r.raw_md, r.source_path, json.dumps(fm, ensure_ascii=False, default=str)),
        )
        for a in r.artifacts:
            conn.execute(
                "INSERT INTO test_artifacts(owner_type, owner_id, path, kind, size) "
                "VALUES(?,?,?,?,?)",
                ("run", rid, a, "artifact", 0),
            )
    # reviews + problems
    for rvid, rv in idx.reviews.items():
        conn.execute(
            "INSERT INTO test_reviews(id, run_id, reviewer, reviewed_at, verdict, "
            "body_md, raw_md, source_path, frontmatter_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (rvid, rv.run, rv.reviewer, rv.reviewed_at, rv.verdict,
             rv.body_md, rv.raw_md, rv.source_path,
             json.dumps(rv.frontmatter, ensure_ascii=False, default=str)),
        )
        for i, p in enumerate(rv.problems):
            conn.execute(
                "INSERT INTO test_review_problems(review_id, idx, description, "
                "attribution_json, objects_json) VALUES(?,?,?,?,?)",
                (rvid, i, p.description,
                 json.dumps(p.attribution, ensure_ascii=False, default=str),
                 json.dumps(p.objects, ensure_ascii=False, default=str)),
            )
    conn.commit()


def load_all(conn: sqlite3.Connection) -> dict:
    """读全部 → {cases, runs, reviews, problems, artifacts}（load_from_db 用）。"""
    return {
        "cases": [dict(r) for r in conn.execute("SELECT * FROM test_cases").fetchall()],
        "runs": [dict(r) for r in conn.execute("SELECT * FROM test_runs").fetchall()],
        "reviews": [dict(r) for r in conn.execute("SELECT * FROM test_reviews").fetchall()],
        "problems": [dict(r) for r in conn.execute("SELECT * FROM test_review_problems").fetchall()],
        "artifacts": [dict(r) for r in conn.execute("SELECT * FROM test_artifacts").fetchall()],
    }
