# 三层图谱构建规范

> 本目录是 Agent 构建三层知识图谱资产的权威依据——**一个整体能力包**。
> 版本：见 [VERSION](VERSION)；变更：见 [CHANGELOG](CHANGELOG.md)

---

## 这是什么

一套**自包含、场景无关**的构建规范。整体是一个大能力包；**每一层又是一个独立的能力包**。

- **命令层**：命令、配置对象（参数在命令 md 原文内，不单独建）
- **特性层**：特性、license
- **业务层**：业务域、场景、方案
- **Task 层**（贯穿）：原子 task、步骤 task、特性 task

| 特点 | 含义 |
|---|---|
| 场景无关 | 规范里不写具体业务场景，只写方法 |
| Agent 导向 | 命令式、明确输入输出、带可核查检查点、自包含 |
| 自包含 | 不依赖外部代码或现有数据，可整体迁移 |
| 可演进 | 版本号 + 变更回路，见 [演进机制](演进机制.md) |

---

## 结构原则：全局放顶层，每层下沉

- **全局的东西放顶层**（所有层共用）：治理、通用约定、共享脚本
- **每层的东西下沉到该层文件夹**（构建师 / 核查 / SKILL / 字段 / 模板 / 脚本 / change-requests）：每层是一个**独立、可单独拿走测试**的能力包

### 顶层（全局）
```
三层图谱构建规范/
├── README.md / VERSION / CHANGELOG.md / 演进机制.md / 语料演进SOP.md   治理（全局：规范演进 + 图谱内容演进）
├── 层包标准.md          每层文件夹统一结构标准（加新层照此）
├── conventions/         通用约定（命名/ID/evidence，跨所有层）
└── scripts/             共享脚本（阶段0 产品文档导出，所有层入口）
    └── product_doc_md_exporter_optimized.py
```

### 每层（独立能力包，统一模板）
```
{layer}/                    command / feature / task / business 同构
├── agent.md                该层构建师人设
├── check.md                该层核查（只审不建）
├── SKILL.md                构建方法（输入/输出/流程/规范）
├── 字段定义.md             字段权威
├── template/               文件骨架
├── scripts/                该层脚本
├── change-requests/        该层变更请求
└── （调研等辅助文档）
```

> 每层结构详见 [层包标准](层包标准.md)。加新层 = 按标准建文件夹填内容。**层与层独立，互不依赖。**

---

## 每层内部的协作闭环

```
@构建师（按 SKILL 构建）→ 产出 → check.md 核查
                                        │
                              ┌─────────┴──────────┐
                            通过                  不通过
                              │                    │
                            收口            回构建师返工
                                  （若属 SKILL 缺口）
                                         │
                                  提本层 change-requests
```

每个层包自带"构建 → 核查 → 反馈"闭环，不依赖其它层。

---

## 两类构建体裁

| 体裁 | 用于 | 回答 |
|---|---|---|
| **Spec（规格）** | 代码/脚本构建的对象 | "输入→输出→字段投影规则" |
| **Procedure（步骤）** | Agent 手工构建的对象 | "一步步怎么做" |

某层用哪种，在该层 `SKILL.md` 声明。

---

## 阅读顺序

1. 本 README（全局结构 + 层包模板）
2. [层包标准](层包标准.md)（每层文件夹统一结构，加新层照此）
3. [演进机制](演进机制.md)（规范怎么变）
4. [语料演进SOP](语料演进SOP.md)（基于新语料持续演进图谱——业务专题/配置指导书等任意新语料）
5. [conventions/命名规范-建议](conventions/命名规范-建议.md)（通用命名）
6. 构建某层时，读该层 `{layer}/` 下全部（agent → SKILL → 字段 → check）
7. 实际跑构建时，读 [scripts/README.md](scripts/README.md)（共享导出脚本）

---

## 当前状态

| 状态 | 内容 |
|---|---|
| ✅ 已完成 | 全局骨架：README / VERSION / CHANGELOG / 演进机制 / conventions / scripts(阶段0) |
| ✅ 已完成 | command/ 命令层（全量验证 UDG+UNC：13075 命令 + 3500 配置对象）|
| ✅ 已完成 | feature/ 特性层能力包（Feature feature_code 聚合模型 + 文件名 ID + License 段落模型；全量 UDG 验证 258 特性/865 文档 + 187 license）|
| 🟡 进行中 | task/（atom 全建；compound/feature_task 迁移中）|
| ✅ 层包就位 | business/ 业务层能力包（SKILL/check/字段/template/CR；资产待迁入 `三层图谱资产/Business/`）|

**当前焦点：task 层 compound/feature_task 迁移 + business 资产迁移（`assets/business/` → `三层图谱资产/Business/`）。**
