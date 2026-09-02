"""UI 层映射：registry 6 层 → 前端 4 个层 Tab（命令层/特性层/任务层/业务层）。

- 前端 LayerNav 有 4 个层 Tab；registry 有 6 个 layer（Command/ConfigObject/
  Feature/License/Task/Business）。本模块提供二者映射，供 /stats 聚合与
  /objects?layer= 过滤共用，避免数据/视图两端各写一份硬编码。
- ``UI_LAYER_TYPES``：UI 层 → 该层包含的 type 集合（供 /objects?layer= 过滤）。
"""
from typing import Optional

# registry 层 → UI 层（4 个 Tab）
REGISTRY_TO_UI = {
    "Command": "命令层",
    "ConfigObject": "命令层",
    "Feature": "特性层",
    "License": "特性层",
    "Task": "任务层",
    "Business": "业务层",
}

# UI 层有序列表（前端 Tab 顺序）
UI_LAYERS = ["命令层", "特性层", "任务层", "业务层"]

# UI 层 → 该层包含的 type（供 /objects?layer= 过滤）
UI_LAYER_TYPES = {
    "命令层": ["MMLCommand", "ConfigObject"],
    "特性层": ["Feature", "License"],
    "任务层": ["AtomTask", "CompoundTask", "FeatureTask", "Task"],
    "业务层": ["BusinessDomain", "NetworkScenario", "ConfigurationSolution"],
}

# 图谱浏览页三 Tab 别名（2026-09-03，用户决策：**仅浏览页**改名 + 任务/业务合并
# 展示；与统计页口径一致）。纯增量——旧 4 层名保留不动（旧 /stats 聚合键、
# tests-module 关联图谱分组、e2e、MCP 说明均继续用旧名），/objects?layer= 新旧都收。
UI_LAYERS_GRAPH = ["命令图谱", "特性图谱", "业务图谱"]
UI_LAYER_TYPES.update({
    "命令图谱": UI_LAYER_TYPES["命令层"],
    "特性图谱": UI_LAYER_TYPES["特性层"],
    "业务图谱": UI_LAYER_TYPES["任务层"] + UI_LAYER_TYPES["业务层"],
})


def ui_layer_of(registry_layer: Optional[str]) -> str:
    """registry 层 → UI 层；未注册的层原样返回（不丢数据）。"""
    if registry_layer is None:
        return ""
    return REGISTRY_TO_UI.get(registry_layer, registry_layer)
