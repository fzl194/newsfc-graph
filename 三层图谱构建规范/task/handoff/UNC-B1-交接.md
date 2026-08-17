# UNC-B1：负荷动态调整交接

> 执行日期：2026-08-11  
> 批次状态：**已完成（1 项正常可执行 FeatureTask，新增 1 个 CompoundTask）**。

## 当前产物

| Feature | 文档结论 | 当前产物 |
|---|---|---|
| `WSFD-010005` 负荷动态调整 | 激活页给出稳定的 `SET TOKENALLOCWT → SET DYNAMICPOLICY →（可选）ADD CPUABILITYCFG` 链，调测页仅为查询/观察 | `UNC@FeatureTask@WSFD-010005`（draft），`UNC@CompoundTask@dynamic-load-adjustment-enable`（draft） |

## 编排与来源处理

- FT 主流程直接编排 CompoundTask；其两个必执 Atom 是 `SET TOKENALLOCWT`、`SET DYNAMICPOLICY`，异构 CPU 能力标定 `ADD CPUABILITYCFG` 为可选子步骤，未从示例强制新增 CPU 记录。
- 调测中的 `LST TOKENALLOCWT`、`LST DYNAMICPOLICY`、`LST CPUABILITYCFG`、`DSP DYNAMICHISTLOAD` 均按 SOP 剥离，系统运行期的负载学习和自动调权也未写成人工命令。
- 明确保留两个 Feature 内部冲突：`ADJUSTTHRESHOLD=70`（数据规划）与 `75`（任务示例）；任务示例 `GLBBASEOST` 与数据表/Atom 的 `GLBBASECOST`。两者都标为待本端规划及实际 CLI 确认，未擅自择一；`CONFIRM=Y` 标为执行确认项而非业务规划数据。

## 集成

- 独立审查首轮发现 `70/75` 未标冲突、FT 未以 CT 为主流程、`CONFIRM=Y` 归属不精确；均已按来源修复，最终复审 `CRITICAL=0 / HIGH=0 / MEDIUM=0`。
- 新 CT 已重生 `_index.md`；CompoundTask 总数 43，`command_set` 总条目 236。
- 本轮跨层审计 `fail=0`；Feature→Atom 强覆盖仍为 `952/952`。
