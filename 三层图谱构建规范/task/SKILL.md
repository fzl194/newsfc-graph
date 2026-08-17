---
name: task-layer-build
description: 把命令层+特性层资产构建成 task 层资产（atom/compound/feature_task）。Procedure 体裁：agent 以已构建资产为主输入，理解后梳理出"动态配置方法"，自己写 md。特性/步骤 Task 常规只读 Feature 文档簇和 AtomTask；原始文档仅在特性资产不足时回查并留痕。命令/特性层承载静态知识，task 层承载动态配置方法。
sop_version: 0.19.0
---

# Task 层构建 SKILL

> task 层在命令层、特性层之上，把"静态知识"转化为"动态配置方法"。
> **体裁：Procedure**——agent 理解输入自己写 md（命令/特性层是 Spec，代码构建）。
> **静态/动态拆分（本层存在的根因）**：一条命令既有命令层 md（静态：功能/参数表/规格/notes，原文 verbatim），又有 atom md（动态：这条命令有哪些合法配置方法、配置生成时怎么选）。task 层不重复静态知识，承载动态配置方法。

> **权威声明（v0.17.0）**：本 SKILL + `字段定义.md` + `template/` + `check.md` 是 Task 层规范**唯一权威**。`handoff/` 下各交接文档为**历史交接记录**（构建进度/教训），不作规范引用源；本 SKILL 与 handoff 表述不一之处，**以本 SKILL 为准**（历史 handoff §5.x 规则已吸收进本版）。

## 三类对象总览

| 对象 | Type | 存储 | ref 指向 | 回答 | 状态 |
|---|---|---|---|---|---|
| atom | `AtomTask` | `AtomTask/{nf}/` | `MMLCommand` | 这条命令有哪些配置方法（配置方法字典） | ✅ 本 SOP |
| compound | `CompoundTask` | `CompoundTask/{nf}/` | `null` | 这个多命令步骤怎么配（可复用模块） | ✅ 本 SOP |
| feature_task | `FeatureTask` | `FeatureTask/{nf}/` | `Feature` | 这个特性怎么配（编排+DP） | ✅ 本 SOP |

**统一约定**（同命令/特性层）：资产 = YAML(最小抽取) + 正文 + `## 边`；ID 三段 `{nf}@{Type}@{local}`，文件名=ID；引用 `[[{nf}@{Type}@{local}]]` 双方括号，**引用粒度 = md 级（一个逻辑ID = 一个 md，无 md 内部章节锚）**——故 DP/约束不编号；无证据段。

> **无版本（v0.19.0，CR-20260817-001）**：Task 层**剥离版本属性**——version 不进 ID、不进 YAML、不进路径。Task 引用的命令/特性知识有版本，但"配置方法/编排"是版本无关的方法论（使用时按目标环境自选命令/特性版本）。存储路径 `{Type}/{nf}/`，YAML 7 字段（id/type/name/name_zh/nf/ref/status；compound 无 ref 有 command_set）。与平台 `default_registry.yaml` `scope: task` 对齐。

## 边的规定（task 层全局）

Task 的 `## 边` **只允许指向以下四类对象**：

- **命令**（`MMLCommand`）—— atom 对应命令
- **特性**（`Feature`）—— feature_task 对应特性
- **Task**（atom/compound/feature_task 之间）—— Task↔Task 引用（compound/feature_task 阶段建立）
- **业务方案**（`ConfigurationSolution`）—— 上层方案引用 Task

**禁止**：Task 不直接关联 `ConfigObject` / `License` / `CommandParameter` 等命令层/特性层内部对象——那些静态结构在各自层内，Task 通过"命令/特性"间接关联（静态/动态拆分）。

> atom 阶段：边只有 `对应命令`（命令）。Task↔Task、Task↔特性、Task↔方案 在 compound/feature_task 阶段才建立。

## 构建顺序（整层）

```
1. atom 建设（可全量或按领域提前分批）
2. 逐批次：feature_task + compound_task 同步构建（per 特性）
```

atom 是最底层。**可执行编排的硬前置是：该 Feature 实际涉及的每条可恢复配置类命令均已有 AtomTask 并通过参数准入；不要求等待其他无关命令的 AtomTask 全部完成。**

**信息受限 FeatureTask 规则**：完整 Feature 文档簇明确了独立配置责任，但未提供激活案例、可恢复 MML、对象顺序或参数实例时，仍须构建 `status: draft` 的 FeatureTask，不能静默不写。该 Task 只沉淀文档可确认的对象链、能力/场景边界、决策与待补输入；`## 配置流程`、`## 激活方法与参数差异`、`## 参数核对` 明确标注“信息不足，未编排”，不虚构 AtomTask、CompoundTask、命令、参数或顺序。缺 AtomTask 的实际命令同样记录为待补前置，不能在 compound/feature 批次临时补造。只有缺独立配置责任的特性才使用 `status: foundation`。

---

# Part A · atom 构建

## A.1 定位（静态/动态拆分）

- 命令层 md（`Command/.../{nf}@MMLCommand@{命令}.md`）= **静态知识**：功能、参数真相表、规格、notes，原始手册 verbatim。
- atom md = **动态配置方法**：这条命令有哪些合法配置方法（配置维度 + 各取值 + 作用）、配置生成时怎么选。
- atom **不重复静态知识**：引子链命令层，参数真相表/规格不抄进来；通过**理解命令层 md 梳理出**动态配置信息。
- 一条命令一个 atom（1:1），atom ID 用命令名做锚（弃编号）。

## A.2 范围与批次

**所有命令都建 atom**，结构一致（配置方法字典 + 决策点 + 约束 + 边，该有的都要）。但 **FT/CT 配置流程只编排引用配置类命令 atom**（`ADD/MOD/SET/DEL/RMV/LOD/持久化 STR`）；查询/调测类（`DSP/LST/EXP/STP/调测`）atom 按命令层 md 梳理建（无特性示例的第二批），但**不被 FT/CT 编排引用**（调测剥离，§B.6）。即 atom 全建，FT/CT 引用面只覆盖配置类。
按"特性资产里是否有该命令的配置示例"分两类——**只影响输入源，不影响 atom 的结构要求**：

| 类别 | 输入 | 配置方法字典梳理依据 | 批次 |
|---|---|---|---|
| 有特性配置示例 | 命令层md + 特性资产配置示例（代码汇总）+ 命令原文 | 参数表/notes + 真实配置范式（数据规划取值/场景佐证） | 第一批 |
| 无特性配置示例 | 命令层md | 参数表/notes/使用实例——agent 读命令层 md **理解后梳理** | 后续批 |

> 两类都要完整的 **配置方法字典 + DP + 约束**（从命令层 notes/参数梳理）。
> **无特性配置示例的命令不是"精简/引用实例"**，而是 agent 直接读命令层 md 理解后，梳理出同样完整的配置信息。DP 和约束该有就有（用法单一则 DP 显式说明"无分支"）。

## A.3 输入

**前置依赖**：Command 层 + Feature 层已构建。

| 输入 | 来源 | 用途 | 适用 |
|---|---|---|---|
| 命令真相（命令层 md **全文**） | `Command/{nf}/{ver}/{nf}@MMLCommand@{命令}.md` | ① 全文 verbatim（引子链 + 约束梳理源） | ✅ 所有 atom |
| 特性层配置示例（数据规划行/任务脚本/操作步骤） | `Feature/{nf}/{ver}/{nf}@Feature@{code}/*.md` | ②-A 配置方法佐证 + DP 派生 | ⬠ 第一批 |
| 原始产品文档配置样例（业务专题/网络部署） | `--doc-root` 下语义目录（自动发现，见 A.5 泛化约定） | ②-B 端到端方案/部署配置样例，丰富佐证 | ⬠ 第一批（推荐） |

> 命令/特性层带版本（`{ver}` 在路径里）——Task 层引用它们时不绑版本（引用 `[[{nf}@MMLCommand@{cmd}]]` / `[[{nf}@Feature@{code}]]` 本就不含 version 段），构建时按当前构建目标版本读取对应层资产。

## A.4 输出

`三层图谱资产/AtomTask/{nf}/{nf}@AtomTask@{命令}.md`（每命令一个，文件名=完整ID）

## A.5 构建流程

### 第一步·代码筛选整合

脚本 `task/scripts/collect_command_examples.py`，输入源 = 命令层资产 + 特性层资产 + 原始产品文档（`--doc-root`）：

```
① 命令真相 = 命令层 md 全文 verbatim（不再只抽功能/参数/notes 片段）
②-A 扫 Feature 资产所有 md，按命令名命中判定（数据规划行/任务脚本/操作步骤上下文）
②-B 扫 --doc-root 下"业务专题/网络部署"语义目录所有 md（正则兼容 [**CMD**](url) 链接形式）
③ 配置方法差异汇总（②-A + ②-B 的数据规划行合并派生：每参数取值分布）
输出（中间态·非资产）：三层图谱资产/_intermediates/atom-input/{nf}/{命令}.md
```

用法（默认 `--skip-built` + `--skip-existing` 都开：跳过已建 atom、不覆盖已有中间态，只补待建缺口）：
```
# 全量采集待建缺口（推荐）
python collect_command_examples.py --nf UDG --version 20.15.2 --all \
    --doc-root output/UDG_Product_Documentation_CH_20.15.2
# 干跑（只统计命中/缺口规模，不写）
python collect_command_examples.py --nf UDG --version 20.15.2 --all --dry-run \
    --doc-root output/UDG_Product_Documentation_CH_20.15.2
# 旧行为（只扫特性层，不扫原始文档）
python collect_command_examples.py --nf UDG --version 20.15.2 --all --no-raw
```

> 注意：collect 脚本的 `--version` 是**输入选择器**（命令/特性层带版本，用它定位 `Command/{nf}/{ver}/`、`Feature/{nf}/{ver}/` 输入），**不是 Task 层属性**——atom 产出（`AtomTask/{nf}/` + YAML）无版本。audit / gen_compound_index 只扫 Task 层资产，无 `--version` 参数。

> **默认开关**：`--skip-built`（跳过已建 AtomTask 的命令）、`--skip-existing`（不覆盖已有中间态，增量）——两者默认开，常规跑只补"待建缺口"。重建某命令用 `--no-skip-built`；强制全量重写用 `--no-skip-existing`。
>
> **性能**：`--all` 模式预建倒排索引（一次扫所有文档提取命令候选），命中走索引——no-hit 命令秒过（不读命令 md），只有有候选的命令才 aggregate。UDG 4577 / UNC 8498 命令均分钟级跑完（优化前几小时跑不完）。

中间态是 agent 工作底稿（①命令真相全文 + ②-A特性层 + ②-B原始文档 + ③差异），**不进 atom md**（atom 无证据），git ignore。

#### 原始文档检索的泛化约定（跨网元/版本）

- 检索按**语义目录名**（业务专题、网络部署）在 `--doc-root` 下**自动发现**，**不硬编码路径**。
- 不同网元/版本产品文档结构不一致：UDG 业务专题在 `特性部署/业务专题`，UNC 在 `网络部署/业务专题`——脚本按目录名递归定位，自动适配，新增网元/版本无需改脚本。
- 产品文档根由 `--doc-root` 显式指定（各版本根目录命名不同，如 `UDG_Product_Documentation_CH_20.15.2` 与 `UNC 20.15.2 产品文档(裸机容器) 05`，无法自动推断）。
- 语义目录名清单可用 `--raw-dirs` 覆盖（默认 `业务专题,网络部署`）；`--no-raw` 关闭（等价旧行为）。

### 第二步·agent 理解梳理（所有命令 · Procedure 核心）

agent 读：命令层 md（必有）+ 第一步中间态（若有）。

- **配置方法字典**：理解命令功能/参数表，梳理配置维度（每参数的枚举/取值域 = 一种配置方法），列取值+作用；有配置示例的用真实场景佐证
- **决策点（DP）**：从配置维度派生选择点（多配置方法时必建 DP，每个 option 影响全记；命令用法单一则显式说明"本命令无分支"）
- **约束（rule）**：从 notes 梳理（规格上限/生效时延/唯一性/互斥等），编号化

### 第三步·写 atom md

按 [template/atom.md.tpl](template/atom.md.tpl)，字段见 [字段定义](字段定义.md)。

## A.6 规范要点

- YAML 7 字段（id/type/name/name_zh/nf/ref/status）——无 version（Task 层去版本，见顶部总览）
- 正文：`# {配置动作名}（{命令}）` + 引子（链命令层）+ `## 配置方法`(字典) + `## 决策点` + `## 约束`
- `## 边`：只 `- 对应命令: [[{nf}@MMLCommand@{命令}]]`（单向；静态信息如操作对象在命令层，不重复）
- **无证据**：不写 source_evidence_ids、不写 `## 证据` 段
- 引用统一 `[[逻辑ID]]`
- 配置方法字典讲"命令有哪些合法配置方法"，**不逐特性罗列取值**（逐特性是 feature_task 的事）
- **决策点/约束该有都有**（无论命令是否有配置示例；无分支/无约束则显式说明）；DP/约束**不编号**（引用只到 md 级，无章节锚）

## A.7 规范引用

- 字段：[字段定义](字段定义.md) · 骨架：[template/atom.md.tpl](template/atom.md.tpl)
- 核查：[check.md](check.md)
- 命名/ID/存储统一约定：同命令/特性层（见顶层 [conventions/命名规范-建议](../conventions/命名规范-建议.md)）

## A.8 核查（构建后必做）

产出交 [check.md](check.md)：字段必填 / ID 三段 / 文件名=ID / 正文5段 / 边只有对应命令且引用真实命令 / 无证据段残留 / 配置方法字典非逐特性罗列 / DP 与约束齐（无则显式说明）。

---

# Part B · compound + feature_task 一并构建

## B.0 一并构建总览

compound 和 feature_task **必须一并构建**，构建单元 = **特性**（不是命令，也不能分两次）。理由：① compound 的边界由 feature_task 的步骤拆分决定，无法预枚举；② feature_task 配置流程直接引用 compound，必须同时存在；③ compound 复用库（`_index`）逐特性增量积累。

构建顺序两级：
```
第 1 级：atom 建设（单元=命令；可提前全量或按领域分批，Part A）
第 2 级：compound + feature_task 一并构建（单元=特性；本 Feature 涉及的 AtomTask 全部可用后，本 Part）
```

每构建一个特性 = 一个完整 pass（拆步骤 → 建/复用 compound → 迭代步骤合理性 → 成文）。

### 输入（前置：本 Feature 涉及的 AtomTask 已建 ✓ + 特性层已建 ✓）

| 输入 | 来源 | 用途 |
|---|---|---|
| 特性文档簇（操作步骤/数据规划表/任务脚本/激活配置） | `Feature/{nf}/{ver}/{nf}@Feature@{code}/*.md`（特性层带版本） | **常规唯一业务输入**；必须读完整文档簇，feature_task 的逐场景流程、参数和条件依据 |
| atom 配置方法字典 | `AtomTask/{nf}/{nf}@AtomTask@{cmd}.md`（本特性涉及的命令，已全建） | feature 引用 atom / compound 组成 atom |
| compound 复用库 | `CompoundTask/{nf}/_index.md` | compound 复用判定（Jaccard） |
| 原始产品文档 | 产品文档归档 | **默认不读**。仅当 Feature 文档簇无法回答必须的命令顺序、参数、取值或约束时回查；必须在交付中记录回查原因、文件和结论 |

### 输出（一个特性 pass）

| 输出 | 路径 | 数量 |
|---|---|---|
| feature_task md | `FeatureTask/{nf}/{nf}@FeatureTask@{code}.md` | 1/特性 |
| compound md（新建） | `CompoundTask/{nf}/{nf}@CompoundTask@{英文名}.md` | 0~N/特性 |
| 待索引变更清单 | 新建/更新 CompoundTask 清单 | 并行构建 Agent 只提交清单；唯一集成 Agent 合并后重生 `_index` |

## B.1 compound 对象规范

- Type `CompoundTask`，ID `{nf}@CompoundTask@{英文名}`（英文名 Agent 取，kebab-case，稳定不变）
- ref: **null**（compound 无上层对象）
- YAML：`id/type/name/name_zh/nf/version/command_set/status`
  - `command_set`：命令名列表（如 `["ADD URR","ADD URRGROUP","ADD PCCPOLICYGRP"]`），**复用判定 + 快速查询的核心字段**
- 正文：`# {中文名}` + 引子(定位+被引用于) + `## 配置方法`(单表格:步骤/命令/关键参数 + 典型脚本 + 步骤位置) + `## 场景差异`(每个引用 Feature 的**每种激活方法**一行) + `## 决策点` + `## 约束` + `## 边`
- 边：`组成 → [[atom...]]`（compound→atom）；`被引用于 → [[feature_task...]]`（反向，逐特性回填）；可选 上游/下游 compound
- compound 不重复 atom 的完整参数字典（atom 讲命令有哪些合法配置方法，compound 讲多命令怎么组装成步骤）；但必须记录各场景实际执行/省略的命令子集、相对基线参数=值、对象与相位，避免把特性差异泛化丢失。

## B.2 feature_task 对象规范

- Type `FeatureTask`，ID `{nf}@FeatureTask@{feature_code}`（1:1 特性）
- ref → `{nf}@Feature@{feature_code}`（静态/动态拆分：Feature 层=静态知识，feature_task=动态配置编排，同构 atom→command）
- YAML：`id/type/name/name_zh/nf/version/ref/status`
- 正文：`# {特性名}（{code}）` + 引子(链特性层) + `## 配置概览`(对象链+场景骨架) + `## 配置流程`(步骤+单命令混合编排) + `## 激活方法与参数差异` + `## 参数核对`(每命令 Feature 实例参数 vs AtomTask 配置方法字典逐项核对；冲突标"冲突/待 Atom 更正"、缺最小值标"待数据规划补齐"、不得写"通过"敷衍) + `## 决策点` + `## 约束` + `## 边`
- 配置流程形态（**混合编排**，步骤≥2命令→compound，单命令→直接 atom）：
  ```
  1. **步骤A**（一句话）：`CMD1` + `CMD2` → [[UDG@CompoundTask@step-a]]
     - 关键参数：P1=<值>
  2. **命令B**（一句话）：`CMDB` → [[UDG@AtomTask@command-b]]
     - 关键参数：P3=<值>
  ```
- 边：`对应特性 → [[UDG@Feature@{code}]]`；`编排 → [[compound/atom...]]`
- `## 激活方法与参数差异` 必须为逐场景表，固定列：`激活方法/条件 | 配置相位 | 执行的 Task（[[CompoundTask]] / [[AtomTask]]） | 省略的 Task | 关联 AtomTask | 相对基线的参数差异（参数=值） | 目标对象与生效说明`。一方法跨多个相位可多行；所有源脚本实际执行命令（含 `INHERIT`、重复刷新）必须可由这些行还原。

## B.3 逐特性构建流程（pass）

```
1. **准入预检，不合格不落盘**：读完整 Feature 文档簇，提取配置类命令（ADD/MOD/SET/DEL/RMV/LOD/持久化 STR）和每个场景的实际参数=值；逐项核对 AtomTask 是否存在、其“配置方法”是否允许该值。只有文件存在不算通过。
   - 缺 AtomTask：不在本批补造 AtomTask；若该命令链无法恢复，改建信息受限 `draft` FeatureTask，并在参数核对中列为待补前置；若其他链可恢复，只编排已准入链并显式省略该链。
   - Feature 实例与 Atom 字典冲突：FeatureTask 保留 Feature 实际流程和值，但在“参数核对/约束”明确标为“冲突/待 Atom 更正”；不得伪称合法或凭常识改值。
   - Feature 未给 Atom 最小参数集的实际值：标为“待数据规划补齐”，不得虚构默认值或称可直接执行。
2. 以 Feature 的操作步骤、数据规划和任务脚本还原**每种激活方法的命令时间线**：保留对象、可选分支、重复命令、`INHERIT` 和每次刷新所在相位；原始文档仅按 B.0 的例外规则回查。
   - 不得按通用经验重排命令。特别是 `SET REFRESHSRV`：在哪个对象、分支、阶段出现，就在 FeatureTask 该处表达；不得一律移到末尾。
   - 所有场景都显式配置的全局基线必须先执行；后续 APN/rule/对象覆盖才可标为可选，不能将基线弱化为“按需”。
3. 拆 步骤 + 单命令：
   - ≥2 命令 + 高频/经典/可复用 → compound 候选
     · 查 _index 复用库：command_set 签名 + Jaccard 判定 → 复用 / reference / 新建
     · 新建：Agent 取英文名，写 compound md（command_set 必填）
   - 单命令 → 直接引 atom（合法，非例外）
4. 迭代步骤合理性（多次审视，§B.5 硬规则）：防平铺 / 重复识别 / 防假通用
5. 写 feature_task md（配置流程=步骤+单命令混合）+ compound md（新建）；将逐场景的命令子集、参数差异、对象和相位分别沉淀到 FT 与 CT 的适当位置，不能只留在交付报告
6. 并行 Agent 不重生 `_index`，也不修改未分配的共享 CompoundTask；输出待整合回填清单。唯一集成 Agent 合并后运行 `gen_compound_index.py` 和跨层审计
```

## B.4 compound 复用机制

**复用层级**：全通用（跨一切特性：License前置/刷新生效）/ 域通用（业务域内多特性：过滤链/计费三件套/BWM控制器族）/ 特性专属（单特性）

**复用判定**（建 compound 前必查 `_index`，按 command_set 算 Jaccard）：
- 命令集 Jaccard ≥ 0.75 **且** 相位同义 → **复用**（feature 编排引已有 compound，不新建）
- 0.4–0.75 或相位近义 → **reference**（新建但共享子 atom）
- < 0.4 或相位不同 → **新建**

**抽取 floor**：FT 配置流程 **<3 distinct 配置 atom → 直引 atom，不抽 CT**（单/双命令直接引 atom 合法，非例外）。

**相位同义（复用门槛的操作化定义）**：① 配置目标同（解决同一配置问题）② 对象链同义（操作对象/前后序一致）③ 共享命令相对顺序一致；三项满足 ≥2 项 = 相位同义。Jaccard 只是门槛——**配置语义判定优先**（语义不同则不复用，不论 Jaccard 多高，如 `license-access-prep` Jaccard=1.0 但相位不同→不复用）。

**compound 归属**：被多 feature 引用是常态，`被引用于` 列引用方 feature_task（逐特性回填）。

## B.5 迭代硬规则

- **防平铺**：feature_task 配置流程连续 ≥3 atom 无 compound → 强制评估抽 compound
- **重复识别**：≥3 命令阶段内聚 + 本族 ≥2 特性共用 → 必须抽 compound
- **防假通用（R1.2）**：复用 compound 时，本 feature 引入的差异（参数变种/专属命令/组装方式/约束）必须**双向回填**到 compound「场景差异」，不能只写进 feature DP
- **族通用 compound 命令多带陷阱**：族通用 compound 命令集是族内并集，个别 feature 只用子集 → compound「场景差异」**逐 feature 列命令子集**（执行/省略），不并集泛化；feature 编排时对省略段加脚注
- **时序不可泛化**：不同激活方法的命令顺序、对象、条件和重复执行都属于动态配置知识；不得因复用 CT 而把它们压成统一顺序。刷新命令、加载后生效、Rule 后绑定等必须保留原相位。
- **参数差异不可丢失**：FeatureTask 逐场景表与 CompoundTask 场景差异共同承载实际参数变体；AtomTask 仅承载完整合法字典。参数/值的来源和冲突必须可追溯到 Feature 文档簇与 AtomTask。

## B.6 规范要点（compound + feature_task 共用）

- **调测剥离**：配置流程/配置方法只含配置类命令（`ADD/MOD/SET/DEL/RMV/LOD/STR持久化`），调测/查询/导出（`DSP/LST/EXP/STP/STR探测`）不入
- **DP 规范**：多配置方法差异用 DP 组织（不建多套流程），每 option 影响全记；多 DP 按差异独立轴（≥2 轴才分表）；DP/约束**不编号**（md 级引用）
- **无证据段，但保留冲突说明**：不写 source/source_evidence_ids、不写 `## 证据`。正常参数须来自 AtomTask 配置方法字典；若 Feature 实例与字典冲突，在 FT/CT 的参数核对或约束中简要写明两者与待办，不另建证据段。
- **能力型底座特性**：无命令且无独立配置责任的被动响应特性（如会话管理），建骨架 feature_task（status=`foundation` + 配置概览说明"本特性无独立配置，靠被依赖特性"）+ 指向被依赖特性的 compound；不建配置流程。
- **信息受限特性**：有独立配置责任但无可恢复命令链/实例时，建 `status: draft` FeatureTask；说明责任与场景，显式列“待补 MML、对象顺序、参数实例/数据规划”，不引用或杜撰 Atom/CT。
- **族内构建顺序**：族内多特性先建最复杂（差异最全），通用 compound 场景差异一次补齐，后续简单特性复用

## B.7 批次集成与强制独立审查

一个领域批次可以并行构建，但一个 Feature 只能由一个构建 Agent 写入；共享 CompoundTask 必须有唯一维护者。每批按以下关卡流转：

1. 构建 Agent 完成准入预检、Task 产物和自检，提交新建/修改清单、共享 CT 待回填清单、逐场景参数追溯表；
2. **独立审查 Agent**（不得是构建 Agent，且不修改资产）回读同批 Feature 文档簇、相关 AtomTask、FT/CT 和 `_index`，逐场景检查命令顺序、分支、命令子集、对象、参数=值、刷新次数/位置、CT 反链与调测剥离；
3. 任何 CRITICAL/HIGH 退回构建 Agent 修正后复审。未达到 CRITICAL=0 且 HIGH=0，**不得**合入共享 CT 或重生全局 `_index`；
4. 唯一集成 Agent 合并共享 CT 场景差异，运行：
   `python task/scripts/gen_compound_index.py --nf {nf}`，再运行：
   `python task/scripts/audit_compound_feature.py --nf {nf}`。

结构审计通过只说明引用/字段结构合格；参数语义、时序和分支仍必须由独立审查人工确认。
