from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Object:
    id: str                       # 版本无关逻辑ID（NF 3段 / 跨NF 2段）
    type: str
    layer: str                    # Command/ConfigObject/.../Business
    scope: str                    # "nf" | "cross"
    version: Optional[str]        # 本实例版本（NF有；cross 为 None）
    versions: list                # 该 id 全部兄弟版本
    frontmatter: dict
    body_md: str                  # 去 frontmatter 与 ## 边
    raw_md: str                   # 原始全文
    source_path: str              # 资产库内相对路径
    nf: Optional[str] = None
    domain: Optional[str] = None
    scenario: Optional[str] = None

@dataclass
class Edge:
    from_id: str                  # 源节点版本无关 id
    from_version: Optional[str]   # 源节点版本（NF有；cross None）
    relation: Optional[str]
    to: str                       # 目标版本无关 id（wikilink，不带版本）
