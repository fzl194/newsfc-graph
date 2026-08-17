#!/usr/bin/env python3
"""
命令层构建器（命令层独立能力包）
原始命令 md → 命令资产 md（顶 YAML + 清洗后原文 + 底"边"章节）
纯标准库。

要点（v0.8.2 修复）:
  - 只收真正的命令 md（H1 = `中文（ENGLISH 命令）`，如 `增加URR（ADD URR）`）；
    概念页/目录页（如"集中配置概念"）跳过。
  - 清洗原文：去 TOC 链接行、去标题 anchor `(#xxx)`。
  - 边校验：命令↔命令"参见"边只引真实存在的命令（2 趟：先收命令名集，再校验）。

用法:
  python build_commands.py --nf UDG --version 20.15.2 \
      --mml-dir "三层图谱资产/output/UDG MML命令" --storage "三层图谱资产"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import _common

SOP_VERSION = "0.13.0"
VERBOSE = False


def log(msg: str) -> None:
    if VERBOSE:
        print(msg, file=sys.stderr)


# ============ 原始 md 解析 ============
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
# 标题：中文（ENGLISH）；ENGLISH 必须像命令（大写 VERB [OBJECT...]）
_TITLE_RE = re.compile(r"^(.+?)[（(]\s*([^（）()]+?)\s*[）)]\s*$")
_CMD_EN_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,}(?:\s+[A-Z0-9][A-Z0-9_]*)*$")


def parse_title(md: str) -> tuple[str, str]:
    """H1 `增加URR（ADD URR）` → (中文, 英文命令)。非命令（无英文码/不像命令）→ ('','')。"""
    m = _H1_RE.search(md)
    if not m:
        return "", ""
    title = m.group(1).strip()
    mt = _TITLE_RE.match(title)
    if not mt:  # 无（英文） → 概念/目录页，跳过
        return "", ""
    name_zh, name = mt.group(1).strip(), mt.group(2).strip()
    if not _CMD_EN_RE.match(name):  # 英文不像命令 → 跳过
        return "", ""
    return name_zh, name


def _heading_text(line: str) -> str:
    s = re.sub(r"^#+\s*", "", line)
    s = re.sub(r"\([^)]*\)", "", s)
    return s.strip(" []　").strip()


def get_section(md: str, name: str) -> str:
    lines = md.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("#") and _heading_text(ln) == name:
            start = i + 1
            break
    if start is None:
        return ""
    body = []
    for ln in lines[start:]:
        if ln.startswith("#"):
            break
        body.append(ln)
    return "\n".join(body).strip()


def extract_applicable_nf(function_text: str) -> list[str]:
    m = re.search(r"适用NF\s*[：:]\s*([^\n]+)", function_text or "")
    if not m:
        return []
    raw = m.group(1).strip().strip("*").strip()
    return [x.strip() for x in re.split(r"[、,，/]", raw) if x.strip()]


def extract_effect_mode(notes_text: str) -> str:
    if not notes_text:
        return ""
    if "立即生效" in notes_text:
        return "立即生效"
    if "对新流" in notes_text:
        return "对新流生效"
    if "对新用户" in notes_text:
        return "对新用户生效"
    if "延迟" in notes_text or "重启" in notes_text:
        return "延迟生效"
    return ""


def extract_is_dangerous(notes_text: str, function_text: str) -> bool:
    blob = (notes_text or "") + (function_text or "")
    return any(k in blob for k in ("高危", "谨慎使用", "严重影响", "破坏性"))


# ============ 原文清洗 ============
_TOC_LINE_RE = re.compile(r"^\s*-\s+\[.+?\]\(#.+?\)\s*$")


def clean_md(md: str) -> str:
    """去 TOC 链接行（- [章节](#anchor)）、去标题 anchor（#### [name](#x) → #### name）。"""
    out = []
    for ln in md.splitlines():
        if _TOC_LINE_RE.match(ln):  # TOC 条目
            continue
        if ln.startswith("#"):  # 标题：去 (anchor) 与 []
            ln = re.sub(r"\]\(#.*?\)", "]", ln).replace("[", "").replace("]", "")
        out.append(ln)
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ============ 边模块 ============
Edge = tuple[str, str]


def edge_configobject(md: str, name: str, nf: str, ctx: dict) -> list[Edge]:
    parts = name.split()
    if len(parts) < 2:
        return []
    obj = parts[1]
    # 边按"查"：对象对应一个已存在的配置对象（被某配置/查询类命令产生）就有边。
    # 不按本命令动词过滤——ACT 与 ADD 可能操作同一配置对象。
    if obj in ctx.get("cfg_objects", ()):
        return [("操作配置对象", f"{nf}@ConfigObject@{obj}")]
    return []


# 命令↔命令：正文 "参见/参考/通过 + VERB OBJECT"；object token ≥2 字符
_CMDREF_RE = re.compile(
    r"(?:参见|参考信息|参考|通过)\s*[：:]?\s*([A-Z]{2,}(?:\s+[A-Z0-9]{2,}[A-Z0-9_]*){0,3})"
)


def edge_cmdref_body(md: str, name: str, nf: str, ctx: dict) -> list[Edge]:
    names = ctx.get("command_names") or set()  # 真实命令名集（校验用）
    out: list[Edge] = []
    for m in _CMDREF_RE.finditer(md):
        ref = re.sub(r"\s+", " ", m.group(1)).strip().rstrip("。，；,;。")
        if ref and ref != name and ref in names:  # 只引真实存在的命令
            out.append(("参见", f"{nf}@MMLCommand@{ref}"))
    return _dedup(out)


def edge_cmdref_intranet(md: str, name: str, nf: str, ctx: dict) -> list[Edge]:
    intranet = ctx.get("intranet") or {}
    return [("参数引用", f"{nf}@MMLCommand@{r}") for r in intranet.get(name, []) if r and r != name]


EDGE_MODULES = [edge_configobject, edge_cmdref_body]


def _dedup(edges: list[Edge]) -> list[Edge]:
    seen, uniq = set(), []
    for e in edges:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return uniq


def build_edges(md: str, name: str, nf: str, ctx: dict) -> list[Edge]:
    edges: list[Edge] = []
    for mod in EDGE_MODULES:
        try:
            edges.extend(mod(md, name, nf, ctx))
        except Exception as e:
            log(f"  边模块 {mod.__name__} 出错: {e}")
    if ctx.get("intranet"):
        edges.extend(edge_cmdref_intranet(md, name, nf, ctx))
    return _dedup(edges)


# ============ YAML 拼装 ============
def _yaml_str(s: str) -> str:
    return '"' + s.replace('"', '\\"') + '"'


def _yaml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(_yaml_str(str(x)) for x in v) + "]" if v else "[]"
    if isinstance(v, str):
        return _yaml_str(v) if v else ""
    return str(v)


def build_frontmatter(fields: dict) -> str:
    lines = ["---"]
    for k, v in fields.items():
        if k in ("applicable_nf", "category_path"):
            lines.append(f"{k}: {_yaml_value(v if v else [])}")
        else:
            lines.append(f"{k}: {_yaml_value(v)}")
    lines.append("---")
    return "\n".join(lines)


def build_edges_section(edges: list[Edge]) -> str:
    if not edges:
        return "## 边\n（暂无）"
    return "## 边\n" + "\n".join(f"- {rel}: [[{tgt}]]" for rel, tgt in edges)


# ============ 单命令构建 ============
def build_one(md_text, nf, version, cat, ctx, src_path) -> tuple[str, str] | None:
    name_zh, name = parse_title(md_text)
    if not name:
        return None
    logical_id = f"{nf}@MMLCommand@{name}"
    func = get_section(md_text, "命令功能") or get_section(md_text, "功能描述")
    notes = get_section(md_text, "注意事项")
    edges = build_edges(md_text, name, nf, ctx)
    fields = {
        "id": logical_id, "type": "MMLCommand", "name": name, "name_zh": name_zh,
        "nf": nf, "version": version, "category_path": cat,
        "status": "active", "applicable_nf": extract_applicable_nf(func),
        "effect_mode": extract_effect_mode(notes),
        "is_dangerous": extract_is_dangerous(notes, func),
    }
    fm = build_frontmatter(fields)
    cleaned = clean_md(md_text)
    # 图片：拷进 Command/{nf}/{version}/assets/（全版本共享，hash 去重）；引用改写为本地相对路径
    cleaned, n_img = _common.rewrite_images(cleaned, src_path, ctx["assets_dir"], name, ctx["img_reg"], ctx["hash_cache"])
    ctx["images_copied"] += n_img
    # 文档引用：命令→[[{nf}@MMLCommand@{cmd}]]、特性→[[{nf}@Feature@{code}]]，死链剥 URL 留文字
    cleaned, ref_stats = _common.rewrite_doc_refs(cleaned, nf, ctx["command_names"], ctx["feature_codes"])
    ctx["refs_resolved"] += ref_stats["resolved"]
    ctx["refs_stripped"] += ref_stats["stripped"]
    body = f"{fm}\n\n{cleaned}\n\n{build_edges_section(edges)}\n"
    return logical_id, body


# ============ 主流程 ============
def main() -> int:
    ap = argparse.ArgumentParser(description="命令层构建器")
    ap.add_argument("--nf", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--mml-dir", required=True)
    ap.add_argument("--storage", default="三层图谱资产")
    ap.add_argument("--intranet-edges", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    global VERBOSE
    VERBOSE = args.verbose

    storage = Path(args.storage).resolve()
    mml_dir = Path(args.mml_dir).resolve()
    ctx: dict = {"intranet": None}
    if args.intranet_edges:
        ctx["intranet"] = json.loads(Path(args.intranet_edges).read_text(encoding="utf-8"))

    out_dir = storage / "Command" / args.nf / args.version
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(mml_dir.rglob("*.md"))

    # 第 1 趟：收命令名集 + 存在的配置对象集（被配置/查询类命令产生）+ 过滤非命令 md
    name_set: set[str] = set()
    cfg_objects: set[str] = set()
    valid: list[tuple[Path, str]] = []
    skipped_noncmd = 0
    for f in files:
        try:
            md = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            md = f.read_text(encoding="utf-8", errors="replace")
        _, name = parse_title(md)
        if name:
            name_set.add(name)
            valid.append((f, md))
            parts = name.split()
            if _common.is_config_verb(parts[0]) and len(parts) > 1:
                cfg_objects.add(parts[1])
        else:
            skipped_noncmd += 1
    ctx["command_names"] = name_set
    ctx["cfg_objects"] = cfg_objects
    ctx["assets_dir"] = out_dir / "assets"
    ctx["hash_cache"] = {}
    ctx["img_reg"] = {"hash2name": {}, "name2hash": {}}
    ctx["feature_codes"] = _common.build_feature_codes(storage, args.nf, args.version)
    ctx["images_copied"] = 0
    ctx["refs_resolved"] = 0
    ctx["refs_stripped"] = 0
    log(f"扫描 {len(files)} md → 有效命令 {len(valid)}（跳过非命令 {skipped_noncmd}）")

    # 第 2 趟：构建（边校验用 name_set）
    built = []
    for f, md in valid:
        try:
            rel = f.relative_to(mml_dir)
            cat = list(rel.parts[:-1])
        except ValueError:
            cat = []
        result = build_one(md, args.nf, args.version, cat, ctx, f)
        if not result:
            continue
        logical_id, body = result
        (out_dir / f"{logical_id}.md").write_text(body, encoding="utf-8")
        built.append(logical_id)
        log(f"  ✓ {logical_id}")

    manifest = {
        "sop_version": SOP_VERSION, "object_type": "MMLCommand",
        "nf": args.nf, "version": args.version,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "command_count": len(built), "skipped_non_command": skipped_noncmd,
        "commands": built,
        "images_copied": ctx["images_copied"],
        "doc_refs_resolved": ctx["refs_resolved"],
        "doc_refs_stripped": ctx["refs_stripped"],
        "edge_modules": [m.__name__ for m in EDGE_MODULES]
        + (["edge_cmdref_intranet"] if ctx["intranet"] else []),
    }
    (out_dir / "_build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"构建完成：{len(built)} 命令（跳过非命令 {skipped_noncmd}）→ {out_dir}")
    print(f"  图片拷贝 {ctx['images_copied']} 张；文档引用解析 {ctx['refs_resolved']} / 剥死链 {ctx['refs_stripped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
