"""FastAPI 应用入口：lifespan 预热建索引 + CORS + 挂载 routers + 静态托管前端 dist。

- API 前缀 ``/api/v1``。
- 前端 ``frontend/dist`` 构建产物（如存在）挂在根路径下（SPA 兜底）。
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .middleware.auth import AuthMiddleware
from .routers import admin as admin_router
from .routers import assets as assets_router
from .routers import fs as fs_router
from .routers import objects as objects_router
from .routers import telemetry as telemetry_router
from .routers import tests as tests_router
from .routers import users as users_router
from .service import get_service
from .tests.service import get_test_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动预热：构造单例 → 建索引（assets 目录不存在时 Store 会 mkdir）。
    # 4585 个对象首次建索引约 10s，给进度日志避免"看起来卡住"。
    import time
    t0 = time.time()
    print("[startup] 正在加载资产库并构建索引（数据量大时可能数十秒，期间会打印进度，请稍候）…", flush=True)
    svc = get_service()
    print(
        f"[startup] 索引就绪：{len(svc.index.nodes)} 个对象，"
        f"耗时 {time.time() - t0:.1f}s → http://127.0.0.1:80/",
        flush=True,
    )
    # 测试子系统索引（独立于图谱，隔离）
    t_svc = get_test_service()
    print(
        f"[startup] 测试子系统就绪：{len(t_svc.index.cases)} 用例 / "
        f"{len(t_svc.index.runs)} 运行 / {len(t_svc.index.reviews)} 审查",
        flush=True,
    )
    # 用户体系：users.json 为空 → 自动创建 admin（全权限）并打印 KEY（首次 bootstrap）
    try:
        from .users.store import list_users
        if not list_users():
            from .users.service import create_user
            u = create_user('admin', can_frontend=True, can_skill=True, is_admin=True, can_upload=True, can_test=True, can_assets=True)
            print(f"[startup] users.json 为空 → 已自动创建 admin（全权限）。KEY: {u['key']}（请妥善保存，仅显示一次）", flush=True)
    except Exception as e:
        print(f"[startup] WARNING: users.json 读取失败 ({e})", flush=True)
    yield


app = FastAPI(title="Graph Asset Platform", version="0.1.0", lifespan=lifespan)
# 先 add auth（内层），再 add CORS（外层）：CORS 包装 auth 的 401，保证跨域时 401 响应带 CORS 头。
# 同源前端不受影响；此顺序为跨域调试/未来部署预留。
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(assets_router.router, prefix="/api/v1")
app.include_router(admin_router.router, prefix="/api/v1")
app.include_router(fs_router.router, prefix="/api/v1")
app.include_router(objects_router.router, prefix="/api/v1")
app.include_router(telemetry_router.router, prefix="/api/v1")
app.include_router(tests_router.router, prefix="/api/v1")
app.include_router(users_router.router, prefix="/api/v1")

# 前端静态托管（dist 可能尚未构建，不存在则不挂载）
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="spa")


@app.exception_handler(404)
async def spa_fallback(request: Request, exc: Exception):
    """SPA 兜底：非 API 路径 404 → 回 index.html（支持前端路由刷新/深链）；
    API 404 保留原 JSON detail（如对象不存在的提示）。"""
    path = request.url.path
    if path.startswith("/api/"):
        detail = getattr(exc, "detail", "Not Found")
        return JSONResponse(status_code=404, content={"detail": detail})
    index = _dist / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})
