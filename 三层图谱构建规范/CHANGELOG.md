# CHANGELOG

本目录所有变更留痕。**append-only**，最新在上。

---

## 条目格式

每条变更必须包含：

| 字段 | 说明 |
|---|---|
| 版本号 | `MAJOR.MINOR.PATCH`（规则见 [演进机制](演进机制.md)） |
| 日期 | YYYY-MM-DD |
| 变更类型 | 新增 / 修改 / 废弃 / 修复 |
| 变了什么 | 具体改动 |
| 为什么 | 动机 |
| 影响哪些文件 | 文件路径清单 |
| 对已建资产的影响 | 无 / 需重建 / 可兼容 |

## 版本号规则（简述）

- **MAJOR**：不兼容变更，已建资产需重建
- **MINOR**：向后兼容的新增（加字段、加可选规则）
- **PATCH**：措辞澄清、笔误，无行为变化

> 完整规则见 [演进机制](演进机制.md)。

---

## [0.19.0] - 2026-08-17

### 变更（Task 层去版本 + UNC/UDG 计划状态刷新 + 中间态清理）

采纳 [CR-20260817-001](task/change-requests/CR-20260817-001-Task层去版本.md)。用户决策：**Task 层剥离版本属性**——atom/compound/feature_task 引用的命令/特性知识有版本，但"配置方法/编排"是版本无关方法论（使用时按目标环境自选版本）。平台（graph-asset-platform）已于 2026-08-11 先行适配（registry `scope: task` / classify 无版本路径 / DB version=None），本版规范与资产对齐。

- **Task 层无版本成为层约定**（`task/SKILL.md`）：
  - 存储 `{Type}/{nf}/`（去 `{ver}` 目录）；YAML **8 字段 → 7 字段**（删 `version`；atom/FT 为 id/type/name/name_zh/nf/ref/status，compound 为 command_set 替 ref）；ID 本就不含 version。
  - 新增"无版本（v0.19.0）"声明块 + 三类对象总览/输入/输出路径同步。
  - collect 示例命令澄清：`--version` 保留为**输入选择器**（定位命令/特性层带版本输入），非 Task 层属性；audit/gen_compound_index 无 `--version`。
- **字段定义**：三类对象 8→7 字段；version 移入"已删"清单。
- **template**：三张 tpl 删 `version:` 行。
- **check.md**：三类字段必填行改"无 version 字段（出现即 fail）"；audit 脚本调用签名去 `--version`。
- **agent.md / 批次计划 / 构建提示词**：路径 `{nf}/{ver}/`→`{nf}/`、`--version` 同步清理（保留 UNC 计划 atom-input 的 `--version 20.15.2`——输入选择器）。
- **UNC 计划状态刷新**：头部 stale"下一批 UNC-A3"→ 实际进度（P0/F0/A1-A4/B1-B6/C1/C2 已完成，磁盘 173 FT / 59 CT；下一批 C3）；§1.2 atom-input 注记已删除（2026-08-17，可重跑再生）；§1.3 存量更新。
- **UDG 计划状态刷新**：头部标注 4.1/4.2/4.3 全域完成（246 FT + 46 CT），计划转历史参考。
- **中间态清理（用户批准，2026-08-17）**：删 `_intermediates/atom-input/`（1350 md / 20M，UDG 280 + UNC 1070）、5 个旧 zip 快照（148M）、`__pycache__` ×3、`.pytest_cache`。

**为什么**：平台侧 Task 去版本已落地半月，规范/资产/脚本未同步——三层不一致会导致新构建产物与平台 registry 校验冲突（frontmatter 多 version 字段虽被扩展接口容忍，但路径 `{Type}/{nf}/{ver}/` 会被 fs 上传归位到 `{Type}/{nf}/`，审计脚本也按旧路径找资产）。UNC 计划头部"下一批 A3"严重误导恢复上下文（实际已过 B6/C2）。

**影响哪些文件**：`task/SKILL.md`、`task/字段定义.md`、`task/check.md`、`task/agent.md`、`task/template/*.tpl`（3）、`task/UNC领域批次构建计划.md`、`task/UDG领域批次构建计划.md`、`task/UDG特性与步骤Task构建提示词.md`、`task/change-requests/CR-20260817-001-*.md`（新建）、`VERSION`、`CHANGELOG.md`。删除：`三层图谱资产/_intermediates/`、5 zip、缓存。

**对已建资产的影响**：**迁移（非重建）**——存量 atom 1885 / CT 105 / FT 419 三步迁移：①目录上提 `{Type}/{nf}/20.15.2/*`→`{Type}/{nf}/*`；②YAML 删 `version:` 行（内容不变）；③`_index.md` 随迁；迁移后跑 `audit_atoms --nf {nf}` + `audit_compound_feature --nf {nf}` 验证 0 fail。`task/scripts/` 4 脚本路径逻辑同步适配（本 CR 声明，随后落地）。

**迁移落地记录（同日）**：
- 脚本适配：`audit_atoms`（`--version`→`--cmd-version` 输入选择器 + 无版本字段检查）/ `audit_compound_feature`（`--version`→`--feature-version` + D4 补子文档磁盘检查，修 v0.18.0 手工回填子文档的 manifest 盲区）/ `gen_compound_index`（`--version` 删 + `_index` frontmatter 去 version）/ `collect_command_examples`（atomtask 检查与中间态输出去版本路径，`--version` 保留为输入选择器）/ `audit_feature_atom_coverage`（atom 路径去版本）。pytest 9 绿。
- 资产迁移：6 组目录上提 + 2411 md YAML 去版本；文件数守恒（AtomTask UDG 535/UNC 1350，CompoundTask 47/60，FeatureTask 246/173）；version 残留 0。
- audit 验证：atom UDG 444 + UNC 1325 抽查 100% 合规（仅 LOW name_zh 对齐建议）；CT/FT UNC 全绿（fail=0）；UDG fail=2 为**存量缺陷非迁移引入**（D3：`pcc-predefined-rule-chain` 被引用于声明含 GWFD-020354 但该 FT 0 处引用；D4：GWFD-020423→`IPFD-014000` 断链——UDG 特性层缺建该"路由功能"特性，UNC 侧存在；Feature 层 020423 概述亦引用），转对抗评审轨道处置。

**类型**：MINOR（沿 0.8.4 删 source 字段先例——删 YAML 字段 + 路径变更，存量走显式迁移，内容不重建）。

---

## [0.18.0] - 2026-08-11

### 变更（语料演进 SOP + 头增强/防欺诈试点：业务专题纳入 Feature 簇）

新增顶层 [语料演进SOP.md](语料演进SOP.md)——**基于任意新语料（业务专题/配置指导书/方案文档等，格式不预设）自适应演进图谱**的框架，并用头增强/防欺诈族做 worked example。源于用户发现"配置指导书"等更丰富语料冷启动没收，且未来会持续提供各类新语料。

- **新 SOP `语料演进SOP.md`（Procedure 体裁，自适应框架，非固定流水线）**：
  - **恒定原则**：跨层根因定位（症状层≠根因层）/ 闭包与可追溯 / 不臆造 / 冲突调和 / 可复现性纪律。
  - **自适应主流程**：Phase 0 语料辨识（画像）→ Phase 1 策略构建（Agent 据画像定制策略单，不套模板）→ Phase 2 执行 → **Phase 3 个性化校验**（Agent 据策略自定校验项 + 恒定不变量）→ Phase 4 留痕。
  - **工具原语**（可组合工具箱，非一刀切脚本）：语义目录发现 / 实体抽取正则 / 倒排索引 / 特性映射表解析 / 场景切分 / CS 特性关系矩阵归属——复用 `collect_command_examples.py` 骨架。
  - **两参考模式**（非穷举）：模式 A 结构化语料（业务专题型）/ 模式 B 裸场景语料（配置指导书型，不点名特性→命令指纹反推入 CS）；遇新形态 Agent 自扩。
  - "配置指导书不点名特性"对策：决策树（特性映射表 > 特性码 > License > 命令指纹 > 场景语义反推；多对一入 CS 特性关系矩阵）。
- **头增强/防欺诈试点（模式 A worked example）**：
  - **B1 Feature 簇手工回填 4 簇 15 子文档**（GWFD-110261/110262/110263 + GWFD-110401）：从业务专题补 激活/原理/约束限制/参考信息 子文档（110401 无参考信息源，未臆造），frontmatter+stopgap 注+命令引用转 `[[UDG@MMLCommand@...]]`+图片拷 assets/+`属于特性`/`包含子文档` 边。
  - **B2 FT 核对**：4 个 FT 对照新可用激活文档——110261/110262/110401 CLEAN，110263 补 WELLKNOWNPORT PRIORITY=10（MEDIUM）；引子补链簇内激活子文档。
  - **B3 NSH 标注**：业务专题有 NSH头增强但无特性映射/FT——标"疑似新特性待确认特性码"，不盲建。
  - **B4 CR**：[feature/change-requests/CR-20260807-002](feature/change-requests/CR-20260807-002-业务专题纳入Feature簇构建.md)——建议补丁=扩 `build_features.py` 加 topic-dir + 特性映射解析 + `_DOC_TYPE_KEYWORDS` 补"差异" + check 加"激活齐全性"；可复现声明=手工回填待自动化重建。
- **README**：顶层结构 + 阅读顺序加入 `语料演进SOP.md`。

**为什么**：冷启动 Feature 层只扫特性指南，业务专题（含激活文档）系统性漏收，致一批特性簇仅 概述.md（FT 反而建对）。用户未来会有大量配置指导书（格式不统一、不一定点名特性），需自适应演进框架持续补全图谱，而非每次重跑冷启动。头增强试点把案例沉淀为模式 A 通用方法。

**影响哪些文件**：新增 `语料演进SOP.md`、`feature/change-requests/CR-20260807-002-*.md`；修改 4 × Feature 簇（补 15 子文档+图片+边）、4 × FeatureTask（引子链+110263 PRIORITY）、`README.md`、`VERSION`、`CHANGELOG.md`。

**对已建资产的影响**：**可兼容，无需重建（本轮）**。手工回填 4 簇是 stopgap（待 `build_features.py` 扩展后 Feature 层重建，MAJOR 级，CR-20260807-002 已声明）；重建时核 stopgap 注与命令引用转换正确继承。新 SOP 是规范新增，不影响既有构建。

**类型**：MINOR（向后兼容新增：SOP + 试点回填；Feature 层自动化重建待 CR-20260807-002 集成执行）。

---

## [0.17.0] - 2026-08-07

### 变更（task 层信息可追溯性 + SOP 权威统一）

采纳 [CR-20260807-001](task/change-requests/CR-20260807-001-Task层信息可追溯性与SOP权威统一.md)。源于全量 UDG Task 层（246 FT + 46 CT + ~250 atom）信息丢失审计：解决 SOP/handoff/template 三方矛盾，新增命令级+参数级+反向追溯+信息源边界对账 4 类闭包审查项，定义 command_set 成员与 CT 抽取阈值。

- **SOP 权威统一**：
  - `SKILL.md §B.2` FT 正文正式定为 **7 段**（增 `## 参数核对`），与 template 对齐——修 SOP（6 段无参数核对）与 template/handoff（7 段）矛盾。
  - `SKILL.md` 顶部加"单一权威"声明：SKILL+字段定义+template+check 为唯一权威，handoff 为历史交接不作规范引用源。
  - 三份 handoff（4.1/4.2/4.3）顶部加"历史化标注"。
  - `SKILL.md sop_version` 0.2.0 → 0.17.0（历史 stale 一并修）。
- **字段精确定义**：`字段定义.md` compound `command_set` = 本 CT `## 配置方法` 编排的组成 atom 命令名（不含上游前置/不含引用的其他 CT）——防 010155 C1/C2 类（ADD VPNINST 误入 command_set+上游）。
- **atom 范围澄清**（`SKILL.md §A.2`）：atom 全建，但 FT/CT 配置流程只编排引用配置类 atom（ADD/MOD/SET/DEL/RMV/LOD/持久化 STR）；查询/调测类 atom 建但不被 FT/CT 引用（调测剥离）。
- **CT 抽取阈值入 SOP**（`SKILL.md §B.4/§B.5`）：<3 distinct 配置 atom → 直引不抽 CT（floor）；相位同义操作化定义（配置目标/对象链/共享命令顺序 三项 ≥2）；Jaccard 是门槛、配置语义判定优先。
- **check.md 增 4 类闭包审查项**（feature_task 表）：B1 命令闭包 / B2 参数闭包 / B3 反向追溯 / B4 信息源边界对账（防 112001 类：边界声明覆盖簇子集但静默漏配 SET NETYPE / 镜像 SIP 子功能）。
- **审查独立性统一**（`check.md` 审查角色纪律）：独立审查须非构建者 Agent；构建方可自派子 Agent 预审但不替代独立审查（统一 SOP §B.7 与历史 handoff §5.9 分歧）。
- **audit 脚本扩展规格（交集成轨道实现，本 CR 出规格）**：`audit_compound_feature.py` D5（atom 覆盖）info→warning；新增 **D6 命令闭包（CRITICAL）** + **D7 参数闭包（CRITICAL）**——Feature 簇配置命令/param=value ⊆ FT/CT 或标注，否则 fail；盲区独立性（Feature 侧抽取正则与 builder 不同源）。
- **数据修复（本批 T3 就地）**：GWFD-112001（2C+1H：信息源边界枚举排除+决策点可选分支）/ GWFD-110471（1M：补激活方法表+参数核对）/ GWFD-110301（1M：stale 待回填标注）。

**为什么**：用户核心担忧"特性层→task 层无信息丢失，尤其命令级/参数级"——审计确认防线原仅靠人工对抗评审（D5 info 不 fail，无闭包检查）。抽样 ~108 FT 仅 1 真缺陷（112001）但根因是 SOP 未强制信息源边界对账；同时 SOP/handoff/template 三方矛盾致构建/审查标准不一。本版把闭包检查沉淀为审查项+脚本规格，统一权威源。

**影响哪些文件**：`task/SKILL.md`（§B.2+权威声明+§A.2+§B.4/§B.5+sop_version）、`task/字段定义.md`（command_set）、`task/check.md`（B1-B4+独立性+D5/D6/D7 规格）、`task/handoff/UDG-{4.1,4.2,4.3}-交接.md`（历史化标注）、`task/change-requests/CR-20260807-001-*.md`（新建）、`VERSION`、`CHANGELOG.md`；UDG 数据 `FeatureTask/.../GWFD-{112001,110471,110301}.md`（T3 修）。

**对已建资产的影响**：**可兼容，无需重建**。B1-B4 为审查项新增；抽样审计 ~108 FT 仅 112001 不合规（已修），定向扫查 60 边界声明 FT 确认 59/60 合规；command_set 定义澄清不改已对齐 CT（CR-20260803-001 已对齐）。`audit_compound_feature.py` D6/D7 待集成实现后全量复跑可 expose 任何残余闭包缺陷。

**类型**：MINOR（向后兼容新增：审查项+SOP 澄清+字段定义精确化；无资产重建）。

---

## [0.16.0] - 2026-08-03

### 变更（task 层跨层核查自动化 + check 盲区补全 + 脚本治理）

采纳 [CR-20260803-001](task/change-requests/CR-20260803-001-跨层核查自动化与check盲区.md)。把 compound/feature_task 跨层一致性核查从纯人工提升为「自动化预检 + 人工复核」，补 3 个盲区，并治理 `task/scripts/`。

- **check.md 增补审查项**：
  - **G1** — compound 审查项新增「复用库」行：`CompoundTask/{nf}/{ver}/_index.md` 必须存在且与各 compound 的 command_set/被引用于 一致（SOP §B.0/§B.4 原要求，check 此前未覆盖）。
  - **G2** — compound + feature_task「边规定」行强化：`被引用于` 声明必须 == 实际反向引用集合（从 FT 反推；UDG 实测曾 34/34 全空，纯人工未发现）。
  - **G3** — atom/compound/feature_task 三段表后各加「自动化核查」小节，指向 audit 脚本；明确「过=未必全对，报错=一定有问题」，守住核查独立性。
  - foundation 豁免：`status: foundation` 骨架 compound 允许 `command_set: []`。
- **脚本治理（`task/scripts/`）**：
  - 提升 `_audit_cross_layer.py` → `audit_compound_feature.py`（参数化 `--nf/--version`；D1-D4 fail 级、D5 atom 覆盖 info 级；D3 反链 check-and-flag，不 auto-write）。
  - 提升 `_bootstrap_index.py` → `gen_compound_index.py`（参数化；可重生；SKILL §B.3 step6 引用）。
  - 删除 9 个临时脚本：`_audit_atoms`（旧版，被 `audit_atoms` 取代）/`_extract_truth`/`_gen_lst_atoms`/`_gen_set_atoms`/`_enrich_set_atoms`/`_enrich_thin_set`/`_reconcile_compounds`（迁移已完）/`_audit_cross_layer`+`_bootstrap_index`（被参数化版取代）。
  - 规范脚本收敛为 4 个：`collect_command_examples` / `audit_atoms` / `audit_compound_feature` / `gen_compound_index`。
- **结构补全**：新建 `task/change-requests/README.md`（层包标准要求，task 层此前缺失）。
- **数据修复（审计顺手抓的真实 bug）**：`addr-pool-hierarchy` 截断 wiki 链接 `[[UDG@AtomTask@ADD CONFL` → `[[UDG@AtomTask@ADD CONFLICTIPV6]]`；`session-n4-interface`（foundation）补 `command_set: []` + 被引用于反链。

**为什么**：UDG compound/feature_task 阶段核查发现 check.md 纯人工在 280+ atom / 34 compound / 46 FT 量级下易漏（_index 缺失、被引用于 34/34 全空都没人工看出来）；脚本沉淀为规范后后续 NF/版本可直接复用。

**影响哪些文件**：`task/check.md`、`task/SKILL.md`（§B.3 step6）、`task/scripts/`（删 9 + 提升 2）、`task/change-requests/README.md`（新建）、`VERSION`、`CHANGELOG.md`；UDG 数据 `CompoundTask/UDG/20.15.2/_index.md`（重生）+ `addr-pool-hierarchy`/`session-n4-interface`（修）。

**对已建资产的影响**：**可兼容，无需重建**。UDG 34 compound 此前已就地对齐，`_index` 已建；本次仅把一次性动作沉淀为规范脚本 + 审查项。UNC 同构同样适用。

---

## [0.15.0] - 2026-07-29

### 变更（task 层采集脚本扩展原始产品文档检索源 + 命令真相全文 + 泛化约定）
- **`collect_command_examples.py` ① 命令真相段改为命令层 md 全文 verbatim**（不再只抽功能/参数/notes 片段），agent 据此梳理不漏信息。
- **新增原始产品文档检索源（②-B）**：脚本在 `--doc-root` 下按语义目录名（业务专题、网络部署）自动发现目录，扫其中 md 提取命令配置样例（端到端方案/部署配置），与特性层（②-A）合并进 ③ 差异汇总。
- **命中正则适配 `[**CMD**](url)` 链接形式**：原始产品文档命令引用是粗体+md链接（特性层资产是纯粗体 `**CMD**`），抽 `cmd_token_re` 统一兼容两种，修复旧正则匹配不到原始文档的问题。
- **泛化（不硬编码网元/版本/路径）**：语义目录名自动发现适配 UDG（业务专题在 `特性部署/`）与 UNC（在 `网络部署/`）结构差异；产品文档根由 `--doc-root` 显式指定；CLI 新增 `--doc-root`/`--raw-dirs`/`--no-raw`，未传 `--doc-root` 降级为只扫特性层（向后兼容，等价旧行为）。
- **新增 `--skip-built`（默认开）**：跳过已建 AtomTask 的命令，中间态只给"待建缺口"（有命中 + 未建 atom）生成，避免给已建命令重复生成无用中间态；`--no-skip-built` 关闭（用于重建/全量统计）。
- **性能优化：倒排索引 + 索引预判**：`--all` 模式预建倒排索引（`build_command_index`，一次扫所有文档提取命令候选），命中走索引；索引无候选的 no-hit 命令直接跳过（不读命令 md、不 aggregate）。复杂度从 O(命令×文档) 降到 O(文档×候选提取)，UDG 4577 / UNC 8498 命令从几小时降到分钟级。
- **`task/SKILL.md`** A.3 输入表（命令真相改全文、原始产品文档升为 ②-B 推荐源）+ A.5 第一步（脚本行为/用法/默认开关 `--skip-built`+`--skip-existing`/`--dry-run`/性能说明）+ 新增"原始文档检索的泛化约定"小节。

### 为什么
- 全力构建第一批 AtomTask（出现在特性中的 1226 命令，已建 517，缺口 806）。原脚本只抽命令片段 + 只扫特性层，配置样例不够丰富；原始产品文档的业务专题（端到端方案）是最丰富的配置样例源（实测 ADD URR 命中 22 特性 + 24 原始文档）。同时不同网元/版本产品文档路径结构不一致，必须泛化以保证脚本跨网元/版本可复用。

### 影响哪些文件
- 修改：`task/scripts/collect_command_examples.py`、`task/SKILL.md`、`VERSION`、`CHANGELOG.md`

### 对已建资产的影响
- 无（atom 产出结构不变，字段/模板/check 不动；仅 atom 构建输入更丰富。已建 517 个 atom 不受影响，新建 atom 可基于更丰富的中间态）。

### 类型
- MINOR（向后兼容的新增：采集脚本加可选检索源 + 正则适配 + 泛化约定；不改 atom 产出结构）

---

## [0.14.1] - 2026-07-23

### 变更（清理一次性迁移产物 + 去当前文档里的 legacy 悬空引用）
- **删除 task 层一次性迁移工程文档**（自声明"不是 SOP"）：`task/迁移指南-旧atom到AtomTask.md`、`task/迁移指南-旧compound到CompoundTask.md`、`task/迁移指南-旧feature_task到FeatureTask.md`。
- **删除 task 层一次性迁移脚本**：`task/scripts/migrate_old_{atoms,compounds,feature_tasks,business}.py` 及对应 `__pycache__` 缓存。（`collect_command_examples.py` 保留——task 构建现行 helper）
- **去掉 business 层文档里指向"已不维护旧 SOP"的悬空引用**：`business/SKILL.md` 6 处"沿用旧 `assets/business/业务层级构建SOP.md` §X"框架 + 末行 legacy 指针；`business/check.md` 顶注"沿用旧 …审视流程.md"。内容早已被新文档吸收，去框不去内容。
- **去掉 FeatureGraph legacy 免责声明**：`feature/SKILL.md` / `feature/需求与路线.md` 边段标题的"不依赖 FeatureGraph jsonl"、需求与路线决策状态的"老资产 legacy 只做 check 不作输入"。
- **去掉 `task/agent.md` 的旧编号注解**（"弃 0-/1-/2- 旧编号"）。
- **`scripts/README.md`** 清掉"待纳入（原 assets/scripts/…）"的 stale 迁移路线表与"纳入原则"迁移框，改为反映现状（顶层 `scripts/` = 阶段0 导出器；各层构建脚本在各自 `{layer}/scripts/`）。

### 为什么
- 迁移已完成、旧资产体系（0-/1-/2- 编号、FeatureGraph jsonl、`assets/business` 旧 SOP）不再作为输入；一次性迁移文档/脚本与 legacy 悬空引用留着只会误导、稀释规范约束力。

### 影响哪些文件
- 删除：`task/迁移指南-*.md`(3) + `task/scripts/migrate_old_*.py`(4) + `__pycache__/migrate_old_*.{atoms,compounds,business}.pyc`(3)
- 修改：`business/SKILL.md`、`business/check.md`、`feature/SKILL.md`、`feature/需求与路线.md`、`task/agent.md`、`scripts/README.md`、`VERSION`、`CHANGELOG.md`

### 对已建资产的影响
- 无（纯规范文档清理，不改任何构建行为与产出物）。

### 类型
- PATCH（清理一次性迁移产物 + 去悬空引用，无行为变化）

---

## [0.14.0] - 2026-07-20

### 变更（business/ 层包补齐 + 业务层输出格式对齐新约定）
- **business/ 从"仅种 agent.md"补齐为完整层包**：新增 `SKILL.md`（Procedure：7 步 CS 流程 + 复用判定 + 特性关系矩阵 + 前置门 + 双向回填 + 族内顺序，沿用旧 `assets/business/业务层级构建SOP.md`）、`check.md`（R1 5 维度 + R2 辅助 + 严重级，沿用旧审视流程）、`字段定义.md`（BD/NS/CS 字段权威）、`template/`（business_domain / network_scenario / configuration_solution 三骨架）、`change-requests/README.md`；更新 `agent.md`。
- **业务层输出格式对齐 v0.13.0 新约定**（输入 = 老 `assets/business/`，输出格式全部翻新）：
  - **ID**：两段 `Type@slug`（业务跨 UDG+UNC，无 nf/version，与平台 `default_registry.yaml` 一致）
  - **资产位置**：`三层图谱资产/Business/{domain}/[{scenario}/]`（domain/scenario 树保留，权威 = `classify.py` + registry `path_fields`）
  - **引用**：裸 `[[逻辑ID]]`（与 `## 边` 同源，无路径无 .md），**取代**旧 `[名](assets根路径.md)` / 编号引用（`2-00006` → `[[UDG@FeatureTask@...]]`）
  - **关系段**：`## 关联`（叙述）→ `## 边`（typed edges：下游场景 / 上游域 / 编排特性 / 复用步骤·命令 / 被引用于）
  - **frontmatter**：6 字段 → 7 字段（+ `name_zh`，对齐其他层）；BD 无 scenario；无 nf/version/ref
  - **无证据**：业务层不建证据文件/不设 `## 证据` 段（同 task 层）；md 结构统一 **YAML 顶 → 内容中 → `## 边` 底**（`## 边` 承载 BD↔NS↔CS↔task 双向关系，必为最后一段）
- **scripts/ 与层包标准**：business 不建 `scripts/`（Procedure 体裁，无构建脚本）；`层包标准.md §2` 加脚注"Procedure 体裁层（task/business）若无构建脚本可省略 scripts/，须在 SKILL.md 说明"。
- **License 去重修复（附带，issue #1）**：`feature/scripts/build_licenses.py` 的 manifest `licenses` 列表现在按 logical_id 去重（同一 license 跨多源文档重复登记导致 UNC `license_count` 虚高 773→实际 448）；UNC manifest 已就地修正为 448。
- **命名规范-建议修正（附带，issue #3）**：`conventions/命名规范-建议.md` 过时的"4 段 ID"建议改为实际落地的"3 段 `{nf}@{Type}@{local}`（version 不进 ID）"，并补 task 弃编号、文件名=完整 ID 等已落地共识。

### 为什么
- task 层已按新约定落地，business 层作为最上层必须对齐，否则跨层引用（CS→FeatureTask）断链。
- 平台后端（`graph-asset-platform`）的 `default_registry.yaml` 已定义业务层为 cross scope / 2 段 ID / `Business/{domain}/[{scenario}/]` 路径——业务层规范须与此一致，否则平台扫描 classify 失败。

### 影响哪些文件
- 新增：`business/SKILL.md`、`business/check.md`、`business/字段定义.md`、`business/template/*.md.tpl`（3 个）、`business/change-requests/README.md`
- 修改：`business/agent.md`、`层包标准.md`（§2 脚注 + §5 状态）、`README.md`（状态表）、`VERSION`、`CHANGELOG.md`
- 修复：`feature/scripts/build_licenses.py`、`三层图谱资产/License/UNC/20.15.2/_build_manifest.json`、`conventions/命名规范-建议.md`
- 设计文档：`docs/superpowers/specs/2026-07-20-business-layer-spec-design.md`

### 对已建资产的影响
- **无（规范层变更，不改已建资产）**。业务层资产仍在老位置 `assets/business/`（旧格式），**资产迁移 `assets/business/` → `三层图谱资产/Business/`（含 ID/引用重写）是后续单独任务**，不在本次范围。
- License UNC manifest 已就地修正（448，与磁盘一致），无需重建。

---

## [0.13.0] - 2026-07-18

### 变更（文档引用统一为 `[[逻辑ID]]` + 三层落地 + 前端查名渲染）
- **引用格式：相对路径 → 裸逻辑引用 `[[ID]]`**。特性/命令/ConfigObject 三层正文里的命令引用、特性引用统一成 `[[{nf}@MMLCommand@{cmd}]]` / `[[{nf}@Feature@{code}]]`，与 `## 边` 段同源；前端一套正则识别 + 跳转。**接续并取代 v0.12.0 的相对路径引用**（v0.12.0 的特性引用是 `[文字](../../../../Command/…)`，本版起全改 `[[ID]]`）。
- **特性引用精确到具体子文档**（非笼统指特性文件夹）：特性层构建前预算「源文件名→目标文档ID」映射，特性引用按源文件名精确命中——概述引用→`[[{nf}@Feature@{code}]]`，子文档引用→`[[{nf}@Feature@{code}-{slug}]]`。修了一个关键 bug：子文档文件名**不含特性码**（码在文件夹路径里），旧逻辑靠叶子名匹配特性码会漏掉全部子文档引用（曾误剥为纯文字）。
- **命令层 / ConfigObject 首次具备图片+引用处理**（v0.12.0 只做了特性层）：移植 `rewrite_images`/`rewrite_doc_refs` 到 `command/scripts/_common.py`；`build_commands.py` 接线（命令索引用第一趟内存 `command_names`，图片拷到 `Command/{nf}/{ver}/assets/`）；`build_configobjects.py` 对继承自命令的 `desc` 补图片重解析（`[[ID]]` 透传）。
- **前端 `[[ID]]` 查名渲染**：后端新增 `GET /api/v1/names`（{id:name} 字典）；前端 `MdPreview.vue` 拉 `/names` 建 id→name 映射，正文 `[[ID]]` 显示目标 name（无则显 ID）、`title` 存 ID；点击跳转复用既有 `inlineLinksIntoHtml→emit('navigate')→syncTo` 链路（零改）。
- 文档同步：`conventions/资产图片与引用处理.md`（引用规则改 `[[ID]]`+子文档精度+三层落地）、`feature/SKILL.md`+`check.md`（引用闭环改 `[[ID]]`）、`command/SKILL.md`+`check.md`（sop_version 0.13.0、新增图片闭环/引用闭环两项）。

### 修复
- **`build_features.py:assign_slugs` 死循环**：撞名消歧的 `while True` 在「两个文档 slug 相同且父目录相同/为空」时无限前补父目录（字符串一直变长、`resolved` 永真）→ UNC 某特性触发后构建挂死。改为「一轮父目录消歧后撞名数未减则加序号收尾」。此 bug 先于 v0.13.0 存在，UNC 数据首次触发；UDG 未受影响（无此碰撞）。

### 为什么
- v0.12.0 的相对路径引用能点但脆（目录树一搬就断），且与 `## 边` 的 `[[ID]]` 两套格式；用户要求统一成 `[[ID]]` 供前端自动识别跳转，并精确到特性的具体子文档（特性是多文档文件夹）。

### 自测
- **特性 UDG**：258 特性/865 文档；图片 830；引用解析 8258 / 剥死链 968。其中命令引用 7227、特性概述引用 1424、**特性子文档引用 1170**（修 bug 前为 0，全被误剥）；0 残留相对路径。
- **命令 UDG**：4577 命令；图片 493；引用解析 1267 / 剥死链 35。**ConfigObject UDG**：1175 个 / 图片 219。
- **命令 UNC**：图片 635 / 引用解析 4951；**ConfigObject UNC**：2325 / 图片 279。
- **特性 UNC**：470 特性；图片 2155；引用解析 20862 / 剥死链 4637（含子文档精确引用，如 `[[UNC@Feature@IPFD-010001-控制接口震荡特性]]`）。
- 抽样：`[[UDG@MMLCommand@SET UPGTPPATH]]`、`[[UDG@Feature@GWFD-010102-配置GTP_PFCP路径管理参数]]`（子文档精确命中）、`[[UNC@MMLCommand@DSP PORT]]`。

### 对已建资产的影响
- **三层资产均需重建**（已按 v0.13.0 重建：特性/命令/ConfigObject × UDG+UNC）。引用格式从相对路径切到 `[[ID]]`，旧相对路径引用全部失效需重建。

### 类型
- MINOR（引用格式变更 + 命令/ConfigObject 新增图片/引用处理；向后兼容新增，但已建资产需重建）

---

## [0.12.0] - 2026-07-17

### 变更（特性层图片纳入 + 文档引用改写/清理）
- **推翻 v0.10.0 的「图片不纳入」决策**：特性层资产现在**保留图片**。每特性文件夹下一个扁平 `assets/`，合并该特性全部源 md 旁的 `{md名}.assets/` 图片（按文件夹 hash 去重，同名异内容按源 slug 前缀消歧），md 里 `![]({旧名}.assets/x.png)` 改写为 `![](assets/x.png)`。
- **文档引用改写/清理**（特性 md 正文里的 `[文字](相对路径)`）：
  - **命令引用**（叶子名/标签含全角括号 `（CMD）` 或标签即命令名）→ 改写为到 `Command/{nf}/{ver}/{nf}@MMLCommand@{CMD}.md` 的相对路径；需命令资产已存在。
  - **特性引用**（叶子名含 `[A-Z]+FD-\d{6}`）→ 改写为到 `Feature/…/{nf}@Feature@{code}/概述.md` 的相对路径（v1 跳概述）。
  - **其余/不可解析**（PDF/外链/未建命令/分类码）→ **剥 URL 留文字**（`[文字](死链)` → `文字`）。
  - 外链 http/锚点/图片语法不动。
- 新增跨层约定 `conventions/资产图片与引用处理.md`（所有层共用；本次仅特性层落地，命令层/ConfigObject 后续照搬）。
- 实现：`feature/scripts/_common.py` 增 `build_command_index / build_feature_codes / extract_cmd_name / rewrite_images / rewrite_doc_refs`（纯标准库，URL 解析用 `_parse_link_url` 正确处理含空格路径）；`build_features.py` 在每特性文件夹建 `assets/`、按文档循环改写；manifest 增 `images_copied / doc_refs_resolved / doc_refs_stripped`。
- 文档同步：`SKILL.md`（图片纳入+输出+构建流程，sop_version 0.12.0）、`字段定义.md`（图片/引用均不进 YAML 注）、`check.md`（增图片闭环/引用闭环两项，原文完整行更新）。

### 为什么
- 源 md 旁有 `.assets/` 图片（全量 UDG 特性指南 431 目录/844 PNG）+ 正文相对路径文档引用，旧构建器只搬 md 文本 → **图片全丢、引用全成死链**。资产不自包含、引用不可跳。

### 自测（全量 UDG）
- 258 特性 / 865 文档（与 v0.10.0 一致，无回归）。
- **图片**：830 处引用对应图片拷入，落盘 797 张（去重后）；0 残留 `{旧名}.assets/` 旧路径；0 个 `.assets` 目录（全改扁平 `assets/`，178 个特性文件夹有图）。抽样 `GWFD-020401`：`![](assets/zh-cn_image_0226536218.png)` 指向实存 png。
- **引用**：解析 7867（命令 7227 + 特性 461 + 余量）/ 剥死链 1359；0 残留指向 output/ 的相对路径。抽样命令引用 `../../../../Command/UDG/20.15.2/UDG@MMLCommand@SET UPGTPPATH.md` 目标实存；PDF 等死链已剥成纯文字。
- 实现期修了一个关键 bug：URL 含空格（`UDG MML命令`、`GWFD-000101 支持…assets`）被 `split()[0]` 截断 → 改 `_parse_link_url` 按 `"` 标题切、保留空格，命令解析 33→7227、图片 437→830。

### 对已建资产的影响
- **Feature 侧需重建**（已按 v0.12.0 重建：图片+引用就位）。License 侧无图片/引用问题，不受影响。

### 类型
- MINOR（新增图片纳入 + 引用改写规则；向后兼容新增，但已建 Feature 资产需重建）

> 注：本版本与并行的 [0.11.0]（task 层 AtomTask 迁移）互不冲突——task 工作明确不动 command/feature 层；二者仅共享 VERSION/CHANGELOG，本条目置于其上。

---

## [0.12.0] - 2026-07-17

### 新增
- **task 层 AtomTask 资产构建（二期：UNC 全量迁移）**。基于 v0.11.0 已验证的迁移脚本:
  - 迁移脚本扩展支持 `--nf UNC` 参数（默认 `--nf UDG` 保持向后兼容）；模块级 `NF/VERSION` 通过 CLI 覆盖
  - UNC atom 资产特点: 280 个 atom（UDG 237 个），无 `nf:` 字段但 ref 同 UDG 格式 (`UNC@20.15.2@MMLCommand@...`)；命令行分布 ADD 154 / SET 73 / MOD 27 / RMV 13 / DSP 9 / 其他 4
  - 共建产出：`三层图谱资产/AtomTask/UNC/20.15.2/UNC@AtomTask@{COMMAND}.md`（**280 个**）

### 自测
- UDG 237/237 + UNC 280/280 = **517/517** 全通过 ad-hoc 验证（`hermes-verify-migrate.py`，含 YAML 8 字段 / id 三段式 / ## 边 单行 / 禁词零命中 / 业务内容保留 / 关键转换点）
- 业务正文总量 1,509,997 字符 / 40,372 行（UDG 711k / UNC 799k，平均 2,920 字/篇）
- ad-hoc 验证脚本支持 `--nf UDG|UNC` 自适应（cmdmap 数量、期望命令、关键转换点都按 NF 分流）

### 修复
- **破损 markdown 链接保护**: UNC 0-00164 源文件含破损 markdown `[ADD CHGTARI](task/UNC/20.15**（warning，rule-0-03168）`（粗体闭合符截断），迁移脚本 MD_LINK_RE 收紧为 `[^)\s*][^)\s]*`（拒绝目标含 `*`），不误吃破损链接，原样保留
- **DP 编号语义改写 `（DP 0-NNNNN，xxx）` 形式**: 之前 regex 只匹配纯 `(DP 0-NNNNN)`，遇到带 ",xxx" 的形式残留 `（，xxx）`。扩展为 `(DP 0-NNNNN，xxx)` -> `(决策点，xxx)`
- **code block 保护机制**: 之前 strip 函数可能误吃 ``` 围栏代码块和行内代码里的字符。新增 `_protect_code_blocks` / `_restore_code_blocks`，所有 strip 在 code block 保护上下文跑、最后还原
- **strip_dp_inline_refs 顺序**: 之前 `replace_bare_atom_refs` 在 `strip_dp_inline_refs` 之前跑，把 `DP 0-00019` 提前吃成 `DP [[UDG@AtomTask@SET LICENSESWITCH]]`，导致 9 条 DP 编号语义改写模板全部失效。调成 `strip_dp_inline_refs` **先于** `replace_bare_atom_refs`
- **尖括号 `0-XXXXX` 引用**: 新增 `<0-00215 产出>` 形式识别（IPSECINTFCFG 围栏外 `//` 注释行），strip_paren_atom_num 加 #4 刀

### 为什么
- 用户要求"UNC 也要一并处理下，UNC 的命令级别的 task"。UNC 与 UDG 是同构资产（YAML/H1/## 配置方法/## 决策点/## 约束/## 关联 一致），可直接复用 v0.11.0 迁移脚本，扩展 `--nf` CLI 参数即可支持

### 影响文件
- 改 `task/scripts/migrate_old_atoms.py`（加 argparse、加 _protect_code_blocks、5 类 regex 修复）
- 新增 `三层图谱资产/AtomTask/UNC/20.15.2/UNC@AtomTask@{COMMAND}.md`（**280 个**）

### 对已建资产的影响
- **task 层资产** — UDG 237 个 + UNC 280 个 AtomTask 全建
- **command/feature 层** — 无影响
- 旧的 `assets/task/UNC/20.15.2/0-XXXXX.md` 由迁移指南 §0 明确"只迁格式不删源"，保留为可追溯的旧版本

### 类型
- MINOR（task 层资产新增；向后兼容；v0.11.0 UDG 产物不动）

---

## [0.11.0] - 2026-07-17

### 新增
- **task 层 AtomTask 资产构建（一期：旧 atom 全量迁移）**。按 [task/迁移指南-旧atom到AtomTask.md](task/迁移指南-旧atom到AtomTask.md) 执行：
  - 新增 `task/scripts/migrate_old_atoms.py`（一次性迁移脚本；纯标准库；237 个 atom 一次性批处理）
  - 产出：`三层图谱资产/AtomTask/UDG/20.15.2/UDG@AtomTask@{COMMAND}.md`（**237 个**，与旧 atom 一对一）
  - YAML 8 字段：`id`/`type`/`name`/`name_zh`/`nf`/`version`/`ref`/`status`，id 三段式 `{nf}@AtomTask@{命令}`（无 version/无编号），ref 三段式 `{nf}@MMLCommand@{命令}`
  - 文件名 = 完整 ID；命令名含空格时保留（如 `UDG@AtomTask@LST POOL.md` / `UDG@AtomTask@EXP MML.md`）
  - 业务正文原样保留（只改格式不改内容）；删除证据/配置对象链接/Task↔Task/被引用于；保留并转译命令层 markdown 链接为 `[[{nf}@MMLCommand@{cmd}]]`；旧四段式 wiki 占位剥 `20.15.2@` 段、按 Type 分流
  - ## 边 段统一为 `- 对应命令: [[{nf}@MMLCommand@{命令}]]` 单行

### 自测
- 237 个 atom 全部通过 §6 校验清单：YAML 8 字段齐全且顺序正确 / id 三段式无 version 无编号 / ref 三段式 / name=name_zh / 文件名=ID / ## 边 只有对应命令一行 / 全部禁词零命中（`0-XXXXX`/`rule-0-`/`DP 0-`/`configobject/`/`evidence/`/`(command/`/`(task/`/`@20.15.2@`/YAML 旧字段 `task_layer`/`task_intent`/`task_logical_name`/`source_evidence`/`****`/空括号）
- 业务正文总量 667,466 字符 / 16,091 行（平均 2,816 字/篇）；命令行分布 ADD 147 / SET 72 / LST 5 / MOD 5 / DSP 3 / LOD 3 / EXP 1 / STR 1
- 命令名从每个旧 `0-XXXXX.md` YAML 的 `ref` 字段末段现场读取（不依赖附录 A 静态表，单源可信）

### 边界 case 处理（指南未明文，遇到后沉淀到脚本）
- 全角/半角括号 + 全角/半角逗号都要吃 `rule-0-XXXXX`
- `（warning，rule-0-00110 同族）` / `（critical，rule-0-00443，命令 notes）` 等多级来源标记一并删
- `**rule-0-00178-impl**` 单独成粗体标题时删（仅 0-00214 出现 1 次）
- 正文裸 `0-XXXXX` 不在 markdown 链接/wiki 占位/括号里 → 转 `[[UDG@AtomTask@{cmd}]]`（如 `License 0-00019` / `须 0-00144 先生效` / `引用 0-00215 产出`）
- 括号里 `0-XXXXX.XXX` / `0-XXXXX:XXX`（编号+点/冒号+参数引用形式）→ 删编号段
- `§0-XXXXX` / `feature-rule 0-XXXXX` / `selection_rule 0-XXXXX` 引用 → 删
- 旧 wiki4 占位单层方括号变体 `[UDG@20.15.2@DecisionPoint@0-XXXXX]`（CONTCATE 系列）→ 按 Type 分流
- `0-00XXX.md` 链接（未建对象的占位符）→ 用显示文字做命令名
- `command-evidence/0-XXXXX` 自引用（仅 NTPSVR）→ 整段删
- DP 编号 `DP 0-XXXXX` 正文出现按语义改写：`另存演进` → `另存一个演进决策`；`仅在 ... 标注` → `仅在决策点标注`；`决策点驱动` / `由决策点编排` / `见决策点` 等
- 占位删除后残留的双重粗体 `****` 兜底清理

### 为什么
- 旧 atom (237 个 `0-XXXXX.md`) 用了旧 ID 体系（`UDG@20.15.2@Task@0-XXXXX`），不符合 task 层新 SOP（id 用命令名做锚，三段式）；同时引用形式 / 关联段结构 / 证据字段等都需按新规范重构。本次只迁 atom (1:1)，compound (1-) / feature_task (2-) 留待后续批次

### 影响文件
- 新增 `task/scripts/migrate_old_atoms.py`（一次性脚本，~400 行）
- 新增 `task/迁移指南-旧atom到AtomTask.md`（迁移 SOP 文档）
- 新增 `三层图谱资产/AtomTask/UDG/20.15.2/UDG@AtomTask@{COMMAND}.md`（**237 个**）

### 对已建资产的影响
- **task 层资产** — 全新产出，旧 atom 不动（保留在 `assets/task/UDG/20.15.2/0-XXXXX.md` 作历史档案）；atom 阶段闭环完成
- **command/feature 层** — 无影响
- 旧的 `assets/task/UDG/20.15.2/0-XXXXX.md` 由迁移指南 §0 明确"只迁格式不删源"，保留为可追溯的旧版本

### 待用户确认（不影响本批）
- `三层图谱资产/AtomTask/UDG/20.15.2/` 当前 git 仍 ignore（沿用 `三层图谱资产/` 的全局 ignore）。是否要为 `AtomTask/` 单独放行？详见迁移指南 §9

### 类型
- MINOR（task 层资产新增；向后兼容；旧 atom 资产保留）

---

## [0.10.0] - 2026-07-16

### 变更（采纳 CR-20260716-001）
- **Feature 模型：文件夹模型 → feature_code 聚合模型**。`build_features.py` 改为遍历 feature-dir 下**全部 md**，按其路径里**最深的 feature_code** 归组（最深=最具体的特性，跳过上级分类码）。同 code 的所有 md 进一个特性文件夹。
  - 解决 v0.9.0 三大缺口：① 嵌套子目录 md 漏收（`glob("*.md")` 非递归）② 特性 md 作为文件落在分类目录里扫不到 ③ 同 code 多文件夹互相覆盖。
- **ID 机制：doc_type 降为 YAML 字段，改用源文件名 slug 作 ID 区分位**。
  - 子文档 ID = `{nf}@Feature@{code}-{slug}`（slug=源文件名去 `_{数字id}.md` 后缀）；概述仍 = `{nf}@Feature@{code}`。
  - 原因：doc_type 是多对一分类（一特性下 N 个「原理」文件），拿它当 ID 后缀会撞名覆盖（如 IPFD-014001 的 28 个原理文件争抢 `-原理`）。同特性 slug 撞名 → 前补父目录消歧。
- `_common.py`：加 `slugify_doc()`、`derive_doc_type()`（文件名关键词优先、否则按所在子目录）；doc_type 关键词补 `调测/部署/术语`；删无用 `sanitize_doc_type`。
- **修复双 H1**：`build_features.py` 之前 prepend `# {doc_name}`，但原文自带 H1 → 全部双 H1。改为**对齐命令层**：body 不 prepend、保留原文 H1（单 H1）；`name` 改从原文首个 H1 取（修掉无文件夹特性 name 回退纯 code 的问题）。
- **修复 License 漏建**：`LICENSE_HEAD_RE` 之前要求段头 control_id 为纯数字 `(\d+)`，但实际 control_id 有**两种格式**（纯数字 `81203214` + 字母数字 `82200CKP`）→ 漏建 89 个 license。放宽为 `([A-Z0-9]+)`，code 锚定 LKV 格式。License 98 → **187**。
  - 教训：v0.9.0 核查 License"98/98 干净"是假象——核查用了和构建**同一条正则**，盲区一致查不出漏建。`check.md` 增"核查独立性"项。
- **修复所需License 边误报**：之前扫概述**全文**取 LKV code，把互斥/交互表里**别的特性的 license** 误挂成本特性所需（如 GWFD-010108 错挂 GWFD-110910 的 LKV3G5RBMS01）。改为**只扫「可获得性」章节**；依赖特性边的 `or md_text` 兜底同步收紧为空。所需License 边 225→168，**真误报 82→0、真漏 0**（对可比特性集与旧版 feature_requires_license.jsonl 完全对齐）。
- 文档同步：`SKILL.md`（聚合模型+文件名ID）、`字段定义.md`（Feature 7 字段、doc_type 不进 ID、control_id 两格式）、`check.md`（ID 唯一/聚合/概述存在/单H1/核查独立性 检查项）、`需求与路线.md`（决策状态）。

### 自测
- 全量 UDG：**258 特性 / 865 Feature 文档 + 187 License**（v0.9.0 仅 127/417 + 98）。铁证 IPFD-014001 支持OSPF：源 29 个 md 全收齐，每个 ID 唯一；铁证 LKV3G5RBMS01（control_id `82200CKP`）从漏建→已建。
- 全局 0 重复 ID / 0 同文件夹重名 / 865 文档单 H1；无概述特性 1 个（NPFD-010005）、多概述候选 4 个（取首个并记录）。
- 边闭环 1929 条，闭环 1885（**97%**）；剩 44 断裂全是真·无资产引用（2 跨产品 license + 41 指向分类码/无概述特性 + 1 NPFD-010005），非构建 bug。
- **所需License 边精度**：对可比特性集与旧版 `feature_requires_license.jsonl` 完全对齐（真误报 0、真漏 0）；168 条边里 25 条是旧版未收录特性的合法边。
- 用老版本（FeatureGraph legacy，**仅 check 不作输入**）对比：老 303(含 83 幽灵)/831 doc；本次 258/865 覆盖 216/220 真特性（漏的 4 个是分类目录码，不建才对）+ 多收老漏的 25 个真特性。

### 对已建资产的影响
- **Feature + License 侧均需重建**（v0.9.0 资产作废，已删重建）。

### 类型
- MINOR（Feature 收集模型 + ID 机制变更；向后兼容的新规则集合，但已建 Feature 资产需重建）

---

## [0.9.0] - 2026-07-16

### 新增
- **特性层能力包**（`feature/`）：与命令层同构
  - **Feature 文件夹模型**：每特性一个文件夹，里面每个 md（概述/激活/参考信息…）都是 `YAML+原文+边` 统一资产，按 ID 引用（概述=`{nf}@Feature@{code}`，子文档=`…-{doc_type}`）
  - **License 段落模型**：控制项 md 按 `#### [{control_id} {code} {名}]` 切段，每 license 一资产
  - `SKILL.md` / `字段定义.md`（Feature 6字段 + License 7字段）/ `check.md` / `template/`
  - `scripts/`：`build_features`（文件夹+doc类型识别+边推导）/ `build_licenses`（段切分）/ `build_all`（编排）/ `_common`（共享）
  - 边全从源文档推导（Feature↔License 所需License↔对应特性、Feature→Feature 依赖、概述↔子文档），**不依赖 FeatureGraph jsonl**

### 自测
- IPv6功能子集：**6 特性 / 22 文档 + 98 license**。验证：文件夹结构、doc类型识别（概述/激活/参考信息/原理…）、概述边（所需License+依赖特性）、license 段切分+对应特性边

### 类型
- MINOR（新增特性层能力包）

---

## [0.8.4] - 2026-07-16

### 变更
- **删除 `source` 字段**（命令 + 配置对象）：命令正文即原始产品文档内容（复用原文），source 指向 output/ 属冗余；配置对象合成、source 无意义
- **原始产品文档不进资产**：`build_all` 的 `--product-doc` 改为导出到**临时目录**（不写 `{storage}/output/`）；资产只有 `Command/` + `ConfigObject/`
- 字段数：命令 12→11、配置对象 10→9；文档（字段定义 / SKILL / check）同步去 source
- 验证：三层图谱资产/ 仅 Command+ConfigObject、无 source 字段、无 output/

### 类型
- MINOR（字段删减 + 存储模型简化；命令正文内容不变，pre-1.0 资产重建无迁移负担）

---

## [0.8.3] - 2026-07-16

### 修复（文档同步 + 规则定稿）
- **配置对象产生规则定稿**：只有配置类命令(ADD/MOD/DEL/RMV/SET)产生配置对象；查询(LST/DSP)/动作(ACT)不产生（但可关联已存在的）。全量 UDG 配置对象 2107→1175（剔除查询/动作专属对象）
- 文档同步到当前实现：
  - 重写 `check.md`（旧规则全替换：三段式逻辑ID、逻辑ID文件名、关系统一进"边"章节、`source` 字段、配置类产生规则、参数不单独建）
  - `字段定义.md` 配置对象改 10 字段（+`object_kind`）、正文仅 `## 说明`
  - `SKILL.md` 补"配置类才产生配置对象"规则、边表更新、sop_version 0.8.3
- 清空样例资产目录 `三层图谱资产/`（交付干净状态）

### 类型
- PATCH（文档同步 + 规则收窄；命令层构建行为对齐最终规则）

---

## [0.8.2] - 2026-07-16

### 修复（测试反馈 5 问题）
1. **非命令混入**：`集中配置概念` 等无"中文（英文码）"标题的页面被误收 → `parse_title` 强制命令标题模式，跳过（4580→4577，过滤 3）
2. **边假阳**：`参见:[[...ADD A]]` 正文片段误匹配 → 边校验（只引真实存在的命令，2 趟收名集）+ regex 收紧（object token ≥2 字符）
3. **冗余**：TOC 链接行 + 标题 anchor `(#xxx)` 导出残留 → `clean_md` 清洗
4. **命令↔命令边**：校验后保留真实边（1326 命令有"参见"边，如 `ADD URR → MOD CFGTHRESHOLD`）
5. **配置对象无描述**：补 ADD 命令"命令功能"作描述（对应原 jsonl `description`）

### 影响
- 重写 `build_commands.py`（过滤 + 清洗 + 2 趟校验）；改 `build_configobjects.py`（补描述）
- 重跑全量 UDG 验证：4577 命令 + 2210 配置对象，5 问题全解

### 类型
- PATCH（构建质量修复；输出微调：原文清洗 + 配置对象补描述）

---

## [0.8.1] - 2026-07-16

### 清理 / 交付
- `command/` 清理为干净任务包：删 obsolete `调研-输入输出与存储格式.md`（旧全量抽取路线，已被 `需求与路线.md` 取代）+ `scripts/__pycache__`
- 修 `agent.md` / `check.md` 旧"三类对象"表述 → 命令+配置对象两类（参数在命令 md 内）；修 agent.md 已删调研文档的断链
- 构建样例资产目录 `三层图谱资产/`（全量 UDG：**4580 命令 + 2210 配置对象**，自包含 `output/`，source 路径资产根相对、边闭环验证通过）

### 类型
- PATCH（文档清理 + 样例产物；无构建行为变更）

---

## [0.8.0] - 2026-07-16

### 变更
- 命令层对象收窄为 **命令 + 配置对象** 两类：**参数不单独建 md**（参数说明表在命令 md 原文内）
- 删 `build_parameters.py`；新增 `build_configobjects.py`（按 object_keyword 聚合命令族 → 配置对象 md，**反向边闭环**）
- 新增 `_common.py`（共享解析/YAML/边工具）
- 新增 `build_all.py` **端到端编排器**：原始产品文档(自动导出到 {storage}/output/) 或 已解压目录 → 命令 → 配置对象

### 自测
- 计费控制子集：**40 命令 + 17 配置对象**端到端通过。配置对象 URR 验证：聚合 ADD/LST/MOD/RMV URR 命令族，边 `被操作` 与命令的 `操作配置对象` **双向闭环**

### 为什么
- 用户明确：参数在命令 md 内不单独建；命令层=命令+配置对象；要端到端（原始文档→资产）

### 影响文件
- 新增 `command/scripts/{_common,build_configobjects,build_all}.py`
- 删 `command/scripts/build_parameters.py`
- 重写 `command/{SKILL,字段定义}.md`（2 类对象）；更新 需求与路线 / README

### 类型
- MINOR

---

## [0.7.0] - 2026-07-16

### 新增
- **命令层能力包核心**（`command/`）：
  - `SKILL.md` 构建流程（输入 5 项 → 输出；模块化边）
  - `字段定义.md`（12 YAML 字段，来源/规则）
  - `template/command.md.tpl`（骨架）
  - `scripts/build_commands.py`（构建器，纯标准库；模块化边：`edge_configobject` 代码推导 / `edge_cmdref_body` 正文扫描 / `edge_cmdref_intranet` 内网图谱可选）

### 自测
- 计费控制子集 **40 命令构建通过**（0 跳过）。ADD URR 验证：YAML 12 字段全对（id 网元在前、`applicable_nf=[PGW-U,UPF]`、`effect_mode=立即生效` 正确抽取）、原始 md 原样保留、边正确（`[[UDG@ConfigObject@URR]]` 推导 + `[[UDG@MMLCommand@MOD CFGTHRESHOLD]]` 正文扫出）

### 为什么
- 命令层需求全锁定（`需求与路线.md`），落地**可测试**的能力包：另一个 Agent 直接跑脚本即可验证

### 影响文件
- 新增 `command/SKILL.md` / `字段定义.md` / `template/command.md.tpl` / `scripts/build_commands.py`
- `VERSION` → 0.7.0

### 类型
- MINOR

---

## [0.6.0] - 2026-07-15

### 新增
- 顶层 `层包标准.md`：每层文件夹统一结构标准（加新层照此，确保四层同构）
- `feature/agent.md` / `task/agent.md` / `business/agent.md`：**恢复**上轮重构误删的其它层构建师人设（已按层下沉、对齐 per-layer 模型）
- `command/需求与路线.md`：忠实记录命令层新需求与路线转变（复用原始md + YAML frontmatter，非全量抽取；evidence 不拷贝直接引用 output；引用以资产根相对路径）

### 为什么
- 统一目录管理需罗列清楚，确保其它层照标准构建；上轮重构误删其它层 agent.md 需恢复；命令层路线重大调整必须记录以免遗忘

### 影响文件
- 新增 `层包标准.md` / `feature/agent.md` / `task/agent.md` / `business/agent.md` / `command/需求与路线.md`
- 更新 `README.md`（引用层包标准 + 各层状态）、`VERSION` → 0.6.0

### 对已建资产的影响
- 无

### 类型
- MINOR（向后兼容新增）

---

## [0.5.0] - 2026-07-15

### 重构
- 结构改为"**全局顶层 + 每层独立能力包**"（整体=大能力包，每层=独立能力包）
- 顶层 `agents/` 解散（构建师 / 核查下沉到各层）
- 顶层 `change-requests/` 下沉到各层（→ `command/change-requests/`）
- `command/` 成为完整独立包：`agent.md` + `check.md` + `change-requests/` + 调研

### 为什么
- 每层构建要独立可测。全局放顶层，每层下沉；层与层互不依赖

### 影响文件
- 移动 `agents/命令构建师.md` → `command/agent.md`（角色引用同步改为本层 check / 本层 change-requests）
- 移动 `change-requests/` → `command/change-requests/`
- 删除顶层 `agents/`（特性/Task/业务构建师 + 核查师 + SOP维护师——随各层开建时在层内重建）
- 新增 `command/check.md`（命令层核查：角色纪律 + 审查项类别）
- 重写 `README.md`（结构原则 + 统一层包模板 + 每层协作闭环）

### 对已建资产的影响
- 无（尚无资产；纯规范结构重组）

### 类型
- MINOR（结构重组，向后兼容；无绑定 spec 变更）

---

## [0.4.0] - 2026-07-15

### 新增
- `conventions/命名规范-建议.md`：基于现有 `assets/` 的命名观察 + 统一建议（advisory）

### 为什么
- 现有资产命名存在 NF 隔离/非隔离两类、大小写不统一、命令语义段空格等问题。先给统一建议，各层细化时定夺后再升格为绑定规则

### 影响文件
- 新增 `conventions/命名规范-建议.md`
- 更新 `README.md`（结构 + 状态）、`VERSION` → 0.4.0

### 对已建资产的影响
- 无（advisory，非绑定；现有 `assets/` 不据此改动）

### 类型
- MINOR（向后兼容的新增）

---

## [0.3.0] - 2026-07-15

### 新增
- `agents/` 人设组件：6 个特化 Agent 角色
  - 4 个构建师（命令/特性/Task/业务，按层特化）
  - 1 核查师（独立审查，与构建方分离）
  - 1 SOP 维护师（处理 change-request，修规范）

### 为什么
- 构建工作由不同人设完成，避免单一 Agent"自建自审"。核心是职责分离：**构建 ≠ 核查 ≠ 维护**

### 影响文件
- 新增 `agents/README.md` + 6 个人设规格文档（命令构建师/特性构建师/Task构建师/业务构建师/核查师/SOP维护师）
- 更新 `README.md`（结构 + 状态 + 阅读顺序）、`VERSION` → 0.3.0

### 对已建资产的影响
- 无（尚无资产；人设规格只定角色边界，具体构建方法在各层 SOP）

### 类型
- MINOR（向后兼容的新增）

---

## [0.2.0] - 2026-07-15

### 新增
- `scripts/` 组件：构建管线（产品文档 → 资产）
- 纳入阶段0 脚本 `product_doc_md_exporter_optimized.py`（复制自仓库根目录，原文件保留）

### 为什么
- 本规范的输入起点是**原始产品文档**，不是已导出的 md。必须把"产品文档→md"这第一环纳入，否则 Agent 有 SOP 却没入口工具

### 影响文件
- 新增 `scripts/README.md`
- 复制 `product_doc_md_exporter_optimized.py` 到 `scripts/`（根目录原文件保留）
- 更新 `README.md`（结构 + 状态 + 阅读顺序）、`VERSION` → 0.2.0
- 仓库根 `README.md`：标注同名副本亦在规范包
- 规范文档（README / 演进机制 / change-requests）去除部署术语（内网/外网），统一为角色表述（SOP 维护方 / Agent）

### 对已建资产的影响
- 无（尚无资产基于本规范构建；脚本复制一份，原文件保留，行为不变）

### 类型
- MINOR（向后兼容的新增）

---

## [0.1.0] - 2026-07-15

### 新增
- 初始架构骨架

### 为什么
- 建立规范的元框架（Agent 入口 + 演进机制 + 变更回路），为逐类对象 SOP 打基础

### 影响文件
- `README.md`
- `VERSION`
- `CHANGELOG.md`
- `演进机制.md`
- `change-requests/README.md`

### 对已建资产的影响
- 无（尚无资产基于本规范构建）
