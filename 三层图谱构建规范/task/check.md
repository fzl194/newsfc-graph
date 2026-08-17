# Task 层核查（check）

> task 层产出的独立质量审查。**只审不建**，与 @Task构建师分离。

## 审查角色纪律

- **怀疑主义**：只认证据，默认产物有问题
- 问题必须可定位（对象 ID + 规则）
- 区分"产物问题"（回构建师返工）和"SKILL 缺口"（提 change-request）
- **独立性（v0.17.0 统一）**：独立审查须由非构建者 Agent 担任（不改文件）；构建方可自派子 Agent 做预审/自检，但**不替代独立审查**——独立审查仍是合入共享 CT/集成的硬前置（统一 SOP §B.7 与历史 handoff 分歧）

## 审查输入

- 待审的 task 层构建产物（atom / compound / feature_task）
- [字段定义](字段定义.md)、[SKILL](SKILL.md)、对应 template（字段和正文结构权威）
- atom：命令层资产（核 `ref` 真实性）
- compound / feature_task：**同批完整 Feature 文档簇、相关 AtomTask、CompoundTask `_index.md` 和关联 CT**。原始产品文档只在构建者声明 Feature 资产不足时才检查回查合理性

## 审查输出

核查报告：`{通过/不通过, 问题清单[{对象, 问题类型, 严重级, 归属}]}`

## 审查项（atom）

| 类别 | 检查点 |
|---|---|
| 字段必填 | `id/type/name/name_zh/nf/ref/status` 不空；**无 version 字段**（v0.19.0 去版本，出现即 fail） |
| ID 格式 | 三段 `{nf}@AtomTask@{命令名}`（命令名做锚、无编号；local 保留空格；不含 version） |
| 文件名 ↔ ID | 文件名 = 完整 ID（`UDG@AtomTask@ADD URR.md`） |
| ref 真实 | `ref` 指向的命令层对象存在（`Command/{nf}/{ver}/{nf}@MMLCommand@{命令}.md`） |
| 结构统一 | 每资产 = YAML + 正文 + `## 边`；关系只在 `## 边`，正文不重复 |
| 正文 5 段 | `# 标题` + 引子(链命令层) + `## 配置方法` + `## 决策点` + `## 约束` |
| 静态不重复 | 参数真相表 / 规格 / 命令功能 **不抄进 atom**（引命令层）；atom 只讲动态配置方法 |
| 配置方法字典 | 讲"命令有哪些合法配置方法"（维度+取值+作用），**不逐特性罗列取值** |
| DP / 约束齐 | DP 每个 option 影响全记；**DP/约束不编号**（引用只到 md 级）；无分支 / 无约束**显式说明**（不能空着） |
| **边的规定** | `## 边` 只指向 命令/特性/Task/方案；**atom 阶段只有 `对应命令`**；**禁止指向 ConfigObject/License/CommandParameter** |
| 无证据 | 无 `source` / `source_evidence_ids`、无 `## 证据` 段残留 |
| 引用形式 | 全部 `[[{nf}@{Type}@{local}]]` 双方括号（**非** markdown 相对路径）；**引用只到 md 级，无 `#章节` 锚点** |

### 自动化核查（atom）

`audit_atoms.py --nf {nf}` 自动判定 字段必填 / ID 三段 / 文件名=ID / ref 真实 / 正文 5 段 / 边只对应命令 / 无证据 等可机器判定的项。
脚本与 builder 共用正则有盲区——**过=未必全对，报错=一定有问题**，人工仍须按上表逐项复核（核查独立性）。

## 交接

- 通过 → 收口
- 不通过 + 产物问题 → 回 **@Task构建师** 返工
- 不通过 + SKILL 缺口 → 提本层 `change-requests/`

---

## 审查项（compound）

| 类别 | 检查点 |
|---|---|
| 字段必填 | `id/type/name/name_zh/nf/command_set/status` 不空；ref 缺省 null；**无 version 字段** |
| ID 格式 | 三段 `{nf}@CompoundTask@{英文名}`（英文名 kebab-case，无编号；不含 version） |
| 文件名 ↔ ID | 文件名 = 完整 ID |
| command_set | 非空（`status: foundation` 骨架豁免，可 `command_set: []`）；命令名与 `组成` 边引用的 atom 一致；各命令的 AtomTask 文件存在 |
| `## 边` 标题 | `## 边` 必须是独立标题行，不能与正文或表格末行粘连；否则平台不会解析关系 |
| 边规定 | `组成`→atom、`被引用于`→feature_task；不指向 ConfigObject/License。**`被引用于` 声明必须 == 实际反向引用集合**（被哪些 feature_task 真实编排，从 FT 反推；不一致即断链） |
| 复用库 | `CompoundTask/{nf}/_index.md` 存在；各 compound 的 command_set / 被引用于 与 _index 登记一致（SOP §B.0/§B.4，新建 compound 前按 Jaccard 查复用） |
| 场景差异 | 被多 feature 引用时，每引用方的**每种激活方法**均回填：执行/省略命令子集（含 `INHERIT`）、相对参数=值、对象与相位；不得用“按需执行”吞掉真实脚本命令，也不得把 Feature 专属差异压成通用 CT |
| 调测剥离 | 配置方法/典型脚本只含配置类命令（无 DSP/LST/EXP/STP） |
| 无证据 | 无 source/source_evidence_ids、无 `## 证据` 段 |

### 自动化核查（compound）

`audit_compound_feature.py --nf {nf}` 自动判定 D0（`## 边` 标题独立）、D1（command_set 非空 / 边标签规范）、D2（→atom 真实）、D3（被引用于 声明==实际反链）、D4（→Feature 真实）；D5（atom 覆盖率）为 info 级不判 fail。
脚本与 builder 共用正则有盲区——**过=未必全对，报错=一定有问题**，人工仍须按上表逐项复核（核查独立性）。

## 审查项（feature_task）

| 类别 | 检查点 |
|---|---|
| 字段必填 | `id/type/name/name_zh/nf/ref/status` 不空；**无 version 字段** |
| ID 格式 | 三段 `{nf}@FeatureTask@{feature_code}`（1:1 特性；不含 version） |
| 文件名 ↔ ID | 文件名 = 完整 ID |
| ref 真实 | `ref` 指向特性层对象存在 |
| 配置流程 | 步骤+单命令混合编排；每步链 compound 或 atom（`[[逻辑ID]]`）；引用的 compound/atom 文件存在；按 Feature 操作步骤、数据规划和任务脚本核真实命令时间线：对象、可选分支、重复命令、`INHERIT` 和每次刷新位置均不得丢失或按常识重排 |
| 激活方法与参数差异 | 必有 `## 激活方法与参数差异`，逐场景表固定包含：激活方法/条件、配置相位、执行的 Task、省略的 Task、关联 AtomTask、相对基线参数=值、目标对象与生效说明；每行可回溯实际命令子集和 AtomTask |
| 参数合法性 / 冲突 | 每个实际参数=值须逐项核 AtomTask “配置方法”，不能只确认文件存在。Feature 值与 Atom 字典冲突时，FT 必须保留 Feature 语义并标“冲突/待 Atom 更正”；Feature 未给最小参数值时标“待数据规划补齐”，均不得写成“通过/可直接执行” |
| **B1 命令闭包**（v0.17.0） | Feature 簇任务脚本/数据规划的**配置类命令集合** ⊆ {FT 配置流程 atom 引用 ∪ 引用 CT command_set 执行子集 ∪ 激活方法表省略列}。每条 Feature 配置命令须可由 FT/CT 还原或显式省略；静默丢失 = CRITICAL |
| **B2 参数闭包**（v0.17.0） | Feature 数据规划每条 `param=value` ⊆ {FT 激活方法差异相对基线列 ∪ 引用 CT 场景差异 ∪ 参数核对}，或标注“待数据规划补齐/冲突”。静默丢失 = CRITICAL；标注待补但 Feature 实有值 = MEDIUM |
| **B3 反向追溯**（v0.17.0） | FT/CT 中每个 `param=value` 须可追溯到 Feature 簇某行/脚本；无 Feature 来源的参数（臆造变体行）= CRITICAL |
| **B4 信息源边界对账**（v0.17.0） | FT 若声明信息源边界（覆盖簇子集），须**逐文档枚举排除项 + 论证**（部署态/可选子功能/调测/纯原理/非本 NF）；静默排除承载配置命令的簇文档 = CRITICAL（防 112001 类：边界声明覆盖子集但漏配 SET NETYPE / 镜像 SIP 子功能） |
| 防平铺 | 连续 ≥3 atom 无 compound → 警告（评估抽 compound） |
| 边规定 | `对应特性`→Feature、`编排`→compound/atom；不指向 ConfigObject。编排某 compound 时，该 compound 的 `被引用于` 须回填本 FT（反链一致，与 compound 审查项联动） |
| 调测剥离 | 配置流程只含配置类命令 |
| DP / 约束 | DP option 影响全记；无分支显式说明；不编号（md 级引用） |
| 无证据 | 无 source/source_evidence_ids、无 `## 证据` 段 |
| 回查例外 | 若构建者读取原始产品文档，核 Feature 文档簇确实无法回答该必要问题，且交付记录了回查原因、文件和结论 |

### 自动化核查（feature_task）

`audit_compound_feature.py --nf {nf}` 同上覆盖 feature_task 的 D2（→atom 真实）/ D3（反链一致）/ D4（→Feature 真实）；**D5 atom 覆盖（warning 级）**；**D6 命令闭包（CRITICAL：Feature 配置命令 ⊆ FT/CT）**；**D7 参数闭包（CRITICAL：Feature param=value ⊆ FT/CT 或标注）**——D5 升级 / D6 / D7 规格见 [CR-20260807-001](change-requests/CR-20260807-001-Task层信息可追溯性与SOP权威统一.md)，待集成轨道实现（本机无 python）；防平铺、参数语义、时序与分支目前仍需人工判。
并行构建 Agent 不得重生 `_index.md`；由唯一集成 Agent 在 CRITICAL/HIGH 为 0 后重跑 `gen_compound_index.py --nf {nf}` 刷新索引，并执行跨层审计。
脚本与 builder 共用正则有盲区——**过=未必全对，报错=一定有问题**，人工仍须按上表逐项复核（核查独立性）。
