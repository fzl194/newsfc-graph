def segment_count(id_: str) -> int:
    return id_.count("@") + 1

def is_nf_scoped(id_: str) -> bool:
    return segment_count(id_) == 3

def split_id(id_: str):
    """3段→(nf,type,local)；2段→(None,type,semantic)。local/semantic 内含空格原样保留。"""
    parts = id_.split("@")
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return None, parts[0], parts[1]
    raise ValueError(f"非法逻辑ID（非2/3段）: {id_!r}")
