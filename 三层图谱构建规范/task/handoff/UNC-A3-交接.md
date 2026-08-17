# UNC-A3：Portal 运维、配置/跟踪与 NTP 交接

> 执行日期：2026-08-11  
> 批次状态：**已完成（7 项均已落盘；6 项信息受限 draft，NTP 为正常单 Atom 编排）**。

## 当前准入与产物

所有 Feature 均读取完整静态文档簇；未以原始产品文档替代 Feature 输入。

| Feature | 文档结论 | 当前产物 |
|---|---|---|
| `NPFD-010001` 性能管理 | Portal 监控、业务监控、阈值规则责任明确；无 UNC MML、脚本、对象顺序或参数实例 | `UNC@FeatureTask@NPFD-010001`（draft，信息受限） |
| `NPFD-010005` 配置管理 | 仅确认 `EXP MML` 导出能力；无导入/恢复命令和时间线 | `UNC@FeatureTask@NPFD-010005`（draft，信息受限） |
| `NPFD-010006` 安全管理 | 账号、密码策略、角色、日志、证书、密钥更新责任明确；无可恢复 UNC 链 | `UNC@FeatureTask@NPFD-010006`（draft，信息受限） |
| `NPFD-010007` 日志管理 | 日志级别、留存、下载/收集责任明确；无可恢复 UNC 链 | `UNC@FeatureTask@NPFD-010007`（draft，信息受限） |
| `NPFD-010010` 在线加载 | 软件包、路径、解压、主/依赖包完整性检查责任明确；无可恢复 UNC 链 | `UNC@FeatureTask@NPFD-010010`（draft，信息受限） |
| `NPFD-010013` 跟踪功能 | 跟踪生命周期、软参位、资源/隐私约束明确；无配置入口、位值、对象关系或时序 | `UNC@FeatureTask@NPFD-010013`（draft，信息受限） |
| `NPFD-010014` 支持 NTP | `ADD NTPSVR` 是激活页唯一实配命令；`LST NTPSVR` 仅调测 | `UNC@FeatureTask@NPFD-010014`（draft，直引 `[[UNC@AtomTask@ADD NTPSVR]]`） |

## 信息受限处理

前六项均有独立配置责任，不能写 foundation；但 Feature 簇未提供可恢复 MML、对象顺序或参数实例。其 FT 的配置流程、激活方法与参数核对均明确“信息不足，未编排”，并逐项列待补 MML、对象顺序与数据规划；未编造 Atom、CT、命令或参数。

## NTP 参数与场景核对

- Feature 示例的 `ADD NTPSVR` 八项参数均可在 AtomTask 配置方法中核验；`KEYSTRING=*****` 是脱敏值，FT 标为待安全数据规划补真实密钥。
- `FusionStage-only` 场景无网元侧 Task，明确省略 `ADD NTPSVR`；网元直连外部 NTP 或以 OMC 为时间源时才编排该 Atom。
- 修正 `ADD NTPSVR` Atom：`AUTHFLAG` 仅在 `PROTOCOLVERSION=NTPV4` 时条件必选，`NTPV3` 不需要该参数。
- 单一配置 Atom，不新建 CompoundTask；未重生 `_index.md`。

## 独立审查与集成

- 6 个信息受限 FT：`CRITICAL=0 / HIGH=0 / MEDIUM=0`。
- NTP FT/Atom：首轮 2 个 MEDIUM（FusionStage-only 分支、`AUTHFLAG` 条件性）已修复，复审 `CRITICAL=0 / HIGH=0`。
- 本批无 CT 变更；完成后运行 Atom 与跨层结构审计。
