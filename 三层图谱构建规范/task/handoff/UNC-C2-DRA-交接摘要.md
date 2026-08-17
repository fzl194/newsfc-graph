# UNC-C2 DRA 子范围交接摘要

## 范围与产出

| Feature | 准入结论 | FeatureTask | CompoundTask |
|---|---|---|---|
| WSFD-011125 S5接口 | foundation：无 MML/激活/数据规划 | [[UNC@FeatureTask@WSFD-011125]] | 无 |
| WSFD-011126 S8接口 | foundation：无 MML/激活/数据规划 | [[UNC@FeatureTask@WSFD-011126]] | 无 |
| WSFD-011132 Gx over DRA | ready：TCP/SCTP，Atom 完整 | [[UNC@FeatureTask@WSFD-011132]] | [[UNC@CompoundTask@dra-diameter-transport-route]]、[[UNC@CompoundTask@gx-dra-pcc-realm-enable]] |
| WSFD-011133 Gy over DRA | ready：TCP/SCTP，Atom 完整 | [[UNC@FeatureTask@WSFD-011133]] | [[UNC@CompoundTask@dra-diameter-transport-route]]、[[UNC@CompoundTask@gy-dra-ocs-direct-peer]] |
| WSFD-011134 S6b over DRA | ready：TCP/SCTP，Atom 完整 | [[UNC@FeatureTask@WSFD-011134]] | [[UNC@CompoundTask@dra-diameter-transport-route]]、[[UNC@CompoundTask@s6b-dra-aaa-binding]] |

完整只读输入、命令/Atom 准入、候选 CT 判定及原始文档例外记录见 [[UNC-C2-DRA-输入与准入记录]]。

## 构建决策

- 新建 `dra-diameter-transport-route`：三项 Feature 的 DRA 对端、Diameter 链路组/链路、Realm 路由相位共同稳定，且传输协议分支和应用类型均已写入场景差异；未误将接口原理或调测查询写入流程。
- Gx 的 PCC/Realm、Gy 的直连 OCS、S6b 的 AAA/FQDN 分别为稳定的特性专属步骤，故各建一个 CT；没有修改既有共享 CT。
- Gx `ADD PCRF`、`SET PCCTIMER` 和 S6b `ADD SMFINFO` 在源操作步骤中缺实例，均仍在 FT 中保留为待数据规划补齐的条件步骤，未臆造参数。
- Gy TCP/SCTP 示例中有同一 `ADD APN:APN="apn-test"` 的原文重复；FT 已保留并标注文档异常/幂等性确认，未伪造第二对象。

## 局部核验

- `audit_compound_feature.py --nf UNC --version 20.15.2`：D0–D4 均为 0 fail（在本子批落盘后执行）。
- `audit_feature_atom_coverage.py --nf UNC --version 20.15.2 --strict --format text`：952/952 配置命令已有 Atom，缺失 0。
- 人工自检：五个 FT 的调测 `DSP/LST/EXP` 均未被编排；TCP/SCTP、APN/全局 Realm、FQDN 条件分支均在激活方法表和约束中保留；新 CT 的 command_set、组成 Atom、反链与 FT 引用一致。

## 待集成/审查

- 本摘要**不替代独立对抗审查**。请以五个 Feature 的完整文档簇、上述 Atom 与新 CT 做只读审查，重点核 TCP/SCTP 时间线、Gy 重复 `ADD APN`、Gx 可选 PCRF/定时器、S6b SMFINFO 前置。
- 通过后由 C2 唯一集成者重生 `CompoundTask/UNC/20.15.2/_index.md` 并把本子批合并进总 `UNC-C2-交接.md`；本构建者未修改索引或任何共享 CT。
