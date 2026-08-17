"""命令层共享工具：frontmatter / 章节 / 参数表解析 + YAML / 边拼装
+ 图片/文档引用改写（跨层约定，v0.13+；输出 [[ID]]）。"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import unquote

Edge = tuple[str, str]

_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
_TITLE_RE = re.compile(r"^(.+?)[（(]([^（）()]+)[）)]\s*$")


# ---------- 原始 md 解析 ----------
def parse_title(md: str) -> tuple[str, str]:
    m = _H1_RE.search(md)
    if not m:
        return "", ""
    title = m.group(1).strip()
    mt = _TITLE_RE.match(title)
    if mt:
        return mt.group(1).strip(), mt.group(2).strip()
    return "", title


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


# ---------- frontmatter 读取 ----------
def parse_frontmatter(md: str) -> dict:
    """读 YAML frontmatter → dict（支持 `key: "v"` / `key: ["a","b"]` / bool）。"""
    if not md.startswith("---"):
        return {}
    end = md.find("\n---", 3)
    if end < 0:
        return {}
    block = md[3:end].strip()
    d: dict[str, Any] = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            d[k] = [x.strip().strip('"') for x in re.split(r"\s*,\s*", inner)] if inner else []
        elif v.startswith('"') and v.endswith('"'):
            d[k] = v[1:-1]
        elif v in ("true", "false"):
            d[k] = v == "true"
        else:
            d[k] = v
    return d


def parse_param_table(md: str) -> list[tuple[str, str, str]]:
    """参数说明 章节 markdown 表 → [(参数标识, 参数名称, 说明)]。跳过表头/分隔行。"""
    section = get_section(md, "参数说明")
    rows: list[tuple[str, str, str]] = []
    for line in section.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 3:
            continue
        head = cells[0]
        if head in ("参数标识", "Parameter", "参数", "名称"):
            continue
        if set(head) <= set("- :"):
            continue
        rows.append((cells[0], cells[1], cells[2]))
    return rows


# ---------- YAML 拼装 ----------
def _yaml_str(s: str) -> str:
    return '"' + s.replace('"', '\\"') + '"'


def to_yaml_value(v: Any) -> str:
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
        lines.append(f"{k}: {to_yaml_value(v)}")
    lines.append("---")
    return "\n".join(lines)


# ---------- 边 ----------
def dedup_edges(edges: list[Edge]) -> list[Edge]:
    seen, uniq = set(), []
    for e in edges:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return uniq


def build_edges_section(edges: list[Edge]) -> str:
    if not edges:
        return "## 边\n（暂无）"
    return "## 边\n" + "\n".join(f"- {rel}: [[{tgt}]]" for rel, tgt in edges)


# ---------- 逻辑ID ----------
def split_logical_id(logical_id: str) -> dict:
    """`UDG@MMLCommand@ADD URR` → {nf, type, local}。"""
    parts = logical_id.split("@", 2)
    if len(parts) < 3:
        return {}
    return {"nf": parts[0], "type": parts[1], "local": parts[2]}


def object_of_command(name: str) -> str:
    """`ADD URR` → `URR`；无 object 返 ''。"""
    parts = name.split()
    return parts[1] if len(parts) >= 2 else ""


def verb_of_command(name: str) -> str:
    parts = name.split()
    return parts[0] if parts else ""


# 只有配置类命令(ADD/MOD/DEL/RMV/SET)才"产生"配置对象；
# 查询类(LST/DSP)和动作类(ACT 激活/DEA 去激活/SWP/RST/CLR/SYN/LOD/ULD…)都不产生（但可关联到已存在的配置对象）
CONFIG_VERBS = {"ADD", "MOD", "DEL", "RMV", "SET"}


def is_config_verb(verb: str) -> bool:
    return verb in CONFIG_VERBS


def derive_object_kind(verbs: set) -> str:
    """简化 object_kind 推导（参照 COMMAND_GRAPH_SCHEMA §3.2.1）：
    有 ADD/MOD/DEL/RMV → entity；仅 SET → global_setting；仅 LST/DSP → query_target；默认 entity。"""
    if verbs & {"ADD", "MOD", "DEL", "RMV"}:
        return "entity"
    if "SET" in verbs:
        return "global_setting"
    if verbs and verbs <= {"LST", "DSP"}:
        return "query_target"
    return "entity"


_ZH_VERBS = ("增加", "添加", "修改", "删除", "查询", "显示", "设置", "配置", "激活", "清除", "刷新", "加载", "去激活")


def strip_verb_zh(name_zh: str) -> str:
    """`增加URR` → `URR`。"""
    for v in _ZH_VERBS:
        if name_zh.startswith(v):
            return name_zh[len(v):].strip()
    return name_zh


# ============ 图片 / 文档引用改写（跨层约定，v0.13+；输出 [[ID]]）===========
# 详见 ../../conventions/资产图片与引用处理.md
FEATURE_CODE_RE = re.compile(r"[A-Z]{2,5}FD-\d{6}")
_EXTERNAL_PREFIXES = ("http://", "https://", "//", "mailto:", "tel:", "data:")
_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]*)\)")
_FULLWIDTH_PAREN_RE = re.compile(r"（([^（）()]+)）")


def _parse_link_url(inner: str) -> str:
    """从 (...) 内容取 URL：URL 可含空格；可选标题 ` "..."`；去 `#fragment`。"""
    s = (inner or "").strip()
    qi = s.find('"')
    if qi != -1:
        s = s[:qi]
    return s.split("#")[0].strip()


def build_feature_codes(storage, nf: str, version: str) -> set[str]:
    """扫 Feature/{nf}/{version}/{nf}@Feature@*/ 文件夹，返回已有特性码集合。"""
    codes: set[str] = set()
    d = Path(storage) / "Feature" / nf / version
    if d.is_dir():
        prefix = f"{nf}@Feature@"
        for sub in d.iterdir():
            if sub.is_dir() and sub.name.startswith(prefix):
                m = FEATURE_CODE_RE.search(sub.name[len(prefix):])
                if m:
                    codes.add(m.group(0))
    return codes


def extract_cmd_name(text: str) -> str:
    """从全角括号 （CMD） 抽命令名。"""
    if not text:
        return ""
    m = _FULLWIDTH_PAREN_RE.search(text)
    return m.group(1).strip() if m else ""


def _file_hash(p) -> str:
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _register_image(png_abs, dest_dir, slug: str, reg: dict, hash_cache: dict | None = None) -> str:
    src_key = str(png_abs)
    if hash_cache is not None and src_key in hash_cache:
        h = hash_cache[src_key]
    else:
        h = _file_hash(png_abs)
        if hash_cache is not None:
            hash_cache[src_key] = h
    if h in reg["hash2name"]:
        return reg["hash2name"][h]
    base = Path(png_abs).name
    name = base
    if name in reg["name2hash"] and reg["name2hash"][name] != h:
        name = f"{slug}_{base}"
        i = 2
        while name in reg["name2hash"]:
            name = f"{slug}_{i}_{base}"
            i += 1
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy2(png_abs, Path(dest_dir) / name)
    reg["hash2name"][h] = name
    reg["name2hash"][name] = h
    return name


def rewrite_images(md: str, src_md_path, dest_assets_dir, slug: str, reg: dict,
                   hash_cache: dict | None = None) -> tuple[str, int]:
    """把 md 里 ![]({旧}.assets/x.png) 引用的源 png 拷进 dest_assets_dir，改写为 ![](assets/x.png)。"""
    src_dir = Path(src_md_path).parent
    dest_assets_dir = Path(dest_assets_dir)
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        alt = m.group(1)
        url = _parse_link_url(m.group(2))
        if not url or url.startswith(_EXTERNAL_PREFIXES) or url.startswith("#"):
            return m.group(0)
        png_abs = (src_dir / unquote(url)).resolve()
        if not png_abs.exists():
            return m.group(0)
        name = _register_image(png_abs, dest_assets_dir, slug, reg, hash_cache)
        count += 1
        return f"![{alt}](assets/{name})"

    new_md = _IMG_RE.sub(repl, md)
    return new_md, count


def rewrite_doc_refs(md: str, nf: str, cmd_index: set[str], feature_codes: set[str],
                     feature_src_to_id: dict | None = None) -> tuple[str, dict]:
    """改写 md 里的 [文字](目标) 文档引用为裸逻辑引用 [[ID]]：
    命令→[[{nf}@MMLCommand@{cmd}]]；特性→精确到具体子文档（feature_src_to_id 命中）否则退回概述；其余→剥 URL 留文字。"""
    resolved = stripped = 0

    def repl(m: re.Match) -> str:
        nonlocal resolved, stripped
        label, inner = m.group(1), m.group(2)
        url = _parse_link_url(inner)
        if not url or url.startswith(_EXTERNAL_PREFIXES) or url.startswith("#"):
            return m.group(0)
        leaf = os.path.basename(unquote(url))
        cmd = extract_cmd_name(leaf) or extract_cmd_name(label)
        if not cmd:
            bare = label.strip().strip("*").strip()
            if bare in cmd_index:
                cmd = bare
        if cmd and cmd in cmd_index:
            resolved += 1
            return f"[[{nf}@MMLCommand@{cmd}]]"
        fc = FEATURE_CODE_RE.search(leaf)
        if feature_src_to_id is not None and leaf in feature_src_to_id:
            resolved += 1
            return f"[[{feature_src_to_id[leaf]}]]"
        if fc and fc.group(0) in feature_codes:
            resolved += 1
            return f"[[{nf}@Feature@{fc.group(0)}]]"
        stripped += 1
        return label

    new_md = _LINK_RE.sub(repl, md)
    return new_md, {"resolved": resolved, "stripped": stripped}
