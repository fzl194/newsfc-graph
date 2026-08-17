---
id: "ConfigurationSolution@{{scenario-slug}}-{{solution-slug}}"
type: "ConfigurationSolution"
name: "{{方案中文名}}"
name_zh: "{{方案中文名}}"
domain: "{{domain-slug}}"
scenario: "{{scenario-slug}}"
status: "draft"
---

# {{方案中文名}}

> {{一句话：这个方案怎么配}}。属于 [[NetworkScenario@{{scenario-slug}}]]。编排 {{N}} 个特性（跨网元 UDG+UNC）。

## 概览

{{方案是什么 + 用了哪些特性（跨网元）+ 协同骨架}}。1-2 段。

## 配置与协同

> 特性优先：仅详述本方案的**特性级变种/排除项** + **跨特性协同**。各特性未变化的配置走其标准配置方法（见 FeatureTask），CS 不重复。

本方案编排 {{N}} 个特性：`{{FeatureTask 列表}}`。

**特性关系矩阵**（★必填——回答"哪些必配 / 可选 / 包含 / 正交"）：

| 特性 | 角色 | 必配? | 关系说明 |
|---|---|---|---|
| [[{{nf}}@FeatureTask@{{feature_code}}]] | 核心 / 基础(依赖前提) / 维度增强 / 跨网元对端 / 二选一 | 必配 / 可选(条件) | {{与核心的重叠/正交/组合/包含；配置是否重叠}} |

> 矩阵规则：①**核心**=方案主体（必配）；②**基础/依赖前提**=核心依赖的底层（必配，配置常与核心重叠）；③**维度增强**=正交维度可选叠加；④**跨网元对端**=另一网元对应特性（组合）；⑤**二选一**=互斥路径选其一。**配置重叠必须在「关系说明」注明**（防"额外配一遍"误解）。**依赖前提特性（License 前置）必须进矩阵**，不只在约束段提。

### {{网元}} 侧：{{特性名}}

走标准配置方法（见 [[{{nf}}@FeatureTask@{{feature_code}}]]）。若有**变种/排除**（方案独有）：详述差异点（参数/命令/组装）+ 原因；标准里有但本方案不用的命令注明排除 + 原因。无变种则一句"走标准配置方法，无特性级变种"。

### 跨网元/跨特性协同

{{特性间协同顺序 + 一致性约束 + 参数对齐——方案独有，详述}}

## 决策点

> 配置级 DP。每 option 影响全记。DP 不编号（引用只到 md 级）。

### DP1：{{决策点名}}
| 选项/场景 | 影响（参数/命令/联动） |
|---|---|
| {{选项}} | {{选哪些 FeatureTask / 走哪个 CompoundTask / 跨网元路径 / 关键参数}} |

## 约束

- **{{规则名}}**（{{severity}}）：{{约束}} — {{后果}}

## 边

> CS 的边指向上游场景 + 编排的 task 层动态对象（FeatureTask/CompoundTask/AtomTask）。禁止直连 Feature/License/ConfigObject（静态/动态拆分，同 task 层）。
> 反向：被引用的 FeatureTask/CompoundTask/AtomTask 的 `## 边` 须追加 `被引用于 → [[本CS]]`。

- 上游场景: [[NetworkScenario@{{scenario-slug}}]]
- 编排特性: [[{{nf}}@FeatureTask@{{feature_code}}]], [[{{nf}}@FeatureTask@{{feature_code}}]]
- 复用步骤: [[{{nf}}@CompoundTask@{{slug}}]]
- 复用命令: [[{{nf}}@AtomTask@{{命令名}}]]
