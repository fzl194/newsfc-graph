#!/usr/bin/env python3
"""
License 构建器（特性层）
控制项 md（功能控制项/资源控制项）按 license 段 `#### [{control_id} {code} {名}]` 切段 →
每段建一个统一资产（YAML + 原文表格 + 边）。纯标准库。

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

SOP_VERSION = "0.9.0"
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
    ap.add_argument("--storage", default="三层图谱资产")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    global VERBOSE
    VERBOSE = args.verbose

    storage = Path(args.storage).resolve()
    lic_dir = Path(args.license_dir).resolve()
    out_dir = storage / "License" / args.nf / args.version
    out_dir.mkdir(parents=True, exist_ok=True)

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
            # 边：对应特性（从段正文取 feature_code）
            fcs = list(dict.fromkeys(_common.FEATURE_CODE_RE.findall(body)))
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
            content = f"{fm}\n\n{header}\n{_common.clean_md(body)}\n\n{_common.build_edges_section(edges)}\n"
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
    }
    (out_dir / "_build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"License 构建完成：{len(built)} 个 → {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
