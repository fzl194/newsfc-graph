#!/usr/bin/env python3
"""
配置对象构建器（命令层）
从已建命令 md 聚合 → ConfigObject md。每个 object_keyword 一个，正文含描述（取自 ADD 命令的"命令功能"），
边回引所有操作它的命令（命令→配置对象的反向边，闭环图谱）。

用法:
  python build_configobjects.py --nf UDG --version 20.15.2 --storage "三层图谱资产"
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import _common

SOP_VERSION = "0.13.0"
VERBOSE = False


def log(m: str) -> None:
    if VERBOSE:
        print(m, file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="配置对象构建器")
    ap.add_argument("--nf", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--storage", default="三层图谱资产")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    global VERBOSE
    VERBOSE = args.verbose

    storage = Path(args.storage).resolve()
    cmd_dir = storage / "Command" / args.nf / args.version
    out_dir = storage / "ConfigObject" / args.nf / args.version
    out_dir.mkdir(parents=True, exist_ok=True)
    if not cmd_dir.exists():
        print(f"命令目录不存在，先跑 build_commands.py：{cmd_dir}", file=sys.stderr)
        return 1

    # ConfigObject 共享 assets/（全版本去重）；hash_cache 跨对象共享
    cfg_assets_dir = out_dir / "assets"
    cfg_hash_cache: dict = {}
    cfg_img_reg: dict = {"hash2name": {}, "name2hash": {}}
    images_copied = 0

    # 按 object_keyword 聚合；记 ADD 命令的 md（取描述）
    families: dict[str, dict] = {}
    for f in sorted(cmd_dir.glob("*.md")):
        if f.name.startswith("_"):
            continue
        md = f.read_text(encoding="utf-8")
        fm = _common.parse_frontmatter(md)
        name = fm.get("name", "")
        obj = _common.object_of_command(name)
        if not obj:
            continue
        verb = _common.verb_of_command(name)
        fam = families.setdefault(obj, {"cmds": [], "add_md": None, "add_path": None,
                                        "cfg_md": None, "cfg_path": None, "has_cfg": False})
        fam["cmds"].append({
            "id": fm.get("id", ""), "name": name, "verb": verb,
            "name_zh": fm.get("name_zh", ""), "applicable_nf": fm.get("applicable_nf", []),
            "source": fm.get("source", ""),
        })
        if _common.is_config_verb(verb):
            fam["has_cfg"] = True  # 配置/查询类命令产生配置对象
            if verb == "ADD" and fam["add_md"] is None:
                fam["add_md"] = md
                fam["add_path"] = f
            if fam["cfg_md"] is None:
                fam["cfg_md"] = md
                fam["cfg_path"] = f

    built = []
    skipped_no_cfg = 0
    for obj, fam in sorted(families.items()):
        if not fam["has_cfg"]:
            skipped_no_cfg += 1  # 仅动作类命令、无配置/查询类 → 不产生配置对象
            continue
        cmds = fam["cmds"]
        add = next((c for c in cmds if c["verb"] == "ADD"), cmds[0])
        # 描述 = ADD（优先）或首个配置/查询类命令的"命令功能"
        desc_md = fam["add_md"] or fam["cfg_md"]
        desc = _common.get_section(desc_md, "命令功能") if desc_md else ""
        # desc 继承自命令资产 md：图是 assets/x.png（相对命令目录）→ 拷到 ConfigObject assets/ 重解析；[[ID]] 透传
        desc_src = fam["add_path"] or fam["cfg_path"]
        if desc and desc_src is not None:
            desc, n_img = _common.rewrite_images(desc, desc_src, cfg_assets_dir, obj, cfg_img_reg, cfg_hash_cache)
            images_copied += n_img
        logical_id = f"{args.nf}@ConfigObject@{obj}"
        verbs = {c["verb"] for c in cmds}
        fields = {
            "id": logical_id, "type": "ConfigObject", "name": obj,
            "name_zh": _common.strip_verb_zh(add["name_zh"]) or obj,
            "nf": args.nf, "version": args.version,
            "object_kind": _common.derive_object_kind(verbs),
            "applicable_nf": add["applicable_nf"],
            "status": "active",
        }
        fm = _common.build_frontmatter(fields)
        # 关系统一进"边"章节（不在正文重复）：被操作 = 反向闭环
        edges = _common.dedup_edges([("被操作", f"{args.nf}@MMLCommand@{c['name']}") for c in cmds])
        edges_sec = _common.build_edges_section(edges)
        parts = [f"# {obj}"]
        if desc:
            parts.append(f"## 说明\n\n{desc}")
        body = "\n\n".join(parts) + "\n"
        (out_dir / f"{logical_id}.md").write_text(f"{fm}\n\n{body}\n{edges_sec}\n", encoding="utf-8")
        built.append(logical_id)
        log(f"  ✓ {logical_id}（{len(cmds)} 命令）")

    manifest = {
        "sop_version": SOP_VERSION, "object_type": "ConfigObject",
        "nf": args.nf, "version": args.version,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "object_count": len(built), "objects": built,
        "images_copied": images_copied,
    }
    (out_dir / "_build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"配置对象构建完成：{len(built)} 个 → {out_dir}（图片拷贝 {images_copied} 张）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
