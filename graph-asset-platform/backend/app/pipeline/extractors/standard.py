"""标准三抽取器（用户决策 2026-08-26）：①命令+配置对象（整体）②License ③Feature。

- cmd：build_commands（mml 多目录单次调用）+ build_configobjects（读 Command 层）；
  沙箱预拷 Feature（feature_codes 剥引用语义）+ Command（分次累积时旧命令在场）。
- license：build_licenses（license 必选，feature 目录可选仅扩校验集）；预拷 Feature。
- feature：build_features（读 Command+License+自身输出）；needs Command+License 阻断；
  rerun_after 重跑 cmd 两脚本补命令层特性引用（two_pass 跨任务版）。
"""
from . import Builder, ExtractorDef, register

_CMD = Builder(script="command/build_commands.py", layer="Command",
               src_args={"mml": ("--mml-dir",)}, reads=("Command", "Feature"))
_CONFIG = Builder(script="command/build_configobjects.py", layer="ConfigObject",
                  needs=("Command",), reads=("Command",))
_LICENSE = Builder(script="feature/build_licenses.py", layer="License",
                   src_args={"license": ("--license-dir",), "feature": ("--feature-dir",)},
                   reads=("Feature",))
_FEATURE = Builder(script="feature/build_features.py", layer="Feature",
                   src_args={"feature": ("--feature-dir",)},
                   reads=("Command", "License", "Feature"))

register(ExtractorDef(
    id="cmd", name="命令+配置对象",
    keywords={"mml": ("MML命令", "MML 命令", "命令参考")},
    builders=(_CMD, _CONFIG),
    needs=(), required_roles=("mml",),
))
register(ExtractorDef(
    id="license", name="License",
    keywords={"license": ("License描述", "License 控制", "License控制"),
              "feature": ("特性指南",)},
    builders=(_LICENSE,),
    needs=(), required_roles=("license",),
))
register(ExtractorDef(
    id="feature", name="Feature（特性）",
    keywords={"feature": ("特性指南",)},
    builders=(_FEATURE,),
    needs=("Command", "License"), required_roles=("feature",),
    rerun_after=(_CMD, _CONFIG),
))
