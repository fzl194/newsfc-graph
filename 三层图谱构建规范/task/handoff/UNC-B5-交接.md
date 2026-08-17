# UNC-B5：QoS 与流量管理交接

> 执行日期：2026-08-13  
> 批次状态：**已完成（3 项 FeatureTask；新增 2 个特性专属 CompoundTask）**。

## 当前产物

| Feature | 文档结论 | 当前产物 |
|---|---|---|
| `WSFD-010701` QoS 管理 | GGSN、PGW-C、SMF、MME 都有可恢复 QoS 实例；GGSN/5GC 命令适用范围存在文档冲突 | FT + `unc-qos-global-profile-remark`、`unc-qos-apn-profile-remark-bind` |
| `WSFD-010702` 流量控制 | 可恢复的规则/限速链有限；`ADD QOSTRANS` 仅参考信息、无激活参数/时序 | FT，直引 Atom，`ADD QOSTRANS` 信息受限未编排 |
| `WSFD-010703` DSCP 重标记 | 有独立配置责任，但实际 `SET DSCPRMK` 缺 Atom | 信息受限 draft FT |

## 关键边界与冲突

- `010701`：完整保留 GGSN `ADD PRER8REMARK` 的 Profile、全局 `SET QOSGLOBAL` 的数据规划/脚本差异；PGW-C 的 `SET LICENSESWITCH` 作为全局和 APN 两条 EPS 链的前置，未被泛化为 CT 组成。GGSN 激活页提到而无同 NF 准入输入的 `ADD 5GCREMARK` 标适用范围冲突、未编排。
- `010702`：修正 IMSI 范围已有 `BEG/END` 实例的表述；`ADD QOSTRANS` 已明列为参考命令，缺激活输入、未编排。
- `010703`：不临时补造 `SET DSCPRMK` Atom，也不编造参数或顺序。

## 审查与集成

- 首轮独立审查发现 1 个 CRITICAL（GGSN Profile 参数遗漏）、1 个 HIGH（PGW-C License 时间线遗漏）、2 个 MEDIUM（QOSTRANS 登记与 IMSI 实例表述），均按 Feature 原文修复。
- 聚焦复审结果：`CRITICAL=0 / HIGH=0`；无待处理 MEDIUM。
- 已重生 `_index.md`；当前 CompoundTask 51、FeatureTask 151，跨层审计 `fail=0`，Feature→Atom 强覆盖 `952/952`。
