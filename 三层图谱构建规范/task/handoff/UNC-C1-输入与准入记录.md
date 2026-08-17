# UNC-C1：漫游控制、系统间改变与鉴权集转换——输入与准入记录

> 批次范围：`WSFD-011001`、`WSFD-011002`、`WSFD-011003`。  
> 记录时间：2026-08-13。此记录是构建前只读准入底稿，不替代 Task 正文。

## WSFD-011001

- **完整 Feature md**：`概述.md`、`激活漫游控制特性(适用于AMF).md`、`激活漫游控制特性(适用于SGSN_MME).md`、`调测漫游控制特性.md`、`WSFD-011001 漫游控制参考信息.md`。
- **激活方法/配置场景**：SGSN/MME 配置互联 PLMN 与 VPLMN 话单属性；AMF 配置 5G 互联 PLMN 与漫游受限拒绝原因。调测页仅含 LST 查询和跟踪，剥离。
- **配置类命令与 Atom 准入**：`ADD CONNECTPLMN` → `AtomTask/UNC/20.15.2/UNC@AtomTask@ADD CONNECTPLMN.md`（存在；数据规划基线 `MCC=460,MNC=00,MATCHIMSI=1234,NOID=3,SM=YES,MAXSMNUM=2,SMS=YES,SMSCR=YES,SMSCT=861395678956778,LCS=YES,S5S8TYPE=GTP,EXCLUSIVEPLMN=NO` 可核；`CC=86`、`COUNTRYORAREANAME=noname` 未列入 Atom 字典，待 Atom 更正。任务脚本只给其中 `MCC/MNC/CC/SMS/SMSCR/SMSCT` 子集）；`SET CHGPLMNCHAR` → `...@SET CHGPLMNCHAR.md`（存在；数据规划基线 `PLMN=VPLMN,MP=YES,SP=YES,SMOP=YES,SMTP=YES,LCSMOP=YES,LCSMTP=YES,LCSNIP=YES` 可核；任务脚本以 `LCSNIP=NO` 作为相对基线变体）；`ADD NGCONNECTPLMN` → `...@ADD NGCONNECTPLMN.md`（存在；`NOID=0,MCC=123,MNC=45` 可核；脚本中的 `DESC="for MNO A"` 未列入 Atom 字典，待 Atom 更正）；`SET NGMMPROCTRL` → `...@SET NGMMPROCTRL.md`（存在；`PROT=OTHER_PROC,ROAMRST=0` 可核）。
- **候选 CT**：无。每个激活方法均为 2 个 distinct 配置 Atom，低于抽取 floor；`unc-location-dns-family` 与对象链无关。
- **原始产品文档回查**：否。Feature 文档簇已给出每条时间线和实例。
- **结论**：`ready with Atom conflicts`；构建 normal draft FeatureTask，直接编排 Atom，不新建/复用 CT，并在参数核对中保留 `ADD CONNECTPLMN.CC`、`ADD CONNECTPLMN.COUNTRYORAREANAME`、`ADD NGCONNECTPLMN.DESC` 的 Atom 字典缺口。另：数据规划 `NOID=3` 需先核实对应 `ADD MVNO` 前置，当前 Feature 簇未给该实例。

## WSFD-011002

- **完整 Feature md**：`概述.md`、`激活系统间改变.md`、`实现原理.md`、`调测系统间改变.md`。
- **激活方法/配置场景**：SGSN 的 2G/3G 系统间改变能力；激活页明确把数据和步骤外链到“配置到SGSN的数据”，本簇未包含该页面。调测页出现的 `ADD IPV4DNSH`、可选 `ADD DNSN`、可选 `ADD SGSNDNS` 是验证前两台 SGSN 的部署准备，非本 Feature 可恢复的激活脚本；`DSP` 查询剥离。
- **配置类命令与 Atom 准入**：`ADD IPV4DNSH` → `...@ADD IPV4DNSH.md`（存在，但本簇无实际 `param=value`）；`ADD DNSN` → `...@ADD DNSN.md`（存在，但仅条件说明且无实例）；`ADD SGSNDNS` → AtomTask 不存在。三者均不作为本 Feature 的可恢复激活链编排。
- **候选 CT**：`unc-location-dns-family` 命令集与调测部署准备相近，但其 Atom 覆盖不完整、且 Feature 簇未给激活命令/参数/顺序；不复用。
- **原始产品文档回查**：否。当前缺口是 Feature 静态资产所引用的簇外“配置到SGSN的数据”页面，不能用原始文档越过静态层缺失。
- **结论**：`information-limited`；有独立配置责任但无本簇可恢复 MML 时间线，写 draft FeatureTask，不建 CT、不编排 Atom。

## WSFD-011003

- **完整 Feature md**：`概述.md`、`WSFD-011003 鉴权3元组和5元组参考信息.md`。
- **激活方法/配置场景**：3 元组/5 元组在 SGSN 内随 SIM/USIM、Gb/Iu 和 R98/R99 条件运行时转换；无激活页、数据规划或任务脚本。
- **配置类命令与 Atom 准入**：参考信息明确“本特性无相关命令”。概述仅在原理说明中提到 `SET GMM`/`SET PMM` 可配置鉴权请求重发次数，未提供本特性的参数实例或转换开通命令；不把它们伪作转换功能的激活链。
- **候选 CT**：无；无可恢复命令集。
- **原始产品文档回查**：否。Feature 文档簇已明确无相关命令；无必要参数/顺序可供例外澄清。
- **结论**：`information-limited`；写 draft FeatureTask，不建 CT、不编排 Atom。
