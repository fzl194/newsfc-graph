# UNC-C2（DRA接口）输入与准入记录

> 本记录在 Task 落盘前完成，只记录本批只读输入与准入判断。业务输入仅使用 Feature 静态文档簇；未回查原始产品文档。查询/调测文档中的 `DSP`、`LST`、`EXP` 未纳入配置编排。

## WSFD-011125

- **完整 Feature md**：`概述.md`、`WSFD-011125 S5接口参考信息.md`。
- **场景与配置命令**：同 PLMN 的 SGW-C/PGW-C 信令接口；文档无配置类 MML、无激活/数据规划/任务脚本。参考信息仅列 `DWORD1062 BIT8` 软参，未给出 UNC MML、对象、值或顺序。
- **Atom / CT**：无候选 Atom、无候选 CT。
- **原始文档例外**：否。
- **结论**：`foundation`。文档说明接口能力与部署位置，不给出独立 UNC 配置责任；不得将协议栈原理或软参名称臆造为 Task 流程。

## WSFD-011126

- **完整 Feature md**：`概述.md`、`WSFD-011126 S8接口参考信息.md`。
- **场景与配置命令**：漫游 PLMN 的 SGW-C/PGW-C 信令接口；文档无配置类 MML、无激活/数据规划/任务脚本。参考信息仅列 `DWORD1062 BIT8` 软参，未给出 UNC MML、对象、值或顺序。
- **Atom / CT**：无候选 Atom、无候选 CT。
- **原始文档例外**：否。
- **结论**：`foundation`，理由同 S5；不能把接口协议原理误写为配置流程。

## WSFD-011132

- **完整 Feature md**：`概述.md`、`实现原理.md`、`激活Gx over DRA（静态路由+BFD组网）.md`、`调测Gx over DRA.md`、`WSFD-011132 Gx over DRA参考信息.md`。
- **激活场景**：TCP 与 SCTP 两种 Gx-over-DRA 链路；均先由外部“静态路由+BFD组网”建立可达性，再配置本端、DRA、链路、Realm 路由及 PCC/Realm 绑定。调测页只读，已剥离。
- **配置类命令及 Atom**：`ADD VPNINST`、`SET CONCENPOINT`、`ADD LOGICIP`、`ADD LOGICINF`、`ADD DIAMLOCINFO`、`ADD PCRF`、`SET PCCTIMER`、`ADD SCTPENDPOINT`、`SET DIAMETERPARA`、`ADD DRA`、`ADD DIAMPEERADDR`、`ADD DIAMCONNGRP`、`ADD DIAMCONNECTION`、`ADD DIAMRTREALM`、`ADD DIAMRTNEXTHOP`、`ADD PCCTEMPLATE`、`ADD APN`、`SET APNPCCFUNC`、`ADD IMSIMSISDNSEG`、`SET PCCFUNC`、`ADD GLBDIAMREALM`、`ADD REALMBINDAPN`；均有同名 `AtomTask/UNC/20.15.2/UNC@AtomTask@*.md`。实例中的 IPv4/SCTP、`GX`、`LOCALPORT`、`ENABLE`、`MASTER_SLAVE`、`SESSION_ID`、`DISABLE` 等枚举均在对应 Atom 配置方法可核；地址、主机名、Realm、VPN、端口和号码段为规划值。
- **候选 CT**：现有 `pcrf-diameter-chain` 与本特性直连 PCRF 对接相位不同，且没有 DRA/Realm 路由，不能复用；新建 `dra-diameter-transport-route`（共同 DRA 传输/路由相位）与 `gx-dra-pcc-realm-enable`（本特性 PCC/Realm 相位）。
- **原始文档例外**：否。
- **结论**：`ready`；外部静态路由+BFD 的命令实例不在本簇，作为前置条件明确保留，未伪造 Atom 编排。

## WSFD-011133

- **完整 Feature md**：`概述.md`、`实现原理.md`、`激活Gy over DRA（静态路由+BFD组网）.md`、`调测Gy over DRA.md`、`WSFD-011133 Gy over DRA参考信息.md`。
- **激活场景**：TCP 与 SCTP 两种 Gy-over-DRA 链路；TCP 示例还配置直连 OCS，直连不可用时由 DRA 转交。调测页只读，已剥离。
- **配置类命令及 Atom**：`ADD VPNINST`、`SET CONCENPOINT`、`ADD LOGICIP`、`ADD LOGICINF`、`ADD DIAMLOCINFO`、`ADD OCS`、`ADD DIAMPEERADDR`、`ADD OCSGROUP`、`ADD OCSBINDING`、`ADD DCCTEMPLATE`、`ADD SCTPENDPOINT`、`SET DIAMETERPARA`、`ADD DRA`、`ADD DIAMCONNGRP`、`ADD DIAMCONNECTION`、`ADD DIAMRTREALM`、`ADD DIAMRTNEXTHOP`、`ADD APN`、`ADD REALMBINDAPN`、`ADD GLBDIAMREALM`；均有同名 AtomTask。`GY`、`LOCALPORT`、`ENABLE`、`MASTER_SLAVE`、`IPv4`/`SCTP` 可在 Atom 中核；端点/地址/主机名/Realm/端口为规划值。
- **候选 CT**：复用新建 `dra-diameter-transport-route`，相位、对象链和共享命令顺序均相同；OCS 组和 Realm 绑定与既有 CT 无相位同义候选，直引 Atom。
- **原始文档例外**：否。
- **结论**：`ready`。TCP 任务脚本的相同 `ADD APN` 出现两次但没有第二个对象实例；在 FT 中保留为原文重复，标为执行前需确认的文档异常，不能臆造第二个 APN。

## WSFD-011134

- **完整 Feature md**：`概述.md`、`实现原理.md`、`激活S6b over DRA（静态路由+BFD组网）.md`、`调测S6b over DRA.md`。
- **激活场景**：TCP 与 SCTP 两种 S6b-over-DRA 链路；可选配置 AAA Server 组/APN 绑定与 FQDN 主机名。调测页只读，已剥离。
- **配置类命令及 Atom**：`ADD VPNINST`、`SET CONCENPOINT`、`ADD LOGICINF`、`ADD DIAMLOCINFO`、`ADD DIAMAAAGRP`、`ADD APNDIAMAAAGRP`、`ADD PGWHOSTNAME`、`SET DIAMETERPARA`、`ADD SCTPENDPOINT`、`ADD DRA`、`ADD DIAMPEERADDR`、`ADD DIAMCONNGRP`、`ADD DIAMCONNECTION`、`ADD DIAMRTREALM`、`ADD DIAMRTNEXTHOP`、`ADD APN`、`ADD REALMBINDAPN`、`ADD GLBDIAMREALM`、`ADD SMFINFO`；均有同名 AtomTask。`S6B`、`LOCALPORT`、`ENABLE`、`MASTER_SLAVE`、`IPv4`/`SCTP` 可在 Atom 核；地址、主机名、Realm、VPN、端口、APN 为规划值。
- **候选 CT**：复用新建 `dra-diameter-transport-route`；新建 `s6b-dra-aaa-binding` 以承载 AAA 组、APN 绑定与可选 FQDN 联动。
- **原始文档例外**：否。
- **结论**：`ready`。`ADD SMFINFO` 只作为 `PGWHOSTNAME` 的 FQDN 一致性前置被引用，激活脚本没有实例；FT 只标为条件前置和“待数据规划补齐”，不虚构值。

## 待集成清单

- 新建 CT：`UNC@CompoundTask@dra-diameter-transport-route`、`UNC@CompoundTask@gx-dra-pcc-realm-enable`、`UNC@CompoundTask@gy-dra-ocs-direct-peer`、`UNC@CompoundTask@s6b-dra-aaa-binding`。
- 本子批不修改共享 CT 或 `_index.md`；由集成者在独立审查 C/H 清零后生成索引。
