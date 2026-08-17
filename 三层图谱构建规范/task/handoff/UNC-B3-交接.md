# UNC-B3：鉴权、身份隐私、NAS/SBI 加密与证书交接

> 执行日期：2026-08-13  
> 批次状态：**已完成（7 项 FeatureTask；新增 2 个 CompoundTask）**。

## 当前产物

| Feature | 文档结论 | 当前产物 |
|---|---|---|
| `WSFD-010301` 鉴权功能 | 2G/3G/4G/5G 激活链均有可恢复 MML；Intra RAU 软参无完整实例 | 重构 FT，直引已准入 Atom；软参信息受限未编排 |
| `WSFD-010302` 用户身份保密性 | 3G/4G/5G 链可恢复；2G `SET GMMPTMSIREALLOC` 缺 Atom 和脚本实例 | draft FT，已准入链直引，2G 待补前置 |
| `WSFD-010303` NAS 信令加密与完整性 | LTE 有稳定三命令类型链；5G 是两 Atom 分支 | FT + `lte-nas-protection` CT |
| `WSFD-010304` 强制身份识别 | 仅 2G/Gb 与 3G/Iu 各一条激活命令 | FT，直引 Atom，无 CT |
| `WSFD-010305` 日志匿名化 | 日志匿名化与 CHR 本地假名化是独立小流程；网管操作非本地 MML | FT，直引 Atom，无 CT |
| `WSFD-010308` SBI 安全 | CERT、PSK 两条激活链可恢复，均复用本端 TLS/HTTP/SBI 端点步骤 | FT + `sbi-tls-local-endpoint` CT |
| `WSFD-010309` 证书管理 | 有独立证书管理责任，未给激活、MML、顺序、参数 | 信息受限 draft FT |

## 关键边界与冲突

- `010302`：2G 命令缺 Atom 且无实例，未临时补造；只记录待补前置。
- `010304`：Gb Atom 缺 `IDRQ` 配置字典项，Feature 实例如实标待补。
- `010305`：`VALUE=0`/`VALUE_0` 与 Atom 文本口径、`PSEUDONYPOLICY.KEY` 的长度/字符规则冲突均已标待澄清；实际 KEY 脱敏，未写明文。
- `010308`：CERT 两个 `ADD TLSPARA` 的完整 `CIPHER` 集合已逐字符还原；PSK 值仅为源文示例，生产密钥仅可由受控数据规划和执行通道注入，禁止在 Task、脚本、交接和日志中落盘。FQDN DNS 所需的两 Atom 缺失、NRF 新增最小字段不足，均未编排。
- `010309`：内部通信证书更新将重启全部 POD；无可执行资料时未挪用 `010308` 的流程。

## 审查与集成

- `010301`–`010305` 首轮独立审查：`CRITICAL=0 / HIGH=0 / MEDIUM=0`。
- `010308` 首轮发现 CERT 缺 `CIPHER` 和 PSK 示例安全标注不足；修复后二次审查：`CRITICAL=0 / HIGH=0 / MEDIUM=0`。`010309` 审查通过。
- 集成者移除了 `unc-apn-access-infra` 对重构后 `010301` 的历史无来源反链，并重生 `_index.md`。
- 当前全局：CompoundTask 49、FeatureTask 147；跨层审计 `fail=0`，Feature→Atom 强覆盖 `952/952`，Task 脚本单测 9/9 通过。
