# 特性层核查（check）

> 特性层产出的独立质量审查。**只审不建**，与 @特性构建师分离。

## 审查角色纪律
- **怀疑主义**：只认证据，不给面子，默认产物有问题
- 问题必须可定位（对象 ID + 规则）
- 区分"产物问题"（回构建师返工）和"SKILL 缺口"（提 change-request）

## 审查输入
- 特性层构建产物（Feature 文件夹 + License md）
- [字段定义](字段定义.md)
- 该批 build manifest

## 审查输出
核查报告：`{通过/不通过, 问题清单[{对象, 问题类型, 严重级, 归属}]}`

## 审查项（特性层）

| 类别 | 检查点 |
|---|---|
| 字段必填 | Feature 文档：`id/type/name/nf/version/feature_code/doc_type`；License：`id/type/name/nf/version/license_code/control_item_id/control_item_type` 不空 |
| ID 格式 | 逻辑ID `{网元}@{Type}@{local}`；Feature 概述 = `{nf}@Feature@{feature_code}`，子文档 = `…-{slug}`（slug=源文件名，**非 doc_type**）；License = `{nf}@License@{license_code}` |
| ID 唯一 | 全局 id 无重复；同特性文件夹内存储文件名无重名（撞名应已按父目录消歧） |
| Feature 聚合 | 按 feature_code 聚合（非父文件夹名）；同特性的全部 md（含 `实现原理/`、`特性配置/` 等子目录、以及落在分类目录里的文件）都在同一文件夹 |
| 概述存在 | 每特性有 `概述.md`（默认引用目标）；manifest 的 `features_without_overview` 清单逐个人工复核 |
| doc_type 分类 | doc_type 是 YAML 字段（不进 ID）；文件名关键词优先、否则按所在子目录；无大面积「其它」误判 |
| License 段切分 | 控制项 md 里每个 `#### [{id} {code} {名}]` 段都切成独立 license md；**control_id 两种格式都要收**（纯数字 `81203214` + 字母数字 `82200CKP`）；段标题三段（control_id/code/name）解析正确 |
| 核查独立性 | **核查不能用与构建同一条正则**（共用盲区查不出漏建）。段切分核查要用独立、更宽松的匹配复核段总数 |
| 原文完整 | 原始 md/段内容原样保留（清洗 TOC/anchor，不删正文）；**单 H1**（不 prepend，保留原文自带 H1，对齐命令层）；**图片纳入**：每特性文件夹 `assets/`（hash 去重），引用改写为本地相对路径 |
| 图片闭环 | `![](assets/x.png)` 引用的 png 实存于同文件夹 `assets/`；**无残留 `{旧名}.assets/` 旧路径**；外链/缺图原样保留可接受 |
| 引用闭环 | 命令引用→`[[{nf}@MMLCommand@{cmd}]]`、特性引用→`[[{nf}@Feature@{code}]]` 或 `[[…@Feature@{code}-{slug}]]`（精确到具体子文档）；死链已**剥 URL 留文字**；**无残留相对路径 / output 路径**；核查用独立正则抽样复核（不复用构建同一条正则） |
| 边闭环 | Feature(概述)↔License（所需License↔对应特性）；概述↔子文档（包含→各 slug-id、子文档属于特性）；Feature→Feature（依赖/冲突）|
| manifest | build manifest 完整（sop_version + model + 特性数/license数 + nf/version + 无概述/多概述清单） |

## 交接
- 通过 → 收口（写 manifest 状态）
- 不通过 + 产物问题 → 回 **@特性构建师** 返工
- 不通过 + SKILL 缺口 → 提本层 `change-requests/`
