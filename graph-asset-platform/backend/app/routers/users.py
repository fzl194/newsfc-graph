"""users router：登录（公开）+ 用户管理（is_admin）。

权限由中间件统一校验（Task 5）：/users/login 豁免；其他 /users* 需 is_admin。
本 Task 先实现端点逻辑，权限依赖 Task 5 中间件。
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..users import service
from ..users import store
from ..telemetry.aggregator import aggregate_activity

router = APIRouter()


class LoginIn(BaseModel):
    username: str
    key: str


class UserCreateIn(BaseModel):
    username: str
    can_frontend: bool = False
    can_assets: bool = False
    can_upload: bool = False
    can_test: bool = False
    can_skill: bool = False
    is_admin: bool = False


class UserPatchIn(BaseModel):
    can_frontend: Optional[bool] = None
    can_assets: Optional[bool] = None
    can_upload: Optional[bool] = None
    can_test: Optional[bool] = None
    can_skill: Optional[bool] = None
    is_admin: Optional[bool] = None
    reset_key: bool = False


def _safe(u: dict) -> dict:
    # 权限位强制 bool（旧用户可能缺字段→None，前端类型要 boolean）
    perms = {k: bool(u.get(k)) for k in ("can_frontend", "can_assets", "can_upload", "can_test", "can_skill", "is_admin")}
    ident = {k: u.get(k) for k in ("username", "key", "created_at")}
    return {**ident, **perms}


@router.post("/users/login")
def login(req: LoginIn):
    """登录：username+key 匹配且 can_frontend → 返用户。公开（中间件豁免）。"""
    u = service.authenticate(req.key)
    if u is None or u.get("username") != req.username:
        raise HTTPException(401, "用户名或 KEY 错误")
    if not service.check_perm(u, "frontend"):
        raise HTTPException(403, "无前端访问权限")
    return _safe(u)


@router.get("/users")
def list_users():
    return [_safe(u) for u in store.list_users()]


@router.post("/users")
def create_user(req: UserCreateIn):
    try:
        return _safe(service.create_user(req.username, req.can_frontend, req.can_skill, req.is_admin, req.can_upload, req.can_test, req.can_assets))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.patch("/users/{username}")
def update_user(username: str, req: UserPatchIn):
    u = store.find_by_name(username)
    if u is None:
        raise HTTPException(404, "用户不存在")
    if req.reset_key:
        service.reset_key(username)
    if any(v is not None for v in (req.can_frontend, req.can_assets, req.can_upload, req.can_test, req.can_skill, req.is_admin)):
        service.set_perms(
            username,
            can_frontend=req.can_frontend if req.can_frontend is not None else u["can_frontend"],
            can_assets=req.can_assets if req.can_assets is not None else bool(u.get("can_assets")),
            can_upload=req.can_upload if req.can_upload is not None else bool(u.get("can_upload")),
            can_test=req.can_test if req.can_test is not None else bool(u.get("can_test")),
            can_skill=req.can_skill if req.can_skill is not None else u["can_skill"],
            is_admin=req.is_admin if req.is_admin is not None else u["is_admin"],
        )
    return _safe(store.find_by_name(username))


@router.delete("/users/{username}")
def delete_user(username: str):
    if not service.delete_user(username):
        raise HTTPException(404, "用户不存在")
    return {"ok": True}


@router.get("/users/{username}/activity")
def user_activity(username: str, days: int = 30):
    """该用户行为轨迹（需 is_admin，中间件校验）。"""
    return aggregate_activity(username, days)
