"""用户操作：生成 key、认证、权限检查、CRUD。"""
import secrets
import string
from datetime import datetime, timezone
from typing import Optional

from . import store

_KEY_PREFIX = "sk-"
_KEY_ALPHABET = string.ascii_letters + string.digits + "-_"  # 字母数字 + 少量特殊符号
_KEY_BODY_LEN = 18


def gen_key() -> str:
    """生成全局唯一 key：sk- 前缀 + 18 位（字母数字+少量符号），撞则重试。"""
    while True:
        k = _KEY_PREFIX + "".join(secrets.choice(_KEY_ALPHABET) for _ in range(_KEY_BODY_LEN))
        if store.find_by_key(k) is None:
            return k


def authenticate(key: str) -> Optional[dict]:
    return store.find_by_key(key)


def check_perm(user: dict, perm: str) -> bool:
    """perm ∈ frontend/assets/upload/test/skill/admin。
    upload/test 依赖 can_frontend（无前端权限则无效）；assets 独立（/fs 资产目录专属，
    不依赖 can_frontend）；is_admin 全权。"""
    if user.get("is_admin"):
        return True
    if perm == "frontend":
        return bool(user.get("can_frontend"))
    if perm == "assets":
        return bool(user.get("can_assets"))
    if perm == "upload":
        return bool(user.get("can_frontend")) and bool(user.get("can_upload"))
    if perm == "test":
        return bool(user.get("can_frontend")) and bool(user.get("can_test"))
    if perm == "skill":
        return bool(user.get("can_skill")) or bool(user.get("can_frontend"))
    return False  # admin 仅 is_admin


def create_user(username: str, can_frontend: bool, can_skill: bool, is_admin: bool = False, can_upload: bool = False, can_test: bool = False, can_assets: bool = False) -> dict:
    if store.find_by_name(username) is not None:
        raise ValueError(f"用户已存在: {username}")
    user = {
        "username": username,
        "key": gen_key(),
        "can_frontend": can_frontend,
        "can_assets": can_assets,
        "can_upload": can_upload,
        "can_test": can_test,
        "can_skill": can_skill,
        "is_admin": is_admin,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return store.add_user(user)


def reset_key(username: str) -> Optional[str]:
    k = gen_key()
    u = store.update_user(username, {"key": k})
    return k if u else None


def set_key(username: str, key: str) -> Optional[dict]:
    """设置指定 KEY（管理员自定义，2026-08-24 用户决策·折中校验）：
    去首尾空白后 ≥8 位、不含任何空白字符，不强制前缀；全局唯一（撞他人 KEY → 拒）。
    KEY 即登录凭证等价于用户名，冲突必须显式失败而非静默顶号。"""
    k = (key or "").strip()
    if len(k) < 8 or any(c.isspace() for c in k):
        raise ValueError("KEY 需 ≥8 位且不含空格")
    hit = store.find_by_key(k)
    if hit is not None and hit.get("username") != username:
        raise ValueError(f"KEY 已被用户 {hit['username']} 占用")
    return store.update_user(username, {"key": k})


def set_perms(username: str, *, can_frontend: bool, can_assets: bool = False, can_upload: bool = False, can_test: bool = False, can_skill: bool, is_admin: bool) -> Optional[dict]:
    return store.update_user(username, {
        "can_frontend": can_frontend, "can_assets": can_assets,
        "can_upload": can_upload, "can_test": can_test,
        "can_skill": can_skill, "is_admin": is_admin,
    })


def delete_user(username: str) -> bool:
    return store.delete_user(username)
