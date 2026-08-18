#!/usr/bin/env python3
"""
License 构建器（特性层）
控制项 md（功能控制项/资源控制项）按 license 段 `#### [{control_id} {code} {名}]` 切段 →
每段建一个统一资产（YAML + 原文表格 + 边）。纯标准库。

v0.21.0：「对应特性」边加存在性校验（--feature-dir 源组码 ∪ 已建码），悬空丢弃；
build_all 编排改为 **licenses 先于 features**（特性侧「所需License」校验需 License 已建）。
v0.22.0：段正文图片改写（rewrite_images 拷入 License/{nf}/{ver}/assets/，对齐其他三类资产）。

用法:
  python build_licenses.py --nf UDG --version 20.15.2 \
      --license-dir "output/UDG.../特性部署/特性指南/UDG License描述" --storage "三层图谱资产"
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import _common

SOP_VERSION = "0.22.0"
VERBOSE = False


def log(m: str) -> None:
    if VERBOSE:
        print(m, file=sys.stderr)


def control_item_type(filename: str) -> str:
    if "功能控制项" in filename:
        return "功能"
    if "资源控制项" in filename:
        return "资源"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="License 构建器")
    ap.add_argument("--nf", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--license-dir", required=True)
    ap.add_argument("--feature-dir", default=None,
                    help="特性源目录：「对应特性」存在性校验（源组码 ∪ 已建码；v0.21.0 悬空丢弃）")
    ap.add_argument("--storage", default="三层图谱资产")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    global VERBOSE
    VERBOSE = args.verbose

    storage = Path(args.storage).resolve()
    lic_dir = Path(args.license_dir).resolve()
    out_dir = storage / "License" / args.nf / args.version
    out_dir.mkdir(parents=True, exist_ok=True)

    # 对应特性校验集（v0.21.0）：源特性组码 ∪ 已建特性码；无 feature-dir 时仅已建
    valid_fcs: set[str] = _common.build_feature_codes(storage, args.nf, args.version)
    if args.feature_dir:
        valid_fcs |= _common.group_feature_codes(args.feature_dir)
    log(f"对应特性校验集：{len(valid_fcs)} 个特性码")
    dangling_dropped = 0

    # 图片（v0.22.0）：License 段正文里的 ![]({旧}.assets/x.png) 拷入 License/{nf}/{ver}/assets/
    # 并改写为本地相对路径（对齐命令/配置对象/特性三类资产；共享 hash 去重）
    lic_assets_dir = out_dir / "assets"
    lic_hash_cache: dict = {}
    lic_img_reg: dict = {"hash2name": {}, "name2hash": {}}
    images_copied = 0

    # built 去重：同一个 license code 可能出现在多个源文件（功能控制项/资源控制项/多个特性指南页），
    # 文件按最后一次写入落盘，manifest 列表必须按 logical_id 去重，否则 license_count 会虚高。
    built: list[str] = []
    built_seen: set[str] = set()
    for f in sorted(lic_dir.rglob("*.md")):
        cit = control_item_type(f.name)
        md = f.read_text(encoding="utf-8", errors="replace")
        for cid, code, name, body in _common.split_license_sections(md):
            if not code:
                continue
            logical_id = f"{args.nf}@License@{code}"
            # 边：对应特性（从段正文取 feature_code；v0.21.0 存在性校验，悬空丢弃）
            fcs = [fc for fc in dict.fromkeys(_common.FEATURE_CODE_RE.findall(body))
                   if fc in valid_fcs]
            dangling_dropped += len(set(_common.FEATURE_CODE_RE.findall(body)) - valid_fcs)
            edges = _common.dedup_edges([("对应特性", f"{args.nf}@Feature@{fc}") for fc in fcs])
            fields = {
                "id": logical_id, "type": "License", "name": name,
                "nf": args.nf, "version": args.version,
                "license_code": code, "control_item_id": cid,
                "control_item_type": cit or "未分类",
                "applicable_nf": _common.extract_license_nf(body),
            }
            fm = _common.build_frontmatter(fields)
            header = f"# {name}\n\n`{code}` · 控制项 {cid} · {cit or '未分类'}\n"
            cleaned_body = _common.clean_md(body)
            cleaned_body, n_img = _common.rewrite_images(
                cleaned_body, f, lic_assets_dir, code, lic_img_reg, lic_hash_cache)
            images_copied += n_img
            content = f"{fm}\n\n{header}\n{cleaned_body}\n\n{_common.build_edges_section(edges)}\n"
            (out_dir / f"{logical_id}.md").write_text(content, encoding="utf-8")
            if logical_id not in built_seen:
                built_seen.add(logical_id)
                built.append(logical_id)
        log(f"  ✓ {f.name}: {len(_common.split_license_sections(md))} 段")

    manifest = {
        "sop_version": SOP_VERSION, "object_type": "License",
        "nf": args.nf, "version": args.version,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "license_count": len(built), "licenses": built,
        "dangling_feature_dropped": dangling_dropped,
        "images_copied": images_copied,
    }
    (out_dir / "_build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"License 构建完成：{len(built)} 个 → {out_dir}（对应特性悬空丢弃 {dangling_dropped}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
