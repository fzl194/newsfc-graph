---
name: feature-layer-build
description: 把产品文档的特性/license 构建成特性层资产。Feature=按feature_code聚合(每md统一资产)，License=控制项md切段。统一 YAML+原文+边，按ID引用。
sop_version: 0.13.0
---

# 特性层构建 SKILL

> 产品文档的特性 + license → 特性层资产。**每个文档 = YAML + 原始文档 + ## 边**，按 ID 引用（同命令层）。**图片纳入**（每特性文件夹 `assets/`），**文档引用统一为 `[[ID]]`**（命令→`@MMLCommand@`、特性→`@Feature@{code}` 或 `@Feature@{code}-{slug}` 精确到子文档）；规则见 [conventions/资产图片与引用处理](../conventions/资产图片与引用处理.md)。
> - **Feature**：遍历全部 md 按**最深 feature_code 聚合**到一个特性文件夹；每 md（概述/激活/原理…）都是统一资产。
> - **License**：控制项 md 按**段**切分，每段（一个 license）建一个统一资产。
> - **ID 机制**：概述=`{nf}@Feature@{code}`（默认引用目标）；子文档=`{nf}@Feature@{code}-{slug}`（slug=源文件名，**doc_type 只进 YAML 不进 ID**，因 doc_type 多对一会撞名）。

## 何时用
拿到一个网元的产品文档（特性目录 + license 目录），构建特性层资产时。

## 输入
| 参数 | 说明 | 示例 |
|---|---|---|
| `--nf` | 网元 | `UDG` |
| `--version` | 版本 | `20.15.2` |
| `--storage` | 资产根（默认 `三层图谱资产`） | `三层图谱资产` |
| `--feature-dir` | 特性源目录（`特性指南/UDG特性指南`） | |
| `--license-dir` | license 源目录（`UDG License描述`） | |

## 输出（`{storage}/` 下）
- `Feature/{nf}/{version}/{nf}@Feature@{feature_code}/{slug}.md` — 每特性一个文件夹（按 code 聚合全部 md）；概述存为 `概述.md`，子文档存为 `{slug}.md`
- `Feature/{nf}/{version}/{nf}@Feature@{feature_code}/assets/*.png` — 特性内全部源文档的图片（按文件夹 hash 去重合并；无图特性的不建该目录）
- `License/{nf}/{version}/{nf}@License@{license_code}.md` — 每 license 一 md
- 各 `_build_manifest.json`

## 构建流程（`scripts/build_all.py` 编排）
1. **特性** `build_features.py`：遍历 feature-dir 下**全部 md**，按**最深 feature_code**（路径段里最靠右的那个 code）归组 → 同 code 的所有 md 进一个特性文件夹 → 每 md 加 YAML+边；**预算「源文件名→目标文档ID」映射**、图片拷入特性文件夹 `assets/`、文档引用统一改写为 `[[ID]]`（特性引用精确到具体子文档，命令引用解析需命令资产已存在）；规则见 [conventions](../conventions/资产图片与引用处理.md)
2. **license** `build_licenses.py`：扫控制项 md → 按 `#### [{control_id} {license_code} {名}]` 切段 → 每段加 YAML+边

## Feature：feature_code 聚合模型 + 文件名 ID
- **按 code 聚合，不靠父文件夹**：产品文档的目录树是「文件归在分类目录 + 多层嵌套」（如某特性 md 是上级分类目录里的文件、或 `实现原理/` 子目录里的文件）。所以用「父文件夹名含 code」会漏一大半。**正确做法**：遍历全部 md，按其路径里最深的 feature_code 归组（最深=最具体的特性，跳过上级分类码）。
- **ID 机制**（doc_type 是多对一分类，**不能**当 ID 区分位，否则同特性的 N 个「原理」文件撞名）：
  - 概述（特性本体）：`{nf}@Feature@{feature_code}` —— **默认引用指向它**
  - 子文档：`{nf}@Feature@{feature_code}-{slug}`，slug = 源文件名净化（去 `_{数字id}.md` 后缀、清 OS 非法字符，保留中文/空格）
  - 同特性内 slug 撞名 → 前面补一层父目录消歧
- **doc_type 只进 YAML 字段**（分类用，不进 ID）：文件名关键词优先（特性概述→概述、激活→激活、调测→调测、参考信息→参考信息…），否则按所在子目录（实现原理→原理、特性配置→配置…），再退回「其它」。
- **概述判定**：文件名含「特性概述」优先；否则文件名=纯特性名（`{code} {名}` 无其它 doc 关键词）。无概述的特性记入 manifest `features_without_overview` 供人工复核。

## 边（从源文档推导，双向闭环）
| 边 | 出现位置 | 来源 |
|---|---|---|
| Feature(概述) → License（所需License） | 概述 md | **只扫概述「可获得性」章节**的 license_code（产品文档在此声明特性自己的 License控制项；不扫全文，否则互斥/交互表里别人的 license 会被误挂）|
| License → Feature（对应特性） | license md | license 表"对应特性"字段取 feature_code |
| Feature → Feature（依赖/冲突） | 概述 md | **只扫概述「与其他特性的交互」章节**的 feature_code |
| Feature(概述) ↔ 子文档（包含/属于） | 概述 + 子文档 | 文件夹归属（闭环）|

## 规范引用
- 字段：[字段定义](字段定义.md)　·　骨架：[template/](template/)　·　决策：[需求与路线](需求与路线.md)
- 核查：[check.md](check.md)
- 统一约定（逻辑ID `{网元}@{Type}@{local}`、`{type}/{网元}/{版本}/` 存储、版本动态解析、无 source 字段）同命令层

## 核查（构建后必做）
产出交 [check.md](check.md)：字段必填 / ID 格式 / doc 类型识别 / license 段切分 / 边闭环（Feature↔License、概述↔子文档）。
