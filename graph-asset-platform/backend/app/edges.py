import re
from .models import Edge
from typing import Optional

# 重新导出，便于 `from app.edges import parse_edges, Edge`
__all__ = ["parse_edges", "Edge"]

# 匹配 `- 关系: <rest>` 行（rest 含 [[...]] 目标，可能多个，用 _WIKI_RE 二次提取）
_LINE_RE = re.compile(r"^\s*-\s*(?P<rel>[^:]+?):\s*(?P<rest>.+?)\s*$", re.M)
# 行内 [[target]]（一行可多个）
_WIKI_RE = re.compile(r"\[\[([^\]]+)\]\]")


def parse_edges(edge_section: str, from_id: str, from_version: Optional[str]) -> list:
    """从 ``## 边`` 章节解析显式边 ``- 关系: [[目标]]``。

    **支持一行多 wikilink**：``- 复用步骤: [[A]], [[B]], [[C]]`` 建多条边（relation 同名）。
    按 ``(from_id, rel, to)`` 去重。

    正文里其他 ``[[ ]]``（非 ``## 边`` 章节）**不**经此函数——它们是给 Agent 跳转的引用，
    不进 edges 表。
    """
    if not edge_section:
        return []
    out = []
    seen = set()
    for m in _LINE_RE.finditer(edge_section):
        rel = m.group("rel").strip()
        rest = m.group("rest")
        for wm in _WIKI_RE.finditer(rest):
            to = wm.group(1).strip()
            key = (from_id, rel, to)
            if key in seen:
                continue
            seen.add(key)
            out.append(Edge(from_id=from_id, from_version=from_version, relation=rel, to=to))
    return out
