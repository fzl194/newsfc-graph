---
id: "BusinessDomain@{{domain-slug}}"
type: "BusinessDomain"
name: "{{业务域中文名}}"
name_zh: "{{业务域中文名}}"
domain: "{{domain-slug}}"
status: "draft"
---

# {{业务域中文名}}

> {{一句话定义}}。含 {{N}} 个场景。

## 概览

{{业务域是干啥的——定义/价值/核心能力}}。1-2 段。

## 范围与边界

- 含场景：{{NS 列表}}
- 不属于本域：{{相邻域区分}}

## 决策点（可选，罕见）

{{域级决策，若有；无则整段省略}}

| 选项/场景 | 影响 |
|---|---|
| {{选项}} | {{影响}} |

## 约束（可选）

- **{{规则名}}**（{{severity}}）：{{约束}} — {{后果}}

## 边

> BD 的边只指向本域的下游场景（NS）。禁止指向 task/特性/命令层（静态/动态拆分）。

- 下游场景: [[NetworkScenario@{{scenario-1}}]], [[NetworkScenario@{{scenario-2}}]]
