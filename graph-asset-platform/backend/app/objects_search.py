"""对象列表过滤/聚合（GET /objects 与 MCP search_objects 共用，MCP 服务化 2026-08-24）。

语义（与原 routers/objects.list_objects 完全一致）：
- ``layer``：UI 层（命令层/特性层/任务层/业务层）→ 多 type 联合过滤；
  ``type``：单 type 过滤，**type 优先于 layer**（层内收窄）。
- ``version``：版本精确匹配——先过滤到 (id, version) 节点再按 id 聚合
  （选旧版本时该 id 只要存在旧版本节点即可见）。
- ``q``：id / name / name_zh（不区分大小写子串）。
- 聚合：多版本合并一行，代表节点取最新版本；排序 (type, id)。
"""
from typing import Optional

from .service import get_service
from .ui_layers import UI_LAYER_TYPES
from .version import is_newer


def _match_q(obj, ql: str) -> bool:
    """搜索匹配：id / name / name_zh（调用方已 lowercase）。"""
    fm = obj.frontmatter
    return (
        ql in obj.id.lower()
        or ql in str(fm.get("name", "")).lower()
        or ql in str(fm.get("name_zh", "")).lower()
    )


def list_objects_rows(*, q: Optional[str] = None, layer: Optional[str] = None,
                      type: Optional[str] = None, nf: Optional[str] = None,
                      version: Optional[str] = None, domain: Optional[str] = None,
                      scenario: Optional[str] = None) -> tuple:
    """过滤 + 按 id 聚合。返回 (rows, total)——分页由调用方做。"""
    idx = get_service().index
    types: Optional[set] = None
    if type:
        types = {type}
    elif layer:
        types = set(UI_LAYER_TYPES.get(layer, []))
    ql = q.lower().strip() if q else None
    matched: dict = {}
    for (id_, _ver), obj in idx.nodes.items():
        if types is not None and obj.type not in types:
            continue
        if nf and obj.nf != nf:
            continue
        if version and obj.version != version:
            continue
        if domain and obj.domain != domain:
            continue
        if scenario and obj.scenario != scenario:
            continue
        if ql and not _match_q(obj, ql):
            continue
        cur = matched.get(id_)
        if cur is None or is_newer(obj.version, cur.version):
            matched[id_] = obj
    rows = [{
        "id": id_,
        "type": obj.type,
        "layer": obj.layer,
        "nf": obj.nf,
        "domain": obj.domain,
        "scenario": obj.scenario,
        "name": obj.frontmatter.get("name"),
        "versions": idx.versions_of(id_),
    } for id_, obj in matched.items()]
    rows.sort(key=lambda r: (r["type"] or "", r["id"]))
    return rows, len(rows)
