"""assets router：导出 + 统计。

（旧的 zip 整包导入 ``POST /import`` 已移除，改由 ``fs`` router 的「指定层上传」
``POST /fs/upload`` 承担。底层 ``bundle.import_bundle`` / ``jobs`` 作为库函数保留，
供测试建夹具与脚本复用。）

- ``GET /export`` : 流式 zip（可选 ``nf/version/domain/scenario`` 过滤）。
- ``GET /stats``  : 按 UI 层聚合的对象/边统计。
"""
import io
from collections import Counter, defaultdict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..bundle import export_bundle
from ..service import get_service
from ..ui_layers import ui_layer_of

router = APIRouter()


def _counts(svc) -> dict:
    c: Counter = Counter()
    for obj in svc.index.nodes.values():
        c[obj.type] += 1
    return dict(c)


def _edge_count(svc) -> int:
    return sum(len(v) for v in svc.index.out.values())


@router.get("/export")
def do_export(nf: str | None = None,
              version: str | None = None,
              domain: str | None = None,
              scenario: str | None = None):
    svc = get_service()
    z = export_bundle(svc.store, nf=nf, version=version,
                      domain=domain, scenario=scenario)
    return StreamingResponse(
        io.BytesIO(z),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=assets.zip"},
    )


def _dd_to_plain(d):
    """把 defaultdict 嵌套结构递归转成普通 dict（JSON 可序列化）。"""
    if isinstance(d, dict):
        return {k: _dd_to_plain(v) for k, v in d.items()}
    return d


@router.get("/stats")
def stats():
    """统计：按 UI 层聚合 node 数（每个 md 实例；多版本计多次，与旧口径一致）。"""
    svc = get_service()
    idx = svc.index

    per_layer: defaultdict = defaultdict(int)
    per_layer_per_nf: defaultdict = defaultdict(lambda: defaultdict(int))
    per_layer_per_nf_per_version: defaultdict = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int)))
    per_domain: defaultdict = defaultdict(int)
    per_domain_scenario: defaultdict = defaultdict(lambda: defaultdict(int))

    for obj in idx.nodes.values():
        ul = ui_layer_of(obj.layer)
        per_layer[ul] += 1
        if obj.nf:
            per_layer_per_nf[ul][obj.nf] += 1
            if obj.version:
                per_layer_per_nf_per_version[ul][obj.nf][obj.version] += 1
        if obj.domain:
            per_domain[obj.domain] += 1
            if obj.scenario:
                per_domain_scenario[obj.domain][obj.scenario] += 1

    return {
        "object_counts_by_type": _counts(svc),
        "edge_count": _edge_count(svc),
        "nfs": sorted(idx.nfs()),
        "versions_per_nf": idx.versions_per_nf(),
        "per_layer": dict(per_layer),
        "per_layer_per_nf": _dd_to_plain(dict(per_layer_per_nf)),
        "per_layer_per_nf_per_version": _dd_to_plain(
            {k: dict(v) for k, v in per_layer_per_nf_per_version.items()}),
        "per_domain": dict(per_domain),
        "per_domain_scenario": _dd_to_plain(dict(per_domain_scenario)),
    }
