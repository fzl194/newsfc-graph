# 部署与数据迁移（内网服务器 / Docker）

> 原则：**代码进镜像、数据落宿主机磁盘**。容器无状态可随时删除重建，数据永不丢。
> 组成：`deploy/Dockerfile`（多阶段构建）+ `deploy/docker-compose.yml`（卷映射）+
> `backend/scripts/pack_data.py`（数据打包/校验）。

## 1. 目录与数据清单（迁移只动一个目录）

```
deploy/platform-data/          ← docker-compose 卷映射点（宿主机磁盘）
  assets/          图谱资产 md+图片（Command/ConfigObject/Feature/License/Task/Business）
  output/          原始产品文档解压包（bundle）
  platform.db      SQLite：索引(objects/edges) + 用户 + 任务历史 + 打点 + 回收站记录
  users.json       用户备份（库损坏时的恢复源；日常以 DB users 表为准）
  tests/           测试用例子系统
  telemetry/       打点 raw 备份
```

**迁移 = 整个 platform-data 目录**，不需要拷代码（代码在镜像里）、不需要单独导数据库。

## 2. 首次部署（内网服务器）

```bash
# ① 拷贝仓库到服务器（或只拷 graph-asset-platform/）
# ② 构建镜像（需要能访问 pip/npm 源；完全离线见 §5）
cd graph-asset-platform
docker build -f deploy/Dockerfile -t graph-asset-platform:latest .
# ③ 起服务（数据目录自动创建；首次为空库）
cd deploy && docker compose up -d
# ④ 验证：浏览器 http://<服务器IP>:8000/ （首次启动 users 空会自动建 admin 并打印 KEY）
```

## 3. 数据迁移（你现在的内网电脑 → 服务器）

```bash
# 源机（内网电脑）——先停平台（避免 SQLite WAL 半写状态被打包）
cd graph-asset-platform/backend
python scripts/pack_data.py                 # 生成 graph-asset-data-YYYYMMDD-HHMM.zip
python scripts/pack_data.py --check 上面的.zip   # 校验（platform.db/users.json 必在）

# 传输：scp / U盘 / 内网共享，把 zip 传到服务器

# 服务器
cd graph-asset-platform/deploy
docker compose down                         # 若在跑先停
mkdir -p platform-data
unzip graph-asset-data-*.zip -d platform-data/
docker compose up -d
# 验证：登录 admin（KEY 与源机相同）；统计页对象数与源机一致
```

Windows → Linux 直接适用：内部路径一律正斜杠相对路径存储，SQLite 文件跨平台通用。

## 4. 日常备份

数据全在 `deploy/platform-data/` 一个目录——定时任务对该目录打包即可：
```bash
docker compose stop && python ../backend/scripts/pack_data.py -o backup-$(date +%F).zip && docker compose start
```
（或直接备份整个目录，但**停服后备份**才保证 DB 一致。）

## 5. 离线构建（服务器无外网）

在有网的机器上构建镜像并导出：
```bash
docker build -f deploy/Dockerfile -t graph-asset-platform:latest .
docker save graph-asset-platform:latest -o gap-image.tar
# 拷到服务器后：
docker load -i gap-image.tar
# 再按 §2 ③ 起服务（compose 里已指定 image 名，不会重新 build）
```

## 6. 说明与边界

- **为什么代码不挂卷**：代码随镜像版本化（回滚=换镜像 tag），数据挂卷才能持久化——两者生命周期不同。若要在服务器上直接改代码调试，可临时加一行卷映射 `- ../backend/app:/gap/backend/app`（仅开发用）。
- 平台内「上传产品文档→自动抽取」产生的所有数据都落在 platform-data/，迁移方式同上。
- 版本升级：拉新代码 → 重建镜像 → `docker compose up -d`（数据卷不动，自动沿用）。
