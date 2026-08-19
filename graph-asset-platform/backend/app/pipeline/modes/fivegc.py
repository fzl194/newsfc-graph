"""5GC 产品文档解析模式（当前唯一模式；UDG/UNC 等网元共用，模式×网元由用户自选）。"""
from . import Builder, ModeDef, register

register(ModeDef(
    id="5gc",
    name="5GC产品文档",
    keywords={
        # 目录名关键词（含变体，casefold 匹配）；定位=推荐+候选人工确认，选错不致命
        "mml": ("MML命令", "MML 命令", "命令参考"),
        "feature": ("特性指南",),
        "license": ("License描述", "License 控制", "License控制"),
    },
    builders=(
        Builder(script="command/build_commands.py", layer="Command", needs=(),
                src_args={"mml": ("--mml-dir",)}),
        Builder(script="command/build_configobjects.py", layer="ConfigObject",
                needs=("Command",)),
        Builder(script="feature/build_licenses.py", layer="License", needs=(),
                src_args={"license": ("--license-dir",), "feature": ("--feature-dir",)}),
        Builder(script="feature/build_features.py", layer="Feature",
                needs=("Command", "License"),
                src_args={"feature": ("--feature-dir",)}),
    ),
    two_pass=True,
))
