from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET

import chardet
from bs4 import BeautifulSoup, Comment, NavigableString, Tag


REMOVE_MARKERS = (
    "footernavbar", "copyright", "bottomnavbtn", "copyrightbottombar",
    "breadcrumb", "toolbar", "navbtn", "footer", "headernav", "topnav",
)

# CHM 工程文件（.hhc, Sitemap 1.0）解析：用于无 navi.xml 时替代目录树。
# 注意：华为 hhc 的 <param> 标签不自闭合（">" 直接接下一个 param），正则需兼容 /> 与 >。
_HHC_OBJ = re.compile(
    r'<param\s+name="Name"\s+value="([^"]*)"\s*/?\s*>\s*<param\s+name="Local"\s+value="([^"]*)"',
    re.I,
)
_HHC_UL_OPEN = re.compile(r"<UL\b", re.I)
_HHC_UL_CLOSE = re.compile(r"</UL\b", re.I)


@dataclass
class TopicRecord:
    topic_id: str
    parent_id: str
    txt: str
    topic_path: List[str]
    url: str
    html_abs_path: str
    html_rel_path: str
    md_rel_path: str
    exists: bool
    file_type: str = ""  # html | pdf
    mode: str = ""  # html | pdf | stub


# =========================
# 通用工具函数
# =========================
def _win_long(path: Path) -> Path:
    """Windows 上把绝对路径转为 ``\\\\?\\`` 前缀形式，突破 MAX_PATH(260) 限制。

    失败页根因：产品文档深层章节 + 图片资产（``<md>.assets/`` 子目录）叠加后路径
    超过 260 字符，LongPathsEnabled=0 时 ``mkdir``/``write``/``copy2`` 抛
    [WinError 3] 系统找不到指定的路径。加 ``\\\\?\\`` 前缀后文件系统调用不再受
    260 限制。

    注意：仅供**文件系统调用**与**枚举**（rglob——普通路径对 >260 条目静默漏扫）
    使用；返回值不要用于相对路径计算 / md 链接映射（``os.path.relpath`` 等对
    ``\\\\?\\`` 前缀会算错）。UNC（``\\\\server\\share``）转 ``\\\\?\\UNC\\`` 形式。

    与 ``config.win_long`` 同逻辑（本模块经 runner 按文件路径独立加载，不能用
    包相对导入，故内联；改动时两处同步）。
    """
    if os.name != "nt":
        return path
    s = str(path)
    if s.startswith("\\\\?\\"):
        return path
    p = os.path.abspath(s)
    if p.startswith("\\\\"):  # UNC 网络路径
        return Path("\\\\?\\UNC\\" + p[2:])
    return Path("\\\\?\\" + p)


def read_text_auto(file_path: str) -> str:
    """自适应解码（v0.24.0 重写：确定性判据优先，chardet 降为兜底）。

    旧实现的坑（整文件乱码根因，CR-20260820-002）：chardet 置信度 ≥0.7 即采用，
    而 GBK/Latin 解码几乎不抛异常——UTF-8 的 html 被统计猜测误判成 GBK 族时
    "成功"产出整文件乱码并固化。新顺序（确定性从高到低）：
      ① BOM（utf-8-sig / utf-16）——文件自声明，最权威
      ② utf-8 严格解码——utf-8 可自校验，严格通过即确定
      ③ HTML meta charset 声明（头部 2KB）——文档自声明编码
      ④ chardet 兜底（阈值 0.9，前 64KB 采样）
      ⑤ 序贯严格解码（gb18030 超集先于 gbk）
      ⑥ errors="ignore" 最后兜底
    """
    raw = _win_long(Path(file_path)).read_bytes()

    # ① BOM
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")

    # ② utf-8 严格自校验（GBK 文本几乎不可能整段合法 utf-8）
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # ③ HTML meta charset（文档自声明，权威；gb2312/gbk 统一用超集 gb18030 防生僻字截断）
    m = re.search(rb'charset\s*=\s*["\']?\s*([A-Za-z0-9_\-]+)', raw[:2048], re.IGNORECASE)
    if m:
        declared = m.group(1).decode("ascii", errors="ignore").lower()
        enc = {"gb2312": "gb18030", "gbk": "gb18030"}.get(declared, declared)
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            pass

    # ④ chardet 兜底（高阈值；前 64KB 采样）
    try:
        detected = chardet.detect(raw[:65536])
        if detected and detected.get("encoding") and (detected.get("confidence") or 0) >= 0.9:
            try:
                return raw.decode(detected["encoding"])
            except Exception:
                pass
    except Exception:
        pass

    # ⑤ 序贯严格解码（超集优先）
    for enc in ("gb18030", "gbk", "big5", "windows-1252", "iso-8859-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue

    # ⑥ 最后兜底
    return raw.decode("gb18030", errors="ignore")


def safe_filename(name: str, max_len: int = 80) -> str:
    raw = name or "untitled"
    safe = re.sub(r'[<>:"/\\|?*]+', '_', raw)
    safe = re.sub(r"\s+", " ", safe).strip().rstrip(". ")
    if not safe:
        safe = "untitled"
    if len(safe) <= max_len:
        return safe

    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]
    keep = max(max_len - 9, 20)
    return f"{safe[:keep]}_{digest}"


def safe_relpath(path_str: str, start: Path) -> str:
    try:
        return Path(os.path.relpath(path_str, start)).as_posix()
    except Exception:
        return path_str


def detect_file_type(url: str) -> str:
    return "pdf" if url and url.lower().endswith(".pdf") else "html"


# =========================
# HTML -> Markdown 转换器
# =========================
class HtmlToMarkdownConverter:
    BLOCK_TAGS = {
        "article", "section", "div", "main", "body", "header", "footer", "nav",
        "p", "ul", "ol", "li", "table", "thead", "tbody", "tfoot", "tr", "td", "th",
        "pre", "blockquote", "figure", "figcaption",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "hr", "details", "dl", "dt", "dd",
    }
    INLINE_TAGS = {
        "a", "span", "strong", "b", "em", "i", "code", "img", "br",
        "sub", "sup", "small", "mark", "u", "s", "del", "ins", "label",
    }
    RAW_HTML_TAGS = {"svg", "math", "iframe", "object", "embed", "canvas"}

    def __init__(
        self,
        log_message: Callable[[str], None] = print,
        copy_non_image_link_targets: bool = False,
    ) -> None:
        self.log_message = log_message
        self.copy_non_image_link_targets = copy_non_image_link_targets
        self._source_html_path: Optional[Path] = None
        self._output_md_path: Optional[Path] = None
        self._page_assets_dir: Optional[Path] = None
        self._html_abs_to_md_abs: Dict[str, str] = {}
        self._copied_assets: Dict[str, str] = {}

    # ---------- 对外入口 ----------
    def convert_file(
        self,
        html_file: str,
        md_file: str,
        html_abs_to_md_abs: Optional[Dict[str, str]] = None,
    ) -> None:
        html_text = read_text_auto(html_file)
        markdown, _ = self.convert_html_string(
            html_text,
            source_html_path=html_file,
            output_md_path=md_file,
            html_abs_to_md_abs=html_abs_to_md_abs,
        )
        md_path = Path(md_file)
        md_path_long = _win_long(md_path)
        md_path_long.parent.mkdir(parents=True, exist_ok=True)
        md_path_long.write_text(markdown, encoding="utf-8")

    def convert_html_string(
        self,
        html_text: str,
        source_html_path: Optional[str] = None,
        output_md_path: Optional[str] = None,
        html_abs_to_md_abs: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, bool]:
        self._prepare_context(source_html_path, output_md_path, html_abs_to_md_abs)
        soup = self._build_clean_soup(html_text)
        meaningful = self._is_meaningful_soup(soup)
        root = soup.body if soup.body else soup
        md = self._post_process_markdown(self._render_children(root).strip())
        return md + ("\n" if md else ""), meaningful

    def is_meaningful_html(self, html_text: str) -> bool:
        return self._is_meaningful_soup(self._build_clean_soup(html_text))

    # ---------- 预处理 ----------
    def _prepare_context(
        self,
        source_html_path: Optional[str],
        output_md_path: Optional[str],
        html_abs_to_md_abs: Optional[Dict[str, str]],
    ) -> None:
        self._source_html_path = Path(source_html_path).resolve() if source_html_path else None
        self._output_md_path = Path(output_md_path).resolve() if output_md_path else None
        self._page_assets_dir = self._output_md_path.with_suffix(".assets") if self._output_md_path else None
        self._html_abs_to_md_abs = html_abs_to_md_abs or {}
        self._copied_assets = {}

    def _build_clean_soup(self, html_text: str) -> BeautifulSoup:
        soup = BeautifulSoup(html_text, "html.parser")
        self._cleanup_soup(soup)
        return soup

    @staticmethod
    def _tag_marker(tag: Optional[Tag]) -> str:
        if not isinstance(tag, Tag):
            return ""
        tag_name = getattr(tag, "name", "") or ""
        cls = " ".join(tag.get("class", []) or [])
        tag_id = tag.get("id", "") or ""
        return f"{tag_name} {cls} {tag_id}".lower()

    def _cleanup_soup(self, soup: BeautifulSoup) -> None:
        for tag in soup.find_all(["script", "style", "noscript", "template"]):
            tag.decompose()
        for comment in soup.find_all(string=lambda x: isinstance(x, Comment)):
            comment.extract()

        to_remove = []
        for tag in soup.find_all(True):
            if getattr(tag, "attrs", None) is None:
                continue
            marker = self._tag_marker(tag)
            if any(target in marker for target in REMOVE_MARKERS):
                to_remove.append(tag)
        for tag in to_remove:
            if getattr(tag, "attrs", None) is not None:
                tag.decompose()

    def _is_meaningful_soup(self, soup: BeautifulSoup) -> bool:
        body = soup.body if soup.body else soup
        if body.find(["table", "img", "pre", "code", "ul", "ol", "blockquote", "svg", "math"]):
            return True

        lines = [re.sub(r"\s+", " ", x).strip() for x in body.get_text("\n", strip=True).splitlines()]
        lines = [x for x in lines if x]
        if not lines:
            return False

        title_candidates = []
        if soup.title and soup.title.get_text(strip=True):
            title_candidates.append(soup.title.get_text(strip=True))
        h1 = body.find("h1")
        if h1 and h1.get_text(" ", strip=True):
            title_candidates.append(h1.get_text(" ", strip=True))

        filtered = [
            line for line in lines
            if line not in title_candidates and not re.search(r"版权所有|copyright", line, re.I)
        ]
        return bool(filtered) and len("\n".join(filtered).strip()) >= 20

    @staticmethod
    def _post_process_markdown(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    # ---------- 结构判断 ----------
    def _has_class_name(self, node: Tag, *keywords: str) -> bool:
        if not isinstance(node, Tag):
            return False
        classes = node.get("class", []) or []
        if isinstance(classes, str):
            classes = [classes]
        joined = " ".join(classes).lower()
        return any(k.lower() in joined for k in keywords)

    def _has_block_child(self, tag: Tag) -> bool:
        for child in tag.children:
            if isinstance(child, Tag) and ((getattr(child, "name", "") or "").lower() in self.BLOCK_TAGS):
                return True
        return False

    def _is_block_like(self, node: Tag) -> bool:
        if not isinstance(node, Tag):
            return False
        name = (getattr(node, "name", "") or "").lower()
        return name in self.BLOCK_TAGS or self._has_block_child(node)

    # ---------- 渲染主流程 ----------
    def _render_children(self, parent: Tag, indent: int = 0) -> str:
        parts: List[str] = []
        for child in parent.children:
            rendered = self._render_node(child, indent=indent)
            if rendered:
                parts.append(rendered)
        return "".join(parts)

    def _render_node(self, node, indent: int = 0) -> str:
        if isinstance(node, NavigableString):
            text = self._normalize_ws(str(node))
            return text if text else ""
        if not isinstance(node, Tag):
            return ""

        name = (getattr(node, "name", "") or "").lower()

        if name in self.RAW_HTML_TAGS:
            return str(node).strip() + "\n\n"

        _node_classes = node.get("class", []) or []
        _is_mml_section = any(str(c).lower().startswith("mml") for c in _node_classes)
        if (self._has_class_name(node, "note", "warning", "caution", "tip")
                and name == "div"
                and not _is_mml_section):
            return self._render_note_block(node)

        if name == "div" and self._has_class_name(node, "fignone"):
            return self._render_vendor_figure_block(node, indent)

        if re.fullmatch(r"h[1-6]", name):
            text = self._render_inline(node).strip()
            return f"{'#' * int(name[1])} {text}\n\n" if text else ""

        if name == "p":
            if self._has_block_child(node):
                return self._render_mixed_block(node, indent=indent)
            text = self._render_inline(node).strip()
            return f"{text}\n\n" if text else ""

        if name == "ul":
            # Handle malformed <ul> without <li> children (e.g. alarm handling sections)
            if not node.find_all("li", recursive=False):
                return self._render_children(node, indent=indent) + "\n"
            return self._render_list(node, ordered=False, indent=indent) + "\n"
        if name == "ol":
            if not node.find_all("li", recursive=False):
                return self._render_children(node, indent=indent) + "\n"
            return self._render_list(node, ordered=True, indent=indent) + "\n"
        if name == "pre":
            return self._render_pre(node)
        if name == "blockquote":
            inner = self._render_children(node).strip() or self._render_inline(node).strip()
            if not inner:
                return ""
            quoted = "\n".join(f"> {line}" if line.strip() else ">" for line in inner.splitlines())
            return quoted + "\n\n"
        if name == "table":
            return self._render_table(node)
        if name == "img":
            img = self._render_inline(node).strip()
            return f"{img}\n\n" if img else ""
        if name == "hr":
            return "---\n\n"
        if name == "figure":
            return self._render_figure(node)
        if name == "details":
            return self._render_details(node)
        if name in {"dl", "dt", "dd"}:
            return self._render_definition_like(node)
        if name == "li":
            text, nested_blocks = self._split_li_content(node, indent=indent)
            if not text and not nested_blocks:
                return ""
            lines = [f"- {text}".rstrip()]
            for block in nested_blocks:
                if block:
                    lines.append(self._indent_text(block.rstrip("\n"), "  "))
            return "\n".join(lines) + "\n"

        if self._is_block_like(node):
            return self._render_mixed_block(node, indent=indent)

        if name in self.INLINE_TAGS:
            return self._render_inline(node)
        return self._render_inline(node)

    # Type prefix mapping for advisory blocks
    _ADVISORY_TYPE_MAP = {
        "note": "说明",
        "warning": "警告",
        "caution": "注意",
        "tip": "提示",
    }

    def _detect_advisory_type(self, node: Tag) -> str:
        """Detect advisory block type from class name and return Chinese prefix."""
        classes = " ".join(node.get("class", []) or []).lower()
        for key, label in self._ADVISORY_TYPE_MAP.items():
            if key in classes:
                return label
        return ""

    def _extract_advisory_title(self, node: Tag) -> str:
        """Extract title text from notetitle/warningtitle/etc. span."""
        for child in node.find_all(True, recursive=False):
            if self._has_class_name(child, "notetitle", "warningtitle", "cautiontitle", "tiptitle"):
                text = child.get_text(" ", strip=True)
                if text:
                    return text
        return ""

    def _render_note_block(self, node: Tag) -> str:
        advisory_type = self._detect_advisory_type(node)
        title = self._extract_advisory_title(node)

        body = None
        for child in node.find_all(True):
            if self._has_class_name(child, "notebody", "warningbody", "cautionbody", "tipbody"):
                body = child
                break
        target = body or node
        text = self._post_process_markdown(self._render_children(target).strip())
        if not text:
            return ""

        # Prepend type prefix if we have one
        prefix = title if title else advisory_type
        if prefix:
            text = f"**{prefix}**\n{text}"

        quoted = "\n".join(f"> {line}" if line.strip() else ">" for line in text.splitlines())
        return quoted + "\n\n"

    def _render_vendor_figure_block(self, node: Tag, indent: int = 0) -> str:
        parts: List[str] = []
        cap = None
        for child in node.find_all(True, recursive=False):
            if self._has_class_name(child, "figcap"):
                cap = child
                break
        if cap:
            cap_text = self._render_inline(cap).strip()
            if cap_text:
                parts.append(cap_text)
        for child in node.children:
            if child is cap:
                continue
            rendered = self._render_node(child, indent=indent).strip()
            if rendered:
                parts.append(rendered)
        return "\n\n".join(parts).strip() + ("\n\n" if parts else "")

    # ---------- 普通块/行内混合处理 ----------
    def _render_mixed_block(self, node: Tag, indent: int = 0) -> str:
        parts: List[str] = []
        inline_buf: List[str] = []

        def flush_inline() -> None:
            nonlocal inline_buf
            if not inline_buf:
                return
            text = "".join(inline_buf)
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r" *<br> *", "<br>", text).strip()
            if text:
                parts.append(text + "\n\n")
            inline_buf = []

        for child in node.children:
            if isinstance(child, NavigableString):
                txt = self._normalize_ws(str(child))
                if txt:
                    if inline_buf and not inline_buf[-1].endswith((" ", "<br>")):
                        inline_buf.append(" ")
                    inline_buf.append(txt)
                continue
            if not isinstance(child, Tag):
                continue

            child_name = (getattr(child, "name", "") or "").lower()
            if child_name == "br":
                inline_buf.append("<br>")
                continue

            if self._is_block_like(child) and child_name not in {"td", "th"}:
                flush_inline()
                rendered = self._render_node(child, indent=indent).strip()
                if rendered:
                    parts.append(rendered + "\n\n")
            else:
                inline = self._render_inline(child)
                if inline:
                    if inline_buf and not inline_buf[-1].endswith((" ", "<br>")):
                        inline_buf.append(" ")
                    inline_buf.append(inline)

        flush_inline()
        return "".join(parts)

    def _split_mixed_inline_and_blocks(self, node: Tag, indent: int = 0) -> Tuple[str, List[str]]:
        inline_parts: List[str] = []
        nested_blocks: List[str] = []

        for child in node.children:
            if isinstance(child, NavigableString):
                txt = self._normalize_ws(str(child))
                if txt:
                    inline_parts.append(txt)
                continue
            if not isinstance(child, Tag):
                continue

            child_name = (getattr(child, "name", "") or "").lower()
            if child_name == "br":
                inline_parts.append("<br>")
                continue

            if self._is_block_like(child) and child_name not in {"td", "th"}:
                rendered = self._render_node(child, indent=indent + 1).rstrip()
                if rendered:
                    nested_blocks.append(rendered)
            else:
                inline = self._render_inline(child).strip()
                if inline:
                    inline_parts.append(inline)

        first_text = "".join(inline_parts)
        first_text = re.sub(r"[ \t]+", " ", first_text)
        first_text = re.sub(r" *<br> *", "<br>", first_text).strip()
        return first_text, nested_blocks

    # ---------- 行内渲染 ----------
    def _render_inline(self, node) -> str:
        if isinstance(node, NavigableString):
            return self._normalize_ws(str(node))
        if not isinstance(node, Tag):
            return ""

        name = (getattr(node, "name", "") or "").lower()
        if name == "br":
            return "<br>"
        if name == "sup":
            inner = self._render_inline_children(node).strip()
            return f"<sup>{inner}</sup>" if inner else ""
        if name == "sub":
            inner = self._render_inline_children(node).strip()
            return f"<sub>{inner}</sub>" if inner else ""
        if name in {"strong", "b"}:
            inner = self._render_inline_children(node).strip()
            return f"**{inner}**" if inner else ""
        if name in {"em", "i"}:
            inner = self._render_inline_children(node).strip()
            return f"*{inner}*" if inner else ""
        if name == "code":
            if node.parent and getattr(node.parent, "name", "").lower() == "pre":
                return node.get_text()
            return self._wrap_inline_code(node.get_text(strip=False))
        if name == "a":
            href = (node.get("href") or "").strip()
            text = self._render_inline_children(node).strip() or href
            return f"[{text}]({self._rewrite_href(href)})" if href else text
        if name == "img":
            src = (node.get("src") or "").strip()
            alt = (node.get("alt") or "").strip()
            title = (node.get("title") or "").strip()
            if not src:
                return alt
            rewritten = self._rewrite_src(src)
            return f'![{alt}]({rewritten} "{title}")' if title else f"![{alt}]({rewritten})"
        return self._render_inline_children(node)

    def _render_inline_children(self, parent: Tag) -> str:
        parts: List[str] = []
        for child in parent.children:
            if isinstance(child, NavigableString):
                txt = self._normalize_ws(str(child))
                if txt:
                    if parts and not str(parts[-1]).endswith((" ", "<br>")):
                        parts.append(" ")
                    parts.append(txt)
                continue
            if not isinstance(child, Tag):
                continue

            child_name = (getattr(child, "name", "") or "").lower()
            if self._is_block_like(child) and child_name not in {"td", "th"}:
                block_text = self._render_node(child).strip()
                if block_text:
                    if parts and not str(parts[-1]).endswith("\n\n"):
                        parts.append("\n\n")
                    parts.append(block_text)
                    parts.append("\n\n")
            else:
                inline = self._render_inline(child)
                if inline:
                    if parts and not str(parts[-1]).endswith((" ", "<br>", "\n\n")):
                        parts.append(" ")
                    parts.append(inline)

        text = "".join(parts)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" *<br> *", "<br>", text)
        return text.strip()

    @staticmethod
    def _ol_bullet(idx: int, ol_type: str) -> str:
        """Generate bullet label for ordered list based on type attribute."""
        if ol_type == "a":
            return f"{chr(ord('a') + idx - 1)}."
        if ol_type == "A":
            return f"{chr(ord('A') + idx - 1)}."
        if ol_type == "i":
            # Simple roman numeral for reasonable indices
            roman_map = [(10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
            n = idx
            parts = []
            for val, sym in roman_map:
                while n >= val:
                    parts.append(sym)
                    n -= val
            return f"{''.join(parts)}."
        if ol_type == "I":
            return HtmlToMarkdownConverter._ol_bullet(idx, "i").upper()
        return f"{idx}."

    # ---------- 列表 ----------
    def _render_list(self, list_tag: Tag, ordered: bool, indent: int = 0) -> str:
        ol_type = (list_tag.get("type") or "").strip() if ordered else ""
        start_idx = int(list_tag.get("start") or 1)
        lines: List[str] = []
        for li_idx, li in enumerate(list_tag.find_all("li", recursive=False)):
            idx = start_idx + li_idx
            if ordered and ol_type:
                bullet = self._ol_bullet(idx, ol_type)
            else:
                bullet = f"{idx}." if ordered else "-"
            prefix = "  " * indent + bullet + " "
            first_text, nested_blocks = self._split_li_content(li, indent=indent)
            lines.append(prefix + first_text if first_text else prefix.rstrip())
            for block in nested_blocks:
                block = block.rstrip("\n")
                if block:
                    lines.append(self._indent_text(block, "  " * (indent + 1)))
        return "\n".join(lines).rstrip() + "\n"

    def _split_li_content(self, li: Tag, indent: int = 0) -> Tuple[str, List[str]]:
        inline_parts: List[str] = []
        nested_blocks: List[str] = []

        for child in li.children:
            if isinstance(child, NavigableString):
                txt = self._normalize_ws(str(child))
                if txt:
                    inline_parts.append(txt)
                continue
            if not isinstance(child, Tag):
                continue

            name = (getattr(child, "name", "") or "").lower()
            if name in {"ul", "ol"}:
                nested_blocks.append(self._render_node(child, indent=indent + 1).rstrip())
            elif name == "pre":
                nested_blocks.append(self._render_pre(child).rstrip())
            elif name == "table":
                nested_blocks.append(self._render_table(child).rstrip())
            elif name == "blockquote":
                nested_blocks.append(self._render_node(child).rstrip())
            elif name == "p":
                if self._has_block_child(child):
                    p_text, p_blocks = self._split_mixed_inline_and_blocks(child, indent=indent)
                    if p_text:
                        if not inline_parts:
                            inline_parts.append(p_text)
                        else:
                            nested_blocks.append(p_text)
                    nested_blocks.extend(p_blocks)
                else:
                    txt = self._render_inline(child).strip()
                    if txt:
                        if not inline_parts:
                            inline_parts.append(txt)
                        else:
                            nested_blocks.append(txt)
            elif self._is_block_like(child):
                nested_blocks.append(self._render_node(child, indent=indent + 1).rstrip())
            else:
                txt = self._render_inline(child).strip()
                if txt:
                    inline_parts.append(txt)

        first_text = "".join(inline_parts)
        first_text = re.sub(r"[ \t]+", " ", first_text)
        first_text = re.sub(r" *<br> *", "<br>", first_text).strip()
        return first_text, nested_blocks

    # ---------- 代码 ----------
    def _render_pre(self, pre: Tag) -> str:
        code_tag = pre.find("code")
        source = code_tag if isinstance(code_tag, Tag) else pre
        code_text = source.get_text("\n", strip=False).rstrip("\n")
        # Collapse excessive blank lines introduced by <span> tags inside <pre>
        code_text = re.sub(r"\n{3,}", "\n\n", code_text)
        lang = self._extract_code_language(source)
        fence = "```" if "```" not in code_text else "````"
        return f"{fence}{lang}\n{code_text}\n{fence}\n\n"

    @staticmethod
    def _extract_code_language(tag: Optional[Tag]) -> str:
        if not isinstance(tag, Tag):
            return ""
        for cls in tag.get("class", []) or []:
            lower = cls.lower()
            if lower.startswith("language-"):
                return lower[len("language-"):]
            if lower.startswith("lang-"):
                return lower[len("lang-"):]
        return ""

    # ---------- 表格 ----------
    def _expand_table_to_grid(self, table: Tag) -> List[List[str]]:
        trs = table.find_all("tr")
        if not trs:
            return []

        grid: List[List[str]] = []
        span_map: Dict[Tuple[int, int], str] = {}

        for r_idx, tr in enumerate(trs):
            row: List[str] = []
            col = 0
            cells = tr.find_all(["th", "td"], recursive=False)

            def fill_spans() -> None:
                nonlocal col
                while (r_idx, col) in span_map:
                    row.append(span_map.pop((r_idx, col)))
                    col += 1

            fill_spans()
            for cell in cells:
                fill_spans()
                text = self._render_table_cell(cell)
                rowspan = int(cell.get("rowspan", 1) or 1)
                colspan = int(cell.get("colspan", 1) or 1)

                for i in range(colspan):
                    row.append(text)
                    for rs in range(1, rowspan):
                        span_map[(r_idx + rs, col + i)] = text
                col += colspan

            fill_spans()
            grid.append(row)

        return grid

    def _render_table(self, table: Tag) -> str:
        rows = self._expand_table_to_grid(table)
        if not rows:
            return ""

        max_cols = max(len(r) for r in rows)
        rows = [r + [""] * (max_cols - len(r)) for r in rows]

        header = rows[0]
        body = rows[1:] if len(rows) > 1 else []
        sep = ["---"] * max_cols
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(sep) + " |",
        ]
        for row in body:
            lines.append("| " + " | ".join(row) + " |")

        result = "\n".join(lines) + "\n\n"

        # Prepend caption if present
        caption = table.find("caption")
        if caption:
            cap_text = caption.get_text(" ", strip=True)
            if cap_text:
                result = f"*{cap_text}*\n\n{result}"

        return result

    def _render_table_cell(self, cell: Tag) -> str:
        text = self._render_table_cell_content(cell)
        text = re.sub(r"[ \t]+", " ", text).strip()
        text = re.sub(r"(<br>\s*){2,}", "<br>", text)
        return text.replace("|", r"\|")

    def _render_table_cell_content(self, node) -> str:
        if isinstance(node, NavigableString):
            return self._normalize_ws(str(node))
        if not isinstance(node, Tag):
            return ""

        name = (getattr(node, "name", "") or "").lower()
        if name == "br":
            return "<br>"
        if name in {"strong", "b"}:
            inner = "".join(self._render_table_cell_content(c) for c in node.children).strip()
            return f"**{inner}**" if inner else ""
        if name in {"em", "i"}:
            inner = "".join(self._render_table_cell_content(c) for c in node.children).strip()
            return f"*{inner}*" if inner else ""
        if name == "code":
            if node.parent and getattr(node.parent, "name", "").lower() == "pre":
                return self._wrap_inline_code(node.get_text(" ", strip=True))
            return self._wrap_inline_code(node.get_text(" ", strip=False))
        if name == "a":
            href = (node.get("href") or "").strip()
            text = "".join(self._render_table_cell_content(c) for c in node.children).strip() or href
            return f"[{text}]({self._rewrite_href(href)})" if href else text
        if name == "img":
            src = (node.get("src") or "").strip()
            alt = (node.get("alt") or "").strip()
            title = (node.get("title") or "").strip()
            if not src:
                return alt
            rewritten = self._rewrite_src(src)
            return f'![{alt}]({rewritten} "{title}")' if title else f"![{alt}]({rewritten})"

        if name == "div" and self._has_class_name(node, "note", "warning", "caution", "tip"):
            title = ""
            body_parts: List[str] = []
            for child in node.children:
                if not isinstance(child, Tag):
                    txt = self._normalize_ws(str(child))
                    if txt:
                        body_parts.append(txt)
                    continue
                if self._has_class_name(child, "notetitle", "warningtitle", "cautiontitle", "tiptitle"):
                    title = self._normalize_ws(child.get_text(" ", strip=True))
                elif self._has_class_name(child, "notebody", "warningbody", "cautionbody", "tipbody"):
                    body = self._render_table_cell_content(child).strip()
                    if body:
                        body_parts.append(body)
                else:
                    body = self._render_table_cell_content(child).strip()
                    if body:
                        body_parts.append(body)

            body_text = "<br>".join(x for x in body_parts if x)
            if title and body_text:
                return f"{title}{body_text}"
            return title or body_text

        if name in {"ul", "ol"}:
            items = []
            for li in node.find_all("li", recursive=False):
                item = self._render_table_cell_content(li).strip()
                if item:
                    items.append(f"- {item}")
            return "<br>".join(items)

        if name == "pre":
            code = node.get_text(" ", strip=True)
            return self._wrap_inline_code(code) if code else ""

        if name in {"p", "div", "section", "span", "li"}:
            parts = []
            for child in node.children:
                rendered = self._render_table_cell_content(child).strip()
                if rendered:
                    parts.append(rendered)
            return "<br>".join(parts) if name in {"p", "div", "section"} else "".join(parts)

        # For <td>/<th> cells, join block-level children with <br>
        if name in {"td", "th"}:
            parts: List[str] = []
            for child in node.children:
                rendered = self._render_table_cell_content(child)
                if rendered:
                    rendered = rendered.strip()
                    if rendered:
                        parts.append(rendered)
            return "<br>".join(parts)

        parts = []
        for child in node.children:
            rendered = self._render_table_cell_content(child)
            if rendered:
                parts.append(rendered)
        return "".join(parts)

    # ---------- 其他块 ----------
    def _render_figure(self, figure: Tag) -> str:
        parts: List[str] = []
        for child in figure.children:
            if isinstance(child, Tag) and ((getattr(child, "name", "") or "").lower() == "figcaption"):
                caption = self._render_inline(child).strip()
                if caption:
                    parts.append(f"*{caption}*")
            else:
                rendered = self._render_node(child).strip()
                if rendered:
                    parts.append(rendered)
        return "\n\n".join(parts) + ("\n\n" if parts else "")

    def _render_details(self, details: Tag) -> str:
        summary = details.find("summary", recursive=False)
        lines: List[str] = []
        if summary:
            title = self._render_inline(summary).strip()
            if title:
                lines.append(f"**{title}**")
        for child in details.children:
            if child is summary:
                continue
            rendered = self._render_node(child).strip()
            if rendered:
                lines.append(rendered)
        return "\n\n".join(lines).strip() + ("\n\n" if lines else "")

    def _render_definition_like(self, node: Tag) -> str:
        node_name = (getattr(node, "name", "") or "").lower()
        if node_name == "dt":
            txt = self._render_inline(node).strip()
            return f"- **{txt}**\n" if txt else ""
        if node_name == "dd":
            txt = self._render_children(node).strip() or self._render_inline(node).strip()
            return f"  {txt}\n" if txt else ""
        return self._render_children(node)

    # ---------- 文本/路径辅助 ----------
    @staticmethod
    def _normalize_ws(text: str) -> str:
        return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()

    @staticmethod
    def _indent_text(text: str, prefix: str) -> str:
        return "\n".join((prefix + line) if line.strip() else line for line in text.splitlines())

    @staticmethod
    def _wrap_inline_code(text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        return f"``{text}``" if "`" in text else f"`{text}`"

    # ---------- 链接/资源 ----------
    def _rewrite_href(self, href: str) -> str:
        kind = self._classify_url(href)
        if kind in {"empty", "remote", "anchor"}:
            return href

        local_path, anchor = self._resolve_local_path_with_anchor(href)
        if not local_path or not self._output_md_path:
            return href

        local_key = str(local_path)
        suffix = local_path.suffix.lower()
        if suffix in {".html", ".htm"} and local_key in self._html_abs_to_md_abs:
            target_md = Path(self._html_abs_to_md_abs[local_key])
            rel = Path(os.path.relpath(target_md, self._output_md_path.parent)).as_posix()
            return rel + (f"#{anchor}" if anchor else "")

        if self.copy_non_image_link_targets and local_path.exists():
            copied = self._copy_asset(local_path)
            rel = Path(os.path.relpath(copied, self._output_md_path.parent)).as_posix()
            return rel + (f"#{anchor}" if anchor else "")

        if local_path.exists():
            rel = Path(os.path.relpath(local_path, self._output_md_path.parent)).as_posix()
            return rel + (f"#{anchor}" if anchor else "")

        self.log_message(f"链接目标不存在，保留原链接: {href}")
        return href

    def _rewrite_src(self, src: str) -> str:
        kind = self._classify_url(src)
        if kind in {"empty", "remote", "anchor"} or not self._output_md_path:
            return src

        local_path, anchor = self._resolve_local_path_with_anchor(src)
        if not local_path or not local_path.exists():
            self.log_message(f"资源不存在，保留原路径: {src}")
            return src

        copied = self._copy_asset(local_path)
        rel = Path(os.path.relpath(copied, self._output_md_path.parent)).as_posix()
        return rel + (f"#{anchor}" if anchor else "")

    @staticmethod
    def _classify_url(url: str) -> str:
        if not url or not url.strip():
            return "empty"
        url = url.strip()
        if url.startswith("#"):
            return "anchor"
        if url.lower().startswith("//"):
            return "remote"
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https", "mailto", "tel", "javascript", "data"}:
            return "remote"
        if parsed.scheme == "file":
            return "local"
        return "remote" if parsed.scheme else "local"

    def _resolve_local_path_with_anchor(self, url: str) -> Tuple[Optional[Path], str]:
        if not self._source_html_path:
            return None, ""
        parsed = urlparse(url)
        anchor = parsed.fragment or ""
        if parsed.scheme == "file":
            return Path(unquote(parsed.path)).resolve(), anchor
        return (self._source_html_path.parent / unquote(parsed.path or "")).resolve(), anchor

    def _copy_asset(self, src_path: Path) -> Path:
        assert self._page_assets_dir is not None
        src_key = str(src_path)
        if src_key in self._copied_assets:
            return Path(self._copied_assets[src_key])

        assets_dir = _win_long(self._page_assets_dir)
        assets_dir.mkdir(parents=True, exist_ok=True)
        target = self._page_assets_dir / safe_filename(src_path.name, max_len=80)
        target_long = _win_long(target)
        if target_long.exists() and not self._same_file(src_path, target_long):
            stem, suffix, idx = target.stem, target.suffix, 2
            while True:
                candidate = self._page_assets_dir / f"{stem}_{idx}{suffix}"
                if not _win_long(candidate).exists():
                    target = candidate
                    target_long = _win_long(candidate)
                    break
                idx += 1

        if not target_long.exists() or not self._same_file(src_path, target_long):
            shutil.copy2(src_path, target_long)
        self._copied_assets[src_key] = str(target)
        return target

    @staticmethod
    def _same_file(a: Path, b: Path) -> bool:
        try:
            return a.samefile(b)
        except Exception:
            return False


# =========================
# 产品文档导出器
# =========================
class ProductDocMarkdownExporter:
    def __init__(
        self,
        extracted_root: str,
        output_root: str,
        log_message: Callable[[str], None] = print,
        copy_non_image_link_targets: bool = False,
    ) -> None:
        self.extracted_root = Path(extracted_root).resolve()
        self.resources_root = self.extracted_root / "resources"
        self.navi_xml_path = self.resources_root / "navi.xml"
        self.output_root = Path(output_root).resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.log_message = log_message
        self.converter = HtmlToMarkdownConverter(
            log_message=log_message,
            copy_non_image_link_targets=copy_non_image_link_targets,
        )
        self._used_rel_paths: set[str] = set()
        self._records: List[TopicRecord] = []
        self._html_abs_to_md_abs: Dict[str, str] = {}
        self._children_by_id: Dict[str, List[str]] = {}

    def export_all(self) -> List[TopicRecord]:
        root = self._parse_catalog_root()
        self._records = self._collect_topic_records(root)
        self._html_abs_to_md_abs = {
            r.html_abs_path: str((self.output_root / r.md_rel_path).resolve())
            for r in self._records if r.exists and r.html_abs_path and r.file_type == "html"
        }
        self._convert_all_records(self._records)
        self._write_mapping_files(self._records)
        self.log_message(
            f"导出完成：共 {len(self._records)} 个 topic，存在 HTML {sum(r.exists for r in self._records)} 个。"
        )
        return self._records

    def _parse_catalog_root(self) -> ET.Element:
        """解析目录树根节点：优先 navi.xml，缺失时回退到 CHM 工程文件 .hhc。

        返回与 navi.xml 同构的 <topics> 树（topic 元素含 txt/url 属性），
        下游 collect/walk/mapping 逻辑与 navi.xml 路径完全一致。
        """
        if self.navi_xml_path.exists():
            return self._parse_navi_xml()
        hhc_files = sorted(self.resources_root.glob("*.hhc"))
        if hhc_files:
            hhc_path = hhc_files[0]
            self.log_message(
                f"navi.xml 不存在，回退使用 CHM 目录树: {hhc_path.relative_to(self.resources_root)}"
            )
            return self._parse_hhc_to_topics(hhc_path)
        raise FileNotFoundError(
            f"目录树文件缺失：resources 下既无 navi.xml 也无 *.hhc ({self.resources_root})"
        )

    def _parse_navi_xml(self) -> ET.Element:
        if not self.navi_xml_path.exists():
            raise FileNotFoundError(f"navi.xml 不存在: {self.navi_xml_path}")
        content = read_text_auto(str(self.navi_xml_path)).strip()
        if content.startswith("\ufeff"):
            content = content[1:]
        root = ET.fromstring(content)
        if root.tag != "topics":
            self.log_message(f"警告：XML 根节点不是 topics，而是 {root.tag}")
        return root

    def _parse_hhc_to_topics(self, hhc_path: Path) -> ET.Element:
        """把 CHM Sitemap 1.0（GBK）目录树转成与 navi.xml 同构的 <topics> 树。

        .hhc 中 <UL> 嵌套即目录层级（与 navi.xml 的 topic 嵌套等价，深度基准差 1，
        这里统一为 navi 的 0-based：根 <UL> 下第一层 = depth 0）。
        标题为 hhc Name 属性，链接为 Local 属性（相对 resources 根）。
        hhc 无显式 topic id：用「父 id + Local + Name」生成稳定唯一 id，
        避免两个目录位置（父标题相同但 url 不同）下的叶子伪 id 碰撞。
        """
        text = read_text_auto(str(hhc_path))
        root = ET.Element("topics")
        # stack[k] = (depth (k-1) 的最近 topic, 其 id, 其下已见 local 集合)
        # stack[0] = (root, "", set())
        stack: List[Tuple[ET.Element, str, set]] = [(root, "", set())]
        pos = 0
        depth = 0
        count = 0
        skipped = 0
        for m in _HHC_OBJ.finditer(text):
            name = m.group(1).strip()
            local = m.group(2).strip()
            span = text[pos:m.start()]
            depth += len(_HHC_UL_OPEN.findall(span)) - len(_HHC_UL_CLOSE.findall(span))
            # hhc depth 1-based -> navi 0-based（根 UL 层的第一个 obj 是 depth 0）
            navi_depth = max(depth - 1, 0)
            # 保持 stack 恰好容纳 navi_depth+1 层：stack[navi_depth] = 父
            while len(stack) > navi_depth + 1:
                stack.pop()
            parent_el, parent_id, parent_seen = (
                stack[navi_depth] if len(stack) >= navi_depth + 1 else (root, "", set())
            )
            # 同一父下同名同链接的重复条目（源数据质量问题）：保留首个
            if local and (local, name) in parent_seen:
                skipped += 1
                pos = m.end()
                continue
            if local:
                parent_seen.add((local, name))
            node_id = hashlib.md5(f"{parent_id}|{local}|{name}".encode("utf-8")).hexdigest()[:16]
            el = ET.SubElement(parent_el, "topic")
            el.set("id", node_id)
            el.set("txt", name)
            if local:
                el.set("url", local)
            # 新 topic 成为该层最近节点；若后续出现更深的 obj，其父即此节点
            del stack[navi_depth + 1:]
            stack.append((el, node_id, set()))
            pos = m.end()
            count += 1
        if skipped:
            self.log_message(f"hhc 目录树解析完成: {count} 个 topic（忽略同父重复条目 {skipped} 个）")
        else:
            self.log_message(f"hhc 目录树解析完成: {count} 个 topic")
        return root

    def _collect_topic_records(self, root: ET.Element) -> List[TopicRecord]:
        records: List[TopicRecord] = []
        for topic in root.findall("topic"):
            self._walk_topic(topic, [], "", records)
        return records

    def _walk_topic(
        self,
        topic: ET.Element,
        parents: List[str],
        parent_id: str,
        records: List[TopicRecord],
    ) -> None:
        txt = (topic.get("txt") or topic.get("id") or "untitled").strip()
        url = (topic.get("url") or "").strip()
        topic_path = parents + [txt]
        topic_id = (topic.get("id") or self._pseudo_topic_id(topic_path, url)).strip()
        file_type = detect_file_type(url)
        source_abs = self._resolve_source_abs(url)
        source_rel = safe_relpath(source_abs, self.extracted_root) if source_abs else ""
        output_rel = self._build_unique_output_rel_path(topic_path, topic_id, ".pdf" if file_type == "pdf" else ".md")
        exists = bool(source_abs and Path(source_abs).exists())

        records.append(
            TopicRecord(
                topic_id=topic_id,
                parent_id=parent_id,
                txt=txt,
                topic_path=topic_path,
                url=url,
                html_abs_path=source_abs,
                html_rel_path=source_rel,
                md_rel_path=output_rel,
                exists=exists,
                file_type=file_type,
                mode="",
            )
        )

        if parent_id:
            self._children_by_id.setdefault(parent_id, []).append(topic_id)
        self._children_by_id.setdefault(topic_id, [])

        for child in topic.findall("topic"):
            self._walk_topic(child, topic_path, topic_id, records)

    @staticmethod
    def _pseudo_topic_id(topic_path: List[str], url: str) -> str:
        return hashlib.md5((" / ".join(topic_path) + "|" + url).encode("utf-8")).hexdigest()[:16]

    def _resolve_source_abs(self, url: str) -> str:
        return str((self.resources_root / url).resolve()) if url else ""

    def _build_unique_output_rel_path(self, topic_path: List[str], topic_id: str, suffix: str) -> str:
        for dir_limit, leaf_limit in zip((40, 28, 20), (60, 40, 28)):
            safe_parts = [safe_filename(p, max_len=dir_limit) for p in topic_path[:-1]]
            leaf_base = safe_filename(topic_path[-1], max_len=leaf_limit)
            if topic_id:
                leaf_base = f"{leaf_base}_{topic_id[-8:] if len(topic_id) > 8 else topic_id}"
            rel = (Path(*safe_parts) / f"{leaf_base}{suffix}") if safe_parts else Path(f"{leaf_base}{suffix}")
            rel_str = rel.as_posix()
            abs_candidate = str((self.output_root / rel).resolve())
            if len(rel_str) <= 180 and len(abs_candidate) <= 240:
                return self._dedupe_rel_path(rel)

        safe_parts = [safe_filename(p, max_len=16) for p in topic_path[:-1]]
        digest = hashlib.md5(" / ".join(topic_path).encode("utf-8")).hexdigest()[:10]
        leaf_base = safe_filename(topic_path[-1], max_len=18)
        rel = (Path(*safe_parts) / f"{leaf_base}_{digest}{suffix}") if safe_parts else Path(f"{leaf_base}_{digest}{suffix}")
        return self._dedupe_rel_path(rel)

    def _dedupe_rel_path(self, rel: Path) -> str:
        rel_str = rel.as_posix()
        if rel_str not in self._used_rel_paths:
            self._used_rel_paths.add(rel_str)
            return rel_str

        base, suffix, idx = rel.with_suffix(""), rel.suffix, 2
        while True:
            candidate = Path(str(base) + f"_{idx}{suffix}")
            candidate_str = candidate.as_posix()
            if candidate_str not in self._used_rel_paths:
                self._used_rel_paths.add(candidate_str)
                return candidate_str
            idx += 1

    def _convert_all_records(self, records: Iterable[TopicRecord]) -> None:
        for rec in records:
            output_path = self.output_root / rec.md_rel_path
            output_path_long = _win_long(output_path)
            output_path_long.parent.mkdir(parents=True, exist_ok=True)
            try:
                if rec.file_type == "pdf":
                    self._handle_pdf_record(rec, output_path)
                    continue
                if not (rec.exists and rec.html_abs_path):
                    continue

                html_text = read_text_auto(rec.html_abs_path)
                markdown, meaningful = self.converter.convert_html_string(
                    html_text,
                    source_html_path=rec.html_abs_path,
                    output_md_path=str(output_path),
                    html_abs_to_md_abs=self._html_abs_to_md_abs,
                )
                if meaningful:
                    output_path_long.write_text(markdown, encoding="utf-8")
                    rec.mode = "html"
            except Exception as exc:
                self.log_message(f"转换失败: {rec.html_abs_path or rec.url} -> {output_path} | {exc}")

        self._cleanup_empty_asset_dirs()

    def _handle_pdf_record(self, rec: TopicRecord, output_path: Path) -> None:
        # 长路径：输出侧必包（深章节 pdf 同样可 >260）；输入侧包上无害
        if rec.exists and rec.html_abs_path and _win_long(Path(rec.html_abs_path)).exists():
            shutil.copy2(_win_long(Path(rec.html_abs_path)), _win_long(output_path))
            rec.mode = "pdf"
        else:
            rec.mode = "stub"

    def _cleanup_empty_asset_dirs(self) -> None:
        # 枚举根须用长前缀：普通路径 rglob 对 >260 目录静默漏扫（空目录清不掉）
        root_long = _win_long(self.output_root)
        for assets_dir in sorted(root_long.rglob("*.assets"), key=lambda p: len(p.parts), reverse=True):
            if not assets_dir.is_dir():
                continue
            try:
                next(assets_dir.iterdir())
            except StopIteration:
                try:
                    assets_dir.rmdir()
                except OSError:
                    pass

    def _write_mapping_files(self, records: List[TopicRecord]) -> None:
        json_path = self.output_root / "html_to_md_mapping.json"
        csv_path = self.output_root / "html_to_md_mapping.csv"

        json_data = []
        for rec in records:
            item = asdict(rec)
            item["topic_path_text"] = " / ".join(rec.topic_path)
            item["md_abs_path"] = str((self.output_root / rec.md_rel_path).resolve())
            item["child_count"] = len(self._children_by_id.get(rec.topic_id, []))
            json_data.append(item)
        json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")

        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "topic_id", "parent_id", "txt", "topic_path_text", "url",
                    "html_abs_path", "html_rel_path", "md_rel_path", "md_abs_path",
                    "exists", "mode", "child_count",
                ],
            )
            writer.writeheader()
            for rec in records:
                writer.writerow(
                    {
                        "topic_id": rec.topic_id,
                        "parent_id": rec.parent_id,
                        "txt": rec.txt,
                        "topic_path_text": " / ".join(rec.topic_path),
                        "url": rec.url,
                        "html_abs_path": rec.html_abs_path,
                        "html_rel_path": rec.html_rel_path,
                        "md_rel_path": rec.md_rel_path,
                        "md_abs_path": str((self.output_root / rec.md_rel_path).resolve()),
                        "exists": rec.exists,
                        "mode": rec.mode,
                        "child_count": len(self._children_by_id.get(rec.topic_id, [])),
                    }
                )


# =========================
# 文件解压 / 入口
# =========================
def extract_hdx_file(hdx_path: str) -> str:
    if not os.path.exists(hdx_path):
        raise FileNotFoundError(f"文档文件不存在: {hdx_path}")

    hdx_filename = os.path.splitext(os.path.basename(hdx_path))[0]
    base_dir = os.path.dirname(os.path.abspath(hdx_path))
    output_base_dir = os.path.join(base_dir, "output")
    os.makedirs(output_base_dir, exist_ok=True)
    extract_dir = os.path.join(output_base_dir, f"extracted_{hdx_filename}")

    if os.path.exists(extract_dir) and os.listdir(extract_dir):
        if os.path.getmtime(hdx_path) <= os.path.getmtime(extract_dir):
            print(f"检测到现有解压目录，直接使用: {extract_dir}")
            return extract_dir
        print("检测到文档文件已更新，重新解压...")

    if os.path.exists(extract_dir):
        shutil.rmtree(_win_long(Path(extract_dir)))
    os.makedirs(extract_dir, exist_ok=True)

    try:
        print(f"开始解压文档: {os.path.basename(hdx_path)}")
        with zipfile.ZipFile(hdx_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
        print(f"文档解压完成: {extract_dir}")
        return extract_dir
    except zipfile.BadZipFile as exc:
        raise ValueError("文件不是有效的 ZIP 格式") from exc


def main(hdx_file: str) -> None:
    extract_dir = extract_hdx_file(hdx_file)
    hdx_filename = os.path.splitext(os.path.basename(hdx_file))[0]
    base_dir = os.path.dirname(os.path.abspath(hdx_file))
    output_root = os.path.join(base_dir, "output", hdx_filename)
    os.makedirs(output_root, exist_ok=True)

    exporter = ProductDocMarkdownExporter(
        extracted_root=extract_dir,
        output_root=output_root,
    )
    exporter.export_all()
    print(f"Markdown 输出完成，结果目录: {output_root}")


def main_from_extracted(extracted_dir: str, output_dir: str) -> None:
    """直接从已解压目录运行转换（跳过解压步骤），保持XML目录结构和链接映射。"""
    exporter = ProductDocMarkdownExporter(
        extracted_root=extracted_dir,
        output_root=output_dir,
    )
    exporter.export_all()
    print(f"Markdown 输出完成，结果目录: {output_dir}")


def main2(input_dir: str, output_dir: Optional[str] = None) -> None:
    src_root = Path(input_dir).resolve()
    if not src_root.exists() or not src_root.is_dir():
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")

    dst_root = Path(output_dir).resolve() if output_dir else (src_root.parent / f"{src_root.name}_md")
    dst_root.mkdir(parents=True, exist_ok=True)

    converter = HtmlToMarkdownConverter()
    html_files: List[Path] = []
    for ext in ("*.html", "*.htm"):
        html_files.extend(src_root.rglob(ext))

    if not html_files:
        print(f"未找到 HTML 文件: {src_root}")
        return

    total = success = failed = 0
    for html_path in html_files:
        total += 1
        try:
            rel_path = html_path.relative_to(src_root)
            md_path = (dst_root / rel_path).with_suffix(".md")
            _win_long(md_path).parent.mkdir(parents=True, exist_ok=True)
            converter.convert_file(
                html_file=str(html_path),
                md_file=str(md_path),
                html_abs_to_md_abs={},
            )
            success += 1
            print(f"[OK] {html_path} -> {md_path}")
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {html_path} | {exc}")

    print(f"\n批量转换完成: 总数={total}, 成功={success}, 失败={failed}, 输出目录={dst_root}")


if __name__ == "__main__":
    hdx_file = "UNC 20.15.2 产品文档(裸机容器) 05.hwics"
    main(hdx_file)
    # main2(
    #     input_dir=r"output/extracted_UDG_Product_Documentation_CH_20.15.2/resources/cdgw/desc",
    #     output_dir=r"output/sample",
    # )
