# UDG 4.1 FeatureTask + CompoundTask 构建 · 交接

> **历史化标注（v0.17.0）**：本页为历史交接记录（进度/教训），**不作规范引用源**；规范疑问查 `task/SKILL.md`（Task 层唯一权威）。本页 §5.x 规则已吸收进 SKILL.md v0.17.0。
> 接手 Agent 读此页 + 文中引用的 SOP/资产即可继续。最后更新：2026-08-04（含 020-C/D/E 补审 + 010-D/010-B/010-C-foundation + 010155 重型独立批）。
> 已覆盖：§4.1 的 020-C/D/E/F + 010-D + 010-B + 010-C **八批**（010155 已完成）。**「构建→子 Agent 对抗评审→修 CRITICAL/HIGH」循环稳态（见 §1/§5.9），21 FT 全过审。**

---

## 0. 一句话现状

4.1 共约 95 Feature 簇，磁盘实测 **94 个 FeatureTask 在盘（42 foundation + 52 draft）**——**Task 层构建 100% 完成**（仅 020155 网管越界 skip）。本构建系列产出 **66 FT + 2 新 CT（ipfarm-pcscf-chain、ipv6-ethsubif-setup）+ 10 既有 CT 回填**；另有 ~28 draft 为早期会话已建。**★ 原"3 BLOCKED（010232/233/020161）"经磁盘复核全错**：均为可建（010232/233 foundation、020161 轻量 draft），批次预检的"缺 atom"是幽灵数据，已补建。**全部 94 FT 过对抗评审（本系列 66 FT CRITICAL/HIGH=0）**。**下一步：集成（python：gen_compound_index 重算被引用于 + audit 脚本）+ atom 轨修缺陷（坑9：SET APNACCESSWAL/SET DEACTIVERATE）**。

> **全量审计（2026-08-07）**：T2 抽样复核 12 FT（8 曾修 + 4 未触）= **0 新缺陷**，既有修复全部 held；详见 [CR-20260807-001](../change-requests/CR-20260807-001-Task层信息可追溯性与SOP权威统一.md)（SOP 升 v0.17.0：B1-B4 闭包审查项 + 单一权威）。

---

## 1. 任务与角色

- **任务**：把 4.1 节 Feature 的"配置方法"沉淀成 Task 层资产（FeatureTask + CompoundTask），遵循新格式（基准 `GWFD-110201`）。
- **角色边界（本会话更新，重要）**：本轨做 **构建 + 自检 + 子 Agent 对抗评审 + 修 CRITICAL/HIGH**（见 §5.9 循环）。**仅"集成"是分离角色**——不重生全局 `_index.md`、不跑 `audit_compound_feature.py`、不替集成签字（需可跑 python 的环境 + 集成 Agent）。
  - 原"独立审查是分离角色"约定**已演进**：本会话起，构建方用 `UDG特性与步骤Task构建提示词.md` 末尾的「对抗评审提示词」**派子 Agent 自审**（general-purpose，1 个/批或并行多批），修到 CRITICAL/HIGH=0 再交付集成。补审证明价值：020-C/020-E 上一手自审过的批次，独立子 Agent 仍抓出 2C+2H / 1C+5H 真问题（臆造变体行、反链漏登、概述矛盾未标）。
- **构建单元 = 一个 Feature 的完整 pass**：同一 pass 内同时产出 1 FT + 0~N CT，不能拆两条流水线。
- **所有权**：4.1 涉及全域（会话/接口/网络/地址/计费）归构建方，可直改相关既有 CT，但每条 CT 同时只能有一个写入者。

---

## 2. 权威 SOP（按此顺序读，路径相对仓库根 `D:\mywork\KnowledgeBase\NewSFCGraph`）

| 优先级 | 文件 | 用途 |
|---|---|---|
| 1 | `三层图谱构建规范/task/UDG特性与步骤Task构建提示词.md` | **构建提示词 + 对抗评审提示词**（最直接，每个 Feature pass 的动作清单） |
| 2 | `三层图谱构建规范/task/UDG领域批次构建计划.md` | §4.1 批次地图、并行写入规则、集成验收闭环 |
| 3 | `三层图谱构建规范/task/SKILL.md` | Part B（compound+feature_task 一并构建）、§B.3 流程、§B.4 复用、§B.5 迭代硬规则 |
| 4 | `三层图谱构建规范/task/字段定义.md` | YAML 8 字段（FT/CT/atom） |
| 5 | `三层图谱构建规范/task/check.md` | 审查项 + 自动化核查（D0-D4）盲区说明 |
| 6 | `三层图谱构建规范/task/template/feature_task.md.tpl`、`compound.md.tpl` | 正文骨架 |
| 7 | `三层图谱构建规范/task/change-requests/CR-20260803-001-跨层核查自动化与check盲区.md` | 上轮闭环：脚本提升 + check 盲区修复历史 |

**记忆（`~/.claude/.../memory/`，背景约定）**：
- `udg-42-featuretask-build-state.md` — 4.2 域约定：**格式基准=GWFD-110201**（不是旧式 110101/010151/020301）、薄 Feature 最小 FT、反链卫生、闭环流程、软参映射。
- `glob-tool-unreliable-use-grep.md` — **Glob 工具在本环境不可靠**，文件存在性/目录枚举一律用 Grep（见 §8）。
- `script-hygiene-generalizable-only.md` — `task/scripts/` 只留可泛化脚本，临时的删；提升走 CR + 升版本。

**格式基准样例**：`三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-110201.md`（新格式，含 `## 激活方法与参数差异` 7 列表 + `## 参数核对`）。
**CT 样例**：`UDG@CompoundTask@charging-core-trio.md`（多族复用、场景差异分族）、`UDG@CompoundTask@ipfarm-pcscf-chain.md`（本轨新建）。

---

## 3. 已完成产物清单

### 新建（68 个文件：2 新 CT + 66 FT，含 39 foundation）
```
三层图谱资产/CompoundTask/UDG/20.15.2/UDG@CompoundTask@ipfarm-pcscf-chain.md   # 020253 用，5 命令
三层图谱资产/CompoundTask/UDG/20.15.2/UDG@CompoundTask@ipv6-ethsubif-setup.md   # 020402 用，6 命令（IPv6 以太网子接口链）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020251.md  # VoLTE基础语音
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020252.md  # SRVCC
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020253.md  # P-CSCF故障恢复
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020254.md  # VoLTE快速恢复
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020281.md  # VoNR
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020282.md  # EPS Fallback
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020304.md  # 关联URL核减
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020307.md  # TCP重传识别
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020308.md  # 7层流量统计
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020352.md  # IPv6 SA（020-F，复用 filter-chain+rule-userprofile-bind）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020356.md  # 计费信息实时提醒（020-F，复用 charging-core-trio+filter-chain+rule-userprofile-bind）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020381.md  # 会话类QoS保证 PGW-U（020-F，无 CT，6 atom 直引）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010201.md  # QoS与流量管理（010-D，复用 qos-simple-classify + QoS CAR 直引）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010191.md  # 移动性管理（010-D，**首个 foundation 骨架**）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010251.md  # 系统过载控制（010-B，4 atom 直引）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010253.md  # 防DDoS（010-B，激活+2维护场景）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010106.md  # 峰值License控制（010-B，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010252.md  # Linux OS安全加固（010-B，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010154.md  # LTE/5G SA 互操作（010-C，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010156.md  # 3GPP 2/3G 接入（010-C，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010155.md  # Untrusted Non-3GPP/ePDG 接入（010-C，4 组网场景，复用 downlink-route-export[场景3]+ipv6-bearer-ospfv3-wlr[场景4]，底链直引 atom，无新 CT）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010222.md  # N6接口（010-F，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010225.md  # SGi接口（010-F，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010228.md  # S1-U接口（010-F，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010231.md  # Gi接口（010-F，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010226.md  # Gn接口（010-G，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010227.md  # Gp接口（010-G，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010229.md  # S5接口（010-G，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010230.md  # S8接口（010-G，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010234.md  # Single IP（010-H，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010235.md  # 缺省承载GBR保障（010-H，foundation，控制面 PCC 触发）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010236.md  # S2b接口（010-H，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010237.md  # S11接口（010-H，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010261.md  # 个人隐私数据保护（010-I，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010262.md  # 密钥安全性管理（010-I，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010281.md  # UDG 实例化（010-J，foundation，VNFM 驱动）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010282.md  # 支持管理面触发的Scale In（010-J，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010283.md  # 支持管理面触发的Scale Out（010-J，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010284.md  # UDG Termination（010-J，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010291.md  # 5G NSA(Opt.3)组网（010-K，foundation，控制面信令）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010221.md  # N3接口（010-E，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010223.md  # N9接口（010-E，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010224.md  # N4接口（010-E，foundation，消息交互条件引他特性白名单命令）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010296.md  # NB-IoT终端标准接入（010-K，单命令 draft SET IOTCAPABILITY:NBIOT=ENABLE）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020151.md  # 支持CUPS架构（020-A，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020152.md  # 支持SSC Mode1（020-A，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020153.md  # 支持SSC Mode2（020-A，foundation）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020404.md  # IPv6在线计费（020-G，foundation，License-gated 能力扩展复用 020300 族）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020405.md  # 逻辑接口支持IPv6（020-G，foundation，License-gated 寻址能力底座）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020481.md  # 软件性能优化（020-I，foundation，构建期能力）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020483.md  # 用户规格提升（020-I，foundation，构建期能力）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020501.md  # 跨域业务访问（020-J，foundation，ULCL 分流信令，互斥多特性）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020502.md  # 跨域用户漫游（020-J，foundation，License-gated ULCL 漫游分流）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020601.md  # 支持QBC计费（020-J，foundation，漫游计费信令）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020422.md  # Direct Tunnel功能（020-H，draft，License 网关 LKV3G5DTTL01）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020451.md  # 端到端用户跟踪（020-I，draft，License 网关 LKV3G5E2ET01）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020101.md  # 支持Reflective QoS（020-A，draft，License 网关 LKV3G5SRQS01）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020154.md  # 用户面负载信息上报（020-A，draft，License LKV3G5UPLR01 + SET PFCPLOADRPT）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020162.md  # 用户面会话过载控制（020-B，draft，SET SESSCHKFUNC 多参，无 License）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020482.md  # 入不转板功能（020-I，draft，SET DATAPLANEINFMODE+ADD LOGICINF+复用 addr-pool-hierarchy/addr-alloc-rule）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020531.md  # 通用DNN漫游分流（020-J，draft，双 UPF SET LICENSESWITCH+SET RTSDNNPARA，与 010155 互斥）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020402.md  # N6/Gi/SGi接口IPv6组网（020-G，draft 重型，License LKV3G5V6NF01 + 新 CT ipv6-ethsubif-setup + PMTU + 可选 SRROUTE6）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020423.md  # 支持路由交叉功能（020-H，draft 重型，12 atom 3 阶段 autoscaling+BGP+VPN RT 交叉，直引不抽 CT）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010232.md  # Sxa接口（010-E，foundation，接口定义；原误判 BLOCKED 已修正）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-010233.md  # Sxb接口（010-E，foundation，接口定义；原误判 BLOCKED 已修正）
三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-020161.md  # CU Full Mesh组网（020-B，轻量 draft SET LICENSESWITCH+SET CPTEIDUALLOC；原误判 BLOCKED 21md 重型 已修正）
```

### 修改既有 CT（3 个，020304 回填：场景差异 + 被引用于）
```
UDG@CompoundTask@filter-chain.md            # +「内容计费 URL 族」020304 行（ISREFEREREN 差异）+ 被引用于
UDG@CompoundTask@userprofile-rule-attach.md # +020304 场景差异行 + 被引用于
UDG@CompoundTask@charging-core-trio.md      # +020304 场景差异行 + 被引用于
```
> 集成时 `gen_compound_index.py` 会重算"被引用于"，手工值应与其一致；若不一致以脚本重算为准。

### 修改既有 CT（020-F 回填：场景差异 + 被引用于）
```
UDG@CompoundTask@filter-chain.md            # +「IPv6 SA 族」020352 行 +「计费提醒族」020356 行 + 被引用于(020352/020356)
UDG@CompoundTask@rule-userprofile-bind.md   # +020352(阻塞动作 PCCPOLICYGRP) + 020356(REFRESHSRV RULE后模板前) 场景差异行 + 被引用于
UDG@CompoundTask@charging-core-trio.md      # +020356(重定向页面计费) 场景差异行 + 被引用于
```
> 020381 未复用任何 CT——license-access-prep 虽 command_set Jaccard=1.0，但相位不同义（USERPROFILE 插在 License 与 APN 间）+ BWM 语义框架不符（LICITEM=LKV3G5TCQS01 ≠ BWM 的 LKV3G5TCSA01）→ 按 §5.4 时序不可泛化，6 命令全部直引 atom。

### 修改既有 CT（010-D 回填：场景差异 + 被引用于）
```
UDG@CompoundTask@qos-simple-classify.md   # +010201（Diff-Serv 双 pass：入口省 QOSPHB/出口省 QOSBA，各 pass 前 SET SRVCOMMONPARA）场景差异行 + 被引用于（IPFD-012001, GWFD-010201）
```
> 010191（foundation）零 CT 复用，无回填。集成时 `_index.md` 待刷新 qos-simple-classify 被引用数 1→2。

### 修改既有 CT（010-C/010155 回填：场景差异 + 被引用于 + 结构自洽修正）
```
UDG@CompoundTask@downlink-route-export.md      # +010155 场景三行（MOD OSPF BFD 增强，注 FT 层叠加非 CT 组成）+ 被引用于；★C1 修：ADD VPNINST 移出 command_set+组成（仅留上游）→ 4 命令与正文一致
UDG@CompoundTask@ipv6-bearer-ospfv3-wlr.md     # +010155 场景四行（BFD/多实例三件套内嵌 ADD OSPFV3 + AREA 相位差）+ 引子跨特性复用注 + 被引用于；★C2 修：ADD L3VPNINST 移出 command_set+组成 + 去冗余上游 atom 行 → 3 命令与正文一致
```
> 010155 底链（L3VPNINST+VPNINSTAF+SET BFD+VPNINST+LOGICINF）直引 atom（既有候选 mpls-vpn-infra/MPLS-RT 语义、ipv6-bearer-infra/License-gated 语义均不符 + VPNINST 相位跨场景变）；静态路由+BFD/缺省路由为 2 命令对 <3 distinct 直引 atom。**无新 CT**。

### 记忆
```
memory/glob-tool-unreliable-use-grep.md（新）+ MEMORY.md 索引（已加 2 行）
```

---

## 4. 4.1 全域进度地图（批次表）

> 判定来源：8 个并行子代理的预检 + 重点项 Grep 复核。**⚠️ READY/FOUNDATION 计数中，FOUNDATION（0 命令）判定是代理给的、未全部 Grep 复核；READY 的逐 atom 就绪性也未全部 Grep 复核——开建每批前必须自己 Grep 验 atom（见 §6 坑2）。**

| 批次 | Feature | 状态 | 备注 |
|---|---|---|---|
| 010-A | 010102, 010103 | ✅ **补审** | 010102 路径管理（draft，复用 gtp-pfcp-path-mgmt + ADD ECHOIPLIST）；**原标 BLOCKED 缺 PATHDWNALMSEG 是误判**——该命令仅"参考信息"列出、不在任何激活脚本，FT 正确未引，010102 非阻塞；补审抓出漏配"修改Echo重发"场景（C1）已补 + CT/参数核对/决策点联动；010103 foundation 干净通过（全簇零 MMLCommand） |
| **010-B** | 010106, 010251, 010252, 010253 | ✅ **完成** | 010251 过载控制（4 atom 直引）；010253 防DDoS（激活+2维护场景）；010106/010252 两 foundation 骨架 |
| **010-C** | 010154, 010155, 010156 | ✅ **完成** | 010154/010156 foundation；**010155 完成**（Untrusted Non-3GPP/ePDG，4 组网场景重型，复用 downlink-route-export[场景3]+ipv6-bearer-ospfv3-wlr[场景4]，底链直引 atom，**无新 CT**；建+子 Agent 审+修 0C/0H 闭环） |
| **010-D** | 010191, 010201 | ✅ **完成** | 010201 QoS（复用 qos-simple-classify 双 pass + QoS CAR 直引）；010191 移动性（**首个 foundation 骨架**，校准形状） |
| **010-E** | 010221,010223,010224,010232,010233 | ✅ **完成** | 5 foundation 全完成（N3/N9/N4 + Sxa/Sxb 接口定义）。**010232/010233 原"BLOCKED 缺 SET UPINITSETUP"是误判**：SET UPINITSETUP 已存在 + 簇内仅行为描述（开工发起方，非必需配置）+ 簇明示"不支持单独配置通过 N4if 配置" → 实为 foundation |
| **010-F** | 010222,010225,010228,010231 | ✅ **完成** | 4 foundation（N6/SGi/S1-U/Gi 接口定义，用户面通道）；建+子 Agent 轻审 0C/0H/0M |
| **010-G** | 010226,010227,010229,010230 | ✅ **完成** | 4 foundation（Gn/Gp/S5/S8 接口定义）；建+轻审 0C/0H/0M |
| **010-H** | 010234~010237 | ✅ **完成** | 4 foundation（Single IP/缺省承载GBR保障/S2b/S11）；建+轻审 0C/0H/0M |
| **010-I** | 010261, 010262 | ✅ **完成** | 2 foundation（个人隐私数据保护/密钥安全性管理）；建+轻审 0C/0H/0M |
| **010-J** | 010281~010284 | ✅ **完成** | 4 foundation（UDG 实例化 / Scale In / Scale Out / Termination，VNFM 驱动的 VNF 生命周期）；建+轻审（簇 Grep 零配置命令 + 概述明示"无需配置即可使用"）0C/0H |
| **010-K** | 010291, 010296 | ✅ **完成** | 010291 foundation（5G NSA Opt.3 组网）；**010296 完成**（NB-IoT 终端标准接入，单命令 draft `SET IOTCAPABILITY:NBIOT=ENABLE`，atom 含典型范式） |
| **020-A** | 020101, 020151~020155 | ✅ **完成** | 020101 Reflective QoS + 020154 负载上报（draft，License 网关型）+ 020151/152/153 foundation；020155 网管越界（跳过） |
| **020-B** | 020161, 020162 | ✅ **完成** | 020162 会话过载控制 + **020161 CU Full Mesh 完成**（轻量 draft：SET LICENSESWITCH LKV3G5CUFM01 + SET CPTEIDUALLOC SWITCH=DISABLE，2 atom）。**原"BLOCKED 21md 重型缺 4 atom"是误判**：激活脚本仅 2 命令，ADD CPASSOCIATION/UPIDOMAIN/SMFFUNC/RESELECTUPCAUSE 是不可靠批次预检的幽灵 atom（020161 参考信息未列） |
| **020-C** | 020251~020254 | ✅ **完成** | +新 CT `ipfarm-pcscf-chain` |
| **020-D** | 020281, 020282 | ✅ **完成** | License 网关型 |
| **020-E** | 020304, 020307, 020308 | ✅ **完成** | 020304 复用 3 既有 CT；回填 |
| **020-F** | 020352, 020356, 020381 | ✅ **完成** | 020352 IPv6 SA（filter-chain IPv6子集+rule-userprofile-bind）；020356 计费提醒（charging-core-trio+filter-chain+rule-userprofile-bind）；020381 会话QoS（无 CT，6 atom 直引） |
| **020-G** | 020402, 020404, 020405 | ✅ **完成** | 020404/020405 foundation + **020402 完成**（N6/Gi/SGi IPv6 组网重型，License LKV3G5V6NF01 + 新 CT `ipv6-ethsubif-setup`（6 atom 子接口链）+ PMTU + 可选 SRROUTE6；建+审 0C/0H） |
| **020-H** | 020422, 020423 | ✅ **完成** | 020422 Direct Tunnel + **020423 完成**（路由交叉重型，12 atom 3 阶段直引：autoscaling 服务链+BFD 二选一+BGP+VPN RT 交叉；不抽 CT 因分支+特性化；建+审+修 0C/0H，修 1C/3H/1M：补 IPALLOCTYPE4/VPNNAME 数据表-脚本矛盾标注/BFDENABLE 枚举冲突/autoscaling 三命令前置开关约束） |
| **020-I** | 020451, 020481~020483 | ✅ **完成** | 020451 端到端跟踪（License 网关）+ 020481/020483 foundation + **020482 入不转板完成**（draft，SET DATAPLANEINFMODE+ADD LOGICINF+复用 addr-pool-hierarchy/addr-alloc-rule，建+审+修 0C/0H） |
| **020-J** | 020501,020502,020531,020601 | ✅ **完成** | 020501/020502/020601 foundation + **020531 通用DNN漫游分流完成**（draft，双 UPF SET LICENSESWITCH+SET RTSDNNPARA，与 010155 互斥；建+审+修 0C/0H） |

**汇总**（基于磁盘实测 2026-08-06）：4.1 域 **95 个 Feature 簇，94 个 FT 在盘**（42 foundation + 52 draft）。本构建系列产出 **66 FT（含本轮补建 010232 Sxa/010233 Sxb foundation + 020161 CU FullMesh 轻量 draft）+ 2 新 CT（ipfarm-pcscf-chain、ipv6-ethsubif-setup）+ 10 既有 CT 回填**；另有 **~28 draft 为早期会话已建**（新格式合规，非本系列）。**★ 重大修正：原"3 BLOCKED"全错**——010232/010233 是 foundation（SET UPINITSETUP 已存在+行为描述+簇明示"不支持单独配置"）、020161 是 2-atom 轻量 draft（批次预检的 4 幽灵 atom 参考信息未列），均无 atom 阻塞，本轮已补建。**4.1 仅剩 020155 网管越界 skip**（MAE 集中配置组管理，UDG 无 MML 角色，非 Task 层特性）。**全部 94 FT 过对抗评审（本系列 66 FT CRITICAL/HIGH=0；早期 28 FT 抽查新格式合规）**。**仅剩集成动作（python：gen_compound_index 重算被引用于 + audit 脚本）+ atom 轨修缺陷（坑9）**——4.1 Task 层构建 100% 完成。

---

## 5. 构建规则（上一手执行中的约定，保持一致）

### 5.1 YAML 与正文骨架
- FT YAML：`id/type/name/name_zh/nf/version/ref/status`；ref→`{nf}@Feature@{code}`。
- CT YAML：`id/type/name/name_zh/nf/version/command_set/status`（**无 ref**）；command_set 是命令名列表（含空格，如 `"ADD URR"`）。
- 正文（FT）：`# 标题` + 引子 → `## 配置概览` → `## 配置流程` → `## 激活方法与参数差异` → `## 参数核对` → `## 决策点` → `## 约束` → `## 边`。
- 正文（CT）：`# 中文名` + 引子(定位+被引用于) → `## 配置方法`(表+典型脚本+步骤位置) → `## 场景差异` → `## 决策点` → `## 约束` → `## 边`。
- `## 边` 必须是**独立标题行**（否则平台不解析）。FT 边：`对应特性`→Feature + `编排`→atom/compound。CT 边：`组成`→atom + `被引用于`→FT。
- 引用统一 `[[{nf}@{Type}@{local}]]` 双方括号，**md 级粒度**（无章节锚）；**无证据段**（不写 source/## 证据）。

### 5.2 CompoundTask 抽取阈值（关键判定）
- **≥3 个 distinct atom 连续 → 强制评估抽 CT**（SOP §B.5 防平铺）。
- **<3 distinct atom → 直引 atom，不抽 CT**（先例：`GWFD-010151` 2 命令明确不抽）。同一 atom 重复执行（如 020251 的 TCP/UDP 双分类器）算 1 distinct。
- 多命令但**命中既有 CT**（Jaccard≥0.75 且相位同义）→ **复用**，不新建。0.4–0.75 相位近义 → reference（共享 atom）；<0.4 或相位不同 → 新建。Jaccard 只作门槛，**配置语义判定优先**（例：`ipfarm-pcscf-chain` 与 `ipfarm-redirect-chain` Jaccard≈0.71 但 SERVERTYPE/下游消费/参数集不同 → 新建）。
- 020251（2 atom）是边界 case：上一手按 <3 不抽。若倾向更积极，可补 `apn-ims-enable` CT（需用户拍板）。

### 5.3 激活方法表（7 固定列，**只写实演**）
固定列：`激活方法/条件 | 配置相位 | 执行的 Task（[[CompoundTask]] / [[AtomTask]]） | 省略的 Task | 关联 AtomTask | 相对基线的参数差异（参数=值） | 目标对象与生效说明`。

**⚠️ 只放 Feature 文档实演的场景 + 文档明示的可选分支**。**不要**臆造 atom 支持但 Feature 未演示的变体行（IPv6、单协议、开关组合变体等）——atom 级能力留 atom，不冒充 Feature 场景。上一手曾因加 IPv6 臆造行被纠正，已回修。（判定原则：行的"目标对象与生效说明"若需要写"未演示/待数据规划补齐/Atom 字典推导"，就别加这行。）

### 5.4 时序不可泛化
- 按激活脚本**原相位**编排命令，**不得**按常识重排。
- 特别 `SET REFRESHSRV`：脚本里在哪个对象/分支/阶段出现，就在 FT 该处表达（如 020304/110201 是 `ADD RULE` 后、`ADD USERPROFILE` 前）；**不要**一律挪到全局收尾。

### 5.5 参数合法性（每个实参逐项核 atom）
- 每个实际 `参数=值` 都要在对应 atom 的 `## 配置方法` 字典里核到；**只确认 atom 文件存在不算通过**。
- Feature 值与 atom 字典冲突 → FT 保留 Feature 实际值，但在 `## 参数核对` 标 **"冲突，待 Atom 更正"**；Feature 未给最小参数值 → 标 **"待数据规划补齐"**；都不得写成"通过"。

### 5.6 反链卫生（D3 必过）
- FT `编排` 了某 CT ↔ 该 CT `被引用于` 必须含该 FT。复用既有 CT 时**双向回填**：①FT 编排引 CT；②CT `被引用于` 加 FT；③CT `场景差异` 加该 FT 的命令子集/参数差异/对象/相位。
- 骨架/薄 FT（不编排某 CT）**不要**在正文 wikilink 该 CT，否则 `gen_compound_index` 会污染 CT 的"被引用于"。

### 5.7 调测剥离
配置流程/配置方法只含配置类命令（`ADD/MOD/SET/DEL/RMV/LOD/持久化 STR`）；`DSP/LST/EXP/STP/探测性 STR` 不入。

### 5.8 跨特性依赖链接
正文（配置概览/约束）用 `[[UDG@Feature@{code}]]` 表达依赖（上一手选择；4.2 用 `[[UDG@FeatureTask@...]]`，两者都合法、都不影响 audit，未统一——接手可统一为 FT 链接）。

### 5.9 构建→子 Agent 对抗评审→修 循环（本会话确立，每批必走）
每批 FT+CT 落盘后，**必派子 Agent 跑对抗评审**（`general-purpose`，用 `UDG特性与步骤Task构建提示词.md` 末尾「对抗评审提示词」+ 本批文件清单 + 输入源路径），修到 **CRITICAL/HIGH=0** 才算闭环。
- 评审范围：本批新建 FT + 回填 CT（重点核新增场景差异行 + 被引用于反链）。
- 评审输入：Feature 文档簇（**别只信 FT 自述**，逐篇读激活/配置/数据规划）+ AtomTask 字典 + check.md + 格式基准 110201。
- **不预透露**已知问题给评审（保持独立性）；CRITICAL/HIGH 必修，MEDIUM 多数修，LOW 选修/转 atom 轨。
- foundation 批可轻审（形状已校准，重点验 foundation 真实性 = 全簇 Grep `UDG@MMLCommand@` 零命中 + 概述有无"无需配置"明示）。
- 多批可并行评审（一 Agent 一批，同消息多 Agent 调用）。

### 5.10 评审教训（本会话真实案例，避免复发）
- **臆造变体行（020-C 复发，CRITICAL）**：激活表/CT 场景差异**只放 Feature 文档实演**场景，不臆造 atom 支持但 Feature 未演示的变体（IPv6/单Farm/不绑定VPN/省略可选命令）。典型反面：020253 曾加"不绑定VPN"行——PCSCF 必选 VPNINSTANCE，该行是**非法配置**非变体。判定：行需写"未演示/默认/推导"就别加。
- **时序以脚本为准（020-F C-1，CRITICAL）**：操作步骤叙述 vs 任务示例脚本相位不一致时，**以可执行脚本为准**（§5.4）。反面：020381 把 SET QOSCAR 按叙述挪到第 4 步，脚本是在 License 后。
- **参数核对口径须与约束段一致（020-F C-2，CRITICAL）**：与 atom critical 约束冲突的参数**不得写"通过"**，标"冲突/待 Atom 更正"；atom 字典薄（取值"见命令层 md"）标"待 atom 完善"；缺最小值标"待数据规划补齐"。反面：020381 SET QOSCAR/SET QOSSHAPE 与互斥约束冲突却写"通过"。
- **反链引子也要 sync（020-E C-1）**：CT 被引用于在引子段 + 边段两处都有时，**两处必须一致**（4.2 加引用方时易漏引子）。gen_index 重算以边为准，但引子是读者第一眼。
- **Feature 文档内部矛盾要标注（020-E H1/H4）**：概述"不涉及交互" vs 激活依赖、实现原理误归参数（如 020304 把 Referer 开关归 SET LICENSESWITCH）——按激活/atom 处理，但在约束段**显式标矛盾**（"★ Feature 概述与激活矛盾，按激活为准，待 Feature 层澄清"）。
- **license-access-prep 复用要看相位+语义（020381/010251）**：Jaccard=1.0 但相位不同义（命令被其他命令隔开）或 BWM 框架不符（LICITEM 不同）→ 不复用，直引 atom（§5.4 时序不可泛化优先于 Jaccard）。
- **重型多场景 Feature 不一定抽新 CT（010155）**：4 组网场景重型 Feature（~15 atom）实情可能 **0 新 CT**——路由层（OSPF/OSPFv3）若已有既有 CT（downlink-route-export/ipv6-bearer-ospfv3-wlr）则复用，底链 setup 原语（L3VPNINST+VPNINSTAF+SET BFD+VPNINST+LOGICINF）+ 相位跨场景变 → 直引 atom。交接 §7-A"可能抽 1-2 新 CT"是推测，开建前先 Grep 既有 CT 清单再判。
- **既有 CT 回填必须核结构自洽（010155 C1/C2）**：回填既有 CT 场景差异/被引用于时，同步核 ① command_set 与正文"X 条命令"计数一致；② 组成 vs 上游不双计同一 atom（组成=本 CT 编排的 atom，上游=前置依赖 atom，互斥，同一 atom 两处出现是关系歧义）。反面：downlink-route-export 的 ADD VPNINST 同时在 command_set/组成/上游；ipv6-bearer-ospfv3-wlr 的 ADD L3VPNINST 同。修：前置依赖 atom 仅留上游（或上游 CT），出 command_set/组成。
- **Feature 文档多形态矛盾（010155 C3/H2）**：Feature 文档内部矛盾不止"概述 vs 激活"一种——**操作步骤叙述 vs 任务示例脚本**（C3：场景 3 操作步骤明示 VPNINSCAPSIMFLG=TRUE 但脚本遗漏）、**数据表取值样例 vs 脚本实参**（H2：场景 2 数据表 PREFIX=0.0.0.0/0 但脚本 172.16.47.0/24）均可能矛盾。一律以脚本为准（§5.4）+ 在参数核对标"冲突/待 Feature 澄清"+ 约束段显式标矛盾，不写"通过"。
- **多配置文档簇逐篇核（010-A C1）**：Feature 簇常拆多个配置文档（配置X参数 / 修改X / 配置Y），每个文档对应独立激活相位（部署期 vs 运维调整）。FT 激活表须覆盖**每个配置文档**的场景，勿只读"配置X参数"主文档而漏"修改X"运维文档。反面：010102 漏"修改Echo消息的重发数据"（独立运维相位，N3REQUEST 探测 5→运维 3）；atoms 已为该场景建"仅改重发参数"配置方法，FT 层却无对应激活行。判定：开建前枚举簇内所有 doc_type=配置/其它的文档，逐篇提取激活相位。

---

## 6. 已知坑 / 待办 / 待审查（重点）

1. **Glob 工具不可靠（务必传给下一手）**：`**/*.md` 对部分目录静默返回空。文件存在性/目录枚举**一律用 Grep(ripgrep)**：
   - 验某 atom 是否存在：`Grep(pattern='id: "UDG@AtomTask@ADD CPASSOCIATION"', path=<AtomTask dir>, output_mode="files_with_matches")`。
   - 枚举哪些 Feature 码有簇：`Grep(pattern="feature_code:", path=Feature/UDG/20.15.2, glob="UDG@Feature@GWFD-010*/*.md", output_mode="files_with_matches")`。
   - **不要据 Glob 空结果断言"簇/atom 不存在"**。

2. **atom 覆盖未全域 Grep 审计**：完成批次的 atom 已验；**未建批次（READY/FOUNDATION）的逐 atom 就绪性来自代理（用了不可靠 Glob），未全部复核**。开建每批前自己 Grep 验；建议交接后先跑一次全域 `MMLCommand 引用 → atom 存在` 审计钉死缺口（可选，见 §7）。

3. **FOUNDATION 数量（~35）是代理判定**：代理可能漏读某些 Feature 的配置文档而误判 foundation。开建前 Grep 该 Feature 目录的 `[[UDG@MMLCommand@...]]` 确认真假。

4. **foundation FT 形状已校准（010-D 闭环）**：010191（移动性管理）为首个 foundation 骨架样例——`status: foundation` + 配置概览说明"无独立配置"（Feature 5G 概述权威证据"本特性无需配置即可使用"）+ 不建配置流程/激活表/参数核对 + 边只对应特性。对抗评审通过（CRITICAL/HIGH=0，独立验证 foundation 判定）。~34 个 foundation 待建可按此形状复制。**注**：audit 脚本可能对 foundation FT 报"缺配置流程"——属 check.md 已知盲区（脚本仅对 foundation CT 的 command_set 豁免，未对 FT 豁免），非缺陷。

5. ~~**本机 bash 跑不了 python**~~ → **已解锁（2026-08-04）**：git-bash 现可用 python 3.12.7。`gen_compound_index` / `audit_compound_feature` / `audit_atoms` 均已跑通（4.3 轨集成验证，audit D0-D4 fail=0）。

6. **~~未做独立审查~~ → 020-C/D/E 已补审（2026-08-04）**：上一手 9 FT + ipfarm-pcscf-chain CT 原仅自检，已补跑 3 个并行子 Agent 对抗评审——
   - **020-D**：干净（0C/0H，License 网关单命令）。
   - **020-C**：抓 **2 CRITICAL + 2 HIGH**（已全修）——020253 FT + ipfarm-pcscf-chain CT 臆造"不绑定VPN/单Farm/省略心跳调优"变体行（"不绑定VPN"且为 PCSCF 必选 VPNINSTANCE 的**非法配置**，正是上一手曾被纠正的同类错误复发）；CT 决策点 IPv6 DP 越界（无引用方）；CT 典型脚本 ADD LOGICINF 参数序与 Feature 不一致。已删臆造行 + 清 IPv6/VPN决策点 + 脚本序对齐。
   - **020-E**：抓 **1 CRITICAL + 5 HIGH**（已修 4，H5 列语义延后）——userprofile-rule-attach CT 引子"被引用于"漏登 020304/110251/110252（边有 6、引子只 3，已 sync）；C2（CT 场景差异相位不明确）为**误报**（020304 行本已写"固定 RULE 后、模板前"，评审漏读括号）；020308 漏 SA-Basic(110101) 依赖（概述明示，已补）；020307 概述"不涉及交互"与激活依赖 020301 矛盾（已标）+ URRID=1100 追溯（已补）；020304 实现原理把 Referer 开关误归 SET LICENSESWITCH（与激活 ISREFEREREN 冲突，已标）。
   - **结论：20 FT 现全部过对抗评审（CRITICAL/HIGH=0）**（020-C/D/E 补审 + 020-F/010-D/010-B/010-C-foundation 本会话即审）。剩余仅集成动作（`_index` 重生 + `audit_compound_feature.py`，需 python 环境 + 集成 Agent）。

7. ~~**`_index.md` 未重生**~~ → **已重生（2026-08-04，4.3 轨集成）**：`ipfarm-pcscf-chain` 入 _index（compound_count 42→44）；被引用于全量 reflective 重算（含 4.1 各 CT 的 020304/020352/020356/010201 等回填，与脚本重算一致）。audit_compound_feature D0-D4 **fail=0**。集成另修：010155 line 43 prose wikilink 污染（mpls-vpn-infra/ipv6-bearer-infra → 裸文本）；坑14 H1 的 ipv6-bearer-ospfv3-wlr 反链已由脚本重算一致。

8. **真·待审查项（020253）**：激活脚本 farm_test/farm_test2 共用 `phif1/0/0`，与 `ipfarm-redirect-chain`「不同 Farm 须配不同心跳接口」约束冲突；`ADD IPFARM`/`ADD LOGICINF` atom 未强制。已按脚本保留并标注待独立审查确认 PCSCF 场景是否允许共享。

9. **Atom 缺口（两类，不在本轨补）**：
   - 阻塞型 6 个：`ADD PATHDWNALMSEG`、`SET UPINITSETUP`、`ADD CPASSOCIATION`、`ADD UPIPDOMAIN`、`SET SMFFUNC`、`ADD RESELECTUPCAUSE` → 卡 4 Feature。
   - "★R1.5 atom 待补"型（散落 atom 正文）：`SET USRPROFCHARGE`、`ADD CHARGEMETHOD`、`MOD CFGTHRESHOLD`、`MOD APNIMSSIGFLTR`、`MOD IPFARMSERVER`、`MOD EXTENDEDFILTER`、`SET TCPGLOBALCFG`、`ADD PCSCFIP` 等，多为 MOD/RMV/软参，对已建 Feature 不阻塞。
   - **atom 正文质量缺陷（010-B 评审发现，转 atom 轨修复）**：① `SET APNACCESSWAL` atom 第 43 行 wikilink ID 拼断（`[[UDG@AtomTask@SET DEACTIVERATER1.5 atom 待补）]]`、`SET SOFTPARA` 同型）；② `SET DEACTIVERATE` atom 第 21/45 行引号错位（`SGW-U、PGW-U", "UPF` JSON 残留）；③ `SET DEACTIVERATE`/`SET SOFTPARA` atom 字典偏薄（关键参数 RATE/软参取值"见命令层 md"未枚举，致 010251 参数核对只能标"待 atom 完善"）。非阻塞，但影响引用可信度 + 参数合法性核验，待 atom 批次修复。

10. **个别 Feature 文档自相矛盾**：020281/020307 概述写"不涉及交互"但激活文档引用依赖；上一手按激活（配置实情）处理 + 软引用说明。接手遇到同类按激活为准。

11. **020356 REDIRAPPENDINFO 密钥待补（真·待审查）**：`ADD REDIRAPPENDINFO` 配 `IMSIENCRYALGORI=AES256` 但激活脚本未给配套 `IMSISECRETKEY/IMSISECRETKEYCONFIRM`（atom 约束：ENCRYALGORI 配时密钥对必填）→ 020356 FT 参数核对标"待数据规划补齐（密钥敏感值，与对端协商）"，未写通过。

12. **020381 SET QOSSHAPE atom 字典薄 + CAR/Shaping 互斥冲突（真·待审查）**：① SET QOSSHAPE atom 未枚举 USERTYPE 取值（指向命令层 md），020381 `USERTYPE=VISITING` 合法性待 atom 补全后复核；② SET QOSCAR atom 声明"CAR 与 shaping 不可同时启用 SET QOSSHAPE，同开优先 shaping、CAR 无效"，但 020381 激活脚本**同时执行 SET QOSCAR 与 SET QOSSHAPE** → 020381 FT 标冲突/待独立审查确认（是否分属不同作用域 or 脚本需调整）。

13. **020-F 已跑对抗评审 + 修复**（2026-08-03，构建→评审循环首跑）：独立子 Agent 评审发现 **2 CRITICAL + 3 HIGH + 3 MEDIUM**，全部已修复——
    - C-1（020381 时序重排，已修）：Feature 脚本顺序 `License→SET QOSCAR→ADD USERPROFILE→ADD APN→SET APNQOSATTR→SET QOSSHAPE`，原 FT 误按「操作步骤」叙述把 SET QOSCAR 挪到第 4 步，违反 §5.4 时序不可泛化。已复位为脚本相位。
    - C-2（020381 参数核对误写"通过"，已修）：SET QOSCAR/SET QOSSHAPE 与 atom「CAR/Shaping 互斥」critical 约束冲突，参数核对原写"通过"，已改"冲突/待 Atom 更正"。
    - H-1/H-2/H-3/M-1（已补注）：020352 PCCACTIONPROP 4 门控说明 + FILTERIPV6 TCP 出处（atom 维度 2）；020356 CT 边界拆分说明；filter-chain LOD SIGNATUREDB 非本 CT 的相位注。
    - M-2/M-3（旁证复核成立）：020357 确实"未演示"+直引 atom；110331 仅用 PCCACTIONPROP 子集；license-access-prep 确为 BWM 框架（LKV3G5TCSA01）。
    - **教训**：操作步骤叙述 vs 任务示例脚本相位不一致时，必须以脚本为准（C-1 类）；参数核对口径须与约束段一致，冲突不得写"通过"（C-2 类）。
    - **020-C/D/E 的 9 FT 已补审**（见坑6）。后续批次采用「构建→子 Agent 对抗评审→修 CRITICAL/HIGH→下一批」循环（§5.9）。

14. **010155 真待审查 / atom 轨 / 跨批次 CT（010-C 评审产出）**：
    - **C3 场景 3 VPNINSCAPSIMFLG**（真待 Feature/atom 澄清）：Feature 操作步骤明示"VPN 多实例须配 VPNINSCAPSIMFLG=TRUE"但任务脚本遗漏；按脚本保留 + 标冲突；待确认 IPv4 OSPF 私网进程是否真必配（atom ADD OSPF 约束段说必配，但场景 4 IPv6 脚本配了、场景 3 IPv4 脚本没配）。
    - **H2 场景 2 缺省 vs 明细**（真待 Feature 澄清）：数据表取值样例 PREFIX=0.0.0.0/MASKLENGTH=0（缺省）vs 脚本 172.16.47.0/24（明细）；按脚本保留 + 标不一致。
    - **M2 场景 4 共网段接口级缺失**（真待业务确认）：脚本配 VIRTUALSYSFLAG=TRUE（进程级）但未配接口级 ADD OSPFV3INTERFACE，atom 约束 critical"共网段须进程级+接口级同时配"→ 单配进程级不生效；待确认 010155 场景 4 是否真有共网段部署需求。
    - **H3 atom ADD SRROUTE 约束段措辞缺陷**（转 atom 轨，参坑9）：约束段"BFDENABLE=TRUE 时必须 ADD SRBFDTEMPLET"未区分动态 vs 静态 BFD 路径；atom 配置维度 6 明示静态 SESSIONNAME 路径合法（010155 场景 1 用）。待 atom 轨修订约束段措辞。
    - **H1 ipv6-bearer-ospfv3-wlr 场景差异 vs 实际反链**（跨批次，集成时重算）：CT 场景差异表提及 020403/020406 但 Grep 证实两 FT 实际不引该 CT（实际引用方=020401/IPFD-014001/010155）；IPFD-014001 引用但未登被引用于。预存不一致，`gen_compound_index.py` 集成时按实际反链重算被引用于即可，本轨不手工改（防与他批 FT 冲突）。

15. **010-A 补审结果（010102/010103，2026-08-04）**：
    - **010102 漏配"修改Echo重发"场景（C1，已补）**：Feature 第 3 配置文档"修改Echo消息的重发数据"是独立**运维相位**（组网改变/网络调整，前置完成探测参数），脚本 `SET UPGTPPATH:T3RESPONSE=10,N3REQUEST=3` + `SET UPN4UPATH:N4T3RESPONSE=10,N4N3REQUEST=3`（`N3REQUEST` 探测基线 5→运维 3，同 CT 命令重发子集，覆盖全局唯一记录）。FT 原仅 4 行激活表（4G/5G/双模/黑白名单），漏此场景；已补配置流程步骤 3 + 激活表行 + 参数核对 2 行 + DP3 + CT 场景差异行 + 两轴说明。**教训（§5.10 补）**：多配置文档簇须逐篇核（配置/修改/调测分文档），勿只读"配置X参数"主文档而漏"修改X"运维文档。
    - **010102 PATHDWNALMSEG 非阻塞（误判修正）**：交接原标"010102 BLOCKED 缺 ADD PATHDWNALMSEG"是**误判**——该命令仅在"路径管理参考信息"命令清单出现，不在任何配置/激活脚本（属可选告警段配置，atom 亦未建）。010102 FT 正确未引，非阻塞。BLOCKED 列表 4→3（剩 010232/010233/020161）。
    - **010103 foundation 干净通过**：全簇 Grep `UDG@MMLCommand@` 零命中，概述明示"无需配置即可使用"，形状合规。

---

## 7. 下一步接续点（任选其一启动）

- **A（重型续建）**：~~010155~~ **已完成（010-C，4 场景复用 downlink-route-export+ipv6-bearer-ospfv3-wlr，0 新 CT；建+审+修 0C/0H 闭环）**。下一重型候选：**020423（11 命令路由交叉，CT 候选，参 mpls-vpn-infra）**；或 **020402（IPv6 组网，READY）**。
- ~~**A'（补审 010-A）**~~ **已完成（2026-08-04）**：010102/010103 补审闭环——010102 漏配"修改Echo重发"场景已补（C1，配置流程步骤 3+激活表+参数核对+DP3+CT 场景差异）+ PATHDWNALMSEG 非阻塞误判修正；010103 foundation 干净通过。010-A ✅，BLOCKED 4→3。
- **A''（atom 轨，消阻塞 + 修缺陷）**：补阻塞型 6 atom（ADD PATHDWNALMSEG/SET UPINITSETUP/ADD CPASSOCIATION/ADD UPIPDOMAIN/SET SMFFUNC/ADD RESELECTUPCAUSE → 解锁 010102?/010232/010233/020161）；修坑9 atom 正文缺陷（SET APNACCESSWAL wikilink 拼断、SET DEACTIVERATE 引号错位）+ 本批新增 H3（ADD SRROUTE 约束段静态/动态 BFD 路径措辞）。
- **B（清计数）**：**foundation 批量**——形状已校准（5 样例：010191/010106/010252/010154/010156），010-F/G/H/J/K（接口/VNF 类 ~15 个）可快速复制。每批仍走 §5.9 轻审（验 foundation 真实性）。
- **C（消不确定）**：先跑全域 atom 覆盖 Grep 审计（§6 坑2）钉死未建批次隐藏缺 atom；或补 §6 坑9 的 atom 正文缺陷（SET APNACCESSWAL/SET DEACTIVERATE）。
- **✅ D（集成）已完成（2026-08-04，4.3 轨执行）**：python 3.12.7 在 git-bash 解锁后跑通全套——gen_compound_index（_index 42→44，ipfarm-pcscf-chain + 4.3 的 5 CT 全入，被引用于 reflective 重算）+ audit_compound_feature（D0-D4 **fail=0**）+ audit_atoms（431 atom，97% 合规）。4.1 已审产出（含 010155）全部正式入索引。集成另修 010155 line 43 prose 污染（mpls-vpn-infra/ipv6-bearer-infra → 裸文本）+ 坑14 H1 的 ipv6-bearer-ospfv3-wlr 反链由脚本重算一致。**atom 轨遗留（非阻塞，转 atom 轨，参 A''）**：audit_atoms 抓 CRITICAL 5（PROPATTACHIPSECPROPOSAL `[[ADD IPSECPROPOSAL6]]`×4 断链 + ADD QOSAPPLICATION `[[MOD QOSAPPLICATION]]` 断链）+ HIGH 8（ADD ABNTRAFFICDT/IKEPEER/IPSECINTFCFG/IPSECPOLICY/PCCPOLICYGRP/URRGROUP + SET GYONESHOT/IKEGLOBALCONFIG 缺 ## 决策点）+ MEDIUM 1（VPNINSTAFIPSEC markdown 相对路径）+ LOW 281（name_zh 对齐）。

> 单 Feature pass 标准动作：读 Feature 文档簇（激活/配置/数据规划/任务脚本，**别只读概述**）→ Grep 验每条配置命令的 atom 存在 + 核参数 → 还原命令时间线（保留相位/分支/刷新）→ 拆步骤（≥3 distinct 抽 CT / 命中既有 CT 则复用并双向回填 / 单命令直引 atom）→ 写 FT（+CT）→ 自检（字段/真实引用/独立 ## 边/无调测/反链一致/激活表只写实演）。

---

## 8. 环境与工具备忘

- 工作目录：`D:\mywork\KnowledgeBase\NewSFCGraph`；网元 UDG，版本 20.15.2。
- 资产路径：Feature=`三层图谱资产/Feature/UDG/20.15.2/UDG@Feature@{code}/*.md`；Atom=`.../AtomTask/UDG/20.15.2/UDG@AtomTask@{CMD}.md`（文件名含空格）；Compound=`.../CompoundTask/UDG/20.15.2/UDG@CompoundTask@{name}.md` + `_index.md`；FeatureTask=`.../FeatureTask/UDG/20.15.2/UDG@FeatureTask@{code}.md`。
- **Glob 不可靠→用 Grep**（§6 坑1）；~~bash 无 python~~ → **已解锁 python 3.12.7**（§6 坑5），集成脚本现可直跑。
- 脚本：`task/scripts/gen_compound_index.py`（重生 _index）、`audit_compound_feature.py`（D0-D4 结构审计，过≠全对，盲区见 check.md）、`audit_atoms.py`、`collect_command_examples.py`。
