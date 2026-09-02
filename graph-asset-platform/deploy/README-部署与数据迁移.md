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
                   + 8 张 AIMML 历史规则表 B_AI_*（v11，统计页数据源，只读）
  users.json       用户备份（库损坏时的恢复源；日常以 DB users 表为准）
  tests/           测试用例子系统
  telemetry/       打点 raw 备份
```

**迁移 = 整个 platform-data 目录**，不需要拷代码（代码在镜像里）、不需要单独导数据库。

## 2. 首次部署（内网服务器）

```bash
# ① 拷贝整个 graph-asset-platform/ 到服务器——必须包含：
#    backend/（后端源码）+ frontend/dist（前端构建产物：源机先 npm run build）
#    ⚠ 这两样在服务器磁盘上必须已存在：compose 把它们挂载进容器，空目录挂载会异常
# ② 构建镜像（需要能访问 pip 源；完全离线见 §5）
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

## 6. 源码与数据都落服务器磁盘（用户要求）

compose 挂载三处，**容器内零持久状态**（删容器/重建镜像/重启机器都不丢）：

| 挂载 | 服务器磁盘位置 | 作用与更新方式 |
|---|---|---|
| `/data` | `deploy/platform-data/` | 全部数据（DB/资产/原始文档/用户）；迁移备份只动它 |
| `/gap/backend` | `graph-asset-platform/backend/` | **后端源码**：改 `.py` 后 `docker compose restart` 生效 |
| `/gap/frontend/dist` | `graph-asset-platform/frontend/dist/` | **前端构建产物**：前端改动在源机 `npm run build` → 拷 dist 到服务器 → 浏览器强刷 |

说明：
- 镜像内也带了一份代码/产物作兜底（不挂卷裸 `docker run` 也能起），但 compose 部署以**服务器磁盘为准**。
- 前端源码（frontend/src）随仓库在服务器上留档；容器运行只用 dist（服务器无 node，不在服务器构建）。
- ⚠ 空目录挂载陷阱：服务器上 backend/ 或 frontend/dist 不存在时，Docker 会创建**空目录**挂入 → 服务异常。务必按 §2 ①先拷完整目录再 up。
- 平台内「上传产品文档→抽取任务」产生的所有数据都落在 platform-data/，迁移方式同上。
  其中 `.extract_gate/`（2026-08-26 抽取任务化）存放抽取闸门的沙箱与旧版备份：
  `storage/` 为待确认产出（确认后自动清）、`originals/` 为覆盖文件的旧版（按任务回退的
  还原源，随任务历史删除而清理）——迁移整体拷贝即可，不影响。
- 版本升级：更新服务器上的 backend/dist → `docker compose up -d --build`（数据卷不动，自动沿用）。
- **统计页三视图（2026-09-01，db v11；2026-09-02 改版）**：重启自动幂等建 8 张 B_AI_* 规则表（空表）。
  规则数据由内网 GaussDB 导出脚本 `AIMML历史图谱/db_tool/dump_rule_tables_to_platform.py`
  灌入 platform.db（已灌过则只需 git pull + 重启）；未灌数时统计页命令图谱的
  命令/参数/五类规则指标为 0，页面顶部显示"规则表未导入"提示。
  **MOP 动网变更场景统计**（2026-09-02）读 `platform-data/mop_scenarios.xlsx`
  （或 .csv，不走库、随时替换；管理员也可在业务图谱页直接上传）——底表列头需含
  "L1场景"…"L5场景"。运行需 SQLite ≥ 3.38（json_extract；镜像 python:3.11-slim 自带 3.46 ✓）。
  **统计缓存**：启动后台预热（数据量大时约几十秒，日志可见）；图谱数据变更后
  点统计页右上「更新缓存」按钮重建。
  详见 `docs/实施计划-统计页面重构-2026-09-01.md`。
- **Dockerfile 依赖（2026-09-03 核对修复）**：pip 清单补 `mcp` 并钉 **`mcp<2`**
  （MCP /mcp 服务的 SDK，此前 Dockerfile 漏同步——新镜像启动 import 即崩；
  2.x 改名 FastMCP→MCPServer 破坏兼容，代码基于 1.x，pyproject 同步钉版）。
  统计页/MOP/缓存全标准库零新增。镜像已本机构建 + 容器冒烟：启动全绿、
  v11 自动建 8 表、缓存预热、MCP 就绪、统计端点带鉴权 200、MOP 无底表优雅降级。
