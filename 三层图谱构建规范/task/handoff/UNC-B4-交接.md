# UNC-B4：用户数据、会话、地址与路径管理交接

> 执行日期：2026-08-13  
> 批次状态：**已完成（6 项 FeatureTask 原位重构/新建；本批未新增 CompoundTask）**。

## 当前产物

| Feature | 文档结论 | 当前产物 |
|---|---|---|
| `WSFD-010400` 用户数据管理 | 仅能确认 `SET SDBTMR.PURGTMR`、`SET SYS.SUBSTORAG` 的本地责任；无实例/顺序 | 信息受限 draft FT |
| `WSFD-010501` 会话管理 | 多个本地命令和机制明确，但无激活脚本、对象/参数/顺序 | 信息受限 draft FT |
| `WSFD-010502` 地址分配方式 | 可恢复地址池—UPF 绑定九命令子集及独立黑名单；旧 APN/OSPF 链无来源 | 重构 draft FT，复用 `unc-smf-addrpool-hierarchy` 子集，直引 `ADD BLACKLIST` |
| `WSFD-010503` 4G APN 最大会话数 | 仅 4G Internet/WAP 两次 `ADD APNACTNUM` 有实例；5G 仅能力描述 | 重构 draft FT，直引 Atom |
| `WSFD-010504` 控制面地址分配 | 概述/参考列命令但没有激活、参数、对象或顺序 | 信息受限 draft FT |
| `WSFD-010600` 路径管理 | PFCP、GTP-C/GTP-U 多分支有局部可恢复配置；AMF 链缺两个 Atom | 新建 draft FT，直引已准入 Atom，AMF 未闭合链显式省略 |

## 关键边界与冲突

- `010501`：补齐并登记 `ADD CONNECTPLMN`、`SET SMFUNC.APNOIPLY`、`ADD CHGBEHA`、`SET CHGCHAR` 四条原理性依赖；均缺对象、实例、条件、顺序，未编排。
- `010502`：保留 `ADD BLACKLIST` 的 `NAME=testblacklist1`/`testblacklist`、`IPVERSION=IPV4`/`IPv4` 和 `ADD ADDRPOOL.IPVERSION=IPV4`/`IPv4` 数据规划—脚本差异，均为待 CLI/规划确认；确认前不判通过或下发。
- `010503`：移除无来源的 `APNNI=*` 泛化分支，只保留 Internet/WAP 两个源实例；其他 APN 待资料补齐。
- `010600`：保留 GTP-U 操作步骤与任务脚本的两条时序，不强行统一；PFCP Feature 脚本 `NFINSTANCENAME` 与数据表/Atom `UPFINSTANCEID` 明确标“冲突/待 Atom 更正”。
- `010504`：旧版把参考命令清单编为流程，已移除，改按 SOP 的信息受限处理。

## 审查与集成

- 首轮审查发现 2 个 CRITICAL（010502 参数差异漏标、010503 泛化分支）及 1 个 CRITICAL（010501 四条命令遗漏），均已修复；010600 的字段冲突为已正确标注项。
- 六项最终交叉复审均为 `CRITICAL=0 / HIGH=0 / MEDIUM=0`。
- 集成阶段清理了旧 FT 剥离后遗留的共享 CT 反链，重生 `_index.md`。
- 当前全局：CompoundTask 49、FeatureTask 148；跨层审计 `fail=0`，Feature→Atom 强覆盖 `952/952`，脚本单测 9/9 通过。
