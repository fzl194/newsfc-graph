# MCP 配置指南

> 图谱查询 MCP 服务（`/mcp`，5 工具）的完整接入配置：服务端启动 → 获取 API KEY →
> 各类客户端配置 → 云 Agent 用户身份传递 → 验证排障。
> 工具参数与返回明细见 [../图谱平台接口文档.md](../图谱平台接口文档.md) §2。

## 0. 接入模型（一图看懂）

```
Agent（Claude Code / Cursor / 云 Agent）
  │
  │  header：X-API-Key（鉴权，客户端配置一次，所有用户共用）
  ▼
http://<平台地址>:8000/mcp
  │
  ├─ get_domains      全部业务域 md（推荐第一步）
  ├─ get_md           批量取对象 md（沿 [[ID]] 逐层下钻）
  ├─ search_objects   元数据搜索（id/名称/层/网元）
  ├─ search_md        正文全文搜索（FTS5 相关度召回）
  └─ get_object       单对象结构化 + 出边
        ▲
        └─ 每次工具调用必传：AGENT_USERNAME / AGENT_SESSION_ID（用户工号+会话ID，
           从沙箱环境变量读取后传入——打点归因用，不影响结果）
```

鉴权走 **header（静态，配一次）**；用户身份走 **工具参数（动态，每次调用传）**——两者分离，
云 Agent 平台只需配一次 KEY，就能区分每个实际使用者。

---

## 1. 服务端准备

```bash
cd graph-asset-platform/backend
python -m uvicorn app.main:app --port 8000 --host 0.0.0.0
```

- MCP 端点：`http://<服务器IP>:8000/mcp`（与 Web 界面同端口同进程，无独立服务）
- 传输协议：**Streamable HTTP**（stateless + 纯 JSON 响应；无需会话保持，无 SSE 长连接）
- 内网部署注意：`--host 0.0.0.0` 才能让其他机器访问（默认只监听本机）

## 2. 获取 API KEY

MCP 鉴权要求 `skill` 权限：**`can_skill` 或 `can_frontend` 任一为真**（`is_admin` 隐含全权）。

### 方式一：Web 界面（推荐）

admin 登录平台 → 用户管理 → 新建/编辑用户：
- 勾选 `skill` 权限（can_skill）
- KEY 可让系统生成，也可**自定义**（规则：≥8 位、不含空格、无前缀要求、全局唯一）

### 方式二：管理 API（admin 的 KEY 调用）

```bash
# 新建用户（KEY 自动生成，响应里返回）
curl -X POST http://127.0.0.1:8000/api/v1/users \
  -H "X-API-Key: <ADMIN_KEY>" -H "Content-Type: application/json" \
  -d '{"username": "agent-svc", "can_skill": true}'

# 或给已有用户自定义 KEY
curl -X PATCH http://127.0.0.1:8000/api/v1/users/agent-svc \
  -H "X-API-Key: <ADMIN_KEY>" -H "Content-Type: application/json" \
  -d '{"set_key": "my-key-at-least-8-chars"}'
```

> KEY 即凭证等价于密码：请通过内网安全渠道分发，不要提交进代码库。
> 首次部署自动生成的 admin KEY 以 `gap_` 开头（见 README「启动」节）。

## 3. 客户端配置

### 3.1 Claude Code（命令行，一次配置）

```bash
claude mcp add --transport http graph http://<平台地址>:8000/mcp \
  --header "X-API-Key: <你的KEY>"
```

### 3.2 Claude Code（项目级 `.mcp.json`，随仓库共享）

```json
{
  "mcpServers": {
    "graph": {
      "type": "http",
      "url": "http://<平台地址>:8000/mcp",
      "headers": { "X-API-Key": "<你的KEY>" }
    }
  }
}
```

### 3.3 Cursor / 通用 MCP JSON 格式

```json
{
  "mcpServers": {
    "graph": {
      "url": "http://<平台地址>:8000/mcp",
      "headers": { "X-API-Key": "<你的KEY>" }
    }
  }
}
```

### 3.4 云 Agent 平台（平台级配置一次）

在云 Agent 的 MCP 服务配置页填：

| 配置项 | 值 |
|---|---|
| 类型 / 传输 | Streamable HTTP（或 "HTTP"，**不是** stdio / SSE-only） |
| URL | `http://<平台地址>:8000/mcp` |
| 鉴权 Header | `X-API-Key: <平台统一KEY>`（所有用户共用这条连接） |

用户身份**不在这里配**——见下节，随每次工具调用动态传入。

---

## 4. 用户身份传递（云 Agent 场景，关键）

云 Agent 的 MCP 连接是平台级共用的，但每个使用者的工号/会话ID不同——因此
**身份不进 header，进工具参数**。全部 5 个工具都有两个必填参数：

| 工具参数 | 取值来源（沙箱环境变量） | 用途 |
|---|---|---|
| `AGENT_USERNAME` | `_AGENT_USERNAME` | 使用者工号 → 打点 `operator`（谁在用） |
| `AGENT_SESSION_ID` | `_AGENT_SESSION_ID` | 会话ID → 打点 `session_id`（会话维度统计） |

### 给 Agent 的系统提示词模板（直接粘贴到云 Agent 指令配置）

```text
【图谱 MCP 工具调用规范】
调用 graph 服务的任何工具（get_domains / get_md / search_objects / search_md /
get_object）时，必须同时传入：
- AGENT_USERNAME：从环境变量 _AGENT_USERNAME 读取的当前用户工号
- AGENT_SESSION_ID：从环境变量 _AGENT_SESSION_ID 读取的当前会话ID
这两个参数仅用于平台取用统计与追溯，不影响查询结果，但不可省略。

【图谱查询建议路径】
1. 先 get_domains 看全部业务域，按用户需求锁定业务域；
2. 不确定对象 ID 时用 search_md 按业务关键词召回，或 search_objects 按名称/层过滤；
3. 用 get_md 取完整 md，提取正文中的 [[ID]] 引用继续逐层下钻（业务层→任务层→特性层→命令层）。
```

> 说明：Agent 的工具参数名不允许下划线开头，所以环境变量是 `_AGENT_USERNAME`
> 而工具参数是 `AGENT_USERNAME`——名字去掉了下划线前缀，值原样传递。
> 若云平台 MCP 配置支持 header 环境变量插值（如 `${_AGENT_USERNAME}`），
> 可评估改为 header 注入（不依赖 LLM 自觉传参，更可靠）——当前按传参设计。

## 5. 工具速查

| 工具 | 必填参数 | 选填参数 | 一句话用途 |
|---|---|---|---|
| `get_domains` | 工号 + 会话ID | — | 全部业务域 md（入口，量小可全读） |
| `get_md` | `ids[]`(1~100) + 工号 + 会话ID | `version` | 批量取对象完整 md（全程主力；总量≤2MB） |
| `search_objects` | 工号 + 会话ID | `q`/`layer`/`type`/`nf`/`version`/`domain`/`scenario`/`page`/`size` | 元数据搜索（id/名称，不搜正文） |
| `search_md` | `q` + 工号 + 会话ID | `layer`/`type`/`nf`/`version`/`limit`/`offset` | 正文全文搜索，相关度+高亮片段 |
| `get_object` | `id` + 工号 + 会话ID | `version` | 单对象结构化详情+出边 |

## 6. 验证与排障

### 6.1 连通性验证（curl / Postman，无需 MCP 客户端）

```bash
# initialize —— 返回 JSON-RPC 响应即通（stateless，无需会话）
curl -s http://<平台地址>:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: <你的KEY>" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
        "protocolVersion":"2025-03-26","capabilities":{},
        "clientInfo":{"name":"curl","version":"0.0.0"}}}'

# tools/list —— 应返回 5 个工具
curl -s http://<平台地址>:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: <你的KEY>" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

### 6.2 错误对照

| 现象 | 原因 | 处理 |
|---|---|---|
| HTTP 401 `missing or invalid api key` | 未带 / KEY 错误 | 检查 header 名大小写不敏感、KEY 是否被重置 |
| HTTP 403 `permission denied` | 用户无 skill 权限 | admin 给该用户勾 can_skill（或 can_frontend） |
| 客户端连接超时 | 端口未放通 / 未 `--host 0.0.0.0` | 先 `curl http://<IP>:8000/docs` 验证 Web 通 |
| 工具报「全文索引重建中」 | 平台启动初 FTS 后台重建 | 稍等重试（重建中搜索明确报错，不返回残缺结果） |
| get_md 报 ids/总量超限 | >100 id 或响应 >2MB | 按提示分批，每批 ≤50 个 id |
| MCP 工具 isError=true | 参数校验失败/对象不存在 | 错误信息为中文描述，按提示修正 |

### 6.3 打点核对（确认归因是否生效）

调用几次工具后，admin 在平台统计页（或 telemetry 表）按 `caller=mcp` 过滤：
`operator` 列 = 传入的工号，`session_id` 列 = 传入的会话ID，
`params`/`result` 列 = 该次调用的入参 JSON 与出参摘要（截断 2KB）。

若 `operator` 为空 → Agent 没传 `AGENT_USERNAME`，检查 §4 系统提示词是否配置。

---

## 7. 管理员工具配置（前端「MCP 工具」页）

admin 登录平台 → 顶部「MCP 工具」页（仅 admin 可见），可配置：

| 配置项 | 说明 | 生效语义 |
|---|---|---|
| 工具启用开关 | 5 个工具逐个启用/禁用 | **禁用 = 隐藏 + 拦截**：tools/list 不再出现该工具（Agent 看不到），直连调用也返回明确中文错误「已被管理员禁用」兜底 |
| 工具描述 | 每个 tools/list 里 Agent 看到的说明文字 | **完全替换**默认描述（代码内 docstring）；清空 = 恢复默认 |
| 服务总体说明 | initialize 时 Agent 收到的 instructions | **完全替换**默认说明；清空 = 恢复默认 |

要点：

- **全局生效**：一套配置对所有 API KEY / 所有用户生效（不做按用户差异化）
- **保存即生效，无需重启**：启用状态与描述每请求实时读库；总体说明即时应用
- **重启不丢**：配置持久化在 platform.db（`mcp_tools` 表 + `meta.mcp_instructions`），服务重启自动恢复
- 配置 API（admin 的 KEY 调用）：`GET /api/v1/mcp-tools` 查看全量；`PATCH /api/v1/mcp-tools` 保存（body：`{"tools": [{"name", "enabled", "description"}], "instructions": "..."}`）
