# UNC FeatureTask + CompoundTask 统一构建提示词

> 用途：把下方提示词原样交给负责某个 UNC 领域批次的构建 Agent。由派单方只替换花括号中的批次参数。
>
> 适用前提：`P0` 已完成，`CompoundTask/UNC/20.15.2/_index.md` 存在且通过集成基线审计。若 P0 未完成，本提示词只允许做“第一阶段：只读准入”，不得写 FT/CT。
>
> 统一计划：[UNC领域批次构建计划](UNC领域批次构建计划.md)。权威规范仍是 `SKILL.md`、`字段定义.md`、`template/`、`check.md`。

```text
你是 UNC 20.15.2 Task 层的领域构建 Agent。本次必须把分配的每个 Feature 作为一个完整 pass：

- 该 Feature 的 FeatureTask；
- 从其真实配置流程中识别、复用或新建的 0～N 个 CompoundTask。

严禁先只写 FeatureTask、以后补 CompoundTask；也严禁脱离 FeatureTask 单独批量制造 CompoundTask。

【本次任务边界】
- 批次名称：{BATCH_NAME}
- 分配 Feature Code：{FEATURE_CODES}
- 步骤所有权域：{STEP_OWNERSHIP_DOMAIN}
- 可修改的既有 CompoundTask：{OWNED_EXISTING_COMPOUNDS}
- 只读的既有 CompoundTask：{READ_ONLY_COMPOUNDS}
- 工作目录：D:\mywork\KnowledgeBase\NewSFCGraph

你只能创建/改写：
1. 本次分配 Feature Code 对应的 `FeatureTask/UNC/20.15.2/UNC@FeatureTask@{code}.md`；
2. 本批确有必要的新 CompoundTask；
3. 上述“可修改的既有 CompoundTask”。

你不得：
- 创建或修改 AtomTask；本次所有现有 AtomTask 都可作为上层输入；缺 AtomTask 或缺可恢复命令链时，仍须写信息受限 `draft` FeatureTask，但不得编排或臆造该命令；
- 修改未分配的 FeatureTask、未授权的既有 CompoundTask；
- 重生 `_index.md`、自动批量回填跨域 CT、修改 SOP/脚本；
- 用原始产品文档替代 Feature 文档簇，或因原始文档中有命令而绕过缺失 AtomTask。

【唯一权威】
1. `三层图谱构建规范/task/SKILL.md`（尤其 Part B）；
2. `三层图谱构建规范/task/字段定义.md`；
3. `三层图谱构建规范/task/check.md`；
4. `三层图谱构建规范/task/template/feature_task.md.tpl`；
5. `三层图谱构建规范/task/template/compound.md.tpl`；
6. `三层图谱构建规范/task/UNC领域批次构建计划.md`；
7. `三层图谱构建规范/task/UNC特性与步骤Task构建提示词.md`（本提示词）。

================================================================
第一阶段：输入获取与只读准入（信息不足不臆造，仍须落盘）
================================================================

对每个 `{feature_code}`，严格按以下顺序取数。

### 1. Feature 文档簇：唯一常规业务输入，必须全文读取

读取目录：
`三层图谱资产/Feature/UNC/20.15.2/UNC@Feature@{feature_code}/*.md`

必须读取该目录的**全部 md**，不能只读 `概述.md`，也不能只读文件名含“激活”的页面。每个 md 都要判断是否承载以下信息：

- 特性边界、适用网元和场景；
- 激活/配置/部署/操作步骤；
- 数据规划表和任务脚本；
- 命令块、参数=值、对象名；
- 条件分支、全局基线、可选步骤、`INHERIT`、重复执行和刷新位置；
- 实现原理、参考信息、初始配置、子功能文档中可能隐藏的配置命令。

优先定位操作步骤、数据规划、任务脚本和激活/配置/部署内容，但这不是可跳过其他 md 的理由。文件名或 doc_type 不能证明“无配置”；必须读完整簇后才能判 foundation。

### 2. AtomTask：从 Feature 实际命令反推，逐参数核验

从完整 Feature 簇提取配置类命令：`ADD/MOD/SET/DEL/RMV/LOD/持久化 STR`。对每条实际命令读取：

`三层图谱资产/AtomTask/UNC/20.15.2/UNC@AtomTask@{CMD}.md`

你必须核实：

- AtomTask 文件是否存在；
- Feature 每个实际 `param=value` 是否被 AtomTask 的“配置方法”允许；
- AtomTask 的决策点和约束是否影响该场景。

只有 AtomTask 文件存在不算准入通过。

- 缺 AtomTask：不在本批补 atom；将该命令链列为待补前置。若完整簇没有任何可恢复配置链，仍写信息受限 `draft` FeatureTask，不写 Atom/CT 编排；
- Feature 实值与 Atom 字典冲突：可以继续构建 FT，但必须在“参数核对/约束”标 `冲突/待 Atom 更正`，保留 Feature 原始流程和值；
- Feature 未提供必要最小参数值：标 `待数据规划补齐`，不得虚构默认值。

`DSP/LST/EXP/STP` 和调测性命令不进入配置流程或 CompoundTask；它们可能作为 Feature 语义背景被阅读，但不是 Task 编排输入。

### 3. CompoundTask：必须先查复用库，再决定新建

先读：

`三层图谱资产/CompoundTask/UNC/20.15.2/_index.md`

再读取命中候选 CT 全文，核其 `command_set`、配置目标、对象链、共享命令相对顺序、已有场景差异与反链。不得仅按名称或命令数量判断复用。

- Jaccard >= 0.75 且相位同义（配置目标、对象链、相对顺序三项至少两项同义）→ 复用；
- Jaccard 0.4–0.75 或相位近义 → reference/新建，保留共享 atom；
- Jaccard < 0.4 或相位不同 → 新建；
- `<3 distinct` 配置 atom → FeatureTask 直接引用 AtomTask，不强造 CT；
- 连续 >=3 AtomTask 时，必须明确评估是否应抽 CT；同一内聚 >=3 命令且被 >=2 Feature 共用时，必须抽 CT。

复用跨域 CT 时，你只输出“待整合回填清单”；不得直接修改只读 CT。清单必须写明 Feature、激活方法、执行/省略命令子集、参数差异、对象和相位。

### 4. 旧 FeatureTask / 命令层 / 原始产品文档的地位

- 若存在同 ID 旧 FeatureTask，可读取其历史流程、已引用 CT 和遗留差异，但它**不是权威输入**；最终以完整 Feature 文档簇重建。
- 只有 AtomTask 表述不足或参数存在争议时，才读 `Command/UNC/20.15.2/UNC@MMLCommand@{CMD}.md` 做静态澄清；不得复制命令静态参数表到 Task。
- 原始产品文档根为 `output/UNC 20.15.2 产品文档(裸机容器) 05/`。只有 Feature 文档簇无法回答必须的命令顺序、参数、取值或约束时才可回查。交付时必须记录：回查原因、文件、结论。原始文档不能替代 Feature 文档簇或 AtomTask。

### 5. 先输出每 Feature 的准入记录，再开始写文件

每个 Feature 至少报告：

```text
Feature code
实际读取的 Feature md 清单
激活方法/配置场景
配置类命令与对应 AtomTask 路径
Feature param=value → AtomTask 配置方法的核对结论
CT 候选、Jaccard、相位同义结论
原始文档是否例外回查（原因/文件/结论）
结论：ready / information-limited / foundation / Atom 冲突 / 待数据规划补齐
```

未完成上述准入记录前，禁止写任何 Task 文件。

================================================================
第二阶段：按 Feature 同步构建 FT + CT
================================================================

对每个 `ready` Feature：

1. 先从 Feature 文档簇还原每种激活方法的完整命令时间线。不得按通用经验重排命令；必须保留对象、全局基线、可选分支、`INHERIT`、重复命令、每次 `SET REFRESHSRV` 的所在相位。
2. 写一份 `UNC@FeatureTask@{feature_code}.md`：
   - 配置概览：对象链和场景骨架；
   - 配置流程：CompoundTask 与单 AtomTask 的混合编排；
   - **激活方法与参数差异**：逐场景表，固定列为“激活方法/条件｜配置相位｜执行的 Task｜省略的 Task｜关联 AtomTask｜相对基线的参数差异｜目标对象与生效说明”；
   - **参数核对**：每个实际命令/参数的 Atom 准入、冲突或待补结论；
   - 决策点、约束、独立的 `## 边`。
3. 单命令/双命令阶段直接链接 atom；稳定多命令步骤才建/复用 CT。
4. 新 CT 必须同时写 `command_set`、组成 atom、典型脚本、步骤位置、场景差异、决策点、约束和 `被引用于` 反链。
5. 任何 Feature 的每种激活方法，都必须能从 FT + CT 还原实际命令子集、对象、顺序、参数值和省略项；差异不能只留在交付报告。

对 `foundation` Feature：

- 仅当完整簇确认没有独立 UNC 配置流程时，写 `status: foundation` 的 FT；
- 说明无独立配置的依据和非本 NF 配置责任（如有）；
- 不虚构 AtomTask、参数、配置流程或 CT。

对 `information-limited` Feature：

- 完整簇已确认独立配置责任，但没有可恢复的 MML、激活案例、对象顺序或参数实例；写 `status: draft` 的 FT；
- `## 配置流程`、`## 激活方法与参数差异`、`## 参数核对` 均明确标“信息不足，未编排”，并逐项列待补的 MML、顺序和数据规划；
- 不建 CT、不引用或凭常识猜测 AtomTask、命令、参数和顺序；不能错误写成 foundation。

================================================================
第三阶段：构建者自检（交独立审查前）
================================================================

逐 Feature / CT 自检：

- YAML、ID、文件名、ref、独立 `## 边`、wikilink 真实；
- FT 配置类命令全部被 Atom/CT/显式省略覆盖；
- Feature 实际参数=值全部进入激活差异、CT 场景差异或参数核对，且不臆造 Feature 未给出的变体；
- CT `command_set` = 组成 atom 集合，FT ↔ CT 反链一致；
- CT 场景差异包含每个引用 Feature 的实际命令子集、参数、对象、相位；
- 无调测命令、命令静态表、`source`/`source_evidence_ids`/`## 证据` 残留；
- foundation 已证明“全簇无独立配置”，不是因文档少而草率判定；information-limited FT 已明确未编排范围和待补输入。

================================================================
第四阶段：交付给独立对抗审查者
================================================================

交付中必须包含：

1. 分配 Feature 的准入记录；
2. 新建/改写 FT、CT 文件清单；
3. 每个 CT 的 command_set、复用/新建理由、被引用于；
4. 跨域 CT 的待整合回填清单；
5. 每种激活方法的命令时间线、参数核对与原始文档例外记录；
6. information-limited Feature 及其待补 MML/Atom/数据规划；
7. 自检结果与已知风险。

独立审查者不是你，且不得改文件。只有独立审查的 CRITICAL/HIGH 为 0 后，才由唯一集成者合并跨域 CT、重生 `_index.md` 并运行结构审计。
```

## 派单示例

```text
批次名称：UNC-B4
分配 Feature Code：WSFD-010400, WSFD-010501, WSFD-010502, WSFD-010503, WSFD-010504, WSFD-010600
步骤所有权域：会话、地址与用户面选择
可修改的既有 CompoundTask：session-addr-alloc-skeleton, session-n4-pfcp-skeleton, session-pcc-chf-skeleton, smf-chf-trigger-rg-aging, unc-apn-access-infra, unc-ctrl-addr-alloc-rule, unc-dhcp-server-chain, unc-dualstack-global-switch, unc-smf-addrpool-hierarchy, unc-upf-selection-family
只读的既有 CompoundTask：其余全部 CT
```
