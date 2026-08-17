# UNC-A4：Service Fabric 通信亚健康、业务节点故障与自愈交接

> 执行日期：2026-08-11  
> 批次状态：**已完成（2 项正常直引 Atom，1 项信息受限 draft）**。

## 当前产物

| Feature | 文档结论 | 当前产物 |
|---|---|---|
| `SFFD-010008` 通信亚健康自愈 | Fabric 与 Base 平面均有激活数据和实际 SET 脚本；Fabric 数据规划另含脚本未执行的链路切换意图 | `UNC@FeatureTask@SFFD-010008`（draft，直引 `SET FABRICSUBHEALTHY`、`SET COMBASEHEALTH`） |
| `SFFD-010030` 分布式集群防脑裂 | 激活页能恢复 VNFC 的两条 SET 配置，但操作步骤与任务脚本给出相反 SET 顺序；概述明确 VNFP/ACS 不需本地使能 | `UNC@FeatureTask@SFFD-010030`（draft，直引 `SET ELECTSERVICE`、`SET BASESUBHEALTH`） |
| `SFFD-010031` 微服务故障多级自愈 | Feature 给出 `SET PODHEALPLY → ADD PODBLACKLIST → SET PODHEALCTRL`，但三个命令均缺 Atom 且无参数实例 | `UNC@FeatureTask@SFFD-010031`（draft，信息受限） |

## 来源冲突与信息受限处理

- `SFFD-010008`：任务脚本实际只设置 `SUBHEALTHYINTERVAL=30`、`SUBHEALTHYTHRESHOLD=50`；`ISLINKSWITCHENABLE=TRUE` 仅是数据规划意图。FT 明确需补显式开关命令或澄清脚本遗漏，未将两者合写为已执行配置。
- `SFFD-010030`：保留两个来源时间线：操作步骤为 `LST VNFC → SET BASESUBHEALTH → SET ELECTSERVICE`，任务脚本为 `LST ELECTSERVICE → SET ELECTSERVICE → SET BASESUBHEALTH`。`LST VNFC`、`LST ELECTSERVICE` 都是查询核查，已按 SOP 剥离；不伪造唯一 SET 顺序。VNFP/ACS 与激活页任务描述冲突时，以概述“无需本地使能”结论排除，待 Feature 文档更正。
- `SFFD-010031`：按更新后 SOP 仍写入独立信息受限 FT，显式列出 3 条缺失 Atom、缺少实例参数与执行对象；未虚构 Atom、CT、参数或顺序。

## 审查与集成

- `SFFD-010008`、`SFFD-010030` 首轮 2 个 HIGH（脚本/数据规划混合、时序强行唯一化）均已修复，复审 `CRITICAL=0 / HIGH=0 / MEDIUM=0`。
- `SFFD-010031` 独立审查 `CRITICAL=0 / HIGH=0 / MEDIUM=0`。
- 本批无需新建 CompoundTask；当前全局跨层审计 `fail=0`，Feature→Atom 强覆盖 `952/952`。
