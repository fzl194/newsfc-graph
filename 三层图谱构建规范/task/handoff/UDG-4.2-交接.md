# UDG 4.2 FeatureTask + CompoundTask 构建 · 交接

> **历史化标注（v0.17.0）**：本页为历史交接记录（进度/教训），**不作规范引用源**；规范疑问查 `task/SKILL.md`（Task 层唯一权威）。
> **接手 Agent 只读此页 + 文中引用的 SOP/资产即可继续。** 最后更新：2026-08-06（19 批 / **§4.2 全域完成**）。
> 姐妹篇：[`UDG-4.1-交接.md`](./UDG-4.1-交接.md)（4.1 域）。
> 本轨覆盖批次构建计划 **§4.2（GWFD-110~113 业务识别/应用控制/物联网）**。

---

## 0. 现状速览（先读这段）

- **进度**：本轨已完成 **19 批 = 82 个 FeatureTask（⚠️磁盘实测 GWFD-110~113 共 **105 FT**，多 23 为早期会话已建未登，见 [CR-20260807-001](../change-requests/CR-20260807-001-Task层信息可追溯性与SOP权威统一.md) T1 对账） + 1 新建 CompoundTask（`edrx-buffer-tuning`）**；另复用回填 4 个跨域 CT（filter-chain/charging-core-trio/userprofile-rule-attach/session-pcc-policy，+110251/110252/112000/112001）。**★ §4.2 全域（GWFD-110~113 业务识别/应用控制/物联网）Task 层构建完成 ✅**
- **审计**：**本轨域 audit = 0 fail**（D0–D4 全过）。全局 audit 现有 **1 个**并发 fail：D4 `GWFD-020423→IPFD-014000`（IPFD 域 Feature 源全无，待 IPFD 域建，本轨越权不建）；D3 `ipv6pd-prefix-flag` **已清**（2026-08-07 反链回填 +020401）。
- **跨层修复（2026-08-07，用户授权"全面修改"）**：① 110501/502 概述 License 码错已修（LKV6CKTSOU0/SIN0→LKV3G5KTSO01/KTSI01，control_item 同步）；② 110921 License 对应特性码错位已修（110911→110921）；③ ipv6pd-prefix-flag 反链回填（D3 移动靶清，全局 fail 2→1）；④ 计划 §2 补登本轨 19 批/82 FT + 未登早建；⑤ atom 缺口根因记录（坑11：MMLCommand 目录不存在，4 命令无命令层 md，待命令层补）。**未修（交相应层）**：atom 缺口（待命令层 md）、GWFD-020423→IPFD-014000（待 IPFD 域建）、License NF 命名差异/子集（110582/110941/111283/111311-313/111701，交 License 层决策 applicable_nf）、SSUBIGFLOWCTRL 单位/111283 默认值（源不一致待命令层核）。
- **下一批**：**无——§4.2 全域 Task 层构建完成**。
- **质量**：82 FT 全部经独立 subagent 对抗审查（每批 CRITICAL/HIGH=0 放行）+ 1 次全量跨批次复审 + 1 次证据驱动盘点。当前无未决 Task 层问题。

---

## 1. 任务与闭环

### 1.1 任务
把 4.2 节 Feature 的"配置方法"沉淀成 Task 层资产（FeatureTask + CompoundTask），遵循新格式（基准 `GWFD-110201`）。

### 1.2 角色（用户授权的闭环）
**构建 → 独立 subagent 对抗审查 → 返工至 CRITICAL/HIGH=0 → 聚焦复审 → 集成**。审查由**独立 subagent**（非构建者、不改文件、用 `UDG特性与步骤Task构建提示词.md` 末对抗评审提示词）；集成由本轨做。

### 1.3 步骤所有权域（计划 §3）
- 本轨可直改既有 CT：`sa-protocol-identify-chain`、`header-enrich`、`ipfarm-*`、`smart-redirect-*`、`cf-*`、`icap-*`。
- **只读**（复用需新增场景差异时，输出**待整合回填清单**，集成期本轨合并）：`filter-chain`/`charging-core-trio`/`rule-userprofile-bind`/`userprofile-rule-attach`/`pcc-*`/`qos-*`/`bwm-*` 等计费·PCC·QoS 域 CT。

### 1.4 构建单元
**一个 Feature 一个 pass**：同 pass 同时产出 1 FT + 0~N CT，不拆两条流水线。

---

## 2. 接手第一步（3 个动作）

1. **读 SOP**（§3 优先级表前 5 项）——尤其 `UDG特性与步骤Task构建提示词.md`（构建+对抗审查提示词）。
2. **查构建模式库**（§5）：按 Feature 簇形态（薄/富/双方法/atom 缺/信令驱动）选 FT 形态。
3. **跑一次 audit 确认基线**：`python 三层图谱构建规范/task/scripts/audit_compound_feature.py --nf UDG --version 20.15.2`（确认本轨 0 fail，记下全局 fail 移动靶现状）。

---

## 3. 权威 SOP 与资产路径

工作目录：`D:\mywork\KnowledgeBase\NewSFCGraph`。网元 UDG，版本 20.15.2。

| 优先级 | 文件 | 用途 |
|---|---|---|
| 1 | `三层图谱构建规范/task/UDG特性与步骤Task构建提示词.md` | **构建提示词 + 对抗评审提示词 + 交付/自检 7 项** |
| 2 | `三层图谱构建规范/task/UDG领域批次构建计划.md` | §4.2 批次地图、§3 所有权域、§5 集成闭环 |
| 3 | `三层图谱构建规范/task/SKILL.md` | Part B（compound+feature_task 一并构建、§B.3-B.7、§B.6 foundation 范式）|
| 4 | `三层图谱构建规范/task/字段定义.md` | YAML 8 字段 |
| 5 | `三层图谱构建规范/task/check.md` | 审查项两表 + 自动化 D0-D4 盲区 |
| 6 | `三层图谱构建规范/task/template/feature_task.md.tpl`、`compound.md.tpl` | 正文骨架 |

**资产路径**：
- Feature 源：`三层图谱资产/Feature/UDG/20.15.2/UDG@Feature@GWFD-{code}/*.md`（簇内多文档：概述/激活/调测/实现原理/参考信息）
- AtomTask：`三层图谱资产/AtomTask/UDG/20.15.2/UDG@AtomTask@{CMD}.md`（**文件名含空格**，如 `SET LICENSESWITCH.md`）
- CompoundTask：`三层图谱资产/CompoundTask/UDG/20.15.2/UDG@CompoundTask@{name}.md` + `_index.md`
- FeatureTask：`三层图谱资产/FeatureTask/UDG/20.15.2/UDG@FeatureTask@GWFD-{code}.md`
- License：`三层图谱资产/License/UDG/20.15.2/UDG@License@{code}.md`

**格式基准样例**：
- `UDG@FeatureTask@GWFD-110201.md` — 富 FT 范本（`## 激活方法与参数差异` 7 列表 + `## 参数核对` + 时序约束）
- `UDG@FeatureTask@GWFD-110103.md` — License 网关最小 FT 范本
- `UDG@FeatureTask@GWFD-110493.md` — foundation FT 范本（§5 模式 4）
- `UDG@CompoundTask@edrx-buffer-tuning.md` — 本轨新建 CT 范本（4 atom，3 特性共用，场景差异表）

**记忆**（`~/.claude/projects/D--mywork-KnowledgeBase-NewSFCGraph/memory/`）：
- `udg-42-featuretask-build-state.md` — 本域进度+模式（本交接的精简镜像）
- `glob-tool-unreliable-use-grep.md` — **Glob/for-loop ls 不可靠，文件存在性用 `find`**（坑10）
- `script-hygiene-generalizable-only.md` — `task/scripts/` 只留可泛化脚本

---

## 4. 已完成产物清单（82 FT + 1 新 CT，19 批）

### 4.1 CompoundTask
| CT | 性质 | 内容 |
|---|---|---|
| `edrx-buffer-tuning` | ★**新建**（110-L，110-M 回填 +110661） | eDRX 下行缓存调优，4 atom（SET APNDLBUFTIME/APNDLLTBUFFER/GLBDLBUFTIME/GLBDLLTBUFFER），被引用于 110601/110641/110661 |
| `charging-core-trio` / `filter-chain` / `userprofile-rule-attach` / `session-pcc-policy` | **回填**（110-E + 112-A） | 各 +110251/110252（110-E）+ 112000/112001（112-A）场景差异 + 被引用于（跨域 CT，本轨只读，集成期手工回填） |

### 4.2 FeatureTask（按批次）
| 批次 | Feature（数） | 类型 | 关键点 |
|---|---|---|---|
| 110-A | 110102~110107（6）| License 网关（110102 +软参 BYTE53）| SA 协议基础；软参选 SET SOFTPARA（坑1）|
| 110-B | 110131~110136（6）| License 网关 | SA 业务分类Ⅰ；110134 无源约束已删（坑2）|
| 110-C | 110137~110142（6）| License 网关 | SA 业务分类Ⅱ；逐特性差异（坑3）|
| 110-E | 110251/110252（2）| **富 FT，复用 3 跨域 CT** | HTTP3 Host 识别/分析；SET SACOMMONPARA 门控；CT 二选一选 userprofile-rule-attach |
| 110-G | 110402/110403（2）| License 网关 | DNS/HTTP 计费防欺诈（020301 增强）|
| 110-H | 110481/482/493/501/502（5）| 4 License 网关 + **1 foundation**（110493）| NF 可靠性/采集/弹性扩缩容；配置在 VNFM/部署侧；双 LICITEM（110481/482）|
| 110-I | 110551~110560（10）| License 网关 | 5G 超高带宽；5 对 UHBB/UHBA ×5 速率档；§8 预测严重失准（带宽由 SMF/PCF 协商）|
| 110-J | 110581/110582（2）| License 网关 | 超高带宽 TCP/UDP 质量分析；110582 License 子集待核（§8 坑8）|
| 110-K | 110601/606/607/611/612（5）| 富 FT（激活驱动）| NB-IoT eDRX/数据/限速；110601 APNDLLTBUFFER >15s 冲突；license-access-prep 不复用（BWM 域）|
| 110-L | 110641/646/647（3）| 富 FT + **抽 edrx-buffer-tuning CT** | eMTC eDRX；110641 NORMALUSER 上限 15s 结构性冲突；回填 110601 |
| 110-M | 110661/110662（2）| 110661 富 FT（+CT 回填）/ 110662 License 网关 | 5G eDRX/RedCap；110662 15md 全是信令非配置 |
| 110-N | 110910/921/941（3）| 富 FT（110921 **双激活方法**）| 5GC流程/TWAMP/IPSQM；110921 Full/Light；110941 License 子集冲突 |
| 111-A | 111251/252/253（3）| License 网关 | ISSU 在线升级三件套；111251 SET UPGSTEP atom 缺口（坑10 范式）|
| 111-B | 111201/283/284/286（4）| 111283 License+SSUAGINGCFG / 余 License 网关 | 智能采集/加速；111283 License NF 不一致（PCEF/TDF-U vs UPF）|
| 111-C | 111301~111313/111315（14）| 12 License 网关 + 111302 +SET RPTGLBPARA + 111308 atom缺口 + 111311/312/313 子集冲突 | 智能分析上报族；§9 预判"CT 候选"**失准**（实际薄批次，不抽 CT）；111314 无簇不存在；111308 SET VOLTEONEWAYSIL atom 缺、SMF 侧命令不编排 |
| 111-D | 111331/111701（2）| 111331 **foundation**（黄金指标被动上报）/ 111701 富FT（License+SSUBIGFLOWCTRL+USRREALLOCNTY+可选vTCP_OPT） | 111331 无License/无MML；111701 License NF命名差异[PCEF,TDF-U]vs UPF、CCOFLOWRATE 单位+缺省值源不一致、ADD FLOWFILTER 空过滤器与 atom critical 张力，均标"冲突-待核" |
| 111-E | 111401/111402（2）| License 网关（对称）| 5G超高带宽承载 1Gbps/2Gbps 保障；§交互"不涉及"无依赖；License [PGW-U,UPF] 精确匹配；下行带宽 SMF/PCF 协商非 UDG MML |
| 112-A | 112000/001/002/003（4）| 112000 富FT(3CT回填+IMSBYPASS+REFRESHSRV 3相位) / 112001 无License配置型(3CT) / 112002 License+FLOWLETPARA / 112003 License网关(配置指向外部) | 5G-A/智网分支；112000/112001 命中 4 只读 CT（filter-chain/charging-core-trio/session-pcc-policy/userprofile-rule-attach）回填；112000 SET REFRESHSRV 3 相位；112001 无 License（PCC 配置型）；112003 配置在智家随行解决方案文档 |
| 113-A | 113005（1）| License 网关（薄）| 媒体中继；依赖 110101(SA-Basic) + 互斥 111251/010296/110662；硬件媒体中继板部署态；大量业务/部署约束非 UDG MML |

**早建（非本轨）**：110-D（110201/202/203）、110-F（110321）、110404。

> 所有批次均独立 subagent 对抗审查 CRITICAL/HIGH=0 放行。发现的 CRITICAL/HIGH 均已修（110251 verdict、110501/502 LICITEM、110647 漏编 ADD APN、110910 FDMAXNUM 措辞、111201 IPsec wikilink 错指 等）。

---

## 5. 构建模式库（核心：按簇形态选 FT 形态）

**开建每批第一步**：`find 三层图谱资产/Feature/UDG/20.15.2/UDG@Feature@GWFD-{code}/ -maxdepth 1 -name "*.md" -type f` 判定薄/富（坑10：勿用 Glob/for-loop ls）。再按下表选形态。

| 模式 | 触发条件 | FT 形态 | 范例 |
|---|---|---|---|
| **1. License 网关** | 簇仅概述 / 激活仅 `SET LICENSESWITCH`；§可获得性"加载 License 即可用" | 配置流程单步 SET LICENSESWITCH；不抽 CT；不 wikilink CT；依赖以 `[[FT]]` 表达 | 110103, 110402, 110551~560, 110581/582 |
| **2. License + 软参** | 概述提"BYTExx 置N" | + `SET SOFTPARA`（字节级，非 SOFTPARAOFBIT，坑1）| 110102 |
| **3. License + ADD APN** | 速率控制等需配 APN 实例 | + `ADD APN`；门限在控制面（PGW-C/MME）不入流程 | 110611/612/646/647 |
| **4. foundation** | 无 License、无 UDG MML（能力底座/被动响应/MAE 采集）| `status: foundation`；引子明示"无需License/无MML"；配置流程骨架指向外部；**不建激活方法表/参数核对**；边只有对应特性 | 110493（对齐 GWFD-010101）|
| **5. 富 FT + 复用既有 CT** | 簇有激活文档；命中有 `command_set` 的 CT | 编排既有 CT + 单 atom 混合；双向回填被引用于 + 场景差异 | 110251/252（3 跨域 CT）|
| **6. 富 FT + 抽新 CT** | ≥3 内聚命令被 ≥2 feature 共用（动态阈值：单用不抽，第 2 个 feature 加入才抽）| 抽 CT + 回填先建 FT；CT 场景差异承载参数变体 | 110601/641/661 → edrx-buffer-tuning |
| **7. 双/多激活方法** | 激活文档有多个场景（命令子集不同）| **激活方法表分多行**（不压缩为"按需配置"，硬规则）；共享前置 + 分叉 | 110921 TWAMP Full/Light |
| **8. atom 缺口** | 激活/概述提某命令但 atom 文件不存在 | plain-text 提及（反引号，**不 wikilink** 免 D2）+ 信息源边界显眼单列 atom 缺口；不入配置流程/编排边 | 110482(BYPASS)/111251(UPGSTEP)/111201(FEHEARTBEAT) |
| **9. 信令/工具驱动非 UDG 配置** | 簇多 md 但全是 AMF/SMF 信令流程 / 升级工具文档；§可获得性"加载License即可用"+ 参考信息"不涉及MML" | License 网关；实际流程（升级/拨测/采集/保障）声明经工具/信令非 UDG MML，不编排 | 110662, 111-A, 111284/286 |

### 5.x 通用 FT 骨架（除 foundation/模式4）
`# 标题` + 引子 → `## 配置概览` → `## 配置流程` → `## 激活方法与参数差异`（**7 固定列**）→ `## 参数核对` → `## 决策点` → `## 约束` → **独立 `## 边`**。信息源边界作 blockquote 附在约束末（全轨一致，勿改独立 section）。

---

## 6. 构建规则（硬性）

- **YAML**：`id/type/name/name_zh/nf/version/ref/status`；ref→`UDG@Feature@{code}`。
- **激活方法表 7 列**（不得更名/省列）：`激活方法/条件 | 配置相位 | 执行的 Task（[[CompoundTask]] / [[AtomTask]]） | 省略的 Task | 关联 AtomTask | 相对基线的参数差异（参数=值） | 目标对象与生效说明`。表头第 3 列用 wikilink 式 `[[CompoundTask]] / [[AtomTask]]`（非纯文本）。
- **参数合法性**：每实参逐项核 atom 字典（范围/枚举），不只验文件存在。冲突→标"冲突/待 Atom 更正"；缺值→标"待数据规划补齐"；**严禁真冲突标"通过"**（坑9）。
- **verdict 首词合规**（坑9）：冲突状态 verdict 首词必须=冲突；不得"通过"+存疑尾注。
- **时序不泛化**：按激活脚本原相位编排（如 SET REFRESHSRV 在脚本何处就何处，不挪全局收尾）。
- **调测剥离**：配置流程只含 `ADD/MOD/SET/DEL/RMV/LOD/持久化 STR`；`DSP/LST/EXP/STP/探测 STR` 不入（LST DFTPROTGRP 仅作"可查询"文字说明）。
- **反链卫生（D3）**：FT 编排某 CT ↔ 该 CT 被引用于含该 FT，双向回填。**薄 FT 不在正文 wikilink 不编排的 CT**（gen_compound_index 会污染）。
- **引用粒度**：统一 `[[{nf}@{Type}@{local}]]` 双方括号、md 级（无章节锚）；无证据段。
- **信息源边界**：薄 FT（概述单篇）必须声明"基于概述单篇，待激活文档补齐"；atom 缺口/源不一致在此显眼单列。

---

## 7. 已知坑 / 教训（11 条，重点）

1. **软参命令选型**：`BYTExx 置N` → `SET SOFTPARA`（字节级）；只有源明示"第N位"才用 `SET SOFTPARAOFBIT`。
2. **无源约束**：LST DFTPROTGRP 说明/特征库更新约束/计费措辞/应用限制**逐特性不同**——只写概述里实际有的；概述"无应用限制"不得写特征库更新约束（110134 已删）。
3. **逐特性差异核对清单**：LICITEM 与 §License 1:1（小心近似码 110133=LKV3G5EMAL01 非 EMAIL）、章节名引用只引真实 `####` 标题（不造"§原理概述说明"）。
4. **Glob 不可靠**：文件存在性/枚举一律 Grep/Read（见坑10 升级）。
5. **python 在本环境可用**：bash 跑 `audit_compound_feature.py` 正常（与 4.1 交接相反）。
6. **信息源边界/薄批次**：概述单篇构建的 FT 若源有更多配置会漏——每个声明"待激活文档补齐"，不虚构。富批次必须读激活文档。
7. **计划 §2 已补登**（2026-08-07）：`UDG领域批次构建计划.md` §2「已建」原漏登 110-D/F/110404 + 本轨批次，已补登未登早建（110201/202/203、110321、110404）+ 本轨 19 批/82 FT 段。
8. **License 跨层核对**（见 §8 专节）：建 License 网关 FT 必核 license_code（须有资产文件）+ applicable_nf（子集=真风险）。
9. **verdict 标签合规**：真冲突首词必须=冲突，不软化；atom 决策点+critical 是强证据，FT 不得用"按 X 场景"软化 atom 通用约束。
10. **文件存在性以 find 为准**（110647 CRITICAL 教训）：for-loop `ls`/Glob 都会漏显（中文文件名/截断/缓存）；簇枚举一律 `find {dir} -maxdepth 1 -name "*.md" -type f` + 与概述 §边 子文档清单交叉核。
11. **atom 缺口根因 = 命令层 md 缺失**（跨层遗留，2026-08-07 核实）：`三层图谱资产/MMLCommand/UDG/20.15.2/` 目录不存在，4 命令（SET VOLTEONEWAYSIL/FEHEARTBEAT/FEHBRESET/UPGSTEP）无命令层 md → atom 无参数字典可核，按 SOP §1 规则12 不补造 atom；FT 用 plain-text 提及 + 信息源边界单列（111308/111201/111251）；待命令层补 md 后建 atom 回填。

---

## 8. License 跨层核对（坑8 专节）

**建 License 网关 FT 时，除核 LICITEM 与概述 §License 1:1，必核 License 对象**：
- **license_code 必须有对应 License 资产文件**（否则 SET LICENSESWITCH 失败）。
- **applicable_nf 与概述 §适用NF 比对**：子集（License 缺 NF）= **真风险**，FT 必须落约束"待核"；超集（License 多 NF）= 良性，集中记录；NF 命名体系差异（旧域 PCEF/TDF-U vs 5G UPF）= 待核。
- **规律**：超集/子集差异都在 `control_item_type=资源` 的 License（功能型全精确匹配）。

**全量案例表**（已发现，非 audit 项，待 Feature/License 层对齐）：

| FT | 类型 | 详情 | 处置 |
|---|---|---|---|
| 110501/110502 | **license_code 错（CRITICAL，全修 2026-08-07）**| 概述 LKV6CKTSOU0/SIN0→LKV3G5KTSO01/KTSI01（control_item 81202580/8120258→81203221/81203222）| ✅ FT + 概述均修 |
| 110582 | **子集（真风险）**| License [PGW-U,UPF] 缺 SGW-U | ✅ FT 落约束"待核" |
| 110941 | **子集（真风险）**| LKV3G5IPSM01 [SGW-U] 缺 UPF | ✅ FT 标"冲突-待核" |
| 110921 | **特性码错位（已修 2026-08-07）**| LKV3G5TWMP01"对应特性"110911→110921（License 资产 2 处）| ✅ License 资产已修 |
| 111283 | **NF 命名差异**| LKV3G5IBIC01 [PCEF,TDF-U] vs 概述 UPF | FT 标"冲突-待核" |
| 111311/111312/111313 | **子集（真风险）**| LKV3G5SARS01/SIAR01/RTSR01 [SGW-U,PGW-U] 缺 UPF（概述含 UPF）| ✅ FT 标"冲突-待核" |
| 111308/111315 | **超集（良性）**| LKV3G5VOSR01/VRSR01 [SGW-U,PGW-U,UPF] vs 概述 SGW-U/PGW-U(308)/UPF(315) | 集中记录，不阻塞 |
| 111701 | **NF 命名差异**| LKV3G5OBCCS1 [PCEF,TDF-U] vs 概述 UPF | FT 标"冲突-待核"（同 111283 范式） |
| 110402/403/601/606/607/611 | 超集（良性）| License 多 NF | 集中记录，不阻塞 |
| 110481 | 无基准 | 概述无 §适用NF | 待 Feature 层补 |

---

## 9. 批次地图（剩余按此推进）

> ⚠️ 每批开建前必须 `find` 簇 + 读概述/激活判定形态（§5 模式库）——下表"类型"是预判，§8 预测对 UDG 配置**反复失准**（110-G/I/L/M/111-A 均失准）。

| 批次 | Feature | 状态 | 备注 |
|---|---|---|---|
| 110-A/B/C/E/G/H/I/J/K/L/M/N | 见 §4.2 | ✅ 完成 | 47 FT + edrx-buffer-tuning CT |
| 111-A | 111251~111253 | ✅ 完成 | ISSU 三件套 |
| 111-B | 111201/283/284/286 | ✅ 完成 | 智能采集/加速 |
| 111-C | 111301~111313/111315 | ✅ 完成 | 智能分析上报族（14 FT，111314 无簇）；§9 预判 CT 候选失准，实际薄批次不抽 CT |
| 111-D | 111331/111701 | ✅ 完成 | 111331 foundation（黄金指标被动上报）/ 111701 富FT（拥塞小区分析，License NF命名差异+CCOFLOWRATE源不一致+FLOWFILTER atom张力） |
| 111-E | 111401/111402 | ✅ 完成 | 5G超高带宽承载 1Gbps/2Gbps 保障（对称 License 网关）；§交互"不涉及"；License 精确匹配；下行带宽 SMF/PCF 协商非 UDG MML |
| 112-A | 112000~112003 | ✅ 完成 | 5G-A/智网分支（4 FT）：112000 双故障Bypass富FT(3CT回填+IMSBYPASS+REFRESHSRV 3相位) / 112001 Proxy漫游无License配置型(3CT) / 112002 License+FLOWLETPARA / 112003 License网关(配置指向智家随行解决方案) |
| 113-A | 113005 | ✅ 完成 | 媒体中继（薄 License 网关）；依赖 110101(SA-Basic) + 互斥 111251/010296/110662 |
| **★ 全域完成** | GWFD-110~113 | ✅ **§4.2 全域 Task 层构建完成** | 19 批 / 82 FT + 1 新 CT（edrx-buffer-tuning）+ 4 跨域 CT 回填 |

**汇总**：本轨完成 19 批（82 FT + 1 新 CT）；早建未登 3 项（110-D/110-F/110404）；**★ §4.2 全域（GWFD-110~113）Task 层构建完成 ✅**。剩余仅跨层遗留（License NF 命名差异/子集待核、atom 缺口、Feature 层源不一致——见 §8 + 各 FT 信息源边界）。

**111-C 已完成（2026-08-06）**：实际为**薄批次**（§9 预判"CT 候选"**失准**，再次印证 §8 预测不可靠，须 find 簇+读概述判定）——111301~111313/111315 共 14 FT（111314 无簇不存在），全概述单篇，**不抽 CT**：12 纯 License 网关 + 111302(License+SET RPTGLBPARA 抽样率，atom NF=UPF 与特性 NF 张力已记) + 111308(License+SET VOLTEONEWAYSIL atom缺口 + SMF 侧 ADD APNPFCPCMPT/SET PFCPPVTEXT 不编排)。坑8：111311/312/313 License 子集（[SGW-U,PGW-U] 缺 UPF）标"冲突-待核"，111308/315 超集良性。SET RPTGLBPARA 仅 111302 单用未抽 CT（动态阈值）。111283 确为 111301 等基础（License 相关控制项列 7 项），但订阅/指标选择均由 CloudUDN 经订阅接口下发（非 UDG MML），无命令链可抽。

---

## 10. 审计与并发轨

- **本轨域 audit = 0 fail**。判定本轨干净看**本轨 82 FT 是否在 fail 列表**，不是看全局总数。
- **全局 audit 是移动靶**：多轨并发（4.1/4.3/IPFD 等）。当前全局 **1 fail** `GWFD-020423→IPFD-014000`（IPFD 域 Feature 源全无，待 IPFD 域建，本轨越权不建）。**2026-08-07 用户授权"全局移动靶清"**：已清 `ipv6pd-prefix-flag` D3 反链（CT 被引用于 +020401，全局 fail 2→1）；GWFD-020423→IPFD-014000 因 IPFD 域完全缺口无法本轨清，待 IPFD 域。
- 跑法：`python 三层图谱构建规范/task/scripts/audit_compound_feature.py --nf UDG --version 20.15.2`

**历史跨轨 fail**（已由各轨清零，记录备查）：4.3/IPFD atom 断链（IPFD-012001/2）、gre/ipsec/ipv6/mpls 反链（IPFD-010001/014003/015002/015004、010155）、本轨 ipfarm-redirect-chain←020253 D3（已去 wikilink 保语义修）。

---

## 11. 环境与工具

- 工作目录 `D:\mywork\KnowledgeBase\NewSFCGraph`；UDG 20.15.2；bash（Git Bash POSIX sh）；**python 可用**（坑5）。
- **Glob/for-loop ls 不可靠 → `find -name`/Grep/Read**（坑4/10）。
- 脚本（`task/scripts/`）：`audit_compound_feature.py`（D0-D4 结构审计，过≠全对）、`gen_compound_index.py`（重生 _index，仅 CT 变更或集成时跑）、`audit_atoms.py`。
- **闭环**（每批）：构建 → 独立 subagent 对抗审查 → 返工 CRITICAL/HIGH=0 → 聚焦复审 → 集成（有 CT 变更跑 gen_index，跑 audit 确认本批 0 fail）。
- **集成授权**：本轨是该批次唯一写入者时，CRITICAL/HIGH=0 后可跑 `gen_compound_index.py --nf UDG --version 20.15.2`。
