# 语法说明：多阶段构建。
#   Stage 1 构建前端 dist；Stage 2 是运行时（后端 + 前端 dist）。
# 数据（platform-data）不进镜像——靠 docker-compose 的 bind mount 提供，服务器目录为准。

# 注：基础镜像走 DaoCloud 国内加速（直连 docker.io 很慢/被限）。
# 在有外网/已配 registry-mirrors 的环境，可把前缀去掉换回官方镜像：
#   node:20-alpine / python:3.12-slim

# ---- Stage 1: 前端构建 ----
FROM docker.m.daocloud.io/library/node:20-alpine AS frontend-build
WORKDIR /build
# 先拷 lock + package.json，利用层缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com
# 再拷源码并构建（vue-tsc --noEmit && vite build → /build/dist）
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: 运行时 ----
FROM docker.m.daocloud.io/library/python:3.12-slim
WORKDIR /app

# 后端运行时依赖（与 backend/pyproject.toml [project].dependencies 保持一致；
# 不装 dev：pytest/httpx 运行时用不到）。走清华 pypi 源加速。
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    fastapi "uvicorn[standard]" pyyaml python-multipart

# 后端代码
COPY backend/ ./backend/
# 前端构建产物（后端 main.py 把 frontend/dist 挂在根路径托管为 SPA）
COPY --from=frontend-build /build/dist ./frontend/dist

EXPOSE 80
# uvicorn 从 backend 目录起，CWD 让 `app.main` 可导入。
# 监听 80：配合 docker run --network host，uvicorn 直接听宿主 80（host 模式下 -p 被忽略，故不走端口映射）。
# 容器默认 root，可绑特权端口 80。
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
