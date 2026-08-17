"""admin router：运维端点（需 admin 权限）。

- ``POST /admin/reindex``：手动全量重建 DB 索引（兜底；正常写操作已增量维护）。
  md 被外部大批量改、或怀疑 DB 不一致时调用。慢（全量 parse md）。
"""
from fastapi import APIRouter, HTTPException, Request

from ..service import get_service
from ..users.service import check_perm

router = APIRouter()


def _require_admin(request: Request) -> None:
    user = getattr(request.state, "user_obj", None)
    if not user or not check_perm(user, "admin"):
        raise HTTPException(status_code=403, detail="需要 admin 权限")


@router.post("/admin/reindex")
def reindex(request: Request):
    """全量重建 DB 索引 + 重载内存（兜底）。返回对象/边计数。"""
    _require_admin(request)
    svc = get_service()
    svc.rebuild()
    return {"ok": True, "objects": len(svc.index.nodes)}
