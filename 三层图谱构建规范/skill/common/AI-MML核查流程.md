# AI MML 核查流程

> Phase 6 配置核查的标准流程：调用 coremaster configcheck 接口做语法 + 语义核查，解析结果并修正脚本。
> 核查直接调 coremaster configcheck 接口（语法+语义核查），解析结果并修正脚本。无静态降级，统一走接口。
> Token、reference 算子表、核查 API 由部署环境提供。
> 来源：config-generation SKILL 流程固化。

---

## 1. 核查触发条件

Phase 5 生成配置脚本后，**必须询问用户是否调用 AI MML 核查**：
```
配置文件已生成（SMF-MML配置.txt / UPF-MML配置.txt）。
是否需要调用 AI MML 核查能力验证脚本正确性？
- 是 → 进入本流程
- 否 → 直接进入 Phase 6.5 确认
```

---

## 2. 阶段一：信息确认

向用户确认：
1. **核查场景**：新建 vs 动网（动网需现网脚本做基线）
2. **各网元脚本**：动网配置 + 现网配置路径（多网元时每个网元至少一个现网脚本）
3. **逻辑网元类型 + 版本**（如 SMF 20.13.2 / UPF 20.13.2）

**内置步骤**：
- 在 `reference/NE_VERSION_MAPPING.md` 中匹配正确的逻辑网元类型和版本（**务必找到一个正确的**）
- 版本号规范化：
  - 点分式只保留三段（如 `20.13.2`）
  - VRC 版本只保留 SPC 前（如 `V100R009C50`）
- 参数检查：动网配置路径、现网配置路径、**逻辑网元类型**（必须用逻辑类型，否则不能执行）、网元版本
- 告知用户匹配结果（"逻辑网元类型 SMF，版本 20.13.2，核查数据已准备就绪"），确认后执行

---

## 3. 阶段二：Token 获取

```bash
curl -k -X POST "https://w3cloud.huawei.com/ApiCommonQuery/appToken/getRestAppDynamicToken" -H "Content-Type: application/json" -d "{\"appId\": \"com.huawei.nis.coremaster.name\", \"credential\": \"$(echo -n 'PhHbgUsk05f2YHWih8XI3Y7OiKG90z6KUe2LTUEo3UABi75F5A5Ls3O3WjlMZDScA3rDnmML9w3_ipsFRl2WGg' | base64 -w0)\"}"
```
- 返回 `result` 值作为 `${TOKEN}`，格式为 `Basic xxx`

---

## 4. 阶段三：构建并执行核查

### 4.1 构建 scriptInfo（两层嵌套数组）

- **外层 []**：多网元的配置集合
- **内层 []**：每个网元的配置信息（动网 + 现网）

```bash
SCRIPT_INFO='[[
  {"fieldId": "full1", "logicalNeType": "SMF", "neVersion": "20.13.2", "scriptType": 1},
  {"fieldId": "full2", "logicalNeType": "SMF", "neVersion": "20.13.2", "scriptType": 2}
],[
  {"fieldId": "full1", "logicalNeType": "UPF", "neVersion": "20.13.2", "scriptType": 1},
  {"fieldId": "full2", "logicalNeType": "UPF", "neVersion": "20.13.2", "scriptType": 2}
]]'
```

参数说明：
- `fieldId`：full1~fullN，待核查脚本（绝对路径，脚本名自动从路径获取）
- `scriptType`：**1=动网(MOP)，2=现网(full)**
- `scenarioId`：`"语法核查算子ID,通用语义算子assetId"`，逗号分隔
  - **语法核查算子ID**：从 `reference/B_AI_CONFIG_CHECK_ITEM_T_SYTAX.md` 匹配 `CHECK_ID`（一个网元配置只匹配一个值）
  - **通用语义算子ID**：从 `reference/B_AI_CONFIG_CHECK_ITEM_T_UNIVERSAL_SEMANTICS.md` 匹配 `CHECK_ID`，或从 `App.groovy` 获取 assetId

### 4.2 执行核查 API

```bash
curl -k -X POST "https://netlive.gts.huawei.com/apiaccess/coremaster/CMAIConfigCheckCoreService/rest/v1/configcheck/general-check" \
  -H "authorization: ${TOKEN}" \
  -H "Cookie: lang_key=zh_cn;locale=zh_CN;" \
  -F "client=GSC" \
  -F "account=agent" \
  -F "scenarioId=${scenarioId}" \
  -F "full1=@/path/to/${MOP_SCRIPT}.txt" \
  -F "full2=@/path/to/${LIVE_SCRIPT}.txt" \
  -F "scriptInfo=${SCRIPT_INFO}" \
  --output check_result.zip
```

---

## 5. 阶段四：解析核查结果并修正

**内置步骤**：
1. 解压 `check_result.zip`，提取核查结果中的**错误提示信息**
2. 分析每条错误，回溯到对应的命令/参数/对象，修正动网脚本
3. 修正后告知用户："已完成核查并根据结果修正脚本，请确认"
4. 用户确认后进入 Phase 6.5（GATE-3）

---

## 6. reference 资源清单

| 文件 | 用途 |
|---|---|
| `reference/NE_VERSION_MAPPING.md` | 逻辑网元类型 + 版本匹配 |
| `reference/B_AI_CONFIG_CHECK_ITEM_T_SYTAX.md` | 语法核查算子 CHECK_ID |
| `reference/B_AI_CONFIG_CHECK_ITEM_T_UNIVERSAL_SEMANTICS.md` | 通用语义算子 CHECK_ID |
| `App.groovy` | 通用语义算子 assetId |

> 这些 reference 由部署环境提供，本 SKILL 不内置。部署时挂载到 SKILL 的 `reference/` 路径即可。
