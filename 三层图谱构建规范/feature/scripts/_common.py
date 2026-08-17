"""特性层共享工具：原文清洗 / YAML / 边 / 章节解析 + feature_code·doc_type·license段 解析
+ 图片/文档引用改写（跨层约定，v0.11+）。"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import unquote

Edge = tuple[str, str]

# ============ 原文清洗（同命令层）===========
_TOC_LINE_RE = re.compile(r"^\s*-\s+\[.+?\]\(#.+?\)\s*$")


def clean_md(md: str) -> str:
    """去 TOC 链接行、去标题 anchor (#xxx)。"""
    out = []
    for ln in md.splitlines():
        if _TOC_LINE_RE.match(ln):
            continue
        if ln.startswith("#"):
            ln = re.sub(r"\]\(#.*?\)", "]", ln).replace("[", "").replace("]", "")
        out.append(ln)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


# ============ YAML ============
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
    return "\n".join(["---"] + [f"{k}: {to_yaml_value(v)}" for k, v in fields.items()] + ["---"])


# ============ 边 ============
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


# ============ 章节（按标题文本，不限层级）===========
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


def parse_frontmatter(md: str) -> dict:
    if not md.startswith("---"):
        return {}
    end = md.find("\n---", 3)
    if end < 0:
        return {}
    d: dict[str, Any] = {}
    for line in md[3:end].strip().splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            d[k] = [x.strip().strip('"') for x in re.split(r"\s*,\s*", inner)] if inner else []
        elif v.startswith('"') and v.endswith('"'):
            d[k] = v[1:-1]
        else:
            d[k] = v
    return d


# ============ feature_code / doc_type / license ============
FEATURE_CODE_RE = re.compile(r"[A-Z]{2,5}FD-\d{6}")
LICENSE_CODE_RE = re.compile(r"LKV[A-Z0-9]{6,}")


def parse_feature_code(s: str) -> str:
    m = FEATURE_CODE_RE.search(s or "")
    return m.group(0) if m else ""


def parse_license_codes(s: str) -> list[str]:
    return list(dict.fromkeys(LICENSE_CODE_RE.findall(s or "")))


# ============ doc_type（分类字段，从产品文档归纳；文件名优先，否则按所在子目录）===========
# 注意：doc_type 是多对一的「分类」，不参与 ID；ID 区分位用 slugify_doc()。
# 去激活 必须先于 激活（子串关系）。
_DOC_TYPE_KEYWORDS = [
    ("特性概述", "概述"),
    ("去激活", "去激活"),
    ("激活", "激活"),
    ("调测", "调测"),
    ("参考信息", "参考信息"),
    ("影响", "影响"),
    ("原理", "原理"),
    ("配置", "配置"),
    ("部署", "部署"),
    ("术语", "术语"),
]

# 文件名无关键词时，按所在子目录判 doc_type（最深子目录优先）。
_FOLDER_TYPE_KEYWORDS = {
    "实现原理": "原理", "原理": "原理",
    "特性配置": "配置", "配置": "配置",
    "参考信息": "参考信息",
    "调测": "调测",
}


def detect_doc_type(filename: str) -> str:
    """仅看文件名关键词（旧接口，保留）。"""
    for kw, dt in _DOC_TYPE_KEYWORDS:
        if kw in filename:
            return dt
    return ""


def derive_doc_type(filename: str, folder_segments: list[str]) -> str:
    """文件名关键词优先，否则按所在子目录（最深优先）判 doc_type，再退回『其它』。"""
    dt = detect_doc_type(filename)
    if dt:
        return dt
    for seg in reversed(folder_segments):
        if seg in _FOLDER_TYPE_KEYWORDS:
            return _FOLDER_TYPE_KEYWORDS[seg]
    return "其它"


# ============ slug（ID/存储文件名的区分位，源文件名 → 唯一 slug）===========
_OS_ILLEGAL = re.compile(r'[\\/:*?"<>|]')


def slugify_doc(filename: str) -> str:
    """源文件名 → slug：去 _数字id.md 后缀，清 OS 非法字符，保留中文/空格/英文。"""
    s = re.sub(r"_\d+\.md$", "", filename, flags=re.IGNORECASE)
    s = re.sub(r"\.md$", "", s, flags=re.IGNORECASE)
    s = _OS_ILLEGAL.sub("", s).strip()
    return s or "正文"


# ============ license 段切分 ============
# 段标题：#### [control_id LKVxxxx 名](#anchor)
# control_id 有两种格式：纯数字(81203214) / 字母数字混合(82200CKP)。code 锚定 LKV 格式。
LICENSE_HEAD_RE = re.compile(r"^####\s*\[\s*([A-Z0-9]+)\s+(LKV[A-Z0-9]{6,})\s+(.+?)\s*\]")


def split_license_sections(md: str) -> list[tuple[str, str, str, str]]:
    """控制项 md 按 license 段标题切成 [(control_id, license_code, name, body)]。"""
    lines = md.splitlines()
    sections: list[tuple[str, str, str, str]] = []
    cur = None
    for ln in lines:
        m = LICENSE_HEAD_RE.match(ln.strip())
        if m:
            if cur:
                sections.append((cur[0], cur[1], cur[2], "\n".join(cur[3]).strip()))
            cur = [m.group(1), m.group(2), m.group(3).strip(), []]
        elif cur is not None:
            cur[3].append(ln)
    if cur:
        sections.append((cur[0], cur[1], cur[2], "\n".join(cur[3]).strip()))
    return sections


def extract_license_nf(section_body: str) -> list[str]:
    m = re.search(r"归属NF\s*\|\s*([^|\n]+)", section_body or "")
    if not m:
        return []
    raw = m.group(1).strip().strip("|").strip()
    return [x.strip() for x in re.split(r"[、,，/]", raw) if x.strip()] if raw else []


# ============ 图片 / 文档引用改写（跨层约定，v0.11+）===========
# 详见 ../../conventions/资产图片与引用处理.md
_EXTERNAL_PREFIXES = ("http://", "https://", "//", "mailto:", "tel:", "data:")
_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]*)\)")
_FULLWIDTH_PAREN_RE = re.compile(r"（([^（）()]+)）")


def _parse_link_url(inner: str) -> str:
    """从 markdown 链接/图片 (...) 内容取 URL。URL 可含空格（如特性名/UDG MML命令 路径）；
    可选标题 ` "..."` 在 URL 后；去 `#fragment`。"""
    s = (inner or "").strip()
    qi = s.find('"')
    if qi != -1:
        s = s[:qi]
    return s.split("#")[0].strip()


def build_command_index(storage, nf: str, version: str) -> set[str]:
    """扫 Command/{nf}/{version}/{nf}@MMLCommand@*.md，返回命令名集合（@MMLCommand@ 后的文件名 stem）。"""
    names: set[str] = set()
    d = Path(storage) / "Command" / nf / version
    if d.is_dir():
        prefix = f"{nf}@MMLCommand@"
        for f in d.glob(f"{prefix}*.md"):
            names.add(f.stem[len(prefix):])
    return names


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
    """从全角括号 （CMD） 抽命令名，如 '查询ACL规则组配置（LST ACLGROUP）_00841277.md' → 'LST ACLGROUP'。"""
    if not text:
        return ""
    m = _FULLWIDTH_PAREN_RE.search(text)
    return m.group(1).strip() if m else ""


def _file_hash(p: Path) -> str:
    h = hashlib.md5()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def rewrite_images(md: str, src_md_path, dest_assets_dir, slug: str, reg: dict,
                   hash_cache: dict | None = None) -> tuple[str, int]:
    """把 md 里 ![]({旧}.assets/x.png) 引用的源 png 拷进 dest_assets_dir，改写为 ![](assets/x.png)。
    reg = {'hash2name': {}, 'name2hash': {}}：按特性文件夹共享，跨文档 hash 去重；同名异内容按 slug 前缀消歧。
    """
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
            return m.group(0)  # 源图缺失，原样保留
        name = _register_image(png_abs, dest_assets_dir, slug, reg, hash_cache)
        count += 1
        return f"![{alt}](assets/{name})"

    new_md = _IMG_RE.sub(repl, md)
    return new_md, count


def _register_image(png_abs: Path, dest_dir: Path, slug: str, reg: dict,
                    hash_cache: dict | None = None) -> str:
    src_key = str(png_abs)
    if hash_cache is not None and src_key in hash_cache:
        h = hash_cache[src_key]
    else:
        h = _file_hash(png_abs)
        if hash_cache is not None:
            hash_cache[src_key] = h
    if h in reg["hash2name"]:
        return reg["hash2name"][h]
    base = png_abs.name
    name = base
    if name in reg["name2hash"] and reg["name2hash"][name] != h:
        name = f"{slug}_{base}"
        i = 2
        while name in reg["name2hash"]:
            name = f"{slug}_{i}_{base}"
            i += 1
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(png_abs, dest_dir / name)
    reg["hash2name"][h] = name
    reg["name2hash"][name] = h
    return name


def rewrite_doc_refs(md: str, nf: str, cmd_index: set[str], feature_codes: set[str],
                     feature_src_to_id: dict | None = None) -> tuple[str, dict]:
    """改写 md 里的 [文字](目标) 文档引用为裸逻辑引用 [[ID]]：
    命令引用→[[{nf}@MMLCommand@{cmd}]]；特性引用→精确到具体子文档（feature_src_to_id 命中）否则退回概述 [[{nf}@Feature@{code}]]；
    其余/不可解析→剥 URL 留文字。cmd_index/feature_codes 即存在性判定。返回 (新md, {resolved, stripped})。
    """
    resolved = stripped = 0

    def repl(m: re.Match) -> str:
        nonlocal resolved, stripped
        label, inner = m.group(1), m.group(2)
        url = _parse_link_url(inner)
        if not url or url.startswith(_EXTERNAL_PREFIXES) or url.startswith("#"):
            return m.group(0)
        leaf = os.path.basename(unquote(url))

        # 命令引用：叶子名/标签的全角括号抽命令名；标签本身也可能是命令名（如 [LST ME]）
        cmd = extract_cmd_name(leaf) or extract_cmd_name(label)
        if not cmd:
            bare = label.strip().strip("*").strip()
            if bare in cmd_index:
                cmd = bare
        if cmd and cmd in cmd_index:
            resolved += 1
            return f"[[{nf}@MMLCommand@{cmd}]]"

        # 特性引用：源文件名精确匹配优先（概述+子文档都能命中；子文档文件名无特性码，必须靠此）；否则按特性码退回概述
        if feature_src_to_id is not None and leaf in feature_src_to_id:
            resolved += 1
            return f"[[{feature_src_to_id[leaf]}]]"
        fc = FEATURE_CODE_RE.search(leaf)
        if fc and fc.group(0) in feature_codes:
            resolved += 1
            return f"[[{nf}@Feature@{fc.group(0)}]]"

        # 其余：剥 URL 留文字
        stripped += 1
        return label

    new_md = _LINK_RE.sub(repl, md)
    return new_md, {"resolved": resolved, "stripped": stripped}

