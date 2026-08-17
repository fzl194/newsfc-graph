"""users 表读写（DB 后端；保留 list_users/find_by_*/add/update/delete 接口）。

原 ``users.json`` 仅作首次迁移源（``migrate_users``），之后不再读写。service.py /
middleware 不感知存储变更（接口签名不变）。
"""
from typing import Optional

from ..db import get_shared_db
from ..repos import users_repo


def _row(r) -> dict:
    return {
        "username": r["username"], "key": r["key"],
        "can_frontend": bool(r["can_frontend"]), "can_assets": bool(r["can_assets"]),
        "can_upload": bool(r["can_upload"]),
        "can_test": bool(r["can_test"]), "can_skill": bool(r["can_skill"]),
        "is_admin": bool(r["is_admin"]), "created_at": r["created_at"],
    }


def list_users() -> list:
    return [_row(r) for r in users_repo.list_all(get_shared_db())]


def find_by_key(key: str) -> Optional[dict]:
    r = users_repo.find_by_key(get_shared_db(), key)
    return _row(r) if r else None


def find_by_name(username: str) -> Optional[dict]:
    r = users_repo.find_by_name(get_shared_db(), username)
    return _row(r) if r else None


def add_user(user: dict) -> dict:
    db = get_shared_db()
    users_repo.insert(db, user)
    db.commit()
    return user


def update_user(username: str, patch: dict) -> Optional[dict]:
    db = get_shared_db()
    users_repo.update(db, username, patch)
    db.commit()
    r = users_repo.find_by_name(db, username)
    return _row(r) if r else None


def delete_user(username: str) -> bool:
    db = get_shared_db()
    deleted = users_repo.delete(db, username)
    db.commit()
    return deleted
