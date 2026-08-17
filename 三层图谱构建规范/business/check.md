# Business 层核查（check）

> business 层产出的独立质量审查。**只审不建**，与 @业务构建师分离。
> R1 维度沿用既有业务层审视口径，审查项对齐新约定（裸 `[[逻辑ID]]` + `## 边` + 2 段 ID + 位置）。

## 审查角色纪律

- **怀疑主义**：只认证据，默认产物有问题
- 问题必须可定位（对象 ID + 规则）
- 区分"产物问题"（回构建师返工）和"SKILL 缺口"（提 change-request）
- **判 critical 前须穷尽搜索**原始文档 / 特性 wiki / 官方差异表 / 命令 wiki（防误判）

## 审查输入

- business 层构建产物（BD/NS/CS md）
- [字段定义](字段定义.md)（字段权威）
- task 层资产（核 CS 引用的 FeatureTask/CompoundTask/AtomTask 真实性）

## 审查输出

核查报告：`{通过/不通过, 问题清单[{对象, 问题类型, 严重级, 归属}]}`

严重级：**critical**（必修）/ **warning**（应修）/ **info**（可选）。

---

## R1 核心维度（必做）

| 维度 | 检查点 |
|---|---|
| **R1.1 task 覆盖度（防遗漏）** | CS 编排的每个步骤是否都有对应 FeatureTask/CompoundTask/AtomTask；逐步骤核对 ✓/✗/⚠；缺口 = critical |
| **R1.2 复用合理性（防一刀切）** | 复用 CompoundTask 时 Jaccard 判定合理；**假通用判定（critical 必查）**——CS 有差异而被复用 task「场景差异」无对应条目 = 假通用（须补 task） |
| **R1.3 跨网元协同完整性（业务层特有 ★）** | UDG 用户面 + UNC 控制面协同：顺序 / 一致性约束 / CP-UP 参数对齐是否完整记在 CS「跨网元/跨特性协同」段 |
| **R1.4 前置门（critical）** | CS 涉及的 FeatureTask（UDG+UNC 两侧）真建完、无断链、无 `[[占位]]` |
| **R1.5 可追溯性（critical，防编造）** | 每命令/参数可追溯到 AtomTask/FeatureTask；License 编号须原始文档交叉核实（不可按命名规律推断）|

## 审查项（BD）

| 类别 | 检查点 |
|---|---|
| 字段必填 | `id/type/name/name_zh/domain/status` 不空（BD 无 scenario）|
| ID 格式 | 两段 `BusinessDomain@{domain-slug}`（slug 小写 kebab；无 nf/version）|
| 文件名 ↔ ID | 文件名 = 完整 ID；路径 `Business/{domain}/` |
| domain 一致 | `domain:` = id 第二段 = 路径段 |
| 边规定 | `## 边` 只 `下游场景 → [[NetworkScenario@...]]`；不指向 task/特性/命令层 |
| 引用形式 | 全部 `[[逻辑ID]]`（非 markdown 路径）；引用只到 md 级 |

## 审查项（NS）

| 类别 | 检查点 |
|---|---|
| 字段必填 | `id/type/name/name_zh/domain/scenario/status` 不空 |
| ID 格式 | 两段 `NetworkScenario@{scenario-slug}` |
| 文件名 ↔ ID | 文件名 = 完整 ID；路径 `Business/{domain}/{scenario}/` |
| domain/scenario 一致 | 两字段 = 所属 BD slug / 自身 scenario slug；与路径段一致 |
| 边规定 | `上游域 → [[BD]]`；`下游方案 → [[CS...]]`；不指向 task/特性/命令层 |
| 决策点 | 场景级方案路由 DP option 影响全记；不编号 |
| 引用形式 | 全部 `[[逻辑ID]]`；`## 边` 无 SOP/审视/范本伪引用 |

## 审查项（CS）

| 类别 | 检查点 |
|---|---|
| 字段必填 | `id/type/name/name_zh/domain/scenario/status` 不空 |
| ID 格式 | 两段 `ConfigurationSolution@{scenario}-{solution-slug}` |
| 文件名 ↔ ID | 文件名 = 完整 ID；路径 `Business/{domain}/{scenario}/` |
| domain/scenario 一致 | 两字段 = 所属 BD/NS slug；CS id 的 scenario 前缀与 scenario 字段一致 |
| **引用形式（critical）** | 所有图谱对象引用（FeatureTask/CompoundTask/AtomTask/NS）统一裸 `[[逻辑ID]]`；**禁止** markdown 相对路径、`../`、自引用、`.md` 后缀；占位 `[[...]]` 残留 = critical |
| 边规定 | `上游场景 → [[NS]]`；`编排特性 → [[{nf}@FeatureTask@...]]`；`复用步骤/命令 → [[CompoundTask/AtomTask]]`；**禁止直连 Feature/License/ConfigObject**；`## 边` 无 SOP/审视/范本伪引用 |
| ref 真实 | `## 边` 引用的 FeatureTask/CompoundTask/AtomTask 文件存在（`三层图谱资产/{Type}/{nf}/{ver}/`）|
| 反向回填 | 被引用的 task 的 `## 边` 已追加 `被引用于 → [[本CS]]` |
| 特性关系矩阵 | 齐全（角色/必配/关系）；**依赖前提特性进矩阵**（不只在约束段）；配置重叠在「关系说明」注明 |
| 额外步骤进 task | 方案特有命令已建 AtomTask/CompoundTask 进 Task（非空写在 CS 叙述）|
| 调测剥离 | CS 配置叙述只含配置类命令（无 DSP/LST/EXP/STP 探测类）|
| DP / 约束 | DP option 影响全记；severity 标注；无分支显式说明；不编号（md 级引用）|
| 叙述式 | 无旧三层图谱写死字段表格（scopes/participants/uses_semantic_object/constrained_by/has_decision）|
| 无证据 | 无 `source`/`source_evidence_ids`、无 `## 证据` 段（同 task 层）；所有引用统一 `[[逻辑ID]]` |
| md 结构 | YAML 顶 → 内容中 → `## 边` 底（`## 边` 必为最后一段） |

## 交接

- 通过 → 收口（`status` 可升 `active`，单独人审步骤）
- 不通过 + 产物问题 → 回 **@业务构建师** 返工
- 不通过 + SKILL 缺口 → 提本层 `change-requests/`
