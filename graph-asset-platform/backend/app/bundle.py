"""Bundle 导入：zip → 解包 → 合并 types/ 扩展 → 逐 md 归类 → 合并进统一资产库。

流程（spec §5.5）：
1. 解压 zip。
2. **先**扫 ``types/*.yaml``（若有）合并进注册表（同名 bundle 扩展覆盖默认 + 告警）。
3. 逐 md：解析 frontmatter；须有 ``id``+``type`` 且 ``type`` 在合并后的注册表里。
4. 按 classify 派生标准路径 + 文件名（=逻辑ID），写入统一资产库。
   - 与库中已有对象同 id 同版本（同归一化路径）→ 记 ``updated``（后传覆盖先传）。
   - 否则记 ``added``。
   - 同 id 不同版本 → 新增一条版本记录（多版本共存）。
5. 失败策略：md 缺 id/type 或 type 未注册 → 记入 warnings 并跳过（不阻塞整包）。

导入只负责"写库"；索引重建由调用方（service）在导入后触发。
"""
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .classify import classify
from .md_parser import parse_md
from .registry import Registry
from .store import Store


@dataclass
class BundleResult:
    added: int = 0
    updated: int = 0
    skipped: int = 0
    warnings: list = field(default_factory=list)


def import_bundle(zip_bytes: bytes, store: Store, registry: Registry) -> BundleResult:
    """把一个 bundle zip 合并进统一资产库 ``store``，扩展注册表 ``registry``（原地）。"""
    res = BundleResult()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = z.namelist()
        # 1. 先扫 types/*.yaml 合并注册表（必须在解析 md 前，让新类型可用）
        for n in names:
            if n.startswith("types/") and n.endswith(".yaml"):
                try:
                    spec = yaml.safe_load(z.read(n)) or {}
                except yaml.YAMLError as ex:
                    res.warnings.append(f"{n}: YAML 解析失败 {ex}")
                    continue
                type_name = Path(n).stem
                res.warnings.extend(registry.merge_extensions({type_name: spec}))
        # 2. 逐 md 归类合并
        for n in names:
            if not n.endswith(".md"):
                continue
            # 跳过目录条目（zip 里可能有 "dir/" 这种空条目）
            if n.endswith("/"):
                continue
            try:
                text = z.read(n).decode("utf-8")
            except UnicodeDecodeError as ex:
                res.warnings.append(f"{n}: 编码错误 {ex}")
                res.skipped += 1
                continue
            try:
                fm, _body, _edges = parse_md(text)
            except Exception as ex:
                res.warnings.append(f"{n}: 解析失败 {ex}")
                res.skipped += 1
                continue
            id_ = fm.get("id")
            typ = fm.get("type")
            if not id_ or not typ:
                res.warnings.append(f"{n}: 缺 id/type")
                res.skipped += 1
                continue
            if not registry.known(typ):
                res.warnings.append(f"{n}: 未知类型 {typ}")
                res.skipped += 1
                continue
            try:
                rel, fname = classify(id_, registry, fm)
            except ValueError as ex:
                res.warnings.append(f"{n}: {ex}")
                res.skipped += 1
                continue
            target = f"{rel}/{fname}"
            if store.exists(target):
                res.updated += 1
            else:
                res.added += 1
            store.write(target, text)
    return res


def export_bundle(store: Store,
                  nf: str | None = None,
                  version: str | None = None,
                  domain: str | None = None,
                  scenario: str | None = None) -> bytes:
    """把统一资产库打成 zip 快照（spec §5.6）。

    可选过滤参数（任一不传 = 不过滤；全不传 = 全量）：
    - ``nf``      : NF 隔离类路径第二段（如 ``UDG``）。
    - ``version`` : NF 隔离类路径第三段（如 ``20.15.2``）；只对 Layer != Business 生效。
    - ``domain``  : Business 路径第二段。
    - ``scenario``: Business 路径第三段。

    导出无损（目录快照，不改 md）；导出 zip 可再次导入还原（往返一致）。
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in store.list_md():
            parts = rel.split("/")
            layer = parts[0] if parts else ""
            if nf:
                # NF 隔离类路径形如 Layer/nf/version/...；至少 3 段
                if layer == "Business" or len(parts) < 3 or parts[1] != nf:
                    continue
            if version:
                # version 过滤只对 NF 隔离类路径有意义（parts[2] == version）
                if layer == "Business" or len(parts) < 3 or parts[2] != version:
                    continue
            if domain:
                if layer != "Business" or len(parts) < 2 or parts[1] != domain:
                    continue
            if scenario:
                if layer != "Business" or len(parts) < 3 or parts[2] != scenario:
                    continue
            z.writestr(rel, store.read(rel))
    return buf.getvalue()
