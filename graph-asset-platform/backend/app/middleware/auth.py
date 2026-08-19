"""鉴权 + 审计中间件（v2）：KEY 反查用户 → 权限校验 → 请求级打点①。

- /users/login 豁免（登录前无 user，空 users 也能调）。
- 其他 /api/*：无 KEY/未知 KEY → 401；权限不符 → 403。
- 空 users.json → 所有 /api/*（非 login）→ 401（取消旁路）。
- 打点①：鉴权通过后记一行请求级（排除 /users/login、/telemetry/*）。
- caller：X-Client:web → web；否则 skill。
"""
import logging
import urllib.parse

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..telemetry.recorder import record
from ..users.service import authenticate, check_perm

logger = logging.getLogger(__name__)


def _need_perm(path: str) -> str:
    """路径 → 所需权限。/users/login 在 dispatch 里先豁免，不走到这。"""
    if path.startswith("/api/v1/users"):  # 用户管理（login 已豁免）
        return "admin"
    if path.startswith("/api/v1/fs"):  # 资产目录（/fs 文件管理 + /fs/upload 上传）
        return "assets"
    if path.startswith("/api/v1/docs"):  # 原始产品文档（资产页签内，D15 用户决策：页签级权限）
        return "assets"
    if path in ("/api/v1/domains", "/api/v1/md"):
        return "skill"
    if path.startswith("/api/v1/import") or path.startswith("/api/v1/export"):
        return "upload"  # 菜单3：上传/导出
    if path.startswith("/api/v1/tests"):
        return "test"  # 菜单4：测试子系统
    return "frontend"  # 其他前端用的接口（/objects /names /stats /subgraph）


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        # login 豁免（登录前无 user；空 users 也能登录）
        if path == "/api/v1/users/login":
            return await call_next(request)

        key = request.headers.get("X-API-Key", "")
        user = authenticate(key)
        if user is None:
            return JSONResponse(status_code=401, content={"detail": "missing or invalid api key"})

        # caller 从用户属性派生（不信任 X-Client header，防 SKILL 伪装 web 躲统计）
        caller = "web" if user.get("can_frontend") else "skill"
        # operator（工号）仅 SKILL 调用记；前端强制空（防前端伪造工号栽赃）
        operator = request.headers.get("X-User-Id", "") if caller == "skill" else ""
        request.state.user = user["username"]
        request.state.caller = caller
        request.state.operator = operator
        request.state.user_obj = user  # 整 dict，供 router 内 check_perm 二次校验（如 fs 写操作要 upload）

        if not check_perm(user, _need_perm(path)):
            return JSONResponse(status_code=403, content={"detail": "permission denied"})

        response = await call_next(request)

        # 打点①请求级（排除 telemetry 自身避免自循环；login 已豁免不到这）
        if not path.startswith("/api/v1/telemetry"):
            try:
                record(path, id_=_extract_id(path), type_="", user=user["username"], caller=caller, level="request", operator=operator)
            except Exception as e:  # 观测用，不阻断
                logger.warning("audit record failed: %s", e)
        return response


def _extract_id(path: str) -> str:
    """从 /objects/{id}* 提取 id（URL-decode；id 含 @ 与空格）。"""
    if "/objects/" in path:
        rest = path.split("/objects/", 1)[1]
        id_encoded = rest.split("/", 1)[0]
        return urllib.parse.unquote(id_encoded)
    return ""
