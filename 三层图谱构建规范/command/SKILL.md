---
name: command-layer-build
description: 把产品文档 MML 命令构建成命令层资产 md（命令 + 配置对象）。复用原始md+加YAML+加底"边"章节；参数不单独建（在命令md原文内）。
sop_version: 0.13.0
---

# 命令层构建 SKILL

> 产品文档 MML 命令 → 命令层资产。构建 **命令 + 配置对象** 两类（**参数在命令 md 原文内，不单独建**）。每个资产 = 顶 YAML + 正文（命令复用原文 / 配置对象合成）+ 底"边"章节。

## 何时用
拿到一个网元的产品文档（原始归档 或 已导出 md），构建命令层资产时。

## 输入
| 参数 | 说明 |
|---|---|
| `--nf` | 网元，如 `UDG` |
| `--version` | 版本，如 `20.15.2` |
| `--storage` | 资产根（默认 `三层图谱资产`） |
| `--mml-dir` 或 `--product-doc` | MML 命令 md 目录（已解压）/ 原始产品文档归档（自动导出到 `{storage}/output/`） |
| `--intranet-edges` | 内网命令关联图谱 json（可选，命令↔命令边来源） |

## 输出（`{storage}/` 下）
- `Command/{nf}/{version}/{nf}@MMLCommand@{命令名}.md` — 每命令一个（复用原始 md）
- `Command/{nf}/{version}/assets/*.png` — 命令正文图片（全版本共享，hash 去重）
- `ConfigObject/{nf}/{version}/{nf}@ConfigObject@{对象名}.md` — 每 object_keyword 一个（命令族聚合，合成）
- `ConfigObject/{nf}/{version}/assets/*.png` — 配置对象说明图片（继承自命令，重解析）
- 各 `_build_manifest.json`

## 构建流程（`scripts/build_all.py` 编排）
1. **导出**（仅 `--product-doc`）→ `{storage}/output/`
2. **命令** `build_commands.py`：扫命令源 md → 复用原文 + YAML（11 字段）+ 边；**图片拷入 `Command/{nf}/{ver}/assets/`、文档引用统一改写为 `[[ID]]`**（命令索引用第一趟内存命令名集）；规则见 [conventions/资产图片与引用处理](../conventions/资产图片与引用处理.md)
3. **配置对象** `build_configobjects.py`：按 object_keyword 聚合；**仅配置类命令(ADD/MOD/DEL/RMV/SET)产生**配置对象（查询/动作类不产生、但可关联已存在的）→ 合成 md（说明 + 边）；说明段继承自命令 md（引用已是 `[[ID]]`），仅补图片重解析

## 边
| 边 | 出现位置 | 来源 |
|---|---|---|
| 命令 → 配置对象（操作配置对象） | 命令 md | 对象对应**已存在**配置对象（由配置类命令产生）；查询/动作类也可关联 |
| 配置对象 → 命令（被操作） | 配置对象 md | 同 object 的所有命令（**反向，闭环**）|
| 命令 → 命令（参见） | 命令 md | 正文扫描（参见/通过MOD/参考）|
| 命令 → 命令（参数引用） | 命令 md | 内网命令关联图谱（可选）|

边用逻辑ID `[[{网元}@{Type}@{local}]]`，版本动态解析。产出后允许人工/Agent 调整、添加。

## 参数去哪了
参数说明表在**命令 md 原文**里（原样保留），不单独建 Parameter md、不进命令 YAML。查参数直接读对应命令 md。

## 规范引用
- 字段：[字段定义](字段定义.md)　·　骨架：[template/](template/)
- 引用/ID/存储：[需求与路线](需求与路线.md) §6–§8
- 核查：[check.md](check.md)

## 核查（构建后必做）
产出交 [check.md](check.md)：字段必填 / ID 格式 / 边合理（命令↔配置对象闭环）/ 命令原文完整 / manifest。
