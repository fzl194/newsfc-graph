import re

from app.md_parser import parse_md

MD = """---
id: UDG@MMLCommand@ADD URR
type: MMLCommand
nf: UDG
version: 20.15.2
---
# ADD URR
正文行。

## 边
- 操作配置对象: [[UDG@ConfigObject@URR]]
- 参见: [[UDG@MMLCommand@MOD URR]]
"""

def test_frontmatter():
    fm, body, edge_section = parse_md(MD)
    assert fm["id"] == "UDG@MMLCommand@ADD URR"
    assert fm["type"] == "MMLCommand"

def test_body_strips_edge_section():
    fm, body, edge_section = parse_md(MD)
    assert "# ADD URR" in body
    assert "## 边" not in body          # body 不含边章节
    assert "操作配置对象" in edge_section  # 边章节单独切出

def test_no_edges():
    md = "---\nid: X@T@y\ntype: T\n---\n正文\n"
    fm, body, edge_section = parse_md(md)
    assert edge_section == ""


def test_crlf_normalized():
    # CRLF 换行：body 不应残留 \r，表格表头与分隔符仍紧邻
    md = "---\r\nid: x\r\ntype: T\r\n---\r\n| a | b |\r\n| --- | --- |\r\n| 1 | 2 |\r\n"
    fm, body, edge_section = parse_md(md)
    assert "\r" not in body
    assert "| a | b |\n| --- | --- |" in body


def test_double_cr_normalized():
    # \r\r\n（产品文档导出遗留的双回车）：不应变成空行撑开表格
    md = "---\r\r\nid: x\r\r\ntype: T\r\r\n---\r\r\n| a | b |\r\r\n| --- | --- |\r\r\n| 1 | 2 |\r\r\n"
    fm, body, edge_section = parse_md(md)
    assert "\r" not in body
    assert "| a | b |\n| --- | --- |" in body


def test_table_blank_lines_between_rows_collapsed():
    # 产品文档真实样本：表头/分隔符/数据行之间混入的是普通空行（\n\n，非 \r 残留）。
    # GFM 表格遇空行即整表判废（只剩表头，数据行退化为纯文本）。
    # parse_md 须删除"夹在两行管道表格行之间的空行"，让表格连续。
    md = (
        "---\nid: x\ntype: T\n---\n"
        "#### 参数说明\n\n"
        "| 参数标识 | 参数名称 | 参数说明 |\n\n"
        "| --- | --- | --- |\n\n"
        "| APN | APN名称 | 必选参数 |\n\n"
        "| SWITCH | 开关 | 可选参数 |\n"
    )
    fm, body, edge_section = parse_md(md)
    # 表头紧邻分隔符、分隔符紧邻数据行、数据行之间紧邻
    assert "| 参数标识 | 参数名称 | 参数说明 |\n| --- | --- | --- |" in body
    assert "| --- | --- | --- |\n| APN |" in body
    assert "| APN | APN名称 | 必选参数 |\n| SWITCH |" in body
    # body 内不应再残留"管道表格行之间的空行"
    assert re.search(r"\|[^\n]*\|[ \t]*\n[ \t]*\n[ \t]*\|", body) is None


def test_table_collapse_preserves_paragraph_spacing():
    # 表格外部的正常段落空行不应被误删；只有"夹在两行表格行之间"的空行才删。
    md = (
        "---\nid: x\ntype: T\n---\n"
        "段落一。\n\n"
        "| a | b |\n\n| --- | --- |\n\n| 1 | 2 |\n\n"
        "段落二。\n"
    )
    fm, body, edge_section = parse_md(md)
    assert "| a | b |\n| --- | --- |\n| 1 | 2 |" in body  # 表内空行已删
    assert "段落一。\n\n| a |" in body                      # 表前段落空行保留
    assert "| 1 | 2 |\n\n段落二。" in body                  # 表后段落空行保留
