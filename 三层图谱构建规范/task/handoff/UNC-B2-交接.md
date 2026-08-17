# UNC-B2：非 3GPP、共接入、RedCap/FWA 与对等网元选择交接

> 执行日期：2026-08-11  
> 批次状态：**已完成（8 项均按完整 Feature 文档簇重建/新建并复审收敛）**。

## 当前产物

| Feature | 文档结论 | 当前产物 |
|---|---|---|
| `WSFD-010102` 非 3GPP 接入 | 15 个激活 MML 实例；集中点/本端端口有显式与默认自动分配两分支 | FT + `non3gpp-aaa-s6b-chain` CT |
| `WSFD-010105` 4G/5G 共接入 | 参考信息明确无相关命令 | foundation FT |
| `WSFD-010106` 2G/3G 共接入 | 存在纯 2G/纯 3G/混合模式配置责任，但无 MML、对象、参数或时间线 | 信息受限 draft FT |
| `WSFD-010108` 增强型等效 PLMN | AMF 五命令链；SGSN/MME 为单 `ADD PEERPLMN` 分支 | FT + `enhanced-eplmn-amf-group` CT |
| `WSFD-010110` RedCap 接入 | 两套激活脚本可恢复；仅数据表出现的 `ADD AMFN8CMPTPLCY` 未有脚本 | FT + `redcap-access-enable` CT |
| `WSFD-010112` FWA | AMF 统计单命令与 SMF 规则/软参两命令；Rule ID 存在两来源冲突 | FT（直引 Atom） |
| `WSFD-010201` 移动性管理 | 概述明示无需配置即可使用；2G/3G 原理提及的命令不构成独立激活链 | foundation FT |
| `WSFD-010202` 基于位置区域的对等网元选择 | 激活脚本有三条 DNS 命令；原理命令无实例/脚本 | 重建 FT + `location-peer-dns-record-chain` CT |

## 关键来源边界

- `010102`：`SET CONCENPOINT` 是可选项。显式 `LOCALPORT=19765` 分支与 `ADD DIAMCONNECTION.LOCALPORT` 成对使用；默认集中点分支省略两者，由系统自动分配端口。`ADD LOGICIP` 隐含前置和 `apn1` 外部 PDN/APN 前置均标待补；Feature 未说明既有会话生效范围。
- `010108`：AMF 的 `PLMNIDX=0` 依赖外部 `ADD NGSRVPLMN` Serving PLMN 记录，Feature 未提供实例；未补造命令。终端须支持 3GPP R99+。
- `010110`：`ADD AMFN8CMPTPLCY` 仅数据规划、缺脚本和字段选择，正文标未编排且不再以“编排”边连接。
- `010112`：完整保留 `up_87000017`（数据表/脚本）与 `up_870000174`（任务描述/概述/命令层）冲突，待规划、CLI 和实际 PCF Rule ID 确认；`RULE/FULL` 与 Atom 枚举差异亦未掩盖。已沉淀 5G SA、无漫游、存量用户重新上线、AMF/SMF 华为设备限制。
- `010202`：`SET MSCSELPLCY` 的 Atom 已有但 Feature 缺参数/脚本；`ADD SGSNDNS` 同时缺 Atom、参数、脚本，二者均未编排。为收敛旧反链，集成者从 `unc-apn-access-infra` 与 `unc-location-dns-family` 移除了过时的 `WSFD-010202` 引用，未改其余复用语义。

## 审查与集成

- 前半首轮 2 HIGH/3 MEDIUM、后半首轮 2 HIGH/2 MEDIUM 均已修复；两侧最终复审均为 `CRITICAL=0 / HIGH=0 / MEDIUM=0`。
- 新增 4 个 CT，集成后 `_index.md` 为 47 CT、264 条 command_set 项；跨层审计 `fail=0`，Feature→Atom 强覆盖 `952/952`。
