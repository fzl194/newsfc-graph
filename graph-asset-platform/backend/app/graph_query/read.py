"""共享读取核心：get_domains_core / get_md_core / 全文引用提取（M1）。

MCP 工具（get_domains/get_md）与 REST（/domains、/md）的唯一业务实现
（需求 §4/§6/§8/§10）——adapter 只做鉴权上下文、协议包装与打点。

护栏（ids 1~100、响应 2MB）全部在 core 统一执行，REST 不再少护栏。
"""
import json
import re

from . import contracts
from .contracts import (
    INVALID_ARGUMENT,
    OBJECT_NOT_FOUND,
    RESULT_TOO_LARGE,
    VERSION_NOT_FOUND,
    DomainItem,
    GraphError,
    GraphQueryError,
    MdFailure,
    MdSuccess,
)
from ..service import get_service
from ..version import is_newer

_REF_RE = re.compile(r"\[\[([^\]]+)\]\]")


def extract_references(raw_md) -> list:
    """全文 [[ID]] 引用提取：去重、保持首次出现顺序（frontmatter/正文/## 边全含）。"""
    out: list = []
    seen = set()
    for m in _REF_RE.finditer(raw_md or ""):
        ref = (m.group(1) or "").strip()
        if ref and ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def _string_versions(all_versions: list) -> list:
    """无版本对象（内存 versions=[None]）→ API 输出 []，不得返回 [null]（§8.2）。"""
    return [v for v in all_versions if v is not None]


def get_domains_core() -> list:
    """全部业务域（最新版聚合）完整 md + 元数据 + 全文引用，按 id 升序。

    MCP（{domains:[...]} envelope）与 REST（裸数组）共享本结果。
    """
    idx = get_service().index
    latest: dict = {}
    for (id_, _v), obj in idx.nodes.items():
        if obj.type != "BusinessDomain":
            continue
        cur = latest.get(id_)
        if cur is None or is_newer(obj.version, cur.version):
            latest[id_] = obj
    return [
        DomainItem(
            id=id_, type=obj.type, name=obj.frontmatter.get("name"),
            version=obj.version, md=obj.raw_md,
            references=extract_references(obj.raw_md),
        )
        for id_, obj in sorted(latest.items())
    ]


def get_md_core(ids: list, version=None) -> tuple:
    """批量取 md 的唯一业务实现。返回 (result_map, telemetry_summary)。

    - ids：每项 trim（trim 后空 → INVALID_ARGUMENT）；按 trim 后规范 ID 去重保序；
      去重后 1~MAX_IDS_PER_CALL。
    - version：None=各 id 最新现存版本；空白 → INVALID_ARGUMENT；否则全局精确。
    - 单项失败：OBJECT_NOT_FOUND / VERSION_NOT_FOUND（回带 available_versions），
      不阻断整批。
    - 2MB 护栏：对完整业务 map 的紧凑 JSON UTF-8 字节计量（含动态 ID key），
      严格大于上限整单失败（RESULT_TOO_LARGE）——通过护栏后 adapter 才写
      object 遥测（§8.4）。
    """
    normalized: list = []
    seen = set()
    for raw in ids:
        key = (raw or "").strip()
        if not key:
            raise GraphQueryError(GraphError(
                code=INVALID_ARGUMENT, message="ids 每项 trim 后须非空"))
        if key not in seen:
            seen.add(key)
            normalized.append(key)
    if not (1 <= len(normalized) <= contracts.MAX_IDS_PER_CALL):
        raise GraphQueryError(GraphError(
            code=INVALID_ARGUMENT,
            message=(f"ids 数量须在 1~{contracts.MAX_IDS_PER_CALL}"
                     f"（去重后 {len(normalized)}）——请分批调用")))
    if version is not None:
        version = version.strip()
        if not version:
            raise GraphQueryError(GraphError(
                code=INVALID_ARGUMENT, message="version 须为 null 或 trim 后非空"))

    idx = get_service().index
    out: dict = {}
    failed_ids: list = []
    for id_ in normalized:
        all_versions = idx.versions_of(id_)
        if not all_versions:
            out[id_] = MdFailure(
                ok=False,
                id=id_, error_code=OBJECT_NOT_FOUND, error="对象不存在",
                requested_version=version, available_versions=[],
            ).model_dump()
            failed_ids.append(id_)
            continue
        obj = idx.resolve_node(id_, version)
        if obj is None:
            out[id_] = MdFailure(
                ok=False,
                id=id_, error_code=VERSION_NOT_FOUND,
                error=f"版本不存在: {id_}@{version}",
                requested_version=version,
                available_versions=_string_versions(all_versions),
            ).model_dump()
            failed_ids.append(id_)
            continue
        out[id_] = MdSuccess(
            ok=True,
            id=id_, type=obj.type, name=obj.frontmatter.get("name"), nf=obj.nf,
            domain=obj.domain, scenario=obj.scenario, version=obj.version,
            versions=_string_versions(all_versions), md=obj.raw_md,
            references=extract_references(obj.raw_md),
        ).model_dump()

    payload_bytes = len(json.dumps(
        out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if payload_bytes > contracts.MAX_TOTAL_BYTES:
        raise GraphQueryError(GraphError(
            code=RESULT_TOO_LARGE,
            message=(f"响应总量超 {contracts.MAX_TOTAL_BYTES // 1024 // 1024}MB 上限"
                     f"（本次 {payload_bytes} bytes）——请分批调用，每批 5~20 个 ID"),
            details={"bytes": payload_bytes, "limit": contracts.MAX_TOTAL_BYTES,
                     "ids": len(normalized)}))

    summary = {
        "ids": normalized,
        "version": version,
        "ok": len(normalized) - len(failed_ids),
        "failed": len(failed_ids),
        "failed_ids": failed_ids[:20],
        "bytes": payload_bytes,
    }
    return out, summary
