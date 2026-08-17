# UDG 4.3 FeatureTask + CompoundTask 构建 · 交接

> **历史化标注（v0.17.0）**：本页为历史交接记录（进度/教训），**不作规范引用源**；规范疑问查 `task/SKILL.md`（Task 层唯一权威）。
> 接手 Agent 读此页 + 文中引用的 SOP/资产即可继续。最后更新：2026-08-04（**含集成闭环**）。
> 已覆盖：**§4.3 全域（IP/平台/可靠性）完整 Task 化** + 4.1 的 **010-A**（跨域）+ **集成闭环**（gen_index + audit D0-D4 全过 fail=0）。47 FT + 5 CT + 5 atom。
> 本轨与 4.1 轨（`UDG-4.1-交接.md`）并行：4.1 轨做 020-C/D/E/F + 010-B/C/D；本轨做 4.3 全量 + 010-A。**010-A 由本轨建**（4.1 轨原标 BLOCKED，本轨已建，见 §4/§6 坑3）。

---

## 0. 一句话现状

4.3（IP/平台/可靠性，IPFD/NPFD/SFFD，~50 Feature）**全部 Task 化完成**：47 个 FeatureTask（磁盘实测 **8 config + 39 foundation**——IPFD-015002 GRE / IPFD-015004 IPSec 亦为 config draft 原 §3 roster 漏登，IPFD-012003 BFD 实为 foundation；见 [CR-20260807-001](../change-requests/CR-20260807-001-Task层信息可追溯性与SOP权威统一.md) T1 对账）+ 5 个 CompoundTask（4 新 + 1 跨域）+ 5 个补建 AtomTask。**关键发现：UDG 的 IPFD 特性簇几乎全是原理/概述（OSPF 29 篇、BGP 23 篇全原理），真配置只在 GWFD 部署特性/既有 CT**——故 4.3 的 foundation 占比极高（40/47），真配置仅 7 个（IP-1 QoS/ACL/BFD、NTP、SFFD-010030/010031/010008）。**集成已完成**（2026-08-04：gen_compound_index 重生 _index 42→44 CT + audit_compound_feature D0-D4 fail=0；集成修 9 处反链/断链，见 §7 A）。仅剩 atom 层遗留（非阻塞，转 atom 轨，见 §6 坑5）。构建→子 Agent 对抗评审→修循环稳态（9 批连审 0C/0H）。

---

## 1. 任务与角色

- **任务**：把 4.3 节 Feature 的"配置方法"沉淀成 Task 层资产（FeatureTask + CompoundTask），遵循新格式（基准 `GWFD-110201`，同 4.1/4.2）。
- **角色边界**：本轨做 **构建 + 自检 + 子 Agent 对抗评审 + 修 CRITICAL/HIGH**（循环同 4.1 §5.9）。**仅"集成"分离**——不重生 `_index.md`、不跑 `audit_compound_feature.py`（本机 git-bash 无 python）。
- **构建单元 = 一个 Feature 的完整 pass**：同 pass 产 1 FT + 0~N CT。
- **所有权**：4.3 涉及 IP/平台/可靠性域，归本轨；可直改相关既有 CT（如 `downlink-route-export`、`ipv6-bearer-ospfv3-wlr` 已被 GWFD 部署特性复用，本轨未改）。**010-A 跨入 4.1 域**——已与 4.1 轨协调（见 §4/§6 坑3）。

---

## 2. 权威 SOP（按此顺序读，路径相对仓库根）

| 优先级 | 文件 | 用途 |
|---|---|---|
| 1 | `三层图谱构建规范/task/UDG特性与步骤Task构建提示词.md` | 构建提示词 + **对抗评审提示词**（末尾）|
| 2 | `三层图谱构建规范/task/UDG领域批次构建计划.md` | §4.3 批次地图、并行写入规则、集成闭环 |
| 3 | `三层图谱构建规范/task/SKILL.md` | Part B（§B.3 流程/§B.4 复用/§B.5 迭代硬规则/§B.6 foundation）/ §A（atom 构建，补建 atom 时读）|
| 4 | `三层图谱构建规范/task/字段定义.md` | YAML 8 字段 |
| 5 | `三层图谱构建规范/task/check.md` | 审查项 + D0-D4 盲区 |
| 6 | `三层图谱构建规范/task/template/{feature_task,compound,atom}.md.tpl` | 正文骨架 |
| 7 | `三层图谱构建规范/task/handoff/UDG-4.1-交接.md` | **姊妹轨**，构建规则 §5.1-5.10 + 教训（与本轨一致，互补）|

**格式基准样例**：`UDG@FeatureTask@GWFD-110201.md`（新格式）；**foundation 样例**：`UDG@FeatureTask@IPFD-014001.md`（OSPF foundation，本轨校准）；**config 样例**：`UDG@FeatureTask@IPFD-012001.md`（QoS，含 CT+参数核对+冲突标注）。
**CT 样例**：`UDG@CompoundTask@gtp-pfcp-path-mgmt.md`（3 全局 SET 按网络制式取子集）、`pod-self-heal-setup.md`（3 atom Pod 自愈）。

**记忆（`~/.claude/.../memory/`）**：`udg-43-ip1-batch-status.md`（本轨进度，本交接为权威源后可精简）、`glob-tool-unreliable-use-grep.md`、`sed-not-perl-for-at-strings.md`（本轨新增，见 §6 坑4）。

---

## 3. 已完成产物清单（47 FT + 5 CT + 5 atom）

### config FeatureTask（7 个，有配置流程+参数核对）
```
UDG@FeatureTask@IPFD-012001.md      # QoS 简单/复杂流分类 + DSCP映射（3 SET族 + ACL）
UDG@FeatureTask@IPFD-012002.md      # ACL/ACL6 规则组+规则
UDG@FeatureTask@IPFD-012003.md      # BFD（foundation，但归此处：原理-only，无配置流程）
UDG@FeatureTask@NPFD-010014.md      # NTP（单命令 ADD NTPSVR）
UDG@FeatureTask@SFFD-010030.md      # 业务节点故障管理 HA+ETCD（SET ELECTSERVICE+BASESUBHEALTH）
UDG@FeatureTask@SFFD-010031.md      # 微服务多级自愈 Pod→Node
UDG@FeatureTask@SFFD-010008.md      # 通信亚健康自愈 Fabric/Base（doc_type 误标"其它"实为真配置）
```
> 012003 实为 foundation（BFD 簇纯原理，配置在 OSPF/BGP/静态路由特性内）。列此处的 6 个是有真配置流程的。

### foundation FeatureTask（40 个）
```
IPFD-014001(OSPF)/014002(BGP)/010001(接口)/010002(VLAN)/011001(ARP)/014003(静态路由)/014004(直连路由)  # IP-2/3/4，7个
NPFD-010004(自动化配置)/010005(配置管理)  # doc_type 误标"配置"实为原理/元能力，2个
NPFD-010001/002/003/006/007/008/009/010/011/013/017/018  # 性能/软件/故障/安全/日志/帮助/补丁/在线加载/远程维护/跟踪/SSH/可靠性，12个
SFFD-010004/005/009/010/011/013/014/015/022/029/032/033/034/035/036/042/043  # VNF扩缩容/可靠性保障/负载均衡/虚机容器/IPv6组网/本地存储等，17个
IPFD-012003(BFD)  # 见上
GWFD-010103(数据转发)  # 010-A 跨域，概述明示"无需配置即可使用"
```
> IPFD-011000（IP协议栈基本功能）为空壳（仅标题+"边（暂无）"），**不建 FT**。

### CompoundTask（5 个：4 新 + 1 跨域）
```
UDG@CompoundTask@qos-simple-classify.md           # IP-1：DS域+BA/PHB映射+接口绑定（4 cmd）
UDG@CompoundTask@qos-mqc-complex-flow-policy.md   # IP-1：MQC 流策略组装+应用（8 cmd）
UDG@CompoundTask@acl-rule-chain.md                # IP-1：ACL规则组+规则 IPv4/IPv6（6 cmd）
UDG@CompoundTask@pod-self-heal-setup.md           # SFFD-010031：Pod自愈策略+黑名单+开关（3 cmd）
UDG@CompoundTask@gtp-pfcp-path-mgmt.md            # 010-A：GTP/PFCP路径探测参数（3 全局 SET）
```

### AtomTask（5 个补建，解锁 SFFD-010030/010031）
```
UDG@AtomTask@SET ELECTSERVICE.md / SET BASESUBHEALTH.md   # SFFD-010030
UDG@AtomTask@SET PODHEALPLY.md / ADD PODBLACKLIST.md / SET PODHEALCTRL.md  # SFFD-010031
```

### 修改既有资产
- `qos-simple-classify.md` 被用户/linter 回填了 GWFD-010201 场景差异行（被引用于 +1）——本轨未改，尊重该编辑。
- 其余既有 CT 未改（4.3 foundation 多为底座，复用既有 CT 的少）。

---

## 4. 4.3 进度地图

| 批次 | Feature | 状态 | 备注 |
|---|---|---|---|
| **IP-1** | 012001/012002/012003 | ✅ | 012001/012002 config（3 CT）；012003 foundation（BFD）|
| **IP-2** | 014001 OSPF | ✅ foundation | 簇全原理，配置在 downlink-route-export 等既有 CT |
| **IP-3** | 014002 BGP | ✅ foundation | 簇全原理，配置待 GWFD-020423 等部署特性 |
| **IP-4** | 010001/010002/011001/014003/014004（+011000 跳过）| ✅ foundation | 接口/VLAN/ARP/静态路由/直连路由，全原理 |
| **OPS-1** | NPFD-010014 | ✅ config | NTP 单命令 |
| | NPFD-010004/010005 | ✅ foundation | doc_type"配置"实为原理/元能力 |
| | NPFD-010001~018（余 12）| ✅ foundation | 性能/软件/故障/安全/日志/帮助/补丁/在线加载/远程维护/跟踪/SSH/可靠性 |
| **OPS-2** | SFFD-010030/010031/010008 | ✅ config | 故障管理/微服务自愈/亚健康自愈（补 5 atom）|
| | SFFD-010004~043（余 17）| ✅ foundation | VNF扩缩容/可靠性保障/负载均衡/虚机容器/IPv6组网/本地存储等 |
| **010-A（跨 4.1 域）** | 010102/010103 | ✅ | 010102 config（路径探测+黑白名单+修改重发）+ 010103 foundation。010102 由本轨建，4.1 轨后续补审增强（+修改Echo重发场景）；PATHDWNALMSEG 经 4.1 补审判定为非阻塞（参考信息列名，非配置流程）。见 §6 坑3 |

**汇总**：4.3 全部 Task 化（47 FT + 5 CT + 5 atom）+ 集成闭环（D0-D4 fail=0）+ atom 参数核对收尾（3 薄 atom 补全 + 2 待核命令层确认），9 批连审 CRITICAL/HIGH=0。仅剩 atom 轨建议性补全（SET QOSBA/MOD MQCPOLICY 字典枚举 + SET BGP STALE 标签，非阻塞）。

---

## 5. 构建规则（本轨执行约定，与 4.1 轨一致 + 4.3 特化）

### 5.1-5.8 通用规则
同 `UDG-4.1-交接.md` §5.1-5.8（YAML 骨架、CT 抽取阈值 ≥3 distinct、激活表 7 列只写实演、时序不可泛化、参数合法性逐项核 atom、反链卫生 D3、调测剥离、跨特性依赖链接）。**接手必读 4.1 §5**，此处不重复。

### 5.9 构建→子 Agent 对抗评审→修循环（每批必走）
同 4.1 §5.9。本轨 9 批全走：IP-1/IP-2/IP-3/IP-4/OPS-NPFD/SFFD-config/SFFD-010008/foundation-29/010-A + IP-4 HIGH 复审。**foundation 批可轻审**（重点验 foundation 真实性 = 全簇 Grep `UDG@MMLCommand@` 零命中 + 概述"无需配置"明示）；config 批必全审（参数核对 + 反链 + 调测剥离）。

### 5.10 4.3 特化经验（本轨真实案例）
- **doc_type 标签不可信，读内容**：NPFD-010004/010005 doc_type="配置" 实为原理/元能力（无 MML）→ foundation；SFFD-010008 doc_type="其它" 实为真配置（有操作场景/数据/脚本）→ config。**判定看簇内有无「操作步骤+数据规划+任务脚本」，不看 doc_type**。
- **IPFD 特性几乎全 foundation**：OSPF(29md)/BGP(23md) 看似"重型配置"，实际簇内全原理，真配置在 GWFD 部署特性/既有 CT。别被 md 数量误导。
- **SFFD 全域需 License**：20 个 SFFD 特性都需 Service Fabric 虚 CPU License（`[[UDG@License@LKV6SFVCPU01]]`，控制项 82206513），FT 约束标"需 License"。NPFD/IPFD 多"无需 License"。**别一刀切"无需"**（本轨曾因此触发 HIGH，17 文件批量改）。
- **foundation FT 形状**：`status: foundation` + 配置概览说明"无独立配置/机制说明" + 不建配置流程/激活表(可放简表)/参数核对 + 边只对应特性（无 atom 时编排边可省，仅留对应特性；纯平台机制无 atom 不要虚构）。样例 `IPFD-014001`。
- **参数核对抓真冲突**：IP-1 抓到 `SET QOSBA:BATYPE=ip_dscp` vs atom `DSCP/8021p`（待核命令层）、`MOD MQCPOLICY:STCENABLE` 数据规划值`5`vs脚本`enable`（笔误）。冲突标"待 Atom 更正/待数据规划补齐"，**不写"通过"**。
- **CT 抽取边界**：3 个并行全局唯一 SET（不同对象） borderline——本轨 gtp-pfcp-path-mgmt 抽了 CT（按网络制式取子集，族通用模式）；若 3 SET 完全独立无共享语义可不抽。配置语义判定优先于 Jaccard。
- **补建 atom 走 Part A**：命令层 md 存在 + atom 缺 → 读命令层 md 理解 → 写 atom（配置方法字典+DP+约束+对应命令边）。本轨补 5 个 SFFD atom 解锁 2 特性。

---

## 6. 已知坑 / 待办（重点）

1. **Glob 不可靠→用 Grep/Bash**（同 4.1 坑1）。文件存在性/目录枚举/`doc_type` 普查一律 Bash `grep`/`ls`，**勿用 Glob**（含 `glob` 参数大括号 `{a,b}` 也失效，假阴性）。

2. **含 `@` 的批量替换用 sed，勿用 perl**（本轨新增教训）：`perl -i -pe "s|...|...$NEW|"` 把替换串里 `@License@LKV6SFVCPU01` 当**数组插值**吞掉，`[[UDG@License@LKV6SFVCPU01]]` → `[[UDG]]`（断链）。本轨曾打断 17 文件，事后 sed 修正。**一律 `sed -i 's|old|new|g'`**（sed 不插值）；改完 `grep -lF '断链特征'` 验证。

3. ~~**010102 漏 ADD PATHDWNALMSEG**~~ → **已澄清为非阻塞（4.1 轨补审 2026-08-04）**：4.1 轨补审 010-A 后判定 PATHDWNALMSEG **非配置流程**——该命令仅在「路径管理参考信息」相关命令清单出现，不在任何配置/激活脚本（可选告警段配置），atom 未建；010102 FT 正确未引，非阻塞。本轨原"未覆盖待补"措辞过度谨慎。**另**：4.1 轨补审给 010102 补了"修改Echo重发参数"运维场景（C1：步骤 3+激活表+参数核对+DP3+CT 场景差异），本轨原建版本已被增强。010-A 状态：BLOCKED → **✅ 完成**。

4. ~~**bash 无 python**~~ → **已解锁（2026-08-04）**：git-bash 现可用 `python`（3.12.7）。`gen_compound_index.py`/`audit_compound_feature.py`/`audit_atoms.py` 均已跑通。集成不再阻塞。

5. **atom 层遗留（非 FT 缺陷，影响 D5/参数核对）**：
   - `SET BGP` atom 把已存在的 `ADD BGPVRF` 误标"★R1.5 待补"（STALE 标签，交 atom 维护者清理）。
   - ~~4 个薄 atom 字典待补~~ → **3 已补全（2026-08-04）**：`SET FABRICSUBHEALTHY`/`SET COMBASEHEALTH`/`SET NODEREPSWITCH` 补全配置维度字典（Part-A，命令层枚举核对）；`SET NODEHEALCTRL` 实际已列全 9 开关（无需补）。SFFD-010008/010031 对应参数核对行已改"通过（atom 已补全）"。
   - ~~`SET QOSBA BATYPE=ip_dscp` 待核~~ → **命令层确认合法**：BATYPE 枚举 `8021p/ip_dscp/mpls_exp`，Feature `ip_dscp` 合法；atom 字典 `DSCP` 为 `ip_dscp` 简写（非冲突，建议 atom 轨补全枚举）。IPFD-012001 已改"通过"。
   - ~~`MOD MQCPOLICY STCENABLE` 字典缺~~ → **命令层确认合法**：STCENABLE 可选枚举 `enable/disable`，Feature 脚本值 `enable` 合法；数据规划表值 `5` 非法确认笔误。atom 字典薄（仅 POLICYNAME），待 atom 轨补。IPFD-012001 已改"通过"。
   - `apn-access-infra` CT 的 YAML `command_set` 仅 `[SET LICENSESWITCH]`，正文实际含更多命令（历史遗留，IP-4 复审 LOW）。

6. **foundation FT 的 audit 盲区**：`audit_compound_feature.py` 可能对 foundation FT 报"缺配置流程"——check.md 仅对 foundation **CT** 的 command_set 豁免，未对 FT 豁免。非缺陷（同 4.1 坑4）。

7. ~~**`_index.md` 未重生**~~ → **已重生（2026-08-04）**：5 个新 CT 全入 `_index.md`（compound_count 42→44），被引用于 reflective 重算刷新（`qos-simple-classify` 被引用数 1→2，+GWFD-010201）。

8. **qos-simple-classify 被引用于含 GWFD-010201**（用户/linter 回填）：集成 gen_index 重算"被引用于"应以脚本为准；本轨 FT 编排与 CT 被引用于一致。

---

## 7. 下一步接续点

- **✅ A（集成）已完成（2026-08-04）**：python 3.12.7 在 git-bash 解锁后，跑通全套集成脚本：
  - `gen_compound_index.py`：_index 重生，compound 42→44（+pod-self-heal-setup +gtp-pfcp-path-mgmt），被引用于 reflective 重算。
  - `audit_compound_feature.py`：首轮 fail=9 → **修后 fail=0**（D0-D4 全过，EXIT=0）。集成修 9 处：①D2 我的 IPFD-012001/012002 把"待补 atom"误写成 `[[wikilink]]`（ADD QOSIFPHB/QOSRDRVPN/ACLRULEIF/ACLRULEBAS6，4 处）→ 去 wikilink 裸文本（同 010102 PATHDWNALMSEG 处理模式）；②D3 我的 IPFD-010001/014003 foundation FT 在 prose wikilink 了 gre-/ipsec CT（污染反链，5 处，违反 §5.6）→ 裸文本；③D3 4.1 的 GWFD-010155 line 43「CT 抽取判定」rationale wikilink mpls-vpn-infra/ipv6-bearer-infra（同污染模式）→ 裸文本（集成 Agent 跨批修）。
  - `audit_atoms.py`（ADD/MOD/SET/DEL/RMV/LOD 全扫 431 atom）：97% 合规；**本轨 5 atom 全 0 缺陷**；CRITICAL 5 + HIGH 8 全是既有 atom（IPsec/IKE/URR/PCC/QOSAPPLICATION 联动引用断链或缺 ## 决策点）+ LOW 281 name_zh 对齐 = atom 轨遗留（§6 坑5），非本轨。
  - **结论**：4.3（47FT+5CT+5atom）+ 4.1 已审产出（含 010155）全部正式入索引，跨层反链/断链/结构全清。仅剩 atom 轨遗留（B）。
- **B（atom 层收尾，部分已完成）**：~~4 薄 atom 字典 + SET QOSBA BATYPE + MOD MQCPOLICY STCENABLE~~ → **已闭环（2026-08-04，命令层确认 + 3 atom 补全）**。剩：清 SET BGP atom 的 ADD BGPVRF STALE 标签 + atom 轨补 SET QOSBA/MOD MQCPOLICY 字典枚举（建议性，非阻塞，转 atom 轨）。
- **C（跨域协调）**：与 4.1 轨对齐 010-A 状态（本轨建，PATHDWNALMSEG 待补）；4.1/4.2 剩余批次由各自轨继续。本轨 4.3 已完，不再扩。
- **D（010102 PATHDWNALMSEG）**：若 Feature 层补 PATHDWNALMSEG 配置文档 + atom，回填 010102 FT（当前标"未覆盖待补"）。

> 单 Feature pass 标准动作（同 4.1）：读 Feature 文档簇（激活/配置/数据规划/任务脚本，**别只读概述/参考信息**）→ Bash grep 验每条配置命令的 atom 存在 + 核参数 → 还原命令时间线 → 拆步骤（≥3 抽 CT / 命中既有 CT 复用并双向回填 / 单命令直引 / 无配置→foundation）→ 写 FT(+CT) → 自检 → 子 Agent 对抗评审 → 修 CRITICAL/HIGH=0。

---

## 8. 环境与工具备忘

- 工作目录：`D:\mywork\KnowledgeBase\NewSFCGraph`；网元 UDG，版本 20.15.2。
- 资产路径：Feature=`三层图谱资产/Feature/UDG/20.15.2/UDG@Feature@{code}/*.md`；Atom=`.../AtomTask/UDG/20.15.2/UDG@AtomTask@{CMD}.md`；Compound=`.../CompoundTask/UDG/20.15.2/UDG@CompoundTask@{name}.md` + `_index.md`；FeatureTask=`.../FeatureTask/UDG/20.15.2/UDG@FeatureTask@{code}.md`；Command（命令层）=`.../Command/UDG/20.15.2/UDG@MMLCommand@{CMD}.md`。
- **Glob 不可靠→Bash grep/ls**（§6 坑1）；**含 @ 替换用 sed 勿用 perl**（§6 坑2）；**bash 无 python**→集成脚本另寻环境（§6 坑4）。
- 脚本：`task/scripts/gen_compound_index.py`（重生 _index）、`audit_compound_feature.py`（D0-D4）、`audit_atoms.py`、`collect_command_examples.py`（atom 输入采集）。
- 姊妹交接：`UDG-4.1-交接.md`（4.1 域，构建规则 §5 互补）、4.2 域记忆 `udg-42-featuretask-build-state.md`（格式基准 110201）。
