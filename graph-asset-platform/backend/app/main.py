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
from .mcp_server import asgi_app as mcp_asgi_app
from .routers import admin as admin_router
from .routers import assets as assets_router
from .routers import docs as docs_router
from .routers import fs as fs_router
from .routers import mcp_tools as mcp_tools_router
from .routers import objects as objects_router
from .routers import productdoc as productdoc_router
from .routers import stats as stats_router
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
    # 抽取任务对账（须在 sweep **之前**）：中断于入库/回退执行中的任务复位
    # （applying→awaiting 可重试/撤销；reverting→done 可重发起回退）
    from .pipeline import gate as _gate_mod
    flipped = _gate_mod.reconcile_interrupted()
    if flipped:
        print(f"[startup] 已复位 {flipped} 个中断于入库/回退执行中的抽取任务", flush=True)
    # 导入任务清账：①终止上个进程遗留的子进程树 ②processing 标记 failed
    from . import jobs as jobs_mod
    swept = jobs_mod.sweep_interrupted()
    if swept:
        print(f"[startup] 已将 {swept} 个中断的导入任务标记为 failed（可覆盖重建续跑）", flush=True)
    # 孤儿临时目录清扫（硬 kill 遗留的 .pdoc_/.pdoc_up_/.tmp_*）
    from .pipeline import bundles as bundles_mod
    orphans = bundles_mod.sweep_orphan_tmp()
    if orphans:
        print(f"[startup] 已清扫孤儿临时目录/文件 {orphans} 个", flush=True)
    # 抽取闸门沙箱清扫：processing 任务已标 failed → 其沙箱为孤儿可清；
    # awaiting（待闸门确认）跨重启存活不动（2026-08-26 抽取任务化）
    from .pipeline import gate as gate_mod
    gates = gate_mod.sweep_orphan_gates()
    if gates:
        print(f"[startup] 已清理孤儿抽取沙箱 {gates} 个", flush=True)
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
    # 统计缓存后台预热（2026-09-02：内网百万行级聚合缓存化，筛选走内存过滤；
    # 构建期间统计端点等待首个构建完成，之后「更新缓存」按钮重建）
    try:
        from .stats import cache as stats_cache_mod
        if stats_cache_mod.refresh_async():
            print("[startup] 统计缓存后台预热中（数据量大时约几十秒）…", flush=True)
    except Exception as e:  # noqa: BLE001 —— 预热失败不阻断启动（首个请求会同步构建）
        print(f"[startup] WARNING: 统计缓存预热失败 ({e})", flush=True)
    # MCP 服务（Streamable HTTP，/mcp）：session manager 随应用生命周期启停
    # （SDK 限制 run() 仅一次/实例 → 每次启动重建；测试多 TestClient 场景可重入）
    from .mcp_server import apply_instructions, rebuild_session_manager
    # 总体说明覆盖随配置恢复（enabled/description 每请求读 DB 无需启动应用）
    try:
        from .db import get_shared_db
        from .repos import mcp_tools_repo
        apply_instructions(mcp_tools_repo.get_instructions(get_shared_db()))
    except Exception as e:  # noqa: BLE001 配置恢复失败不阻断启动（回退默认说明）
        print(f"[startup] WARNING: MCP instructions 配置恢复失败 ({e})", flush=True)
    async with rebuild_session_manager().run():
        print("[startup] MCP 服务就绪 → /mcp（鉴权：X-API-Key，需 skill 权限）", flush=True)
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
app.include_router(docs_router.router, prefix="/api/v1")
app.include_router(fs_router.router, prefix="/api/v1")
app.include_router(objects_router.router, prefix="/api/v1")
app.include_router(mcp_tools_router.router, prefix="/api/v1")
app.include_router(productdoc_router.router, prefix="/api/v1")
app.include_router(stats_router.router, prefix="/api/v1/stats")
app.include_router(telemetry_router.router, prefix="/api/v1")
app.include_router(tests_router.router, prefix="/api/v1")
app.include_router(users_router.router, prefix="/api/v1")

# MCP 服务端点（Streamable HTTP，鉴权：X-API-Key → skill 权限，纯 ASGI 中间件）。
# 显式 Route 而非 Mount：Mount 对无尾斜杠精确路径匹配不到（子 app 以 / 注册）。
from starlette.routing import Route
app.router.routes.insert(0, Route("/mcp", endpoint=mcp_asgi_app,
                                  methods=["GET", "POST", "DELETE"]))

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
