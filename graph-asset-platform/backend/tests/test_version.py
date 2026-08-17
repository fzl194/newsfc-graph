from app.version import latest_version

def test_simple():
    assert latest_version(["20.15.2", "20.15.1"]) == "20.15.2"

def test_semantic_not_string():
    # 字符串排序会错把 20.9.10 排到 20.15.2 之后；语义化必须 20.15.2 更新
    assert latest_version(["20.9.10", "20.15.2"]) == "20.15.2"

def test_three_segments():
    assert latest_version(["20.15.2", "20.16.0", "20.15.10"]) == "20.16.0"

def test_non_numeric_fallback():
    # 非纯数字段退化为字符串比较
    assert latest_version(["r1", "r2"]) == "r2"

def test_empty():
    assert latest_version([]) is None
