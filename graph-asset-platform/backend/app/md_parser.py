import yaml
import re

# 优先用 libyaml 的 C 加载器（CSafeLoader，比纯 Python SafeLoader 快数倍），
# 没编译 C 扩展时退回纯 Python SafeLoader。建索引要对数千 md 各解析一次 YAML，值得用 C。
try:
    from yaml import CSafeLoader as _SAFE_LOADER
except ImportError:  # pragma: no cover
    from yaml import SafeLoader as _SAFE_LOADER

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)
_EDGE_HEADER_RE = re.compile(r"\n##\s*边\s*\n", re.M)


def _is_table_row(line: str) -> bool:
    """是否为管道表格行：非空且首尾均为 ``|``（如 ``| a | b |``、``| --- |``）。"""
    s = line.strip()
    return len(s) >= 2 and s.startswith("|") and s.endswith("|")


def _collapse_table_internal_blanks(text: str) -> str:
    r"""删除"夹在两行管道表格行之间的空行"。

    GFM 表格遇到空行即整表判废：产品文档在表头/分隔符/数据行之间普遍混入普通
    空行（``\n\n``，行尾归一化后仍残留——这不是 CRLF 问题），导致 markdown-it
    只渲染出表头、其余数据行退化为纯文本段落。这里只删"前一行与后一行都是
    ``|...|`` 表格行"的空行，段落之间的正常空行原样保留。
    """
    lines = text.split("\n")
    n = len(lines)
    # nxt_row[i]：第 i 行之后首个非空行是否为表格行（供"空行的后邻"判定）
    nxt_row = [False] * n
    following_is_row = False
    for i in range(n - 1, -1, -1):
        nxt_row[i] = following_is_row
        if lines[i].strip():
            following_is_row = _is_table_row(lines[i])
    out: list[str] = []
    for i, line in enumerate(lines):
        if line.strip() == "" and out and _is_table_row(out[-1]) and nxt_row[i]:
            continue  # 丢弃表内空行
        out.append(line)
    return "\n".join(out)


def parse_md(text: str) -> tuple:
    """→ (frontmatter_dict, body_md, edge_section_text)。无 frontmatter→空dict；无##边→''。"""
    # 归一化换行：源 md 可能是 CRLF 甚至 \r\r\n（产品文档导出遗留的双回车）。
    # 不归一化的话，残留 \r 会让 markdown-it 把 \r\r\n 错当成 \n\n（多出空行），
    # 导致表头与分隔符之间被插入空行 → GFM 表格整表判废（只渲染成段落）。
    text = re.sub(r"\r+\n", "\n", text)   # 任意 \r 串 + \n → 单个 \n
    text = text.replace("\r", "\n")        # 残留的裸 \r（老 Mac 换行）→ \n
    fm: dict = {}
    body = text
    m = _FM_RE.match(text)
    if m:
        fm = yaml.load(m.group(1), Loader=_SAFE_LOADER) or {}
        body = m.group(2)
    # 删除表格内部空行（必须在 frontmatter 抽取之后，避免误伤 YAML；## 边 章节
    # 不含管道表格行，故在切边之前/之后处理均可）
    body = _collapse_table_internal_blanks(body)
    # 切出 ## 边 章节（取该标题到文末）
    em = _EDGE_HEADER_RE.search("\n" + body)
    edge_section = ""
    if em:
        # em.start() 指向 "\n## 边\n" 的开头 \n（body 前补了一个 \n）
        cut = em.start()  # 相对 prefixed body
        edge_section = ("\n" + body)[cut:].lstrip("\n")
        body = ("\n" + body)[:cut].rstrip("\n")
    return fm, body, edge_section
