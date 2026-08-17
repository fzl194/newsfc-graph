# UNC-B6：过载保护、信令风暴、IP 承载与寻呼流控交接

> 执行日期：2026-08-13  
> 批次状态：**已完成（6 项 FeatureTask；新增 4 个 CompoundTask）**。

## 当前产物

| Feature | 文档结论 | 当前产物 |
|---|---|---|
| `WSFD-010801` 过载控制 | 含 HTTP、AMF/NRF/NSSF/SMF/SPGW/SGSN/MME 多个独立激活入口 | FT，直引 Atom；HTTP 服务端流程未抽入客户端 CT |
| `WSFD-010802` HTTP/GR 流控 | HTTP 客户端固定流控与 Gr/HTR 流控各有稳定完整时间线 | FT + `unc-http-fixed-flow-control`、`unc-gr-htr-flow-control` |
| `WSFD-010803` 下行通知限流 | MME 单命令与 SGW-C 三命令优先级链为独立入口 | FT + `ddn-throttling-priority-enable` |
| `WSFD-010804` 智能信令风暴平滑 | MME 两命令顺序、SGW-C 单命令分别可恢复 | FT，直引 Atom |
| `WSFD-010900` IP 承载 | 完整簇明确无命令、无独立配置责任 | foundation FT |
| `WSFD-010901` 寻呼流控 | AMF 三命令 TAI 监控链、MME 单命令；性能对象依赖其他特性 | FT + `ta-list-paging-monitor-amf` |

## 关键边界与冲突

- `010801`：回填七份激活脚本的完整非敏感参数闭包；HTTP 实际相位为 IP 组/门限 → `SET HTTPFIXEDFCMSG` ×2 → `HTTPOFC/HTTPFIXEDFCINF`，未以 CT 重排。`APNACCESSWAL` 保留数据表 `apn-test/30` 与换行脚本 `huawei.com/300` 差异。
- `010802`：HTTP CT 仅保留客户端实例，典型脚本不再残留 `010801` 服务端参数。RDS 的 `CIPHERKEY/CIPHERKEYCNFM` 是必填且须一致的受控密钥输入，Task 不落盘样例值，参数核对为待安全输入。
- `010804`：MME 数据规划 `DEFAULT,500000,15` 与脚本 `SPECIFIC,300000,20` 并列保留、不可合并；SGW-C `SUPPTIME=15` 与命令/Atom 无该参数的冲突标未编排待更正。
- `010901`：`SET NGTAIPAGINGMONPARA` 脚本拼写与五处一致的 `SET NGTAIPAGMONPARA` 冲突已记录；PERFOBJ 类命令只转引 `011302`、无实例，不编排。

## 审查与集成

- `010801` 首轮发现 HTTP 时序、APN 差异及参数闭包问题；`010802` 首轮发现客户端 CT 示例与凭据处理问题；均按来源和安全边界修复，最终独立复审均为 `CRITICAL=0 / HIGH=0 / MEDIUM=0`。
- `010803/010804`、`010900/010901` 最终独立复审均为零问题。
- 已重生 `_index.md`；当前 CompoundTask 55、FeatureTask 157。跨层审计 `fail=0`，Feature→Atom 强覆盖 `952/952`，脚本单测 9/9 通过。
