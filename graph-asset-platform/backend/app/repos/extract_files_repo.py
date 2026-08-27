"""extract_files 表 CRUD：抽取任务产物清单（按任务回退的依据）。

行由入图闸门 ``gate.apply_gate`` 在 confirm 时写入（path 为 assets 根相对路径，
正斜杠）；``gate.revert_job`` 读取执行回退，完成后删除。op: add=本次新增（回退=
软删进回收站）；modify=本次覆盖（回退=还原 originals 备份）。
"""
import sqlite3


def replace_for_job(conn: sqlite3.Connection, job_id: str,
                    rows: list) -> None:
    """整任务覆写清单。rows: [(path, op, sha256, layer), ...]。"""
    conn.execute("DELETE FROM extract_files WHERE job_id=?", (job_id,))
    conn.executemany(
        "INSERT INTO extract_files(job_id, path, op, sha256, layer) VALUES(?,?,?,?,?)",
        [(job_id, p, op, sha, layer) for p, op, sha, layer in rows],
    )


def list_for_job(conn: sqlite3.Connection, job_id: str) -> list:
    rows = conn.execute(
        "SELECT path, op, sha256, layer FROM extract_files WHERE job_id=? ORDER BY path",
        (job_id,)).fetchall()
    return [{"path": r["path"], "op": r["op"], "sha256": r["sha256"],
             "layer": r["layer"]} for r in rows]


def count_for_job(conn: sqlite3.Connection, job_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM extract_files WHERE job_id=?", (job_id,)).fetchone()[0]


def delete_for_job(conn: sqlite3.Connection, job_id: str) -> bool:
    return conn.execute(
        "DELETE FROM extract_files WHERE job_id=?", (job_id,)).rowcount > 0
