from functools import cmp_to_key

def _ver_key(v: str):
    parts = v.split(".")
    keyed = []
    for p in parts:
        if p.isdigit():
            keyed.append((0, int(p)))       # 数值优先
        else:
            keyed.append((1, p))            # 非数字退化为字符串
    return keyed

def _cmp(a: str, b: str) -> int:
    ka, kb = _ver_key(a), _ver_key(b)
    # 长度对齐：短的补 (0,0) 视为更小
    n = max(len(ka), len(kb))
    ka += [(0, 0)] * (n - len(ka))
    kb += [(0, 0)] * (n - len(kb))
    return (ka > kb) - (ka < kb)

def latest_version(versions: list):
    """返回最新版本（语义化点分段数值比较，非数字退化为字符串）。空→None。"""
    if not versions:
        return None
    return sorted(versions, key=cmp_to_key(_cmp))[-1]


def is_newer(a, b) -> bool:
    """a 是否比 b 新（语义化比较；None 视为最低——跨 NF 类恒 None 不会与 str 混合）。

    原 routers/objects._is_newer 抽出（MCP 服务化 2026-08-24：objects_search /
    mcp_server 与 router 共用，避免双份漂移）。
    """
    if a == b:
        return False
    if a is None:
        return False
    if b is None:
        return True
    return latest_version([a, b]) == a
