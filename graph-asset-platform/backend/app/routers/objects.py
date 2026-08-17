"""objects router：对象列表 / 单对象 / 邻居 / 原始 md / 子图。

版本解析（spec §6.4）：
- 不带 ``version`` → 该 id **最新现存版本**（语义化最大；id 仅在旧版本时落到旧版本，不 404）。
- ``version=X`` 但 X 不在该 id 的 ``versions[]`` → 404 + ``available_versions``（spec §8.2）。
- id 完全不存在 → 404。

``id`` 含 ``@`` 与空格；FastAPI 路径参数可接收（客户端负责 URL-encode）。
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ..models import Edge, Object
from ..service import get_service
from ..telemetry.recorder import record
from ..ui_layers import UI_LAYER_TYPES
from ..version import latest_version

router = APIRouter()


# ---------- 版本比较辅助 ----------

def _is_newer(a: Optional[str], b: Optional[str]) -> bool:
    """a 是否比 b 新（语义化比较；None 视为最低，跨 NF 类恒 None 不会与 str 混合）。"""
    if a == b:
        return False
    if a is None:
        return False
    if b is None:
        return True
    return latest_version([a, b]) == a


# ---------- 序列化辅助 ----------

def _dump(o: Object) -> dict:
    return {
        "id": o.id,
        "type": o.type,
        "layer": o.layer,
        "scope": o.scope,
        "nf": o.nf,
        "version": o.version,
        "domain": o.domain,
        "scenario": o.scenario,
        "frontmatter": o.frontmatter,
        "body_md": o.body_md,
        "source_path": o.source_path,
    }


def _dump_edge(e: Edge) -> dict:
    return {
        "from": e.from_id,
        "from_version": e.from_version,
        "relation": e.relation,
        "to": e.to,
    }


def _resolve(id_: str, version: Optional[str]) -> Object:
    """解析对象；不存在 / 指定版本缺失 → HTTPException(404)。

    指定版本缺失时附带 ``available_versions``（spec §8.2）。
    """
    idx = get_service().index
    available = idx.versions_of(id_)
    if not available:
        raise HTTPException(status_code=404, detail=f"对象不存在: {id_}")
    obj = idx.resolve_node(id_, version)
    if obj is None:
        # id 存在但指定版本不在 versions[] → 404 + 列出可用版本
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"版本不存在: {id_}@{version}",
                "available_versions": available,
            },
        )
    return obj


# ---------- /objects ----------

@router.get("/objects")
def list_objects(type: Optional[str] = None,
                 layer: Optional[str] = None,
                 q: Optional[str] = None,
                 nf: Optional[str] = None,
                 version: Optional[str] = None,
                 domain: Optional[str] = None,
                 scenario: Optional[str] = None,
                 page: int = 1,
                 size: int = 50,
                 response: Response = None):
    """按 id 聚合列表（多版本合并为一行，versions[] 聚合）。

    过滤参数：
    - ``layer``：UI 层（命令层/特性层/任务层/业务层）→ 多 type 联合过滤
      （如命令层 = MMLCommand + ConfigObject）。
    - ``type``：单 type 过滤。**type 优先于 layer**（在层内进一步收窄，如命令层选"命令"→只 MMLCommand）。
    - ``version``：版本精确匹配。**先按版本过滤到 (id, version) 节点，再按 id 聚合**——
      选旧版本时该 id 只要存在旧版本节点即可见（而不是只看"最新版本"是否等于它）。
    - ``nf/domain/q``：同前。``q`` 匹配 id / name / name_zh（不区分大小写子串）。

    响应头 ``X-Total-Count``：过滤后、分页前的总行数（前端"共 N 项"用）。
    """
    idx = get_service().index
    # 解析 type 集合：type 优先（更窄的子筛选），否则用 layer 的类型集合
    types: Optional[set] = None
    if type:
        types = {type}
    elif layer:
        types = set(UI_LAYER_TYPES.get(layer, []))
    ql = q.lower().strip() if q else None
    # 全部条件先过滤到节点级，再按 id 聚合取代表（版本过滤在聚合前——核心修复）
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
        if cur is None or _is_newer(obj.version, cur.version):
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
    # 稳定排序：按 type 再按 id
    rows.sort(key=lambda r: (r["type"] or "", r["id"]))
    if response is not None:
        response.headers["X-Total-Count"] = str(len(rows))
    start = (page - 1) * size
    return rows[start:start + size]


def _match_q(obj: Object, ql: str) -> bool:
    """搜索匹配：id / name / name_zh（调用方已 lowercase）。"""
    fm = obj.frontmatter
    return (
        ql in obj.id.lower()
        or ql in str(fm.get("name", "")).lower()
        or ql in str(fm.get("name_zh", "")).lower()
    )


# ---------- /domains ----------

@router.post("/domains")
def list_domains_with_md(request: Request):
    """一次性返回全部业务域的完整 md（``[{id, name, md}, ...]``）。

    业务域是用户最优先的业务归属定位层——数量少（跨 NF 类，version 恒 null），
    Agent 入口直接取全部域 md。其他层级仍按 ``POST /md`` 沿 ``[[ID]]`` 引用下钻。
    """
    idx = get_service().index
    latest: dict = {}
    for (id_, _ver), obj in idx.nodes.items():
        if obj.type != "BusinessDomain":
            continue
        cur = latest.get(id_)
        if cur is None or _is_newer(obj.version, cur.version):
            latest[id_] = obj
    out = [
        {"id": id_, "name": obj.frontmatter.get("name"), "md": obj.raw_md}
        for id_, obj in latest.items()
    ]
    for item in out:
        record("/domains", item["id"], "BusinessDomain", user=request.state.user, caller=request.state.caller, level="object", operator=getattr(request.state, "operator", ""))
    return out


# ---------- /names ----------

@router.get("/names")
def names():
    """返回 {id: name} 字典（每 id 取最新版本的 name），供前端把正文 [[ID]] 渲染成可读名。"""
    idx = get_service().index
    latest_per_id: dict = {}
    for (id_, _ver), obj in idx.nodes.items():
        cur = latest_per_id.get(id_)
        if cur is None or _is_newer(obj.version, cur.version):
            latest_per_id[id_] = obj
    return {id_: obj.frontmatter.get("name") for id_, obj in latest_per_id.items()}


# ---------- /objects/{id} ----------

@router.get("/objects/{id_}")
def get_object(id_: str, version: Optional[str] = Query(default=None)):
    obj = _resolve(id_, version)
    idx = get_service().index
    return {
        **_dump(obj),
        "versions": idx.versions_of(obj.id),
        "out_edges": [_dump_edge(e) for e in idx.out_edges(obj.id, obj.version)],
    }


@router.get("/objects/{id_}/neighbors")
def neighbors(id_: str,
              hops: int = 1,
              version: Optional[str] = Query(default=None)):
    # hops 目前固定单跳（v1）；保留参数以兼容前端
    _ = hops
    obj = _resolve(id_, version)
    idx = get_service().index
    out = [_dump_edge(e) for e in idx.out_edges(obj.id, obj.version)]
    back = [_dump_edge(e) for e in idx.in_edges(obj.id)]
    return {"center": _dump(obj), "out": out, "in": back}


@router.get("/objects/{id_}/md", response_class=PlainTextResponse)
def get_md(id_: str, version: Optional[str] = Query(default=None)):
    obj = _resolve(id_, version)
    return PlainTextResponse(
        obj.raw_md,
        media_type="text/markdown; charset=utf-8",
    )


# ---------- /subgraph ----------

@router.get("/subgraph")
def subgraph(center: str,
             hops: int = 1,
             type: Optional[str] = None,
             version: Optional[str] = Query(default=None)):
    idx = get_service().index
    start = _resolve(center, version)
    visited: set = set()
    nodes: list = []
    edges: list = []
    # BFS：hops=0 仅中心；hops=1 中心 + 直接邻居（1 条边可达）；以此类推。
    # 每轮把 frontier 节点纳入结果 + 收集其出边目标作为下一轮 frontier；
    # 因此需要 hops+1 轮（第 0 轮纳入中心，第 1..hops 轮纳入对应跳数的邻居）。
    frontier = [(start.id, start.version)]
    for _depth in range(max(0, hops) + 1):
        nxt = []
        for cid, cver in frontier:
            if (cid, cver) in visited:
                continue
            visited.add((cid, cver))
            n = idx.node(cid, cver)
            if n is None:
                continue
            nodes.append(_dump(n))
            for e in idx.out_edges(cid, cver):
                edges.append(_dump_edge(e))
                tv = idx.latest_version_of_id(e.to)
                if tv is not None and (e.to, tv) not in visited:
                    nxt.append((e.to, tv))
        if not nxt:
            break
        frontier = nxt
    return {"nodes": nodes, "edges": edges}


# ---------- /md (batch) ----------

class BatchMdRequest(BaseModel):
    """批量取 md 请求体（Agent 友好，供 SKILL 逐层批次调用）。

    - ``ids``：1~N 个对象 id（版本无关逻辑 ID，可含 ``@`` 与空格）。
    - ``version``：可选全局版本；不传 → 每个 id 各自取**最新现存版本**。
      某 id 不在该版本 → 该 id 计错并回带 ``available_versions``，不影响其余 id。
    """
    ids: list[str] = Field(..., min_length=1)
    version: Optional[str] = None


@router.post("/md")
def batch_md(req: BatchMdRequest, request: Request):
    """批量取多个对象的原始 markdown。

    复用单对象版本解析（``Index.resolve_node``）：不传 version 落到该 id 最新
    现存版本；版本不匹配不整体报错，而是该 id 计错并回带可用版本，其余 id 照常
    返回。响应为 ``{id: {version, md} | {error, available_versions}}``——每个 id
    恰好一个条目，便于 Agent 遍历。
    """
    idx = get_service().index
    out: dict = {}
    # dict.fromkeys 去重并保序；同 id 重复请求只算一次。
    for id_ in dict.fromkeys(req.ids):
        available = idx.versions_of(id_)
        if not available:
            out[id_] = {"error": "对象不存在", "available_versions": []}
            continue
        obj = idx.resolve_node(id_, req.version)
        if obj is None:
            # id 存在但指定版本缺失 → 回带可用版本，供 Agent 改版本重试
            out[id_] = {
                "error": f"版本不存在: {id_}@{req.version}",
                "available_versions": available,
            }
            continue
        out[id_] = {"version": obj.version, "md": obj.raw_md}
        record("/md", id_, obj.type, user=request.state.user, caller=request.state.caller, level="object", operator=getattr(request.state, "operator", ""))
    return out
