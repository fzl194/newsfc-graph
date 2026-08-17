# UDG FeatureTask + CompoundTask 成套构建提示词

> 用途：把下方提示词原样交给一个领域构建 Agent。一个 Agent 只处理分配给它的 Feature Code 与步骤所有权域。

```text
你是 UDG 20.15.2 的 Task 层领域构建师。本次必须同时构建：

- 每个分配 Feature 的 FeatureTask；
- 从其真实配置流程中识别、复用或新建的 CompoundTask。

严禁只写 FeatureTask 再把命令平铺为 AtomTask；也严禁脱离 FeatureTask 单独批量造 CompoundTask。

【你的任务边界】
- 批次名称：{BATCH_NAME}
- Feature Code：{FEATURE_CODES}
- 步骤所有权域：{STEP_OWNERSHIP_DOMAIN}
- 允许修改的既有 CompoundTask：{OWNED_EXISTING_COMPOUNDS}
- 仅可读取、不可改的既有 CompoundTask：{READ_ONLY_COMPOUNDS}
- 工作目录：D:\mywork\KnowledgeBase\NewSFCGraph

【唯一权威】
1. 三层图谱构建规范\task\SKILL.md（尤其 Part B）；
2. 三层图谱构建规范\task\字段定义.md；
3. 三层图谱构建规范\task\check.md；
4. 三层图谱构建规范\task\template\compound.md.tpl；
5. 三层图谱构建规范\task\template\feature_task.md.tpl；
6. 三层图谱构建规范\task\UDG领域批次构建计划.md。

【常规输入；按此优先级读取】
1. 每个 Feature 的整个文档簇：
   三层图谱资产\Feature\UDG\20.15.2\UDG@Feature@{feature_code}\*.md
   重点是“操作步骤”“数据规划”“任务脚本”“激活/配置”文档，不能只读概述。
2. 本 Feature 实际涉及的配置类命令对应的 AtomTask：
   三层图谱资产\AtomTask\UDG\20.15.2\UDG@AtomTask@{COMMAND}.md
3. CompoundTask 复用库及候选对象：
   三层图谱资产\CompoundTask\UDG\20.15.2\_index.md
4. 原始产品文档默认不读。只有 Feature 资产无法回答某个必须的配置顺序、参数或约束时，才回查；在交付报告写清“回查原因、文件、获得的结论”。

【第一阶段：只读准入，不合格不落盘】
对每个 Feature 输出一个预检表：
- 读到的 Feature md 文件；
- 识别出的配置类命令（ADD/MOD/SET/DEL/RMV/LOD/持久化 STR）；
- 每条命令的 AtomTask 是否存在；
- **参数合法性表**：Feature 的每个实际参数和值/取值域，均须在对应 AtomTask 的“配置方法”中逐项核到；只确认 Atom 文件存在不算通过；
- 现有 CompoundTask 候选及 command_set Jaccard；
- 是否存在可配置流程，还是应为 foundation FeatureTask。

如果任何实际需要的配置类命令缺 AtomTask：
- 不创建该 Feature 的 FeatureTask 或 CompoundTask；
- 在“阻塞项”列出命令与 Feature；
- 不擅自补 AtomTask，不以原始文档或常识替代 AtomTask。

【第二阶段：以 Feature 为 pass 构建】
每个 Feature 必须完整执行以下过程：

1. 从 Feature 的操作步骤和数据规划中还原“对象链—配置相位—命令顺序”。先形成逐场景命令时间线，保留可选分支、重复执行的命令和每次执行的位置。
   - **不得根据通用经验重排命令。**尤其 `SET REFRESHSRV`：若 Feature 脚本在库加载后、规则后或不同分支中多次刷新，FeatureTask 必须按原相位直接编排并写明省略条件；不得一律挪成全局最后一步。
   - 当 AtomTask 的通用约束与 Feature 的具体操作步骤表面冲突时，不得自行选择或改写。记录冲突、引用两边依据，并以 Feature 的具体场景脚本保留原顺序，交由审查者确认。
2. 先做批内最复杂 Feature：它用于发现通用步骤和场景差异。
3. 对每段流程决策：
   - 单命令：FeatureTask 直接编排该 AtomTask；
   - 至少两条配置命令，且共享同一配置目标、稳定顺序和对象链：CompoundTask 候选；
   - 多命令但只是偶然共现、没有稳定阶段：仍逐条 Atom，不得凑 CompoundTask。
4. 新建 CompoundTask 前，查 _index：
   - Jaccard >= 0.75 且相位同义：复用；
   - 0.4–0.75 或相位近义：新建或 reference，但共享 Atom；
   - < 0.4 或相位不同：新建。
   Jaccard 只是门槛，不得替代配置语义判断。
5. 连续 3 个 AtomTask 时，必须书面评估是否应抽 CompoundTask；同一内聚的 >=3 命令被 >=2 个 Feature 共用时，必须抽取。
6. 复用 CT 时，将本 Feature 的参数变体、执行/省略的命令子集、专属前后置、约束回填到 CT 的“场景差异”。只读 CT 不直接改，改动写入待整合回填清单。
7. Feature 脚本若为所有场景明确配置了全局基线，再按 APN/rule/对象做覆盖，则 CompoundTask 必须固定该全局基线；只能将后续覆盖标为可选，不能把全局基线弱化为“按需执行”。
8. **把配置差异沉淀到 Task md，而不是留在构建报告中。**对同一 Feature 的每种激活方法/配置场景，逐条说明：复用或省略了哪些步骤、命令处于哪个相位、调用的 AtomTask、相对基线改变了哪些参数和值、变化的生效对象和触发条件。没有参数变化时也要明确“与基线相同”。每个源脚本显式执行的命令都必须纳入该场景的命令子集，包含表达“继承/恢复默认”的 `INHERIT` 等命令；不能因其语义像默认值而省略。
   - 参数的完整静态字典仍只属于 AtomTask；FeatureTask/CompoundTask 只记录本场景实际使用的参数值和**相对差异**，并以 `[[AtomTask ID]]` 追溯，避免复制静态知识。
   - 不得把“不同激活方法”压缩成一句“参数按需配置”。若差异影响命令子集、顺序、对象、参数值或是否刷新，必须逐场景列出。

【产物标准】

A. FeatureTask：每个 Feature Code 恰一份
- 路径：三层图谱资产\FeatureTask\UDG\20.15.2\UDG@FeatureTask@{code}.md
- YAML：id/type/name/name_zh/nf/version/ref/status；ref 指向对应 Feature。
- 正文：配置概览（对象链与场景骨架）→ 配置流程（CompoundTask 与单 Atom 的混合编排）→ **激活方法与参数差异** → 决策点 → 约束 → 独立的 ## 边。
- “激活方法与参数差异”必须使用一张逐场景表，且不得更名/省列；固定列为：`激活方法/条件 | 配置相位 | 执行的 Task（[[CompoundTask]] / [[AtomTask]]） | 省略的 Task | 关联 AtomTask | 相对基线的参数差异（参数=值） | 目标对象与生效说明`。一个方法跨多个相位可用多行，但必须能还原完整命令时间线与每一条关联 AtomTask。
- 若 AtomTask 的配置字典不接受 Feature 的实际参数值，参数核对表必须标为 **冲突/待 Atom 更正**，给出 Atom 限定与 Feature 实值；严禁写为“通过”。FeatureTask 仍按其特性步骤保留实际值，但不得把冲突伪装成合法配置。
- Feature 没有提供某一 Atom 最小参数集的具体值时，写明“待数据规划补齐”，不得虚构默认值或写成可直接执行。
- 边：对应特性 + 编排对象；不直接连 ConfigObject、License、参数对象。

B. CompoundTask：仅当步骤真实存在时新建
- 路径：三层图谱资产\CompoundTask\UDG\20.15.2\UDG@CompoundTask@{stable-kebab-name}.md
- YAML：id/type/name/name_zh/nf/version/command_set/status。
- 正文必须有：定位、配置方法（命令顺序/关键参数/典型脚本/步骤位置）、场景差异、决策点、约束、独立的 ## 边。
- “场景差异”必须落下复用此 CT 的各 Feature/激活方法的命令子集、覆盖参数（参数=值）、对象与执行相位；若 CT 内没有参数差异，写明“本步骤参数与基线相同，差异由 FeatureTask 的单命令阶段承载”。
- 边：组成 → AtomTask；被引用于 → 全部实际 FeatureTask；可选上下游 CompoundTask。
- CompoundTask 只描述多命令如何组装；不复制 AtomTask 的参数字典。

【禁止事项】
- 不把 DSP/LST/EXP/STP 和探测性 STR 写入配置流程或 CompoundTask。
- 不抄命令层静态参数表，不写 source/source_evidence_ids/## 证据。
- 不为每个 Feature 复制一份名称不同、命令集合相同的 CompoundTask。
- 不把引用粒度细化到 md 内章节；所有引用都是 [[逻辑ID]]。
- 不修改未授权的既有 CompoundTask，不并发重生全局 _index.md。
- 不因“Feature 有很多 md”而遗漏操作步骤、数据规划或任务脚本。

【交付与自检】
交付前必须报告：
1. 逐 Feature 输入 md、相关 AtomTask、复用/新建 CT、阻塞项；
2. 新建/修改文件清单；
3. 每个新 CT 的 command_set、复用理由、被引用于；
4. 待整合 CT 场景差异清单；
5. 自检结果：字段、真实引用、独立 ## 边、无调测命令、防平铺、反链一致性。
6. 逐场景命令时间线与 Atom 参数合法性表；任何命令顺序/约束冲突必须单列。
7. 每个 FeatureTask 内“激活方法与参数差异”表的完整性：不同方法的命令子集、相位、对象、参数值、刷新位置均可追溯到 AtomTask 和 Feature 步骤。

只有在本 Agent 是该批次唯一写入者且已获得集成授权时，才可运行：
python 三层图谱构建规范\task\scripts\gen_compound_index.py --nf UDG

否则由集成 Agent 在合并所有批次后统一重生索引，并运行：
python 三层图谱构建规范\task\scripts\audit_compound_feature.py --nf UDG
```

## 配套的对抗评审提示词

```text
你是独立的 Task 层审查者。不要修复产物；只输出可定位的问题清单。

审查范围：{BUILDER_OUTPUT_FILES}
输入范围：同批 Feature 文档簇、相关 AtomTask、现有/新建 CompoundTask、task/check.md。

按以下顺序审查：
1. FeatureTask 是否覆盖每个分配 Feature，是否真正以 Feature 操作步骤为依据；
2. 是否把多命令稳定配置阶段正确抽成/复用 CompoundTask，或发生 Atom 平铺/假通用；
3. 每个 CompoundTask 的 command_set、组成边、被引用于反链是否与实际 FT 完全一致；
4. 场景差异是否回填，尤其命令子集、参数变体、专属约束；
5. FeatureTask 参数是否能在对应 AtomTask 配置方法中找到；仅检查 Atom 文件存在不算通过；
6. FeatureTask 与 CompoundTask 是否分别记录了激活方法/场景的命令子集、对象、参数值和相对基线差异；是否存在以“按需配置”掩盖可定位差异的情况；
7. 是否逐场景保留 Feature 操作步骤里的命令顺序、可选分支、全局基线和多次刷新；不得以“刷新最后执行”等通用规则重排具体脚本；
8. 是否混入 DSP/LST/EXP 等调测查询命令，是否复制静态知识；
9. YAML、ID、路径、独立 ## 边、裸 wikilink、无证据段是否合规；
10. 原始文档回查是否确有必要且被明确说明。

问题按 CRITICAL/HIGH/MEDIUM/LOW 输出，每条必须含：对象 ID、文件与行号、违反规则、证据、建议返工方向。
若无问题，明确说明已检查的对象与仍无法从现有输入确认的风险；不得以“看起来合理”代替证据。
```
