# UNC-A2：路由、GRE、IPSec 交接

> 执行日期：2026-08-11  
> 批次状态：**已完成（BGP、GRE、IPSec 正常构建并集成；OSPF、静态路由已按信息受限规则构建为 draft）**。

## 输入与准入记录

按 SOP，五项均先读取完整 Feature 文档簇；配置类命令逐条读取 AtomTask，先读 `_index.md` 再读取候选 CT。未使用原始产品文档例外回查。

| Feature | 完整 Feature 输入与命令结论 | Atom / CT 准入 | 结果 |
|---|---|---|---|
| `IPFD-014001` OSPF | 读取完整 29 篇簇；OSPF/OSPFv3、认证、BFD、FRR、GR/NSR 等责任可确认，但无实际 MML/实例 | 无可恢复命令链，不建 CT | **信息受限 draft FT 已建**；待补 MML、对象顺序、数据规划。 |
| `IPFD-014002` BGP | 读取 22 篇。唯一可恢复命令在 `BGP负载分担`：VPN CE 双归属、同/异 AS 混合路径用 `ADD BGPVRFAF.EIBGPLOADBALANCE` 指定最大混合分担数；其余均无可恢复 MML 时间线。 | `ADD BGPVRFAF` Atom 存在；Feature 未给 `AFTYPE`、`VRFNAME`、`EIBGPLOADBALANCE` 实值，标数据规划待补。所有 CT 与该单 Atom 交集为 0，且单一 Atom 不建 CT。 | **draft FT**：`UNC@FeatureTask@IPFD-014002.md`，直接引用 Atom。 |
| `IPFD-014003` 静态路由 | 仅 `概述.md`；静态/缺省路由、BFD、FRR、迭代责任可确认，但无 MML/实例 | 无可恢复命令链，不建 CT | **信息受限 draft FT 已建**；待补 MML、对象顺序、数据规划。 |
| `IPFD-015002` GRE | 读取 7 篇：概述、激活、去激活、多租户、Keepalive、报文格式、调测。完整还原 IPv4 本端/对端骨架、创建时或创建后增强、MTU、删除与多租户语义。 | 核验 `ADD INTERFACE`、`ADD IFIPV4ADDRESS`、`ADD GRETUNNEL`、`ADD SRROUTE`、`MOD GRETUNNEL`、`MOD INTERFACE`、`RMV GRETUNNEL`。创建骨架与现有 `unc-gre-tunnel-family` 目标/顺序同义，重构后复用；增强、MTU、删除由 FT 直引。 | **重构 FT + CT**：仅保留经 Feature 脚本证实的 IPv4 流程；IPv6 数据表项明确“Atom 可解释但无时间线，未编排”。 |
| `IPFD-016000` IPSec | 读取完整 24 篇；40 条真实配置命令、普通/国密、IPv4/IPv6、主备、多 Sequence、GRE/OSPF、证书链均可恢复 | 复用并更新 `unc-ipsec-suite` | **FT + CT 已建并集成**；`ADD CERTSCENE` 时序冲突已显式待 Atom 更正。 |

## 本批落盘与复核

- 新建：[`UNC@FeatureTask@IPFD-014002.md`](../../../三层图谱资产/FeatureTask/UNC/20.15.2/UNC@FeatureTask@IPFD-014002.md)。独立审查先发现 Atom 默认 `_public_` 被误作 Feature 候选和“主要用于”被写成排他限制；已修复，复审 `Critical=0 / High=0`。
- 重构：[ `UNC@FeatureTask@IPFD-015002.md`](../../../三层图谱资产/FeatureTask/UNC/20.15.2/UNC@FeatureTask@IPFD-015002.md) 与 [`UNC@CompoundTask@unc-gre-tunnel-family.md`](../../../三层图谱资产/CompoundTask/UNC/20.15.2/UNC@CompoundTask@unc-gre-tunnel-family.md)。独立审查两轮完成：首轮 2 Critical/3 High，已补齐双端脚本、IPv6 数据表“未编排”、内联/后置增强双走法、`IFMTU` 与完整公式；复审 `Critical=0 / High=0`。
- 共享反链：清除 `unc-apn-access-infra`、`unc-downlink-route-export` 对已撤回 `IPFD-015002/IPFD-016000` 的过期反链，清除 `unc-ipsec-suite` 对已撤回 IPSec FT 的过期反链。
- 唯一集成者重生 `CompoundTask/UNC/20.15.2/_index.md`；当前为 38 个 CT、203 条 `command_set` 条目。`audit_compound_feature.py --nf UNC --version 20.15.2` 结果为 **0 fail**。

## 历史输入缺口与后续入口（IPSec 已解除；OSPF/静态路由后续已信息受限落盘）

1. `IPFD-014001`：待补 OSPF/OSPFv3 的激活或部署流程、实际 MML、参数/数据规划、对象顺序，以便把当前信息受限 FT 升级为可执行编排。
2. `IPFD-014003`：待补静态路由和 BFD 绑定的 MML、数据规划、命令顺序与 Atom 对应关系，以便升级当前信息受限 FT。
3. `IPFD-016000`：本条为历史结论，已解除；`MOD IKEPEER` 是原理引用，`SET PKICRLCHECK` 已有 AtomTask，IPSec FT/CT 已完成独立审查与集成。

## 可继续的批次

按 `UNC领域批次构建计划.md`，下一业务批为 `UNC-A3`：`NPFD-010005`、`NPFD-010013`、`NPFD-010014`。启动前仍应按计划 §5.2 全文准入，不能因 A2 的阻塞结论外推。

---

## 2026-08-11 补建准入记录：IPFD-016000（IPSec）

> 本记录在改写任何 Task 前完成。它取代上文该 Feature 的“blocked”结论；其余 A2 Feature 的状态不变。

### 已读取输入

- Feature 完整簇 24 篇：`概述.md`、`AH和ESP.md`、`IKE.md`、`IPsec NAT穿越.md`、`IPsec可靠性.md`、`安全联盟（SA）.md`、`报文封装模式.md`、`相关术语.md`、`调测IPsec功能.md`、`上传IPsec证书.md`、`上传国密IPsec证书.md`，以及普通 IPsec 的 IPv4/IPv6/指定本端接口/多 Sequence/GRE over/IPv4 主备/IPv6 主备/OSPF over 8 篇和国密 IKEv1 的 IPv4/IPv6/指定本端接口/多 Sequence/GRE over 5 篇激活文档。
- 从操作步骤、数据规划和任务脚本抽取 40 条配置类命令；`DSP PKICERTLIST` 等调测查询已剥离。`MOD IKEPEER` 仅见 `IKE.md` 原理引用，不是本特性的配置实例，未纳入命令闭包。
- 已逐条读取并核对 40 个同 NF AtomTask：`ADD ACLGROUP{,6}IPSEC`、`ADD ACLRULEADV{4,6}IPSEC`、`ADD ATTACHIKEPEER`、`ADD CERTSCENE`、`ADD GRETUNNEL`、`ADD IFIPV{4,6}ADDRESS{,IPSEC}`、`ADD IKEPEER{,6}`、`ADD IKEPROPOSAL`、`ADD INTERFACE{,IPSEC}`、`ADD IPBINDVPN{,IPSEC}`、`ADD IPSECINTFCFG{,IPSEC}`、`ADD IPSECPOLICY{,6}`、`ADD IPSECPROPOSALIPSEC`、`ADD L3VPNINST{,IPSEC}`、`ADD OSPF`、`ADD OSPFAREA`、`ADD OSPFIMPORTROUTE`、`ADD OSPFNETWORK`、`ADD PROPATTACHIPSECPROPOSAL`、`ADD SRROUTE{,6}`、`ADD VPNINSTAF{,IPSEC}`、`MOD INTERFACE`、`SET FWSOFTPARA`、`SET IFIPV6ENABLE{,IPSEC}`、`SET IKEGLOBALCONFIG`、`SET PKICRLCHECK`。40/40 文件存在；IPv4/IPv6、PSK/数字信封、主备优先级、多 Sequence、指定源接口、IPv6 开关、国密软参和 CRL 开关的实例值均在对应 AtomTask 配置方法中有允许维度，结论为 **ready**。
- 已读取 `_index.md` 与 `unc-ipsec-suite` 全文。旧 `unc-ipsec-suite` 的 command_set 与本簇 40 命令交集为 31，Jaccard=`31/40=0.775`；同为“VNRS/IPsec 双配 + 流量选择 + IKE/IPsec 协商并应用策略”的目标和顺序，满足相位同义。因此复用并重写该网络/隧道所有权 CT，不新建平行 CT。

### 场景与参数准入

| 场景族 | Feature 实例的关键差异 | Atom 核对 |
|---|---|---|
| 普通 IPv4 / IPv6 | `AFTYPE=ipv4uni/ipv6uni`、`TNLTYPE=IPSEC/IPSEC6`、IPv4/IPv6 ACL、Peer、Policy 与 Route 对版 | 通过 |
| 主备 | `WORKMODE=Master_standby`、两 Peer 以 `PEERPRIORITY=1/2` 绑定；IPv6 同样保留双 next hop | 通过 |
| 多 Sequence | 同 `POLICYNAME` 下 `SEQUENCENUMBER=10/20`，每个 sequence 各有 ACL、Proposal 绑定及 Peer 绑定 | 通过 |
| 指定本端接口 | `SRCIFNAME=LoopBack1`；LoopBack 与 Tunnel 在 VNRS/IPsec 双侧均配置 | 通过 |
| GRE / OSPF over | `ADD GRETUNNEL` 或 OSPF 四命令在 IPSec 基线之后进入相应相位 | 通过 |
| 国密 IKEv1 | `SET FWSOFTPARA:DWORDINDEX=1401,DWORDVALUE=1`；`AUTHMETHOD=Digital_envelope`、`ENCRALGORITHM=Sm4`、`INTEGALGORITHM=Sm3`、`ASYMENCRALG=Sm2`、`VERSION2=FALSE` 与签名/加密证书文件 | 通过 |
| 证书 / CRL | `ADD CERTSCENE` 的 CA/LOCAL 与 `CERTTYPE=Cert_sig/Cert_enc`；有 CRL 时 `SET PKICRLCHECK:ISCRLENABLE=TRUE` | 通过 |

### 信息源例外与结论

- 未读取原始产品文档；Feature 文档簇已给出每个场景的步骤、脚本、对象、顺序和参数。
- 结论：`IPFD-016000` **ready**，可改写 `UNC@FeatureTask@IPFD-016000` 并回填 `UNC@CompoundTask@unc-ipsec-suite`。不重生 `_index.md`。

### 本次落盘与构建者自检

- 新建 `三层图谱资产/FeatureTask/UNC/20.15.2/UNC@FeatureTask@IPFD-016000.md`；改写网络/隧道所有权 CT `三层图谱资产/CompoundTask/UNC/20.15.2/UNC@CompoundTask@unc-ipsec-suite.md`。未修改 `_index.md` 或其他 CT。
- 命令闭包：Feature 真实配置集 40 条 = CT 的 38 条网络/隧道/协商命令 + FT 直引的 `SET PKICRLCHECK`、`ADD CERTSCENE`，自检 `40/40`；`MOD IKEPEER` 未纳入，因为它只在原理页出现。
- 参数闭包：普通 IPv4 基线脚本在 CT 固化；其余 12 个普通/国密场景分别在 CT 与 FT 的逐场景表回填地址族、Tunnel/LoopBack、认证/算法、IPv6 enable、主备优先级、多 Sequence、GRE/OSPF、DPD/NAT 和证书/CRL差异。未虚构 Feature 未给出的 MML 参数。
- 时序闭包：CT 记录“VNRS → VNRS 路由 → IPSec 双配 → ACL → Proposal/Peer → Policy 绑定/应用 → IPv6/DPD/国密/GRE/OSPF 扩展”；GRE 和 OSPF 均明确后置，国密软参在 IKE Proposal 前，证书场景在数字信封 Peer 前。
- 结构审计：`python task/scripts/audit_compound_feature.py --nf UNC --version 20.15.2` = `fail 0`。尚待独立审查；按 SOP 审查前不得重生 `_index.md`。

### 独立审查首轮返修（IPFD-016000）

- 已在 FT/`unc-ipsec-suite` 的 IPv4 主备、多 Sequence、GRE over、OSPF over 四行补入实际 `SET IKEGLOBALCONFIG`。主备为策略应用紧后；多 Sequence、GRE、OSPF 明确为策略应用后、Feature 后续静态路由前。GRE Tunnel 的原脚本位置未被重排。
- FT 证书走法改为：可选 CRL 开关 → Portal 上传证书/CRL → 创建场景 → Portal 关联；普通为 `1 CA + 1 LOCAL`，国密为 `1 CA + 2 LOCAL(Cert_sig/Cert_enc)`。`ADD CERTSCENE` 参数核对已标 **冲突／待 Atom 更正**，不以 Atom 中的“先建场景”表述覆盖 Feature 时序。
- 参数核对改为逐命令 40 行：CT 的 38 条 `command_set` 命令和 FT 直引的 2 条 Atom 均有实际参数和值、对象/场景及核对结论；唯一冲突为上述 `ADD CERTSCENE` 时序。
- 返修后结构审计仍为 `fail 0`；未修改 AtomTask 或 `_index.md`，等待独立复审。

### 最终独立复审与集成

- 复审先发现 GRE 场景与 CT 通用步骤位置矛盾：实际 `ADD GRETUNNEL`/`LoopBack1` 属 VNRS 初始对象链，可在 IPSec 策略前创建；`SET IKEGLOBALCONFIG` 在策略后、后续 `ADD SRROUTE` 前。已修正，聚焦复审 `CRITICAL=0 / HIGH=0`。
- 唯一集成者随后重生 `_index.md`；当前 42 个 CT、233 条 `command_set` 条目。`audit_compound_feature.py` 为 `fail=0`，Feature→Atom 强证据门禁 `952/952`、缺口 0。
- `IPFD-016000` 不再列入阻塞清单；仍待外部澄清的 `ADD CERTSCENE` Atom 时序冲突已在 FT 参数核对中保留，不影响 Feature 按原始文档时间线表达。

### 信息受限规则后的补建

用户确认：有独立配置责任但无可恢复 MML/激活案例/参数实例的 Feature 仍须落盘为信息受限 `draft` FT。原“OSPF、静态路由 blocked”已由下列当前结论取代：

| Feature | 当前产物 | 未编排原因与待补输入 |
|---|---|---|
| `IPFD-014001` | `UNC@FeatureTask@IPFD-014001`（draft） | 29 篇簇确认 OSPFv2/v3、区域、认证、BFD、FRR、GR/NSR、VPN/BGP 联动责任；待补 MML、对象顺序、参数/数据规划实例。 |
| `IPFD-014003` | `UNC@FeatureTask@IPFD-014003`（draft） | 静态/缺省路由、优先级、BFD、FRR、迭代责任可确认；待补 MML、对象顺序及参数实例。 |

两项均通过独立审查 `CRITICAL=0 / HIGH=0`；未新建 CT、未引 AtomTask，流程/激活差异/参数核对均明确“信息不足，未编排”。
