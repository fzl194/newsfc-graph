"""抽取器注册表（2026-08-26 抽取任务化，取代 modes/ 模式注册表）：
一个抽取器 = 一个原子任务脚本组 + 阻断依赖 + 定位关键词。

**新增抽取器**（后台预制）：新建 ``extractors/xxx.py`` 定义 ExtractorDef 并调
``register()``——前端「抽取脚本」下拉自动出现（GET /import/extractors 枚举）。
脚本本体是规范拷贝件（字节一致不可改），平台只经 CLI 参数编排。

语义（用户决策 2026-08-26）：
- 单脚本单任务：一次任务只跑一个抽取器；
- ``needs``：**阻断式**依赖——目标 (nf,version) 槽位缺层直接 400，不自动补齐；
- ``required_roles``：必选源目录角色（license 的 feature 角色可选，不入此列）；
- ``rerun_after``：主构建后自动重跑的构建器（feature 任务补命令层特性引用，
  two_pass 的跨任务版——用最近一次成功 cmd 任务记录的源目录）；
- ``Builder.reads``：该构建器会读的目标层 → 沙箱预拷集合（跨层读在沙箱内闭环）。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Builder:
    """一个构建器 = pipeline 包内脚本 + 产物层 + 依赖声明 + 源目录参数映射。

    src_args: 源目录角色 → 命令行旗标。角色键对应 locate_candidates 的
    mml/feature/license；调度时按用户确认的目录拼参数。
    reads: 构建器从 storage 读的**其他/自身**目标层（沙箱预拷依据；如
    build_commands 读 Feature 层 feature_codes、build_configobjects 读 Command 层）。
    """
    script: str                              # 相对 pipeline 包，如 "command/build_commands.py"
    layer: str                               # 产物层目录名（摘要/依赖判定）
    needs: tuple[str, ...] = ()              # 层依赖（build_configobjects 需 Command 已构建）
    src_args: dict[str, tuple[str, ...]] = None  # type: ignore[assignment]
    reads: tuple[str, ...] = ()              # 沙箱预拷的目标层

    def __post_init__(self) -> None:
        if self.src_args is None:
            object.__setattr__(self, "src_args", {})


@dataclass(frozen=True)
class ExtractorDef:
    id: str                                  # 稳定标识（API 参数）
    name: str                                # 前端显示名
    keywords: dict[str, tuple[str, ...]]     # 源目录定位关键词（含变体），键=mml/feature/license
    builders: tuple[Builder, ...]            # 主构建器（按依赖序）
    needs: tuple[str, ...] = ()              # 阻断依赖：目标槽位须已存在的层
    required_roles: tuple[str, ...] = ()     # 必选源目录角色
    rerun_after: tuple[Builder, ...] = ()    # 主构建后自动重跑（feature 补命令引用）

    def roles(self) -> list:
        """locate 角色（去重保序）。"""
        seen = []
        for b in (*self.builders, *self.rerun_after):
            for r in (b.src_args or {}):
                if r not in seen:
                    seen.append(r)
        return seen


EXTRACTORS: dict[str, ExtractorDef] = {}


def register(x: ExtractorDef) -> None:
    EXTRACTORS[x.id] = x


def get_extractor(xid: str) -> "ExtractorDef | None":
    return EXTRACTORS.get(xid)


def list_extractors() -> list:
    """前端抽取脚本下拉数据源（注册即出现）。"""
    return [{
        "id": x.id, "name": x.name,
        "needs": list(x.needs), "roles": x.roles(),
        "required_roles": list(x.required_roles),
        "rerun": bool(x.rerun_after),
    } for x in EXTRACTORS.values()]


from . import standard  # noqa: E402,F401  (导入即注册；新抽取器在此追加 import)
