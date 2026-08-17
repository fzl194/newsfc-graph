"""测试子系统自带的 md 解析（与图谱 app/md_parser.py 同范式，但代码独立、互不影响）。

- ``parse_md``：frontmatter + 正文 + ``## 边`` 三段切分（降级：无 fm→空dict；无 ##边→''）。
- ``extract_problems``：best-effort 从 Review 正文抽问题清单（识别 ``### 问题 N`` 块），
  抽不到返回空列表，绝不抛错。
"""
import re

import yaml

# 优先 libyaml C 加载器；无则退回纯 Python。
try:
    from yaml import CSafeLoader as _SAFE_LOADER
except ImportError:  # pragma: no cover
    from yaml import SafeLoader as _SAFE_LOADER

from .models import Problem

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)
_EDGE_HEADER_RE = re.compile(r"\n##\s*边\s*\n", re.M)


def parse_md(text: str) -> tuple:
    """→ (frontmatter_dict, body_md, edge_section_text)。"""
    text = re.sub(r"\r+\n", "\n", text)
    text = text.replace("\r", "\n")
    fm: dict = {}
    body = text
    m = _FM_RE.match(text)
    if m:
        fm = yaml.load(m.group(1), Loader=_SAFE_LOADER) or {}
        body = m.group(2)
    edge_section = ""
    em = _EDGE_HEADER_RE.search("\n" + body)
    if em:
        cut = em.start()
        edge_section = ("\n" + body)[cut:].lstrip("\n")
        body = ("\n" + body)[:cut].rstrip("\n")
    return fm, body, edge_section


# ---------- 问题清单 best-effort 抽取 ----------

# 匹配 "### 问题 N" / "### 问题N" / "### 问题：" 等常见写法
_PROBLEM_HEAD_RE = re.compile(r"###\s*问题\b", re.M)
# 行内字段：`- 描述: ...` / `- 归因：...`（兼容中英文冒号）
_DESC_RE = re.compile(r"^\s*[-*]\s*描述\s*[:：]\s*(.+?)\s*$", re.M)
_ATTR_RE = re.compile(r"^\s*[-*]\s*归因\s*[:：]\s*(.+?)\s*$", re.M)
_OBJ_RE = re.compile(r"^\s*[-*]\s*涉及对象\s*[:：]\s*(.+?)\s*$", re.M)
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def extract_problems(body: str) -> list:
    """best-effort 抽问题清单。返回 list[Problem]。抽不到→[]。

    归因按 `,`/`，`/`、` 切成多选列表；涉及对象取该行全部 ``[[ID]]`` 成列表。
    """
    if not body:
        return []
    # 按 "### 问题" 标题切块
    blocks = _PROBLEM_HEAD_RE.split(body)
    problems: list = []
    for blk in blocks[1:]:
        desc_m = _DESC_RE.search(blk)
        attr_m = _ATTR_RE.search(blk)
        obj_m = _OBJ_RE.search(blk)
        desc = desc_m.group(1).strip() if desc_m else _heading_text(blk)
        attr_raw = attr_m.group(1).strip() if attr_m else ""
        attribution = [s.strip() for s in re.split(r"[,，、]", attr_raw) if s.strip()]
        obj_raw = obj_m.group(1).strip() if obj_m else ""
        objects = [m.strip() for m in _WIKILINK_RE.findall(obj_raw)] if obj_raw else []
        problems.append(Problem(description=desc, attribution=attribution, objects=objects))
    return problems


def _heading_text(blk: str) -> str:
    """无 `描述:` 字段时，取块内首个非空、非字段的行作描述兜底。"""
    for line in blk.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        if s.startswith(("- ", "* ")) and ("：" in s or ":" in s):
            continue
        return s
    return ""
