# 命令层核查（check）

> 命令层产出的独立质量审查。**只审不建**，与 @命令构建师分离。

## 审查角色纪律
- **怀疑主义**：只认证据，不给面子，默认产物有问题
- 问题必须可定位（对象 ID + 规则）
- 区分"产物问题"（回构建师返工）和"SKILL 缺口"（提 change-request）

## 审查输入
- 命令层构建产物（命令 + 配置对象 md）
- [字段定义](字段定义.md)（字段权威）
- 该批 build manifest

## 审查输出
核查报告：`{通过/不通过, 问题清单[{对象, 问题类型, 严重级, 归属}]}`

## 审查项（命令层）

| 类别 | 检查点 |
|---|---|
| 字段必填 | 命令：`id/type/name/nf/version/status`；配置对象：`id/type/name/object_kind/nf/version/status` 不空 |
| ID 格式 | 三段式逻辑ID `{网元}@{Type}@{local}`（网元在最前，**不含版本**）；命令 local 含空格 |
| 文件名 ↔ ID | 文件名 = 逻辑ID（如 `UDG@MMLCommand@ADD URR.md`），保留空格 |
| 结构统一 | 每个资产 = YAML + 正文 + `## 边`；关系**只在"边"章节**，正文不重复 |
| 配置对象产生规则 | 只有配置类命令(ADD/MOD/DEL/RMV/SET)产生配置对象；查询(LST/DSP)/动作(ACT)等**不产生**（但可关联已存在的） |
| 边合理 | 命令→配置对象（对象对应**已存在**配置对象）；配置对象→命令（被操作，反向闭环）；命令↔命令（参见，**只引真实存在的命令**） |
| 命令原文 | 原始 md 原样保留（功能/注意事项/参数说明/实例等），TOC/anchor 已清洗；**图片纳入** `Command/{nf}/{ver}/assets/`（hash 去重） |
| 图片闭环 | `![](assets/x.png)` 引用的 png 实存于 `Command/{nf}/{ver}/assets/`（配置对象则在 `ConfigObject/{nf}/{ver}/assets/`）；**无残留 `{旧名}.assets/` 旧路径** |
| 引用闭环 | 命令↔命令引用→`[[{nf}@MMLCommand@{cmd}]]`；死链已**剥 URL 留文字**；**无残留指向 output/ 的相对路径**；核查用独立正则抽样复核 |
| 参数 | 参数说明表在命令 md 原文内，**不单独建** Parameter md |
| manifest | build manifest 完整（sop_version + 对象数 + nf/version） |

## 交接
- 通过 → 收口（写 manifest 状态）
- 不通过 + 产物问题 → 回 **@命令构建师** 返工
- 不通过 + SKILL 缺口 → 提本层 `change-requests/`
