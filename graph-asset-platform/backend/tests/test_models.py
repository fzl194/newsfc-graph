from app.models import Object, Edge

def test_object_minimum():
    o = Object(id="UDG@MMLCommand@ADD URR", type="MMLCommand", layer="Command",
               scope="nf", nf="UDG", version="20.15.2", versions=["20.15.2"],
               frontmatter={"id": "UDG@MMLCommand@ADD URR"}, body_md="x", raw_md="x", source_path="Command/UDG/20.15.2/UDG@MMLCommand@ADD URR.md")
    assert o.id == "UDG@MMLCommand@ADD URR"
    assert o.scope == "nf"

def test_edge():
    e = Edge(from_id="UDG@MMLCommand@ADD URR", from_version="20.15.2",
             relation="操作配置对象", to="UDG@ConfigObject@URR")
    assert e.to == "UDG@ConfigObject@URR"
