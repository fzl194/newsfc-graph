# UNC FeatureTask + CompoundTask 领域批次构建计划

> 状态：执行中（2026-08-17 刷新）。**已完成**：P0、UNC-F0（77 foundation）、UNC-A1~A4、UNC-B1~B6、UNC-C1、UNC-C2（传统接口 011101-011111 + DRA 011125-011134 均有交接）——磁盘实测 173 FT / 59 CT（2026-08-17）。
> **待执行**：UNC-C3~C5（计费/AAA/IoT 接入）、UNC-D1~D8（102-109 大域，仅零星旧 FT）、UNC-E、UNC-F1~F8（201-990）。
> **下一批**：UNC-C3（011201/011202/011206 离线/热/融合计费，启动前仍须按 §5.2 全文准入）。
>
> 适用范围：`UNC 20.15.2` Task 层第二阶段——以现有 AtomTask 为输入，分批建设/重构 FeatureTask 与 CompoundTask。
>
> 本文是 UNC 的**执行与恢复上下文**，不替代规范。构建规则以 `task/SKILL.md`、`字段定义.md`、`template/`、`check.md` 为唯一权威；本文只回答“UNC 的范围是什么、分哪些批、按什么顺序、如何复用和验收”。

---

## 0. 会话恢复与阅读顺序（未来接手必读）

任何后续 Agent 在开始 UNC 新批次前，按下列顺序恢复上下文，不要仅依赖聊天记录：

1. 读本文，确认上一批的完成状态、所属 CT 所有权域与下一个批次；
2. 读 `task/SKILL.md` Part B、`字段定义.md`、两个模板与 `check.md`；
3. 读本批对应的 `task/handoff/UNC-{batch}-交接.md`（批次完成后创建）；
4. 读取 `三层图谱资产/Feature/UNC/20.15.2/_build_manifest.json`，它是 470 个 Feature 静态范围的快照；
5. 在只读准入完成前，读取完整 Feature 文档簇、相关 AtomTask、`CompoundTask/UNC/20.15.2/_index.md` 及候选 CT；
6. 最后运行当前结构审计；**脚本通过不替代独立对抗审查**。

恢复时可用以下只读命令核对静态范围和资产数（不以记忆中的数字替代磁盘真值）：

```powershell
Get-ChildItem '三层图谱资产/Feature/UNC/20.15.2' -Directory
Get-ChildItem '三层图谱资产/AtomTask/UNC/20.15.2' -File -Filter 'UNC@AtomTask@*.md'
Get-ChildItem '三层图谱资产/FeatureTask/UNC/20.15.2' -File -Filter 'UNC@FeatureTask@*.md'
Get-ChildItem '三层图谱资产/CompoundTask/UNC/20.15.2' -File -Filter 'UNC@CompoundTask@*.md'
python '三层图谱构建规范/task/scripts/audit_compound_feature.py' --nf UNC
```

---

## 1. 已确认的范围、输入和边界

### 1.1 本轮目标

- 目标范围是 Feature 静态层清单中的 **470 个 UNC Feature**；每个 Feature Code 最终恰有一个 `UNC@FeatureTask@{code}.md`。
- FeatureTask 的构建单元始终是**一个 Feature 的完整 pass**：同一个 pass 内同步产出/复用该 Feature 所需的 `CompoundTask`，绝不先批量写 FT、以后再补 CT。
- 一个稳定多命令配置步骤才是 CT；`<3` 个 distinct 配置 atom 时直接编排 AtomTask。CT 不是“每 Feature 必须有一个”的对象。
- 本轮 AtomTask 的底层输入边界是磁盘上已存在的 **1,277 个 AtomTask**。它们全部可被上层 Task 使用，不因原始输入来源不同而排除。
- 某 Feature 实际使用的配置类命令若没有 AtomTask，或 Feature 实参不能在 AtomTask 配置方法中核到，不得在 FeatureTask 批次临时补 atom 或凭常识补参数；但**仍须落盘信息受限 `draft` FeatureTask**，如实记录可确认的配置责任、未编排范围与待补输入。只有已恢复并通过 Atom 准入的命令链才可编排 Atom/CT。

### 1.2 AtomTask 基线（2026-08-07 快照）

| 集合 | 数量 | 对上层构建的含义 |
|---|---:|---|
| AtomTask 总数 | 1,277 | 全部可用于 FT / CT 准入 |
| 有现存 `atom-input` 原始底稿的 AtomTask | 997 | 997/997 均已建为 AtomTask |
| 无现存 `atom-input` 底稿的历史/补建 AtomTask | 280 | 同样有效；276 个为 2026-07-17 早期存量，4 个为 2026-08-03 补建 |
| 原始输入中有明确“激活”路径案例 | 678 | 仅用于来源追溯，不是上层引用资格的二次过滤 |

原始输入目录：`三层图谱资产/_intermediates/atom-input/UNC/`。**注**：该目录已于 2026-08-17 删除（用户批准清理中间态）；补建 atom 需重跑 `collect_command_examples.py --nf UNC --version 20.15.2` 再生底稿，280 个历史存量 atom 的输入底稿追溯不再可查（atom 资产本身不受影响）。

### 1.3 当前 Task 存量（2026-08-17 更新）

- P0 已完成：38 个历史 CT 已治理（command_set/边/反链/`_index.md`）。
- 现有 `FeatureTask`：173 个（F0 77 foundation + A/B/C 域 96，含原位重构的旧 FT）。其中 C3~F 域仍按本计划待建。
- 现有 `CompoundTask`：59 个。
- 历史参考（P0 前）：旧 FT 37 个为旧格式，已在所属业务批原位重构，不能从目标范围扣除。旧 FT 代码清单（P0 前快照，仅作迁移参考）：

```text
IPFD-015002, IPFD-016000
WSFD-010202, WSFD-010301, WSFD-010400, WSFD-010501, WSFD-010502, WSFD-010503, WSFD-010504
WSFD-011201, WSFD-011202, WSFD-011206, WSFD-011305, WSFD-011306, WSFD-011307
WSFD-104001, WSFD-104002, WSFD-104004, WSFD-104005, WSFD-104410, WSFD-104411, WSFD-104413
WSFD-106003, WSFD-106203, WSFD-107010, WSFD-107021, WSFD-108007
WSFD-109002, WSFD-109101, WSFD-109102, WSFD-109104, WSFD-109107, WSFD-109108
WSFD-211001, WSFD-211005, WSFD-211009, WSFD-211101
```

---

## 2. P0：既有 CompoundTask 可复用化（所有 Feature 批的硬前置）

### 2.1 目标

将 38 个历史 CT 迁移为可按现行 SOP 复用的步骤库：

- 对每个非 foundation CT 从其 `组成` atom 边推导并写入 `command_set`；
- 统一边标签为 `组成` / `被引用于`，回填已存在 FT 的真实反链；
- 补齐现行要求的场景差异表达，不把旧 FT 中的引用方遗漏掉；
- 生成 `_index.md`，此后所有新 CT 的 Jaccard + 相位同义判定以该索引为入口；
- 独立审查后运行 `audit_compound_feature.py --nf UNC`，P0 的目标是清除当前已知的 CT 结构/反链 fail。

### 2.2 CT 所有权域（精确清单）

| 所有权域 | 既有 CT | 后续优先服务的业务批 |
|---|---|---|
| 会话、地址与用户面选择 | `session-addr-alloc-skeleton`、`session-n4-pfcp-skeleton`、`session-pcc-chf-skeleton`、`smf-chf-trigger-rg-aging`、`unc-apn-access-infra`、`unc-ctrl-addr-alloc-rule`、`unc-dhcp-server-chain`、`unc-dualstack-global-switch`、`unc-smf-addrpool-hierarchy`、`unc-upf-selection-family` | UNC-B、UNC-D（104/107/108）、UNC-F（223/228） |
| 计费、PCC、ADC、QoS 与带宽控制 | `adc-app-detection`、`adc-predefined-rule-bind`、`bwm-local-rule-bind`、`cct-bind-cc`、`charging-msg-cache`、`chf-selection`、`converged-charging-exception`、`converged-charging-rate-id-chain`、`converged-charging-template`、`ofctemplate-bind-apn`、`ofctemplate-bind-cc`、`ofctemplate-bind-userprofile`、`offline-charging-template`、`pcc-switch-template`、`pcrf-diameter-chain`、`pcrf-selection-grouping`、`qos-attr-rule-bind-chain`、`user-location-template-bind` | UNC-C（011 计费/AAA）、UNC-D（109）、UNC-F（211/223） |
| 接入、网络、隧道与路由 | `unc-access-control-family`、`unc-downlink-route-export`、`unc-gre-tunnel-family`、`unc-ipsec-suite`、`unc-l2tp-ctrl-family`、`unc-location-dns-family`、`unc-mpls-vpn-infra`、`unc-ospfv3-route-export`、`unc-radius-chain`、`unc-radius-vsa` | UNC-A、UNC-B、UNC-C（011 接口/AAA） |

构建者只能修改自己批次所属域的既有 CT。跨域复用且需要增加“场景差异”时，只提交待整合回填清单；唯一集成者统一修改共享 CT。

---

## 3. UNC-F0：单文件概述型 foundation 专批

### 3.1 精确范围

此批次是一个**逻辑批次**，不是把 105 个对象交给一个构建者。它按 15–25 个 Feature 切为审查分片，但所有分片遵循同一 foundation 规则，且不共享/新建 CT。

快照选择条件为：Feature 目录内恰有一个 `概述.md`。当前共 105 个：IPFD 7、NPFD 13、SFFD 15、WSFD 70。下列代码清单固定记录本次快照；实际构建前仍须逐簇确认没有配置类命令、激活方法、数据规划或任务脚本。

```text
IPFD: IPFD-014000, IPFD-014003, IPFD-014004, IPFD-014005, IPFD-014006, IPFD-015001, IPFD-017000

NPFD: NPFD-010001, NPFD-010002, NPFD-010003, NPFD-010004, NPFD-010006, NPFD-010007,
      NPFD-010008, NPFD-010009, NPFD-010010, NPFD-010011, NPFD-010017, NPFD-010018, NPFD-010019

SFFD: SFFD-010004, SFFD-010005, SFFD-010009, SFFD-010010, SFFD-010011, SFFD-010013,
      SFFD-010014, SFFD-010015, SFFD-010022, SFFD-010032, SFFD-010033, SFFD-010035,
      SFFD-010036, SFFD-010037, SFFD-010043

WSFD: WSFD-010000, WSFD-010001, WSFD-010002, WSFD-010003, WSFD-010004, WSFD-010306,
      WSFD-010805, WSFD-010807, WSFD-011103, WSFD-011104, WSFD-011105, WSFD-011106,
      WSFD-011112, WSFD-011116, WSFD-011118, WSFD-011119, WSFD-011120, WSFD-011127,
      WSFD-011128, WSFD-011129, WSFD-011130, WSFD-011131, WSFD-011135, WSFD-011136,
      WSFD-011137, WSFD-011138, WSFD-011139, WSFD-011140, WSFD-011141, WSFD-011144,
      WSFD-011304, WSFD-011401, WSFD-011402, WSFD-011403, WSFD-011404, WSFD-011406,
      WSFD-011407, WSFD-011501, WSFD-103007, WSFD-104407, WSFD-104412, WSFD-106402,
      WSFD-107001, WSFD-107005, WSFD-107010, WSFD-107015, WSFD-109008, WSFD-113001,
      WSFD-113002, WSFD-113006, WSFD-113009, WSFD-202003, WSFD-209001, WSFD-209205,
      WSFD-211002, WSFD-214001, WSFD-214002, WSFD-214003, WSFD-214004, WSFD-214005,
      WSFD-219003, WSFD-219005, WSFD-224101, WSFD-224102, WSFD-224103, WSFD-224104,
      WSFD-224105, WSFD-225001, WSFD-227101, WSFD-227103
```

### 3.2 foundation 判定和输出

- 不能仅因“一个 md”就写 foundation。构建者要在预检中列出该唯一 md、是否含配置类命令、是否含激活/配置/数据规划/任务脚本；任一项为真即移出 UNC-F0，回到下方的对应业务批。
- 确认 foundation 后，写 `status: foundation` 的 FeatureTask：说明能力边界、无独立 UNC 配置流程的理由、非本 NF 配置责任（如有）；不虚构 AtomTask、参数或 CompoundTask。
- 已有旧 FT 若落在该清单（例如 `WSFD-107010`），仍按新格式原位重构。

### 3.3 不进入 F0 的无概述异常项

`NPFD-010005`、`WSFD-113011`、`WSFD-214000`、`WSFD-219000` 不满足“单 `概述.md`”条件。它们分别归入 UNC-A、UNC-E、UNC-F（214）和 UNC-F（219）做完整文档簇准入，不能按 foundation 快速处理。

---

## 4. 业务批次地图（除 UNC-F0 外的全部 Feature）

### 4.1 读法与覆盖保证

下表的“范围”使用**目录名前缀 + F0 排除集**定义，是精确集合，不是示例：

- 例如 `全部 IPFD-*（17 个）` 意味着 Feature 静态层中所有 17 个 `IPFD-*` 目录；其中 7 个已在 UNC-F0，剩余 10 个由 UNC-A1/A2 覆盖。
- `WSFD-104* - F0` 意味着所有静态层 `WSFD-104*` 目录，明确排除 F0 内的 `WSFD-104407`、`WSFD-104412`，其余 39 个均属该域，无隐含遗漏。
- 470 个 Feature 的穷尽分解为：IPFD/NPFD/SFFD 51 + WSFD-010 39 + WSFD-011 67 + WSFD-102～109 147 + WSFD-110～130 22 + WSFD-201～990 144。UNC-F0 是从这些业务域抽出的横切专批，而非额外范围。

### 4.2 UNC-A：平台、运维、IP 与网络可靠性（全部 IPFD/NPFD/SFFD）

| 批次 | 精确 Feature 范围 | 业务对象链 / 步骤所有权 | 依赖 |
|---|---|---|---|
| UNC-A1 | `IPFD-010001, 010002, 011001, 012001, 012002, 012003` | 接口、VLAN、ARP、QoS、ACL、BFD；不与业务 PCC/QoS CT 混用 | 可在 P0 后独立 |
| UNC-A2 | `IPFD-014001, 014002, 015002, 016000` | OSPF/BGP、GRE、IPSec；优先复用网络/隧道 CT，已有 `015002/016000` FT 重构 | P0 网络域后 |
| UNC-A3 | `NPFD-010001, 010005, 010006, 010007, 010010, 010013, 010014` | Portal 运维、配置/跟踪与 NTP；先判定正常可执行链还是信息受限 draft，不能因单概述静默不写 | 独立 |
| UNC-A4 | `SFFD-010008, 010030, 010031` | 通信亚健康、业务节点故障、自愈；查询/告警观察不进入 CT | 独立 |

这四个批加 UNC-F0 中 IPFD/NPFD/SFFD 项，覆盖**全部** IPFD 17、NPFD 16、SFFD 18。

### 4.3 UNC-B：核心架构、接入、会话与承载（全部 `WSFD-010*`）

| 批次 | 精确 Feature 范围（均已排除 F0） | 业务对象链 / 复用方向 |
|---|---|---|
| UNC-B1 | `WSFD-010005` | 负荷动态调整；单独判断是否存在稳定多命令步骤 |
| UNC-B2 | `010102, 010105, 010106, 010108, 010110, 010112, 010201, 010202` | 非 3GPP、共接入、RedCap/FWA、移动性与对等网元选择 |
| UNC-B3 | `010301, 010302, 010303, 010304, 010305, 010308, 010309` | 鉴权、身份隐私、NAS/SBI 加密、证书；安全步骤与会话步骤隔离 |
| UNC-B4 | `010400, 010501, 010502, 010503, 010504, 010600` | 用户数据、会话、地址、路径管理；优先复用会话/地址 CT；已有 FT 原位重构 |
| UNC-B5 | `010701, 010702, 010703` | QoS 与流量管理；只在稳定对象链成立时复用 QoS CT |
| UNC-B6 | `010801, 010802, 010803, 010804, 010900, 010901` | 过载保护、信令风暴、IP 承载、寻呼流控 |

UNC-B1～B6 加 F0 中的 8 个 `WSFD-010*`，覆盖**全部 39 个 `WSFD-010*` Feature**。

### 4.4 UNC-C：漫游、接口、计费、AAA 与云化演进（全部 `WSFD-011*`）

| 批次 | 精确 Feature 范围（均已排除 F0） | 业务对象链 / 复用方向 |
|---|---|---|
| UNC-C1 | `011001, 011002, 011003, 011004, 011005, 011006` | 漫游控制、系统间兼容、鉴权映射、话单/QoS 代际兼容 |
| UNC-C2 | `011101, 011102, 011107, 011108, 011111, 011125, 011126, 011132, 011133, 011134` | 传统接口、DRA 接口；不把接口原理误写成配置流程 |
| UNC-C3 | `011201, 011202, 011206` | 离线、热、融合计费；优先复用 `offline-*`、`converged-*`、`ofctemplate-*`、`charging-msg-cache`；已有 FT 重构 |
| UNC-C4 | `011301, 011302, 011303, 011305, 011306, 011307, 011308, 011309, 011310, 011311` | AAA/Radius、用户属性、PLMN；优先复用 `unc-radius-*`、`user-location-template-bind`；已有 FT 重构 |
| UNC-C5 | `011502, 011503, 011511, 011521, 011522, 011601, 011602, 011603` | NSA 与 NB-IoT 接入/话单/QoS；后续 IoT 批可复用但不可并发修改同一 CT |

UNC-C1～C5 加 F0 中的 30 个 `WSFD-011*`，覆盖**全部 67 个 `WSFD-011*` Feature**。

### 4.5 UNC-D：语音、安全、IPv6、接入、UPF 与计费/PCC（全部 `WSFD-102*`～`WSFD-109*`）

这是 147 个 Feature 的最大业务域。每个前缀均是完整范围，内部再按完整文档簇的对象链拆成 3–6 Feature 的实际构建批；不允许只按编号平铺。

| 域批 | 精确范围 | 规模 | 业务边界与既有 CT |
|---|---|---:|---|
| UNC-D1 | 全部 `WSFD-102*` | 27 | VoLTE、语音连续性与语音能力；重型多场景 Feature 单独批 |
| UNC-D2 | `WSFD-103* - {WSFD-103007}` | 4 | GPRS 安全、设备标识、灵活鉴权 |
| UNC-D3 | `WSFD-104* - {WSFD-104407, WSFD-104412}` | 39 | IPv4/IPv6、双栈、地址/承载/计费关联；优先接入会话/地址 CT；已有 7 个 FT 在此重构 |
| UNC-D4 | 全部 `WSFD-105*` | 11 | QoS 覆盖、漫游限制与策略控制 |
| UNC-D5 | `WSFD-106* - {WSFD-106402}` | 29 | 接入控制、二次激活、用户/终端策略；已有 `106003/106203` 重构 |
| UNC-D6 | `WSFD-107* - {WSFD-107001, WSFD-107005, WSFD-107010, WSFD-107015}` | 3 | CUPS、GW-U/UPF 选择；已有 `107021` 重构，复用 `unc-upf-selection-family` |
| UNC-D7 | 全部 `WSFD-108*` | 4 | 预定义规则分流、MEC 保护；已有 `108007` 重构 |
| UNC-D8 | `WSFD-109* - {WSFD-109008}` | 21 | 在线/内容/策略计费、PCC、ADC、带宽控制；集中维护 `adc-*`、`charging-*`、`pcc-*`、`bwm-*`、`qos-*`；已有 6 个 FT 重构 |

UNC-D1～D8 加 F0 中的 9 项，覆盖**全部 147 个 `WSFD-102*`～`WSFD-109*` Feature**。

### 4.6 UNC-E：切片、NRF/NF 服务与短消息（全部 `WSFD-110*`～`WSFD-130*`）

| 批次 | 精确范围 | 业务对象链 |
|---|---|---|
| UNC-E1 | 全部 `WSFD-110*` | NSSAI/切片选择、切片模式与相关策略；与 PCC/计费域只读复用 |
| UNC-E2 | 全部 `WSFD-111*`、`WSFD-112000` | NRF 基本功能、运维、NF 认证 |
| UNC-E3 | `WSFD-113* - {113001, 113002, 113006, 113009}`、全部 `WSFD-114*` | NF 发现/选择、NRF 容灾；`WSFD-113011` 在此按完整簇处理 |
| UNC-E4 | 全部 `WSFD-130*` | 短消息与 SMSF 容灾 |

UNC-E1～E4 加 F0 中的 4 项，覆盖**全部 22 个 `WSFD-110*`～`WSFD-130*` Feature**。

### 4.7 UNC-F：业务演进、IoT、专网、发布与跨域（全部 `WSFD-201*`～`WSFD-990*`）

| 批次 | 精确范围 | 业务对象链 / 依赖 |
|---|---|---|
| UNC-F1 | 全部 `WSFD-201*`、`WSFD-202* - {202003}` | 语音/移动性、CHR、HTTP 头压缩 |
| UNC-F2 | 全部 `WSFD-205*`、全部 `WSFD-206*`、全部 `WSFD-207*` | 网关选择、信令控制、网络共享；与接入/移动性线串行 |
| UNC-F3 | `WSFD-209* - {209001,209205}`、全部 `WSFD-210*`、`WSFD-211* - {211002}`、全部 `WSFD-213*` | 可靠性、超高带宽、位置/业务感知策略、GW-U 隔离；已有 `211001/211005/211009/211101` 重构，计费/PCC CT 只能串行维护 |
| UNC-F4 | `WSFD-214000, WSFD-214101` | 分层 NRF；`214000` 无概述，必须完整簇准入 |
| UNC-F5 | 全部 `WSFD-215*`、全部 `WSFD-216*`、全部 `WSFD-217*`、`WSFD-990005` | NB-IoT/eMTC、PSM/eDRX、限速、保活、RedCap；与 UNC-C5 串行，防止 IoT 步骤重复造 CT |
| UNC-F6 | `WSFD-219000`、全部 `WSFD-220*`、全部 `WSFD-221*` | License/安全隔离、IMR 上报、VoNR 恢复；`219000` 无概述，完整簇准入 |
| UNC-F7 | 全部 `WSFD-223*`、`WSFD-224* - {224101,224102,224103,224104,224105}`、`WSFD-225* - {225001}` | 专网/漫游分流、5G LAN；复用会话/地址/UPF 选择 CT，但由集成者维护跨域差异 |
| UNC-F8 | `WSFD-227102`、全部 `WSFD-228*`、全部 `WSFD-230*` | 灰度拨测、跨域业务、UE Logo/RFSP；上线/回退流程不与业务配置 CT 混用 |

UNC-F1～F8 加 F0 中的 17 项，覆盖**全部 144 个 `WSFD-201*`～`WSFD-990*` Feature**。

---

## 5. 每个实际构建批的工作契约

每次向构建 Agent 派发 Feature 批时，统一使用 [UNC特性与步骤Task构建提示词](UNC特性与步骤Task构建提示词.md)。该提示词是本文“输入获取与构建 pass”的可直接执行版本；派单方只填写批次、Feature Code 与 CT 所有权边界。

### 5.1 批次大小和顺序

- 领域批下的实际构建批以 3–6 个相同对象链 Feature 为宜，约 25–45 篇 Feature md；超过 12 篇 md 或有多套激活方法的重型 Feature 单独批，或最多与 1–2 个紧密 Feature 同批。
- 先构建本域中最复杂、场景最全的 Feature，再让后续同域 Feature 复用已发现的 CT；但复用的 CT 场景差异必须回填，不得只在 FT 里描述。
- 并行仅限 CT 所有权域不同的批。任何批都不得并发重生 `_index.md`。

### 5.2 只读准入（信息不足不臆造，仍须落盘）

#### 构建 Agent 输入协议（每个实际批次都必须遵守）

构建 Agent 不能只看概述、旧 FeatureTask 或某一个“激活”页面。对分配的每个 `{feature_code}`，按以下顺序获取输入：

| 输入 | 必读位置 | 必须取得的信息 | 用途 |
|---|---|---|---|
| **Feature 静态文档簇** | `三层图谱资产/Feature/UNC/20.15.2/UNC@Feature@{feature_code}/*.md` 的**全部** md | 概述、操作步骤、数据规划、任务脚本、激活/配置、实现原理/参考信息中承载的配置命令；完整的场景、对象、命令顺序、分支、参数和值 | FeatureTask 的唯一常规业务来源；先还原每种激活方法的命令时间线 |
| **AtomTask** | 上述文档簇实际出现的每条配置类命令，对应 `三层图谱资产/AtomTask/UNC/20.15.2/UNC@AtomTask@{CMD}.md` | 配置方法字典、允许取值、决策点、约束；核实 Feature 实际 `param=value` 是否可接受 | FT/CT 的底层编排对象和参数准入；只确认文件存在不算通过 |
| **步骤复用库** | `三层图谱资产/CompoundTask/UNC/20.15.2/_index.md`，以及命中候选的 `UNC@CompoundTask@*.md` 全文 | `command_set`、组成 atom、步骤目标/对象链/顺序、已有引用方的场景差异 | 先判定复用、reference 或新建 CT；不得只按名称或 Jaccard 复用 |
| **已有同 ID FeatureTask** | `三层图谱资产/FeatureTask/UNC/20.15.2/UNC@FeatureTask@{feature_code}.md`，仅当该文件存在 | 历史流程、已引用 CT、遗留差异；同时检查其与现行 v0.17 的差距 | 作为迁移线索，**不是权威输入**；最终流程必须回到完整 Feature 文档簇重建 |
| **命令层** | 参数争议或 AtomTask 描述不足时，读取 `三层图谱资产/Command/UNC/20.15.2/UNC@MMLCommand@{CMD}.md` | 命令静态真相、参数说明、notes/规格 | 仅用于理解或定位 Atom 冲突；不把静态参数表复制进 FT/CT |
| **原始产品文档** | `output/UNC 20.15.2 产品文档(裸机容器) 05/` 下相关文档 | Feature 文档簇确实缺失的必要顺序、参数、取值或约束 | **例外输入**：仅在 Feature 簇无法回答必要问题时读取；交付必须记录回查原因、文件和结论 |

输入边界的优先级是：**Feature 文档簇 > AtomTask/CT（动态编排与准入）> 命令层（静态澄清）> 原始产品文档（例外回查）**。原始文档不能替代 Feature 文档簇，更不能据此绕过缺失 AtomTask。

每个 Feature 在任何 Task 文件写入前，构建 Agent 必须先输出一份只读“输入与准入记录”：读到的 Feature md、识别到的配置命令及其 AtomTask 路径、候选 CT、是否使用原始文档例外。该记录随批次交接保存；它不是额外资产层，也不能替代 FT/CT 正文中的场景差异。

每个 Feature 先输出如下预检记录：

```text
Feature code / 完整 Feature md 清单
激活方法或配置场景
配置类命令（ADD/MOD/SET/DEL/RMV/LOD/持久化 STR）
命令对应 AtomTask 是否存在
Feature 每个 param=value 是否可在 AtomTask 配置方法中核到
候选 CompoundTask、command_set Jaccard、相位同义判断
结论：ready / information-limited / foundation / Atom 冲突 / 数据规划待补
```

- Feature 文档簇是常规唯一业务输入；只有它不能回答必要的顺序、参数或约束时，才回查原始产品文档，并在交付中记录原因、文件和结论。
- Feature 实例与 Atom 字典冲突时，保留 Feature 实际流程和值，在 FT 标记“冲突/待 Atom 更正”；不能伪称合法。
- Feature 未给出最小参数集时，标“待数据规划补齐”；不能虚构默认值。
- 完整簇只有能力/责任描述而没有可恢复命令链时，写信息受限 `draft` FT：不建 CT、不编排 Atom，流程与参数表明确“信息不足，待补 MML/顺序/实例”。不得因为文档少把它误写为 foundation，也不得静默不落盘。

### 5.3 构建 pass

1. 从完整 Feature 簇还原每种激活方法的命令时间线：对象、顺序、全局基线、可选分支、`INHERIT`、重复命令和每次刷新所在相位都必须保留。
2. 写 FeatureTask：配置概览、混合编排配置流程、逐场景“激活方法与参数差异”、参数核对、决策点、约束、边。每个 Feature 仅一份 FT。
3. 决定 CT：`<3 distinct` 配置 atom 直引；达到阈值后才以“配置目标 + 对象链 + 共享命令相对顺序”判断是否是稳定步骤。Jaccard >= 0.75 且三项至少两项同义才复用。
4. 新建 CT 时同时写 `command_set`、组成 atom、典型脚本、步骤位置、场景差异、反链；复用 CT 时将本 Feature 实际执行/省略命令子集、参数值、对象、相位回填。
5. 构建者对跨域 CT 只提交待整合回填清单；不得越权直接修改。

---

## 6. UDG 式对抗审查与集成门禁

### 6.1 每批闭环

```text
准入矩阵
  → 构建者：一个 Feature 完整 pass（FT + 0..N CT）
  → 构建者预审
  → 独立审查者：只读对抗审查
  → 构建者修复
  → 独立审查者聚焦复审（Critical/High = 0）
  → 唯一集成者：共享 CT 回填 + _index 重生 + 结构审计
  → 批次交接与下一批
```

### 6.2 构建者预审

构建者自检字段/ID/路径、独立 `## 边`、引用真实性、CT 反链、调测剥离、防 Atom 平铺、参数核对，并预先检查：

- Feature 配置命令是否可由 FT/CT/显式省略还原；
- Feature 的每个实际 `param=value` 是否沉淀在激活差异、CT 场景差异或参数核对；
- Task 中的参数是否可反向追到 Feature 文档簇；
- foundation 是否真的无独立 UNC 配置，而不是“文档少”。

### 6.3 独立对抗审查（硬前置）

审查者必须不是构建者、只读且不改文件。输入为完整 Feature 簇、相关 AtomTask、CT/index、SOP 和 `check.md`。逐场景审查：

- 命令时间线、对象、分支、基线、`INHERIT`、多次 `REFRESHSRV` 的次数和位置；
- 每个实际参数值与 AtomTask 字典的匹配；
- CT 的 `command_set`、组成边、被引用于反链、场景差异是否吞掉特性专属差异；
- 是否臆造未被 Feature 实演的变体，或把 DSP/LST/EXP/STP 等调测查询命令写入流程；
- B1 命令闭包、B2 参数闭包、B3 反向追溯、B4 信息源边界对账。

问题必须带对象 ID、文件与行号、违反规则、Feature/Atom 证据、严重级（CRITICAL/HIGH/MEDIUM/LOW）和返工方向。任何 CRITICAL/HIGH 未清零，批次不得集成。

### 6.4 唯一集成者

仅在独立审查 CRITICAL/HIGH 为 0 后：

1. 合并跨域 CT 的待回填清单并核对反链；
2. 重生 `CompoundTask/UNC/20.15.2/_index.md`；
3. 运行 `audit_compound_feature.py --nf UNC`；
4. 记录审查结论、阻塞 Feature、待补 Atom、CT 变更和未消除风险到 `handoff/UNC-{batch}-交接.md`。

当前自动脚本主要覆盖结构和引用。命令/参数闭包、参数语义、时序、分支和信息源边界必须继续由独立人工对抗审查把关，不能因脚本绿灯而跳过。

---

## 7. 开工顺序与完成定义

执行顺序固定为：

1. `P0`：38 个既有 CT 可复用化并生成索引；
2. `UNC-F0`：105 个 foundation 候选的逐簇核验与构建；
3. `UNC-A`、`UNC-B`、`UNC-C`：建立 IP/会话/接口/计费/AAA 的基础复用面；
4. `UNC-D`：语音、安全、IPv6、UPF、PCC/ADC 大域；其中 D8 与 C3/C4 串行；
5. `UNC-E`、`UNC-F`：NF 服务、业务演进、IoT、专网、发布与跨域；按 CT 所有权域串行、其余可并行；
6. 全量收口：确认 470 个 Feature 各有一个符合现行 SOP 的 FT、所有已引用 CT 反链/索引一致；信息受限 Feature 均明确待补 MML/对象顺序/参数实例和后续 Atom 入口。

“全量完成”不等于每个 Feature 都有配置 CT：foundation FT、信息受限 draft FT、Atom 直引 FT 和含复用/新 CT 的 FT 都是合格产物；任何缺 Atom、MML、对象顺序或参数实例的 Feature 必须在其 FT 中明确待补范围，不能静默遗漏。
