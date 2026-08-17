"""ImportJob 注册表测试（异步导入后台任务的活状态载体）。"""
from app.jobs import ImportJob, create_job, get_job, list_jobs, update_job


def test_job_lifecycle():
    j = create_job()
    assert isinstance(j, ImportJob)
    assert j.status == "processing"
    assert get_job(j.job_id).status == "processing"
    update_job(j.job_id, status="done", added=5, updated=1)
    j2 = get_job(j.job_id)
    assert j2.status == "done"
    assert j2.added == 5
    assert j2.updated == 1
    assert j2.finished_at > 0
    assert any(x.job_id == j.job_id for x in list_jobs())


def test_update_unknown_job_is_noop():
    update_job("nonexistent", status="done")  # 不应抛
    assert get_job("nonexistent") is None


def test_failed_sets_error_and_finished_at():
    j = create_job()
    update_job(j.job_id, status="failed", error="boom")
    j2 = get_job(j.job_id)
    assert j2.status == "failed"
    assert j2.error == "boom"
    assert j2.finished_at > 0


def test_summary_round_trips():
    j = create_job()
    s = j.summary()
    assert s["status"] == "processing"
    assert s["job_id"] == j.job_id
    assert "started_at" in s
