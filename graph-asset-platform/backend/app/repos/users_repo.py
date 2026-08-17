"""users 表 CRUD。bool 字段存 INT（0/1）。"""
import sqlite3
from typing import Optional

_BOOL_COLS = ("can_frontend", "can_assets", "can_upload", "can_test", "can_skill", "is_admin")


def insert(conn: sqlite3.Connection, user: dict) -> None:
    conn.execute(
        "INSERT INTO users(username, key, can_frontend, can_assets, can_upload, can_test, "
        "can_skill, is_admin, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (user["username"], user["key"],
         int(user.get("can_frontend", False)), int(user.get("can_assets", False)),
         int(user.get("can_upload", False)), int(user.get("can_test", False)),
         int(user.get("can_skill", False)), int(user.get("is_admin", False)),
         user.get("created_at", "")),
    )


def list_all(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM users ORDER BY username").fetchall()


def find_by_key(conn: sqlite3.Connection, key: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM users WHERE key=?", (key,)).fetchone()


def find_by_name(conn: sqlite3.Connection, username: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()


def update(conn: sqlite3.Connection, username: str, patch: dict) -> None:
    sets, vals = [], []
    for col in ("key",) + _BOOL_COLS:
        if col in patch:
            sets.append(f"{col}=?")
            vals.append(int(patch[col]) if col in _BOOL_COLS else patch[col])
    if not sets:
        return
    vals.append(username)
    conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE username=?", vals)


def delete(conn: sqlite3.Connection, username: str) -> bool:
    return conn.execute(
        "DELETE FROM users WHERE username=?", (username,)).rowcount > 0


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
