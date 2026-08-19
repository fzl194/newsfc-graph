"""解析模式注册表：一个模式 = 目录定位关键词 + 构建器序列（含依赖）。

**新增模式**（如 IMS/信令产品文档）：新建 `modes/ims.py` 定义 ModeDef 并调
``register()``——前端「自动抽取」模式下拉自动出现（GET /import/modes 枚举），
无需改其他代码。模式与网元**不做强制映射**，由用户在 UI 自选（专家决策，2026-08-19）。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Builder:
    """一个构建器 = pipeline 包内脚本 + 产物层 + 依赖声明 + 源目录参数映射。

    src_args: 源目录角色 → 命令行旗标。角色键对应 locate_candidates 的
    mml/feature/license；调度时按用户确认的目录拼参数。
    """
    script: str                              # 相对 pipeline 包，如 "command/build_commands.py"
    layer: str                               # 产物层目录名（force 清理范围/摘要/依赖判定）
    needs: tuple[str, ...] = ()              # 依赖层（范围勾选联动/执行顺序校验）
    src_args: dict[str, tuple[str, ...]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.src_args is None:
            object.__setattr__(self, "src_args", {})


@dataclass(frozen=True)
class ModeDef:
    id: str                                  # 稳定标识（API 参数）
    name: str                                # 前端显示名
    keywords: dict[str, tuple[str, ...]]     # 源目录定位关键词（含变体），键=mml/feature/license
    builders: tuple[Builder, ...]            # 按依赖序声明
    two_pass: bool = False                   # True: scope 含 Feature+Command 时第二遍补 Command 系
                                             # （修评审清单 D5：force 后 feature_codes 为空剥引用）


MODES: dict[str, ModeDef] = {}


def register(m: ModeDef) -> None:
    MODES[m.id] = m


def get_mode(mode_id: str) -> "ModeDef | None":
    return MODES.get(mode_id)


def list_modes() -> list:
    """前端模式下拉数据源（注册即出现）。"""
    return [{"id": m.id, "name": m.name} for m in MODES.values()]


from . import fivegc  # noqa: E402,F401  (导入即注册；新模式在此追加 import)
