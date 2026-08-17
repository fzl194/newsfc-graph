# UNC-A1：接口、VLAN、ARP、QoS、ACL、BFD 交接

> 执行日期：2026-08-11  
> 批次状态：**已完成（QoS/ACL 正常构建并集成；其余 4 项已按信息受限规则构建为 draft）**。

## 输入与准入记录

所有六项均先读取完整 Feature 文档簇，再读取相关 AtomTask、`CompoundTask/UNC/20.15.2/_index.md` 与命中候选。未使用原始产品文档例外回查；Feature 文档簇已足以做准入判断。

| Feature | 已读 Feature md | 场景与命令核验 | CT 判断 | 结论与产物 |
|---|---|---|---|---|
| `IPFD-010001` | `概述`、`控制接口震荡特性`、`最大传输单元MTU` | 逻辑接口创建、震荡抑制与 MTU 责任可确认；仅有查询链接，无配置 MML/实例 | 无命令集，不建 CT | **信息受限 draft FT 已建**；待补 MML、对象顺序、参数实例。 |
| `IPFD-010002` | `概述`、VLAN 子接口、VLAN 帧格式 | 子接口、VLAN ID、接口 IP 责任可确认；无配置 MML/实例 | 无命令集，不建 CT | **信息受限 draft FT 已建**；待补 MML、对象顺序、数据规划。 |
| `IPFD-011001` | `概述`、ARP 原理/静态/代理等 7 篇 | 静态 ARP 与路由式代理责任可确认；无配置 MML/实例 | 无命令集，不建 CT | **信息受限 draft FT 已建**；待补 MML、IP/MAC/VLAN/出接口实例及顺序。 |
| `IPFD-012001` | QoS/分类/VPN/激活去激活等完整簇 | 46 条配置命令闭环；冲突/待补参数已显式保留 | 新建 4 个 QoS CT | **FT + CT 已建并集成**。 |
| `IPFD-012002` | ACL 分类、IPv4/IPv6 激活去激活等 9 篇 | 15 条配置命令闭环；IPv6 编号与 ICMP 字段冲突已保留 | 每路径 2 Atom，直引 | **FT 已建并集成**。 |
| `IPFD-012003` | `概述`、BFD for IP/静态路由/OSPF/BGP | BFD 会话/绑定责任可确认；无配置 MML/实例 | 无命令集，不建 CT | **信息受限 draft FT 已建**；待补 MML、绑定顺序、参数实例。 |

## 历史输入缺口（后续已按信息受限规则落盘）

### IPFD-010001

待补接口、逻辑接口、MTU 与接口震荡抑制的可执行 MML、对象级顺序、参数名/值和数据规划。现有 `DSP PORT`、`LST INTERFACE`、`DSP IFSTATUS` 是查询命令，不得据此生成配置 Task。

### IPFD-010002

待补 VLAN 子接口创建及 VLAN ID 关联的可执行 MML、对象实例、参数名/值和数据规划。`VLAN ID=1–4094` 仅为能力范围，不能作为配置实例。

### IPFD-011001

待补静态 ARP 与路由式 ARP 代理的可恢复 MML、命令参数、数据规划和相应 AtomTask。动态与免费 ARP 的运行时结论不能覆盖上述明确的配置责任。

### IPFD-012003

待补静态 BFD 会话的创建/提交 MML、本地/远端描述符与检测参数、单跳/多跳对象绑定、协议/静态路由绑定命令、数据规划和相应 AtomTask。关联路由 Feature 仅是责任线索，不能绕过本特性的输入缺口。

### IPFD-012001 缺失 AtomTask

`ADD QOSIFTRUST`、`ADD QOSDIFFERSERV`、`SET QOSBA`、`SET QOSPHB`、`ADD QOSIFPHB`、`ADD QOSRDRVPN`、`RMV QOSIFTRUST`、`RMV QOSRDRVPN`、`RMV QOSIFPHB`、`ADD ACLRULEBAS4`、`SET QOSACTFILTER`、`ADD SQOSREMARK`、`ADD QOSACTRDRPOLICY`、`ADD SQOSRDRVPNGROUP`、`ADD SQOSURPF`、`ADD SQOSCAR`、`ADD QOSAPPLICATION`、`RMV QOSAPPLICATION`、`RMV QOSACTRDRNHP`、`RMV SQOSREMARK`、`RMV QOSACTRDRPOLICY`、`RMV SQOSRDRVPNGROUP`、`RMV SQOSURPF`、`RMV SQOSCAR`、`MOD DSCPMAP`。

还需处理：`MOD MQCPOLICY` 的 Atom 枚举仅允许 `STCENABLE=enable/disable`，但 Feature 数据规划表有 `STCENABLE=5`；Feature 的 VPN 重定向分支未给 `ADD L3VPNINST.VRFNAME` 实值。二者均不能在 FT 中被默认值掩盖。

### IPFD-012002 缺失 AtomTask

`ADD ACLRULEBAS4`、`ADD ACLRULEETH`、`ADD ACLRULEIF`、`ADD ACLRULEBAS6`、`RMV ACLRULEIF`、`RMV ACLRULEETH`、`RMV ACLRULEBAS4`。

另需在补 Atom 时统一 `ADD ACLRULEADV4` 的字段名：配置方法表写作 `ACLICPCODE`，Feature 与 Atom 约束段写作 `ACLICMPCODE`。IPv6 激活页任务描述称创建 3001/3002，实际脚本和数据表均为 3000；未来构建须以脚本 `3000` 为准并保留该待澄清项。

## 复核与集成

- 独立只读对抗审查曾对 `IPFD-011001` 与 `IPFD-012003` 的 foundation 判定提出 2 个 High：两簇均有明确配置责任但缺可恢复命令/参数。已按审查结论撤回两份暂建 FT，并将其改列为 blocked；Critical/High 已清零。
- 本批最终没有新建或修改 CompoundTask，因此无需重生 CT 索引。
- 撤回后已运行 `audit_compound_feature.py --nf UNC --version 20.15.2`：0 fail；FeatureTask 数回到 114，两个撤回文件均不存在。

---

## 2026-08-11 Atom 修复后的恢复构建与集成

修复后的 Feature→Atom 强证据门禁先发现并补建了 QoS/ACL 所需 Atom；其中还修复了粗体包裹命令链接及多行脚本的采集漏项。恢复构建的所有 Feature 均重新读取完整文档簇，不沿用上文旧阻塞结论。

| Feature | 结果 | 关键结论 |
|---|---|---|
| `IPFD-012001` QoS | **新建 FT + 4 个 QoS CT** | 46/46 配置命令闭包；两条源时间线均保留。`policy2` 仅为无创建脚本的数据规划计划值；DSCP 类型、MQC 统计开关、出方向下一跳、VPN 前置和 SQOS 回收占位均显式标为冲突或待补。 |
| `IPFD-012002` ACL | **新建 FT，直引 Atom** | 15/15 命令闭包；每个规则族仅“规则组+规则”两 Atom，不造 CT。IPv6 的 3000/3001/3002 文本冲突和 ICMP 字段名冲突均按脚本真值/待澄清保留。 |
| `IPFD-010001`、`IPFD-010002`、`IPFD-011001`、`IPFD-012003` | **历史 blocked（已由下方信息受限 draft 取代）** | 完整簇无可恢复的配置 MML、对象级顺序和参数实例；不得仅凭能力/原理文本编造可执行流程。 |

### 新建 CT

- `qos-diffserv-domain-bind`
- `qos-simple-classification-teardown`
- `qos-complex-policy-apply`
- `qos-complex-policy-teardown`

独立审查结论：QoS 与 ACL 均为 `CRITICAL=0 / HIGH=0`。唯一集成者已重生 `_index.md`；当前 42 个 CT、233 条 `command_set` 条目。跨层审计 `fail=0`，Feature→Atom 强证据门禁 `952/952`、缺口 0。

### 信息受限规则后的补建

用户确认：完整簇有独立配置责任但无激活案例、MML、对象顺序或参数实例时，不能静默不写；必须创建信息受限 `draft` FT，不编排或杜撰 Atom/CT。原表中四项“仍 blocked”已由下列当前结论取代：

| Feature | 当前产物 | 未编排原因与待补输入 |
|---|---|---|
| `IPFD-010001` | `UNC@FeatureTask@IPFD-010001`（draft） | 接口/逻辑接口、震荡抑制、MTU 责任可确认；待补持久化 MML、对象顺序、参数实例。 |
| `IPFD-010002` | `UNC@FeatureTask@IPFD-010002`（draft） | VLAN 子接口、VLAN ID、接口 IP 责任可确认；待补 MML、对象顺序、数据规划。 |
| `IPFD-011001` | `UNC@FeatureTask@IPFD-011001`（draft） | 静态 ARP 与路由式代理责任可确认；待补 MML、IP/MAC/VLAN/出接口实例及顺序。 |
| `IPFD-012003` | `UNC@FeatureTask@IPFD-012003`（draft） | BFD 会话与路由/协议绑定责任可确认；待补 MML、会话/绑定对象顺序和参数实例。 |

四项均通过独立审查 `CRITICAL=0 / HIGH=0`；未新建 CT、未引 AtomTask，信息不足段已明确标注“未编排”。
