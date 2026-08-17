# UNC-C1：漫游控制、系统间兼容与话单/QoS 兼容交接

> 执行日期：2026-08-13  
> 批次状态：**已完成（6 项 FeatureTask；无新增 CompoundTask）**。

## 输入与产物

- 准入记录：[UNC-C1-输入与准入记录.md](D:\mywork\KnowledgeBase\NewSFCGraph\三层图谱构建规范\task\handoff\UNC-C1-输入与准入记录.md)、[UNC-C1-WSFD-011004-011006-准入记录.md](D:\mywork\KnowledgeBase\NewSFCGraph\三层图谱构建规范\task\handoff\UNC-C1-WSFD-011004-011006-准入记录.md)。
- 全部 17 篇 Feature 文档均已逐簇读取；未使用原始产品文档例外；所有场景均不足 3 个 distinct Atom，未建 CT。

| Feature | 文档结论 | 当前产物 |
|---|---|---|
| `WSFD-011001` 漫游控制 | SGSN/MME 与 AMF 各有两命令激活链 | draft FT，四 Atom 直引 |
| `WSFD-011002` 系统间漫游 | 有独立责任，但激活页外链到簇外资料；DNS 为调测准备 | 信息受限 draft FT |
| `WSFD-011003` 鉴权映射 | 无激活/配置命令；原理 `SET GMM/PMM` 非开通链 | 信息受限 draft FT |
| `WSFD-011004` 系统间兼容 | 默认能力，参考信息明确无命令 | foundation FT |
| `WSFD-011005` 计费兼容 | `SET CHGGA` 可关联，但无 Feature 参数实例/时序 | draft FT，单 Atom 直引入口 |
| `WSFD-011006` QoS 兼容 | 概述明确 `RLBCLSMAP=PROHIBIT/ALLOW` | draft FT，可执行单 Atom 双分支 |

## 关键边界与冲突

- `011001`：数据规划基线和脚本子集均完整保留；包括 `LCSNIP=YES` 基线与 `LCSNIP=NO` 脚本变体。`NOID=3` 的 MVNO 前置、`CC`/`COUNTRYORAREANAME`/`DESC` 的 Atom 字典缺口均明确标注，未伪称准入。
- `011002`：DNS 只用于调测准备，不进入配置流程或边。
- `011003`：不将原理中提及的 `SET GMM`/`SET PMM` 编为转换开通命令。
- `011006`：首轮误降为信息受限；审查后改为来源完整的 `PROHIBIT`/`ALLOW` 可执行分支。

## 审查与集成

- 首轮审查发现 `011006` 分支降级错误、`011001` 数据规划基线遗漏；均已修复，最终双侧复审均 `CRITICAL=0 / HIGH=0 / MEDIUM=0`。
- 当前全局：CompoundTask 55、FeatureTask 163，跨层审计 `fail=0`，Feature→Atom 强覆盖 `952/952`。
