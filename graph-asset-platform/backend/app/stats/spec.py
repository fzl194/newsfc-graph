"""统计口径常量注册表（需求说明书 §3/§4/§7 的代码化）。

- 三视图 from-类型集：图谱归属按**边起点**对象类型判定（跨图谱边归出边方）。
- 成对方向关系：只计 1 次取较大值（§7.1）；自反/交叉对不合并。
- 规则表网元列名两套（§6.1）：GRAPH/REPEAT 用 PHYSICAL_NE_TYPE，
  MOD/SET/DELETE/语法规则表用 NE_TYPE。
"""
from dataclasses import dataclass, field

# ---- 三视图类型集 ----
COMMAND_TYPES: tuple[str, ...] = ("MMLCommand", "ConfigObject")
FEATURE_TYPES: tuple[str, ...] = ("Feature", "License")
BUSINESS_TYPES: tuple[str, ...] = (
    "AtomTask", "FeatureTask", "CompoundTask",
    "ConfigurationSolution", "NetworkScenario", "BusinessDomain",
)
TASK_TYPES: tuple[str, ...] = ("AtomTask", "FeatureTask", "CompoundTask")
ALL_TYPES: tuple[str, ...] = COMMAND_TYPES + FEATURE_TYPES + BUSINESS_TYPES

# ---- 双向成对关系（§7.1：合并取大，不成对相加）----
RELATION_PAIRS: tuple[tuple[str, str], ...] = (
    ("操作配置对象", "被操作"),
    ("包含子文档", "属于特性"),
    ("上游", "下游"),
    ("上游场景", "下游方案"),
    ("上游域", "下游场景"),
)
# 成员关系 → 合并展示键（如 '操作配置对象/被操作'）
PAIR_KEY: dict[str, str] = {
    rel: f"{a}/{b}" for a, b in RELATION_PAIRS for rel in (a, b)
}


def merge_relations(raw: dict[str, int]) -> tuple[dict[str, int], int]:
    """成对方向关系合并（§7.1）：先按原值计数（调用方保证），再对成对分支
    取 MAX（不可先合组再 COUNT——那是相加）。返回 (合并计数, 合并总数)。"""
    merged: dict[str, int] = {}
    for rel, cnt in raw.items():
        key = PAIR_KEY.get(rel, rel)
        if cnt > merged.get(key, 0):
            merged[key] = cnt
    return merged, sum(merged.values())

# ---- 业务图谱边归组（§5.3 D8-D11；键为合并后的 relation 键）----
BUSINESS_EDGE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("编排关系", ("编排", "编排 compound", "编排 atom", "编排特性")),
    ("组成/复用", ("组成", "复用步骤", "复用命令")),
    ("上下游/引用", ("上游/下游", "上游场景/下游方案", "上游域/下游场景",
                    "被引用于", "直接引用 atom", "依赖条件")),
    ("跨图谱任务关联", ("对应命令", "对应特性")),
)

# ---- 导入表注册（表名/网元列/版本列/展示名；DDL 见 db.py v11）----
SYNTAX_TABLE = "B_AI_COMMAND_SYNTAX_CHECK_RULES"
LOGICAL_NE_TABLE = "B_AI_CONFIG_CHECK_LOGICAL_NE_CMD_T"
MAPPING_TABLE = "B_AI_NE_VERSION_MAPPING_T"
# 五类核查规则（顺序即展示顺序）
RULE_TABLES: dict[str, tuple[str, str, str, str]] = {
    "graph": ("B_AI_MML_GRAPH_RULE_T", "PHYSICAL_NE_TYPE", "NE_VERSION", "图规则"),
    "repeat": ("B_AI_MML_REPEAT_CHECK_RULE_T", "PHYSICAL_NE_TYPE", "NE_VERSION", "重复检查规则"),
    "mod": ("B_AI_MOD_RULE_T", "NE_TYPE", "NE_VERSION", "MOD 规则"),
    "set": ("B_AI_MML_SET_CHECK_RULE_T", "NE_TYPE", "NE_VERSION", "SET 规则"),
    "delete": ("B_AI_DELETE_RULE_V2_T", "NE_TYPE", "NE_VERSION", "删除规则"),
}
RULE_TYPE_LABELS: dict[str, str] = {"syntax": "语法规则", **{
    k: meta[3] for k, meta in RULE_TABLES.items()}}

# ---- UPCF 别名（§7.4）：平台 objects.nf='PCF'，规则/映射表用 'UPCF' ----
UPCF = "UPCF"
PCF = "PCF"


def nf_display(nf: str | None) -> str:
    """对外统一显示名：PCF → UPCF（§4 物理网元命名）。"""
    return UPCF if nf == PCF else (nf or "")


def expand_nf_filter(nfs: tuple[str, ...]) -> tuple[str, ...]:
    """筛选值展开：选 UPCF 时 objects 系需同时命中 PCF/UPCF（§7.4）。
    规则表系不必展开（其列值本身就是 UPCF），见 core._rule_where。"""
    out: list[str] = []
    for n in nfs:
        if n == UPCF:
            out.extend([PCF, UPCF])
        elif n and n not in out:
            out.append(n)
    return tuple(out)


@dataclass(frozen=True)
class Filters:
    """统计筛选（需求说明书 §6）。多值以 tuple 传空=不筛。"""
    nfs: tuple[str, ...] = field(default_factory=tuple)          # 物理网元（UPCF 归一值）
    versions: tuple[str, ...] = field(default_factory=tuple)     # 版本（国内号，筛选恒用 local）
    logical_ne: str = ""                                          # 逻辑网元（仅命令相关指标 B1/B2）
    object_types: tuple[str, ...] = field(default_factory=tuple)  # 对象类型
    relations: tuple[str, ...] = field(default_factory=tuple)     # 关系类型
    rule_types: tuple[str, ...] = field(default_factory=tuple)    # 规则类型（syntax+五类）
    domain: str = ""                                              # 业务域
    scenario: str = ""                                            # 场景
    solution: str = ""                                            # 方案（仅收窄方案下钻表）
    overseas: bool = False                                        # 显示国外版本（仅改展示值）

    def echo(self) -> dict:
        return {
            "nfs": list(self.nfs), "versions": list(self.versions),
            "logical_ne": self.logical_ne, "object_types": list(self.object_types),
            "relations": list(self.relations), "rule_types": list(self.rule_types),
            "domain": self.domain, "scenario": self.scenario,
            "solution": self.solution, "overseas": self.overseas,
        }
