---
name: business-layer-build
description: 在 task 层之上构建业务层资产（业务域 BD / 场景 NS / 方案 CS）。Procedure 体裁：agent 读产品文档业务章节 + 已建 task/特性资产，理解后梳理出"业务方案怎么配"，自己写 md。命令层=静态知识，task 层=动态配置方法，business 层=业务编排。
sop_version: 0.1.0
---

# Business 层构建 SKILL

> business 层在 task 层之上，把"动态配置方法"编排成"业务方案"。
> **体裁：Procedure**——agent 理解输入自己写 md（命令/特性层是 Spec，task/business 层是 Procedure）。
> **三层承载**：命令层 md（静态：功能/参数表/规格，原文 verbatim）→ task 层 md（动态：命令/特性怎么配）→ business 层 md（编排：业务方案怎么配，特性级变种 + 跨特性协同）。
> **构建流程**：7 步 CS 流程 / 复用判定 / 特性关系矩阵 / 前置门 / 双向回填 / 族内顺序；**输出格式对齐 v0.13.0 新约定**（裸 `[[逻辑ID]]` + `## 边` + 2 段 ID + 资产位置 `三层图谱资产/Business/`）。

## 三类对象总览

| 对象 | Type | 存储（`三层图谱资产/` 下） | 回答 | 状态 |
|---|---|---|---|---|
| 业务域 | `BusinessDomain` | `Business/{domain}/` | 这个业务域是干啥的（含哪些场景） | ✅ 本 SOP |
| 场景 | `NetworkScenario` | `Business/{domain}/{scenario}/` | 这个场景解决什么业务问题（边界/产出） | ✅ 本 SOP |
| 方案 | `ConfigurationSolution` | `Business/{domain}/{scenario}/` | 这个方案怎么配（编排哪些 task、跨网元协同、配置级 DP/约束） | ✅ 本 SOP |

**统一约定**（同命令/特性/task 层，唯业务层是**跨 NF 类**）：
- 资产 = YAML(最小抽取) + 叙述正文 + `## 边`
- **ID 两段** `{Type}@{slug}`（业务横跨 UDG+UNC，**不带 nf/version**）；文件名 = 完整 ID；`domain`/`scenario` 作存储路径段 + YAML 路由字段
- 引用统一 `[[逻辑ID]]` 双方括号（**裸 ID，无路径无 .md**），与 `## 边` 同源
- **引用粒度 = md 级**（一个逻辑 ID = 一个 md，无 md 内部章节锚）——故 DP/约束**不编号**

## 边的规定（business 层全局）

business 的 `## 边` 只指向 **task 层动态对象 + 业务层同族对象**：

- **业务域**（BD）—— `下游场景 → [[NetworkScenario@...]]`
- **场景**（NS）—— `上游域 → [[BusinessDomain@...]]`；`下游方案 → [[ConfigurationSolution@...]]`
- **方案**（CS）—— `上游场景 → [[NetworkScenario@...]]`；`编排特性 → [[{nf}@FeatureTask@{code}]]`；`复用步骤 → [[{nf}@CompoundTask@{slug}]]`（按需）；`复用命令 → [[{nf}@AtomTask@{cmd}]]`（按需）

**禁止**：CS 不直连 `Feature` / `License` / `ConfigObject` 等特性层/命令层内部对象——CS 通过 `FeatureTask` 间接关联特性（静态/动态拆分，同 task 层纪律）。

> **反向回填（硬约束）**：被 CS 引用的 FeatureTask/CompoundTask/AtomTask，其 `## 边` 须追加 `- 被引用于: [[ConfigurationSolution@...]]`（per-task-md，逐 CS 回填）。

## 构建顺序（整层）

```
1. BD + NS 先建（定义 + 边界，不涉及配置；一个域一个场景树）
2. CS 逐个建（per scenario，族内先建最复杂的，把跨网元协同知识一次沉淀）
```

---

## 0. 产物层级与定位

| 层 | 对象 | 回答 | 引用方向 |
|---|---|---|---|
| 业务域 BD | BusinessDomain | 这个业务域是干啥的 | null（根）|
| 场景 NS | NetworkScenario | 这个场景解决什么业务问题 | 含于 BD |
| 方案 CS | ConfigurationSolution | 这个方案怎么配 | 含于 NS + **向下引用** task 层（FeatureTask/CompoundTask/AtomTask）|

关系链：`BD →(下游场景)→ NS →(下游方案)→ CS →(编排/复用)→ FeatureTask → CompoundTask → AtomTask`

**纯树结构**：BD/NS/CS 是包含树；CS 是叶子，向下引用 task（跨网元 UDG+UNC 的 FeatureTask/CompoundTask/AtomTask，在 `三层图谱资产/{AtomTask|CompoundTask|FeatureTask}/{nf}/{ver}/`）。

**不建 `3-` solution task 对象**：CS 本身（ConfigurationSolution 类型）就是方案对象，承载"是什么"+"怎么配"。业务层只有 BD/NS/CS 三类。

**编排原则**：CS 编排若干步骤——多特性的可复用步骤模块 → 引用已有 CompoundTask；单命令 → 直接引用 AtomTask；方案特有的额外步骤 → 建新 AtomTask/CompoundTask（进 `三层图谱资产/Task/`，CS 引用）。即 **CS 可直接含 AtomTask，CompoundTask 仅为"可复用多命令模块"而建，不是 CS→AtomTask 的必经层**。

## 1. 编号、ID 与目录

- BD/NS/CS 用**两段式 ID**（不带 nf@version，业务层横跨 UDG+UNC）：
  - `BusinessDomain@{domain-slug}`（如 `business-awareness`）
  - `NetworkScenario@{scenario-slug}`（如 `charging`）
  - `ConfigurationSolution@{scenario}-{solution-slug}`（如 `charging-converged`）
- slug 小写 kebab-case（语义命名）
- 目录（`三层图谱资产/` 下）：`Business/{domain}/[{scenario}/]`，**一个 md = 一个对象**：
  - `三层图谱资产/Business/business-awareness/BusinessDomain@business-awareness.md`
  - `三层图谱资产/Business/business-awareness/charging/NetworkScenario@charging.md`
  - `三层图谱资产/Business/business-awareness/charging/ConfigurationSolution@charging-converged.md`
- **业务层不进 `Task/`**：`Task/{nf}/{ver}/` 只放网元内 FeatureTask/CompoundTask/AtomTask；CS 用 `[[{nf}@FeatureTask@{code}]]` 等裸逻辑 ID 引用它们（跨网元，平台按 ID 解析，无需路径）。

## 2. 单方案构建流程（一次 pass）

```
0. 收集资产
   - 已有业务图谱参考（业务图谱体系/{场景}/，只读）→ 知识草稿来源（参考重写，非拷贝）
   - 原始产品文档 md（业务专题/方案章节）→ ★主源
   - 方案涉及的 FeatureTask（查 三层图谱资产/FeatureTask/{nf}/{ver}/）
1. ★前置门（critical）：核对方案涉及的 FeatureTask（UDG + UNC 两侧）是否全建完
   - 全建完 → 继续
   - 有缺口 → 先补建 FeatureTask（按 task 层 SOP），或该 CS 降级待建；不带着断链占位硬建
2. 理解方案：解决什么业务问题 + 跨哪些网元/特性协同 + 核心机制 + 配置级决策维度
   ★ 主源 = 原始产品文档方案/业务专题章节（非凝练版图谱 md）
3. 设计 CS 编排：编排哪些 FeatureTask + 可复用 CompoundTask + 单命令 AtomTask + 方案特有额外步骤
   - 每个候选 CompoundTask 先查复用库（三层图谱资产/CompoundTask/{nf}/{ver}/，按 command_set 算 Jaccard）
   - 额外步骤：单命令→新 AtomTask；多命令可复用→新 CompoundTask（进 Task/，入复用库）
4. 建 CS md（[template/configuration_solution.md.tpl](template/configuration_solution.md.tpl)）：叙述式知识沉淀 + 向下引用 task（裸 [[逻辑ID]]）
5. 双向链接回填：被引用的 FeatureTask/CompoundTask/AtomTask 的 `## 边` → `- 被引用于:` 行追加本 CS（per-task-md）
6. 更新全景（★主流程做，非并行 Agent）：
   - NS 决策点表：本 CS 加入方案路由（真实 `[[ConfigurationSolution@...]]`，非纯文字、非占位）
   - NS `## 边` 下游方案：补本 CS
   - BD `## 边` 下游场景：若本 CS 是所属 NS 的首个 CS，确认 BD→NS 边已建
   - per-task-md 被引用于：被本 CS 引用的 task 追加反向链接
```

> **无证据**（同 task 层）：业务层不拷贝/不建证据文件，不设 `## 证据` 段。CS 知识凝练自产品文档业务章节，所有引用统一裸 `[[逻辑ID]]`，关系全进 `## 边`。License 编号等需溯源的事项，靠构建时对照原始文档核实（见 §6），不落地为证据文件。
>
> 业务层 index（`三层图谱资产/Business/` 下是否建 index.md，或由平台 registry 自动聚合）——本期暂不强制；平台后端按 registry 扫描聚合，无需手维护 index。

## 3. 复用机制

- **CS 复用下层 task**（FeatureTask/CompoundTask/AtomTask）= 业务层复用核心。建 CS 前先查 `三层图谱资产/CompoundTask/{nf}/{ver}/` 的复用候选（按 `command_set`）。
- **复用判定**：方案某步所需命令集，已有 CompoundTask 覆盖（Jaccard ≥ 0.75 且相位同义）→ 复用引用；0.4–0.75 → reference（共享子 AtomTask）；< 0.4 → 新建。
- **方案特有额外步骤**：单命令 → 新 AtomTask（进 `Task/{nf}/{ver}/`）；多命令可复用 → 新 CompoundTask（进复用库）。
- **复用差异双向回填（硬约束，防假通用）**：CS 引入的下层 task 差异（参数变种/专属命令/协同约束），若该 task「场景差异」未记，须回填到该 task，不能只写进 CS。

## 4. wiki 模板与叙述风格

骨架见 [template/](template/)（三个 .tpl）。设计原则：

- **叙述式，非字段填表**：不用旧三层图谱写死字段（scopes/participants/uses_semantic_object/constrained_by/has_decision 表格）。跨网元 participants、核心机制、语义对象——融入叙述散文。
- **配置流程只在 CS，决策点/约束不限层**：BD/NS 不设「配置与协同」段；但「决策点」「约束」可在 BD/NS/CS 任意层（哪里有就记哪里）。
- **特性优先（CS 编排核心 ★）**：CS「配置与协同」以特性为单元，说明每特性的**标准配置方法**（摘要自 FeatureTask）+ 本方案**用法（走标准 / 变种）**。引用优先级：**FeatureTask 为主 > CompoundTask 次之 > AtomTask 末之**。不重复 FeatureTask 内部步骤。
- **特性关系矩阵（★必填，防"都得配"误解）**：CS 编排多特性时禁止平铺成清单——必须先给「特性关系矩阵」明确每特性的**角色 + 必配性 + 关系**：
  - **核心**：方案主体，必配
  - **基础/依赖前提**：核心依赖的底层（如 SA-Basic），必配，配置常与核心重叠
  - **维度增强**：正交维度可选叠加（按业务诉求）
  - **跨网元对端**：同一能力在另一网元的对应特性（组合，两侧同配）
  - **二选一/触发链**：互斥路径选其一
  > **配置重叠判定**：两特性配置对象集高度重合时，矩阵「关系说明」必须注明"重叠，配 X 时已含，不需额外配 Y"。
  > **依赖前提特性必须进矩阵**（License 前置的依赖，如 SA-Basic、PCC 基本功能），角色标「基础(依赖前提)」，不只在约束段提。

## 5. 决策点记录规范

- DP **可在 BD/NS/CS 任意层**（决策不限层级，哪里有决策哪里记）。
- 每 option 的影响**必须全记**（否则配置生成不知编哪条路径）。统一表格式 `| 选项/场景 | 影响 |`。
- 多方案/多配置方法的差异**用 DP 组织**，不建多套流程。
- **DP/约束不编号**（引用只到 md 级，无章节锚）。

## 6. 硬约束（构建完整，非 MVP）

- **前置门（critical）**：CS 涉及的 FeatureTask（UDG + UNC 两侧）必须先全建完，才能开建 CS。有缺口 → 先补建或降级待建，不带着断链占位硬建。"建完" = 结构完整、无 `[[占位]]`；`status` 升 `active` 是单独人审步骤，可后置。
- **额外步骤进 task（critical）**：方案特有的命令不空写在 CS 叙述里——单命令建 AtomTask、多命令建 CompoundTask，进 `Task/`，CS 引用。CS 里每个命令/参数要可追溯到 task（AtomTask/FeatureTask）。
- **License 编号须原始文档交叉核实（critical）**：License 编号 + 控制项**必须从原始特性概述文档 License 表 / FeatureTask 交叉核实，不可按命名规律推断**。实战教训（带宽族）：`LKV3G5ABNT01`/`LKV3G5WIMR01`/`LKV6CHGBILL02`（命名不符同族规律 = 编造）全错——正确应为 `LKV3G5ADTD01`/`LKV3G5ITSR01`/`LKV3G5BCBC01`。
- **叙述式非字段填表（critical）**：不用旧三层图谱写死字段。用 §4 叙述骨架。
- **引用全部裸 `[[逻辑ID]]`（critical，新约定）**：业务层 md 内所有引用统一 `[[逻辑ID]]`（双方括号、裸 ID、无路径无 .md），与 `## 边` 同源——包括 CS→FeatureTask/CompoundTask/AtomTask、CS→NS、NS→BD、NS→CS 等。**禁止** markdown 相对路径链接（`[..](.md)`）、`../`、自引用、`.md` 后缀。平台前端按 ID 查名渲染 + 跳转。
- **双向链接闭环**：CS ↔ 被引用的 task（per-task-md 的 `## 边` → `被引用于:` 追加本 CS）。Grep 新文件无 `[[占位]]` 残留、无断链。
- **NS/CS `## 边` 段不重复 SOP/审视/范本引用**：`## 边` 只列图谱对象关系（上游/下游/编排/复用）。禁止列"业务层 SOP""业务层审视""范本"（与 SOP 文件本身重复）。

## 7. 验收清单（单 CS pass 完成自检）

- [ ] CS 1 md（两段式 ID，`三层图谱资产/Business/{domain}/{scenario}/` 下，文件名 = 完整 ID）
- [ ] frontmatter 7 字段齐（id/type/name/name_zh/domain/scenario/status；slug 与 id 一致）
- [ ] 前置门通过：涉及 FeatureTask（UDG+UNC）全建完
- [ ] CS 向下引用 FeatureTask/CompoundTask/AtomTask 全是裸 `[[逻辑ID]]`（无路径链接、无占位、无断链）
- [ ] 特性关系矩阵齐（角色/必配/关系；依赖前提特性进矩阵；配置重叠注明）
- [ ] 方案特有额外步骤已建 AtomTask/CompoundTask 进 Task（非空写在 CS 叙述）
- [ ] CS 决策点影响表完整、约束 severity 标注；DP/约束不编号
- [ ] 双向链接闭环（被引用 task 的 per-task-md `## 边` 追加"被引用于"）
- [ ] 叙述式（无旧三层图谱写死字段表格）
- [ ] `## 边` 段无 SOP/审视/范本伪引用

## 8. 族内顺序（经验）

同族多 CS（如计费族 7 CS）构建时，**先建差异最全的最复杂 CS**（计费族 = CS-3 融合计费，跨网元 UDG+UNC、双 URR、CHF 协同最全），把跨网元协同知识 + 复用 CompoundTask 场景差异一次沉淀到位；再建简单 CS（纯参数变种）复用即可。避免先建简单 CS（单视角）导致协同知识欠债、后续不断回头补。

> 每完成一族 CS，按 [check.md](check.md) R1 审视（task 覆盖度 / 复用合理性 / 跨网元协同完整性 / 前置门 / 可追溯性），critical 即修，经验回填本 SKILL。
> 构建中如发现本 SKILL 有缺陷 → 挖审查意见 → 修正本文件 → 版本号 +1。准则稳定判据：连续 2 个新 CS pass 人工免改或仅微调。

## 规范引用

- 字段：[字段定义](字段定义.md)
- 骨架：[template/](template/)（business_domain / network_scenario / configuration_solution）
- 核查：[check.md](check.md)
- 命名/ID/存储统一约定：见顶层 [conventions/命名规范-建议](../conventions/命名规范-建议.md)（业务 = 跨 NF 类，2 段 ID）
