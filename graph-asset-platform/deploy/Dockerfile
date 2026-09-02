# 图谱平台镜像（多阶段：前端构建 → 运行镜像）
# 构建：在 graph-asset-platform/ 目录执行
#   docker build -f deploy/Dockerfile -t graph-asset-platform:latest .
# 数据**不进镜像**：运行时 GAP_DATA_DIR=/data（docker-compose 挂宿主机目录）

# ---- 阶段 1：前端构建（dist 静态产物） ----
FROM node:20-alpine AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ .
RUN npm run build

# ---- 阶段 2：运行镜像（FastAPI 同时托管 API 与前端静态） ----
FROM python:3.11-slim
WORKDIR /gap/backend

# 后端依赖（与 backend/pyproject.toml dependencies 保持同步；内网无外网时见 deploy/README 离线说明）
# ⚠ 2026-09-03 补 mcp（MCP 服务 /mcp 的 SDK，2026-08-24 上线时 Dockerfile 漏同步，
#   旧清单构建的镜像会在启动 import mcp_server 时崩溃）；**必须钉 mcp<2**——
#   2.x 把 FastMCP 改名 MCPServer（API 破坏性变更），代码基于 1.x（开发环境 1.27）
# 统计页/MOP 全标准库无新增依赖
RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" pyyaml python-multipart chardet beautifulsoup4 "mcp<2"

# 代码进镜像（数据走卷）：app/ + 前端 dist
# dist 路径对应 main.py 的 Path(__file__).parents[2]/frontend/dist → /gap/frontend/dist
COPY backend/app ./app
COPY --from=frontend /web/dist /gap/frontend/dist

# 数据目录由 GAP_DATA_DIR 指到 /data（compose 挂宿主机）；容器内无状态、可随时重建
ENV GAP_DATA_DIR=/data
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
