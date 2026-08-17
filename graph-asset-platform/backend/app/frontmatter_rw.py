"""frontmatter 改写与校验：供 fs 路由（指定层上传覆盖 / 在线编辑校验）复用。

- ``rewrite_frontmatter``：仅替换 frontmatter 字段，**body 与 ## 边章节原样保留**
  （不走 parse_md 的表格空行折叠，避免对正文引入无谓改动）。
- ``validate_md``：parse + 校验 id/type 必填、type 已注册；返回 (id, type)。

frontmatter 重组范式与 ``routers/tests.py`` 的 ``yaml.dump(..., allow_unicode=True,
sort_keys=False)`` 一致。
"""
import re

import yaml

from .logical_id import split_id
from .md_parser import parse_md
from .registry import Registry

# 与 md_parser._FM_RE 一致；此处自包含复制，避免依赖模块私有名。
_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)


def rewrite_frontmatter(text: str, overrides: dict) -> str:
    """用 ``overrides`` 覆盖 frontmatter 字段；body/边章节原样保留。

    - 无 frontmatter → 新建一段（用 overrides 起）。
    - ``overrides[k] is None`` → 删除该键（用于剥离旧 nf/version 等）。
    - 其余 → 覆盖或新增。
    """
    text = re.sub(r"\r+\n", "\n", text).replace("\r", "\n")
    m = _FM_RE.match(text)
    if m:
        fm = yaml.load(m.group(1), Loader=yaml.SafeLoader) or {}
        rest = m.group(2)
    else:
        fm = {}
        rest = text
    for k, v in (overrides or {}).items():
        if v is None:
            fm.pop(k, None)
        else:
            fm[k] = v
    fm_yaml = yaml.dump(fm, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{fm_yaml}\n---\n{rest}"


def validate_md(text: str, registry: Registry) -> tuple:
    """校验 md 合法性：返回 ``(id, type)``；不合法抛 ``ValueError``。

    要求 frontmatter 有 ``id``；``type`` 缺失则从 id 第二段推（如
    ``UDG@AtomTask@ADD ACL`` → ``AtomTask``）；type 必须在 registry 注册。
    """
    fm, _body, _edges = parse_md(text)
    id_ = fm.get("id")
    if not id_:
        raise ValueError("缺 frontmatter.id")
    typ = fm.get("type")
    if not typ:
        try:
            _nf, typ, _local = split_id(id_)
        except ValueError:
            raise ValueError(f"无法从 id 推断 type（id={id_!r}）")
    if not registry.known(typ):
        raise ValueError(f"未知 type {typ!r}")
    return id_, typ
