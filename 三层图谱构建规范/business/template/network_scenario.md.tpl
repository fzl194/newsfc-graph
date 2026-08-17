---
id: "NetworkScenario@{{scenario-slug}}"
type: "NetworkScenario"
name: "{{场景中文名}}"
name_zh: "{{场景中文名}}"
domain: "{{domain-slug}}"
scenario: "{{scenario-slug}}"
status: "draft"
---

# {{场景中文名}}

> {{一句话：解决什么业务问题}}。属于 [[BusinessDomain@{{domain-slug}}]]。含 {{N}} 个方案。

## 概览

{{场景定义 + 判断依据（什么业务需求触发本场景）+ 典型产出}}。1-2 段。

## 边界

- 覆盖：{{网元/接口/控制维度}}
- 不覆盖：{{相邻场景区分}}

## 决策点

> 场景级决策（如选哪个 CS、场景级方案路由）。DP 不编号（引用只到 md 级）。

### DP1：{{决策点名}}
| 选项/场景 | 影响 |
|---|---|
| {{选项}} | {{影响：选哪个 CS / 走哪条路径}} |

## 约束（可选）

- **{{规则名}}**（{{severity}}）：{{约束}} — {{后果}}

## 边

> NS 的边指向上游域（BD）与下游方案（CS）。

- 上游域: [[BusinessDomain@{{domain-slug}}]]
- 下游方案: [[ConfigurationSolution@{{scenario}}-{{solution-1}}]], [[ConfigurationSolution@{{scenario}}-{{solution-2}}]]
