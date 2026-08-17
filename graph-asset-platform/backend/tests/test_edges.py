from app.edges import parse_edges, Edge

SEC = """## 边
- 操作配置对象: [[UDG@ConfigObject@URR]]
- 参见: [[UDG@MMLCommand@MOD URR]]
- 无关系冒号的行（不是边）
"""

def test_parse_two_edges():
    es = parse_edges(SEC, from_id="UDG@MMLCommand@ADD URR", from_version="20.15.2")
    assert len(es) == 2
    assert es[0].relation == "操作配置对象"
    assert es[0].to == "UDG@ConfigObject@URR"
    assert es[1].relation == "参见"
    assert es[1].to == "UDG@MMLCommand@MOD URR"

def test_empty():
    assert parse_edges("", "a@T@b", "1.0") == []
    assert parse_edges("## 边\n（暂无）", "a@T@b", "1.0") == []

def test_dedup():
    s = "## 边\n- r: [[X@T@y]]\n- r: [[X@T@y]]\n"
    assert len(parse_edges(s, "a@T@b", "1.0")) == 1


def test_multi_wikilink_one_line():
    """一行多 wikilink：- 复用步骤: [[A]], [[B]], [[C]] → 3 条边（relation 同）。"""
    s = "## 边\n- 复用步骤: [[A@T@x]], [[B@T@y]], [[C@T@z]]\n"
    es = parse_edges(s, "f@T@f", "1.0")
    assert len(es) == 3
    assert [e.to for e in es] == ["A@T@x", "B@T@y", "C@T@z"]
    assert all(e.relation == "复用步骤" for e in es)


def test_multi_wiki_dedup():
    """一行内重复 wikilink 去重。"""
    s = "## 边\n- r: [[X@T@y]], [[X@T@y]]\n"
    assert len(parse_edges(s, "a@T@b", "1.0")) == 1
