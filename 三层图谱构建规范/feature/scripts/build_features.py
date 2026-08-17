#!/usr/bin/env python3
"""
特性构建器（特性层）—— feature_code 聚合模型
遍历 feature-dir 下全部 md，按【最深 feature_code】归组（不靠父文件夹名）；
同 code 的所有 md → 一个特性文件夹。每个 md = 统一资产（YAML + 原文 + 边）。

ID 机制（v0.10.0）：
- 概述(特性本体)：{nf}@Feature@{feature_code}（默认引用目标）
- 子文档：{nf}@Feature@{feature_code}-{slug}（slug=源文件名净化；doc_type 只进 YAML 不进 ID）
- 同特性内 slug 撞名 → 前面补一层父目录消歧。

纯标准库。

用法:
  python build_features.py --nf UDG --version 20.15.2 \
      --feature-dir "output/UDG.../特性部署/特性指南/UDG特性指南" --storage "三层图谱资产"
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import _common

SOP_VERSION = "0.12.0"
VERBOSE = False


def log(m: str) -> None:
    if VERBOSE:
        print(m, file=sys.stderr)


def deepest_feature_code(parts: list[str]) -> str:
    """路径段（含文件名）里最深的 feature_code（= 该 md 归属的特性）。"""
    last = ""
    for seg in parts:
        m = _common.FEATURE_CODE_RE.search(seg)
        if m:
            last = m.group(0)
    return last


def first_h1(md_text: str) -> str:
    """取原文第一个 `# ` 标题文本（作 name），无则空。对齐命令层：body 保留原文 H1，不另 prepend。"""
    for ln in md_text.splitlines():
        s = ln.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return ""


def feature_name(code: str, folder_parts_list: list[list[str]]) -> str:
    """从含该 code 的【最深文件夹段】取特性名（段名去掉 code）。"""
    for parts in folder_parts_list:
        for seg in parts:
            if _common.parse_feature_code(seg) == code:
                name = seg.replace(code, "").strip()
                if name:
                    return name
    return code


def pick_overview(code: str, docs: list[tuple[Path, list[str]]]) -> int | None:
    """选概述 doc 下标：优先文件名含『特性概述』；否则文件名=纯特性名（{code} {名}）。"""
    for i, (f, _) in enumerate(docs):
        if "特性概述" in f.name:
            return i
    for i, (f, _) in enumerate(docs):
        stem = _common.slugify_doc(f.name)
        if stem.startswith(code):
            rest = stem.replace(code, "").strip()
            if rest and not _common.detect_doc_type(f.name):  # 纯特性名、无其它doc关键词
                return i
    return None


def assign_slugs(docs: list[tuple[Path, list[str]]], overview_idx: int | None) -> dict[int, str]:
    """给每个非概述 doc 分配 slug；撞名则按父目录消歧；仍撞则加序号。"""
    slugs: dict[int, str] = {}
    for i, (f, _) in enumerate(docs):
        if i == overview_idx:
            continue
        slugs[i] = _common.slugify_doc(f.name)

    def collisions() -> dict[str, list[int]]:
        dup: dict[str, list[int]] = defaultdict(list)
        for i, s in slugs.items():
            dup[s].append(i)
        return {s: idxs for s, idxs in dup.items() if len(idxs) > 1}

    # 消歧：同名 → 前补一层父目录；若一轮后撞名数未减（父目录相同/为空救不了）→ 加序号收尾，避免死循环
    while True:
        colliding = collisions()
        if not colliding:
            break
        old_n = sum(len(v) for v in colliding.values())
        for s, idxs in colliding.items():
            for i in idxs:
                parent = docs[i][1][-1] if docs[i][1] else ""
                cand = f"{parent}-{s}" if parent else s
                if cand != slugs[i]:
                    slugs[i] = cand
        new_colliding = collisions()
        new_n = sum(len(v) for v in new_colliding.values())
        if new_n >= old_n:  # 父目录消歧无进展 → 加序号收尾
            for _s, idxs in new_colliding.items():
                for num, i in enumerate(idxs, 1):
                    slugs[i] = f"{slugs[i]}-{num}"
            break
    return slugs


def build_overview_edges(md_text: str, nf: str, code: str, sibling_ids: list[str]) -> list[_common.Edge]:
    """概述边：所需License + 依赖特性 + 包含子文档。全部限定章节，不扫全文（避免互斥/交互表里
    别人的 license/特性被误挂）。"""
    edges: list[_common.Edge] = []
    # 所需License：只在「可获得性」章节扫（产品文档在此声明特性自己的 License控制项）。
    avail = (_common.get_section(md_text, "可获得性")
             or _common.get_section(md_text, "License支持")
             or _common.get_section(md_text, "License控制项"))
    for lc in _common.parse_license_codes(avail):
        edges.append(("所需License", f"{nf}@License@{lc}"))
    # 依赖特性：只在「与其他特性的交互」章节扫。
    inter = (_common.get_section(md_text, "与其他特性的交互")
             or _common.get_section(md_text, "特性交互"))
    for fc in set(_common.FEATURE_CODE_RE.findall(inter)):
        if fc != code:
            edges.append(("依赖特性", f"{nf}@Feature@{fc}"))
    for sid in sibling_ids:
        edges.append(("包含子文档", sid))
    return _common.dedup_edges(edges)


def main() -> int:
    ap = argparse.ArgumentParser(description="特性构建器（feature_code 聚合模型）")
    ap.add_argument("--nf", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--feature-dir", required=True)
    ap.add_argument("--storage", default="三层图谱资产")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    global VERBOSE
    VERBOSE = args.verbose

    storage = Path(args.storage).resolve()
    feature_dir = Path(args.feature_dir).resolve()

    # 1. 遍历全部 md，按最深 feature_code 归组
    groups: dict[str, list[tuple[Path, list[str]]]] = defaultdict(list)
    skipped = 0
    for f in feature_dir.rglob("*.md"):
        rel_parts = str(f.relative_to(feature_dir)).replace("\\", "/").split("/")
        code = deepest_feature_code(rel_parts)
        if not code:
            skipped += 1
            continue
        folder_parts = rel_parts[:-1]
        groups[code].append((f, folder_parts))
    log(f"源 md: 归组到 {len(groups)} 特性，跳过 {skipped} 个无 code 的 md")

    out_root = storage / "Feature" / args.nf / args.version
    out_root.mkdir(parents=True, exist_ok=True)

    built: list[str] = []
    no_overview: list[str] = []
    multi_overview: list[str] = []
    feature_count = 0
    images_copied = 0
    refs_resolved = 0
    refs_stripped = 0

    # 资产索引：命令引用解析需命令资产已存在；特性引用含本次在建的 code（自洽）
    cmd_index = _common.build_command_index(storage, args.nf, args.version)
    feature_codes = set(groups.keys()) | _common.build_feature_codes(storage, args.nf, args.version)
    log(f"资产索引：命令 {len(cmd_index)} 个；特性码 {len(feature_codes)} 个")
    hash_cache: dict = {}  # 全局 {源png路径: hash}，同一源图全构建只读盘一次

    # 预算 源文件名→目标文档ID：特性引用精确到具体子文档（概述=bare code；子文档=code-slug），命不中才退回概述
    src_to_id: dict[str, str] = {}
    for code0, docs0 in groups.items():
        docs = sorted(docs0, key=lambda x: x[0].name)
        ovi0 = pick_overview(code0, docs)
        slugs0 = assign_slugs(docs, ovi0)
        for i, (f, _) in enumerate(docs):
            src_to_id[f.name] = (f"{args.nf}@Feature@{code0}" if i == ovi0
                                 else f"{args.nf}@Feature@{code0}-{slugs0[i]}")

    for code in sorted(groups):
        docs = sorted(groups[code], key=lambda x: x[0].name)
        name = feature_name(code, [parts for _, parts in docs])
        ovi = pick_overview(code, docs)
        # 多个『特性概述』候选 → 记录，取第一个
        ov_candidates = [i for i, (f, _) in enumerate(docs) if "特性概述" in f.name]
        if len(ov_candidates) > 1:
            multi_overview.append(code)
        if ovi is None:
            no_overview.append(code)
        slugs = assign_slugs(docs, ovi)

        out_folder = out_root / f"{args.nf}@Feature@{code}"
        out_folder.mkdir(parents=True, exist_ok=True)
        feature_count += 1
        img_reg: dict = {"hash2name": {}, "name2hash": {}}  # 按特性文件夹共享的图片去重表

        # 先算每个 doc 的 logical_id（概述=bare code；子文档=code-slug）
        doc_ids: dict[int, str] = {}
        for i, (f, parts) in enumerate(docs):
            if i == ovi:
                doc_ids[i] = f"{args.nf}@Feature@{code}"
            else:
                doc_ids[i] = f"{args.nf}@Feature@{code}-{slugs[i]}"
        sibling_ids = [doc_ids[i] for i in range(len(docs)) if i != ovi]

        for i, (f, parts) in enumerate(docs):
            md_text = f.read_text(encoding="utf-8", errors="replace")
            dt = _common.derive_doc_type(f.name, parts)
            is_ov = (i == ovi)
            logical_id = doc_ids[i]
            # name 取原文首个 H1（最忠实）；无 H1 才退回 folder名/slug
            h1 = first_h1(md_text)
            if is_ov:
                edges = build_overview_edges(md_text, args.nf, code, sibling_ids)
                doc_name = h1 or name
                out_file = "概述.md"
            else:
                edges = _common.dedup_edges([("属于特性", f"{args.nf}@Feature@{code}")])
                doc_name = h1 or _common.slugify_doc(f.name)
                out_file = f"{slugs[i]}.md"
            fields = {
                "id": logical_id, "type": "Feature",
                "name": doc_name, "nf": args.nf, "version": args.version,
                "feature_code": code, "doc_type": dt,
            }
            fm = _common.build_frontmatter(fields)
            # 对齐命令层：不 prepend H1，body = 原文(自带H1) + 边。避免双 H1。
            cleaned = _common.clean_md(md_text)
            # 图片：拷进特性文件夹 assets/，改写为本地相对路径（按文件夹 hash 去重）
            img_slug = "概述" if is_ov else slugs[i]
            cleaned, n_img = _common.rewrite_images(cleaned, f, out_folder / "assets", img_slug, img_reg, hash_cache)
            images_copied += n_img
            # 文档引用：命令/特性引用改写跳转，死链剥 URL 留文字
            cleaned, ref_stats = _common.rewrite_doc_refs(cleaned, args.nf, cmd_index, feature_codes, src_to_id)
            refs_resolved += ref_stats["resolved"]
            refs_stripped += ref_stats["stripped"]
            body = f"{fm}\n\n{cleaned}\n\n{_common.build_edges_section(edges)}\n"
            (out_folder / out_file).write_text(body, encoding="utf-8")
            built.append(logical_id)
        log(f"  ✓ {code}（{len(docs)} doc，概述={'有' if ovi is not None else '无'}）")

    manifest = {
        "sop_version": SOP_VERSION, "object_type": "Feature",
        "model": "feature_code_aggregation",
        "id_rule": "概述={nf}@Feature@{code}; 子文档={nf}@Feature@{code}-{slug}; doc_type为YAML字段不进ID",
        "nf": args.nf, "version": args.version,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "feature_count": feature_count, "doc_count": len(built), "docs": built,
        "features_without_overview": no_overview,
        "features_with_multiple_overview_candidates": multi_overview,
        "images_copied": images_copied,
        "doc_refs_resolved": refs_resolved,
        "doc_refs_stripped": refs_stripped,
    }
    (out_root / "_build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"特性构建完成：{feature_count} 特性 / {len(built)} 文档 → {out_root}")
    print(f"  无概述特性 {len(no_overview)} 个：{no_overview[:20]}"
          + (" …" if len(no_overview) > 20 else ""))
    if multi_overview:
        print(f"  多概述候选 {len(multi_overview)} 个(已取第一个)：{multi_overview[:20]}")
    print(f"  图片拷贝 {images_copied} 张；文档引用解析 {refs_resolved} / 剥死链 {refs_stripped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
