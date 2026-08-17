import pytest
from app.store import Store


def test_write_and_read(tmp_data_dir):
    s = Store(tmp_data_dir)
    rel = "Command/UDG/20.15.2/UDG@MMLCommand@ADD URR.md"
    s.write(rel, "---\nid: x\n---\nbody\n")
    assert "body" in s.read(rel)


def test_list_all_md(tmp_data_dir):
    s = Store(tmp_data_dir)
    s.write("Command/UDG/20.15.2/a.md", "x")
    s.write("Business/d/BusinessDomain@d.md", "y")
    md_files = s.list_md()
    assert len(md_files) == 2
    # 路径用正斜杠归一化
    assert all("\\" not in p for p in md_files)
    assert "Command/UDG/20.15.2/a.md" in md_files
    assert "Business/d/BusinessDomain@d.md" in md_files


def test_exists(tmp_data_dir):
    s = Store(tmp_data_dir)
    s.write("Command/UDG/20.15.2/a.md", "x")
    assert s.exists("Command/UDG/20.15.2/a.md")
    assert not s.exists("nope.md")


def test_list_md_empty(tmp_data_dir):
    s = Store(tmp_data_dir)
    assert s.list_md() == []


def test_path_traversal_blocked(tmp_data_dir):
    s = Store(tmp_data_dir)
    # 试图逃逸 assets 根
    with pytest.raises(ValueError):
        s.write("../../evil.md", "x")
    with pytest.raises(ValueError):
        s.read("../../evil.md")


def test_write_overwrites(tmp_data_dir):
    s = Store(tmp_data_dir)
    rel = "Command/UDG/20.15.2/a.md"
    s.write(rel, "v1")
    s.write(rel, "v2")
    assert s.read(rel) == "v2"
    # 仍是 1 个文件
    assert len(s.list_md()) == 1


def test_write_creates_nested_dirs(tmp_data_dir):
    s = Store(tmp_data_dir)
    deep = "Business/domain/scenario/ConfigurationSolution@sol.md"
    s.write(deep, "x")
    assert s.exists(deep)
