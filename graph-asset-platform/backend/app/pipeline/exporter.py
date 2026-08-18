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
def read_text_auto(file_path: str) -> str:
    encodings = [
        "utf-8", "gb18030", "gbk", "gb2312",
        "utf-16", "big5", "windows-1252", "iso-8859-1", "ascii",
    ]
    raw = Path(file_path).read_bytes()

    try:
        detected = chardet.detect(raw)
        if detected and detected.get("encoding") and (detected.get("confidence") or 0) >= 0.7:
            try:
                return raw.decode(detected["encoding"])
            except Exception:
                pass
    except Exception:
        pass

    for enc in encodings:
        try:
            return raw.decode(enc)
        except Exception:
            continue

    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc, errors="ignore")
        except Exception:
            continue

    raise ValueError(f"无法读取文件编码: {file_path}")


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
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown, encoding="utf-8")

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

        self._page_assets_dir.mkdir(parents=True, exist_ok=True)
        target = self._page_assets_dir / safe_filename(src_path.name, max_len=80)
        if target.exists() and not self._same_file(src_path, target):
            stem, suffix, idx = target.stem, target.suffix, 2
            while True:
                candidate = self._page_assets_dir / f"{stem}_{idx}{suffix}"
                if not candidate.exists():
                    target = candidate
                    break
                idx += 1

        if not target.exists() or not self._same_file(src_path, target):
            shutil.copy2(src_path, target)
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
        root = self._parse_navi_xml()
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
            output_path.parent.mkdir(parents=True, exist_ok=True)
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
                    output_path.write_text(markdown, encoding="utf-8")
                    rec.mode = "html"
            except Exception as exc:
                self.log_message(f"转换失败: {rec.html_abs_path or rec.url} -> {output_path} | {exc}")

        self._cleanup_empty_asset_dirs()

    def _handle_pdf_record(self, rec: TopicRecord, output_path: Path) -> None:
        if rec.exists and rec.html_abs_path and Path(rec.html_abs_path).exists():
            shutil.copy2(Path(rec.html_abs_path), output_path)
            rec.mode = "pdf"
        else:
            rec.mode = "stub"

    def _cleanup_empty_asset_dirs(self) -> None:
        for assets_dir in sorted(self.output_root.rglob("*.assets"), key=lambda p: len(p.parts), reverse=True):
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
        shutil.rmtree(extract_dir)
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
            md_path.parent.mkdir(parents=True, exist_ok=True)
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
