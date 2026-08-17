"""trash 表 CRUD：软删除条目元数据（原路径/时间/操作人）。

物理内容在 ``<data>/.trash/{id}/{原相对路径}``（store 管理），本表只记映射与列表。
"""
import sqlite3
from typing import Optional


def insert(conn: sqlite3.Connection, *, trash_id: str, original_path: str,
           is_dir: bool, md_count: int, deleted_at: str, deleted_by: str) -> None:
    conn.execute(
        "INSERT INTO trash(id, original_path, is_dir, md_count, deleted_at, deleted_by) "
        "VALUES(?,?,?,?,?,?)",
        (trash_id, original_path, int(is_dir), md_count, deleted_at, deleted_by),
    )


def list_all(conn: sqlite3.Connection) -> list:
    rows = conn.execute("SELECT * FROM trash ORDER BY deleted_at DESC").fetchall()
    return [{
        "id": r["id"], "original_path": r["original_path"], "is_dir": bool(r["is_dir"]),
        "md_count": r["md_count"], "deleted_at": r["deleted_at"], "deleted_by": r["deleted_by"],
    } for r in rows]


def get(conn: sqlite3.Connection, trash_id: str) -> Optional[dict]:
    r = conn.execute("SELECT * FROM trash WHERE id=?", (trash_id,)).fetchone()
    if not r:
        return None
    return {
        "id": r["id"], "original_path": r["original_path"], "is_dir": bool(r["is_dir"]),
        "md_count": r["md_count"], "deleted_at": r["deleted_at"], "deleted_by": r["deleted_by"],
    }


def delete(conn: sqlite3.Connection, trash_id: str) -> bool:
    return conn.execute("DELETE FROM trash WHERE id=?", (trash_id,)).rowcount > 0


def delete_all(conn: sqlite3.Connection) -> int:
    return conn.execute("DELETE FROM trash").rowcount


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM trash").fetchone()[0]
