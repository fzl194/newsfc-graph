"""测试子系统的数据模型。

字段语义见 spec §3。所有可选字段缺省均为空串/空列表——索引构建只依赖
路径+文件名，YAML 缺失一律降级，绝不抛错（spec §3.3 降级原则）。
"""
from dataclasses import dataclass, field


@dataclass
class TestCase:
    id: str
    domain: str               # 路径推断；缺→"未分类"
    scenario: str             # 路径推断；缺→""
    name: str                 # fm.name → 正文首 H1 → id
    frontmatter: dict
    body_md: str              # 意图 md 正文
    raw_md: str               # 意图 md 全文
    source_path: str          # 用例文件夹相对 tests 根
    files: list = field(default_factory=list)   # 文件夹内所有文件（相对用例文件夹，排除意图 md）


@dataclass
class Run:
    id: str
    case: str                 # 路径推断（上级目录名）
    name: str
    runner: str               # fm 或 ""
    run_at: str               # fm 或 ""
    status: str               # fm 或 ""
    artifacts: list = field(default_factory=list)   # 同目录实际文件名（除自身 md）
    frontmatter: dict = field(default_factory=dict)
    body_md: str = ""
    raw_md: str = ""
    source_path: str = ""


@dataclass
class Problem:
    description: str = ""
    attribution: list = field(default_factory=list)   # 归因列表（多选：图谱知识/配置流程/其他…）
    objects: list = field(default_factory=list)       # 涉及图谱对象 id 列表（多选 tag）


@dataclass
class Review:
    id: str
    run: str                  # 路径推断（上级目录名）
    reviewer: str = ""
    reviewed_at: str = ""
    verdict: str = ""         # 通过/不通过/部分通过/""
    problems: list = field(default_factory=list)    # list[Problem] best-effort 抽取
    frontmatter: dict = field(default_factory=dict)
    body_md: str = ""
    raw_md: str = ""
    source_path: str = ""
