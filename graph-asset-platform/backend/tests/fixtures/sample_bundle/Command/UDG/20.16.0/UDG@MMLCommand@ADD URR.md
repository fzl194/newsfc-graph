---
id: UDG@MMLCommand@ADD URR
type: MMLCommand
nf: UDG
version: 20.16.0
name: 新增 URR 用量统计规则
source: demo-bundle
status: active
---
# ADD URR (20.16.0)

新增一条用量统计规则。20.16.0 版本新增 METERINGMODE 参数。

## 参数

| 参数 | 说明 |
|------|------|
| URRTMPL | 规则名称 |
| MEASMETHOD | 统计方法 |
| METERINGMODE | 计量模式（新） |

## 边
- 操作配置对象: [[UDG@ConfigObject@URR]]
- 参见: [[UDG@MMLCommand@MOD URR]]
