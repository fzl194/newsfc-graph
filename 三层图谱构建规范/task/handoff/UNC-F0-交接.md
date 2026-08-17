# UNC-F0 单文件概述型 foundation 专批交接

> 执行日期：2026-08-07  
> 批次状态：**已完成**。

## 结论

按 `UNC领域批次构建计划.md` §3 的 105 项快照逐目录读取唯一的 `概述.md`，并核验配置类 MML 命令、激活/配置流程、数据规划和任务脚本。

- 77 项满足 foundation 判定：文档簇确为单一 `概述.md`，未承载独立 UNC 配置类 MML 命令、激活/配置流程、数据规划或任务脚本；已逐篇理解后手写为 FeatureTask。
- 28 项不满足 foundation 判定：概述中存在配置类 MML 命令、明确本地配置责任或 Portal 配置操作，已移出 UNC-F0，回到其所属业务批做完整文档簇准入。
- P0 已完成：38 个既有 CompoundTask 已补齐 `command_set`、统一 `组成` / `被引用于` 边并生成 `_index.md`；跨层审计为 0 fail。
- 77 项 foundation FeatureTask 已逐篇创建，均为 `status: foundation`，不虚构 AtomTask、参数或 CompoundTask。

## 输入与核验方法

- Feature 根目录：`三层图谱资产/Feature/UNC/20.15.2/`
- 每个候选均读取：`UNC@Feature@{code}/概述.md` 全文。
- 105/105 目录均只有一个 Markdown 文件，且文件名均为 `概述.md`。
- 核验配置类动作：`ADD`、`MOD`、`SET`、`DEL`、`RMV`、`LOD`、持久化 `STR`；同时检查激活/配置/数据规划/任务脚本段落。
- 未使用原始产品文档例外回查；唯一概述已足以作本轮 foundation 分流。

## foundation 准入（77 项）

以下每项的准入记录一致：已读完整 `概述.md`；无配置类命令、激活/配置流程、数据规划或任务脚本；无 AtomTask/CT 准入需求；结论为 `foundation`，但因 P0 未完成暂不落盘。

| 范围 | Feature Code |
|---|---|
| IPFD（3） | `IPFD-014000`, `IPFD-014004`, `IPFD-017000` |
| NPFD（9） | `NPFD-010002`, `NPFD-010003`, `NPFD-010004`, `NPFD-010008`, `NPFD-010009`, `NPFD-010011`, `NPFD-010017`, `NPFD-010018`, `NPFD-010019` |
| SFFD（14） | `SFFD-010004`, `SFFD-010005`, `SFFD-010009`, `SFFD-010010`, `SFFD-010011`, `SFFD-010013`, `SFFD-010014`, `SFFD-010015`, `SFFD-010032`, `SFFD-010033`, `SFFD-010035`, `SFFD-010036`, `SFFD-010037`, `SFFD-010043` |
| WSFD-010（7） | `WSFD-010000`, `WSFD-010001`, `WSFD-010002`, `WSFD-010003`, `WSFD-010004`, `WSFD-010306`, `WSFD-010805` |
| WSFD-011（26） | `WSFD-011103`, `WSFD-011104`, `WSFD-011105`, `WSFD-011106`, `WSFD-011118`, `WSFD-011119`, `WSFD-011120`, `WSFD-011127`, `WSFD-011128`, `WSFD-011129`, `WSFD-011130`, `WSFD-011131`, `WSFD-011135`, `WSFD-011136`, `WSFD-011138`, `WSFD-011139`, `WSFD-011140`, `WSFD-011141`, `WSFD-011144`, `WSFD-011304`, `WSFD-011401`, `WSFD-011402`, `WSFD-011403`, `WSFD-011404`, `WSFD-011407`, `WSFD-011501` |
| WSFD-102～109（5） | `WSFD-103007`, `WSFD-104407`, `WSFD-107001`, `WSFD-107015`, `WSFD-109008` |
| WSFD-113～230（13） | `WSFD-113001`, `WSFD-113006`, `WSFD-113009`, `WSFD-202003`, `WSFD-209001`, `WSFD-209205`, `WSFD-214001`, `WSFD-219003`, `WSFD-219005`, `WSFD-224101`, `WSFD-224102`, `WSFD-225001`, `WSFD-227103` |

> 注：`WSFD-113001/113006/113009` 实际归属 UNC-E3；其中“Set ID”只作为文本术语出现，未作为 MML 命令计入配置输入。

## 移出 UNC-F0（28 项）

| Feature Code | 概述中的配置输入 | 后续业务批 | 准入结论 |
|---|---|---|---|
| `SFFD-010022` | `SET FWDFCPARA` 的 ICMP 流控阈值参数 | UNC-A（运维/网络可靠性） | 移出；需完整配置准入 |
| `WSFD-010807` | `ADD/MOD/RMV SCTPLE` | UNC-B6 | 移出；需核 AtomTask 与端点配置流程 |
| `WSFD-011112` | `MOD S1IMEICFG` | UNC-C2 | 移出；需核 IMEI 策略参数 |
| `WSFD-011116` | `ADD DMPE`、`ADD DMRT`、`ADD SCEF` | UNC-C2 | 移出；需核 Diameter/SCEF 配置步骤 |
| `WSFD-011137` | `ADD GTPCLEGRPMEM`、`ADD GTPCLE` | UNC-C2 | 移出；需核实际对象与顺序 |
| `WSFD-011406` | `ADD NGPEIPLCY`、`RMV MSISDNSUBGPMEM` 等 | UNC-C2 | 移出；需完整命令时间线 |
| `WSFD-104412` | `SET IPV6PARA` | UNC-D3 | 移出；需核 IPv6 参数准入 |
| `WSFD-107005` | `SET UPSELECTPRI`、`SET UPSELECTFLAG`、`ADD PNF*`、`ADD UPAREA` 等 | UNC-D6 | 移出；需完整 UPF 选择配置准入 |
| `WSFD-107010` | `SET UPSELECT*`、`ADD PNF*`、`ADD UP*` 等 | UNC-D6 | 移出；已有旧 FT 亦须原位重构 |
| `WSFD-113002` | `ADD SMFSELPLCY`、`SET NRFFUNCSW`、`ADD AMFDNNPLCY` | UNC-E3 | 移出；需核 NRF 选择/策略配置 |
| `WSFD-214004` | `SET NRFFUNCSW`、`ADD NRFIMSIRT` | UNC-F4 | 移出；需核分层 NRF 路由配置 |
| `WSFD-214005` | `SET NRFFUNCSW`、`ADD NRFIMSIRT` | UNC-F4 | 移出；需核分层 NRF 路由配置 |
| `WSFD-224103` | `SET CHFINIT`、`SET HVNEGRCPSW` | UNC-F7 | 移出；需核漫游 QBC 计费开关 |
| `WSFD-227101` | `SET UPGSTEP` | UNC-F8 | 移出；需核在线升级冗余资源配置 |
| `WSFD-106402` | SMF 可本地配置位置相关 Trigger | UNC-D5 | 移出；需还原位置策略配置与依赖关系 |
| `WSFD-211002` | SMF 可本地配置位置相关 Trigger | UNC-F3 | 移出；需还原位置策略配置与依赖关系 |
| `WSFD-214002` | 通过配置触发 L-NRF 去注册 | UNC-F4 | 移出；需核触发配置命令与参数 |
| `WSFD-214003` | L-NRF 心跳周期可通过命令设置 | UNC-F4 | 移出；需核心跳配置命令与参数 |
| `WSFD-224104` | V-SMF 本地 Default QoS Flow 与预制范围配置 | UNC-F7 | 移出；需核 QoS 配置链 |
| `WSFD-224105` | 本地切片映射规则与优先开关配置 | UNC-F7 | 移出；需核切片映射配置链 |
| `IPFD-014003` | 管理员配置静态路由的目的、接口、下一跳和优先级 | UNC-A2 | 移出；需核静态路由命令与对象链 |
| `IPFD-014005` | 配置地址前缀列表或 Route-Policy | UNC-A2 | 移出；需核路由策略配置链 |
| `IPFD-014006` | 配置策略路由 | UNC-A2 | 移出；需核策略路由配置链 |
| `IPFD-015001` | 绑定接口、路由、APN、地址池至 VRF，并含 VRF 路由协议绑定 | UNC-A2 | 移出；需核 VRF 及关联对象配置链 |
| `NPFD-010001` | Portal 配置监控阈值规则 | UNC-A3 | 移出；需明确 Portal 配置资产与责任 |
| `NPFD-010006` | Portal 配置账号、密码、证书和密钥 | UNC-A3 | 移出；需按安全管理流程准入 |
| `NPFD-010007` | Portal 配置日志级别和留存期 | UNC-A3 | 移出；需按运维日志流程准入 |
| `NPFD-010010` | OM Portal 在线加载软件包、路径和完整性检查 | UNC-A3 | 移出；需按软件运维流程准入 |

## 后续动作

1. 将 28 项加入表列出的业务批，按完整 Feature 文档簇、AtomTask 和 CT 复用库执行常规准入。
2. 若 foundation Feature 后续补充操作步骤、数据规划或任务脚本，撤销其 foundation 判定并在所属业务批原位重构。
