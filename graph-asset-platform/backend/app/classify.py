from .logical_id import split_id, segment_count
from .registry import Registry

def classify(id_: str, registry: Registry, frontmatter: dict) -> tuple:
    """返回 (相对目录, 文件名)。文件名恒为 {id}.md（= 版本无关逻辑ID）。"""
    nf, typ, _local = split_id(id_)
    entry = registry.get(typ)
    if entry is None:
        raise ValueError(f"未知类型 {typ!r}（id={id_!r}）")
    filename = f"{id_}.md"
    if entry["scope"] == "nf":
        version = frontmatter.get("version")
        if not version:
            raise ValueError(f"NF 类 {typ} 缺 frontmatter.version（id={id_!r}）")
        # nf 以 id 段0 为准（权威），frontmatter.nf 仅校验
        layer = entry["layer"]
        return f"{layer}/{nf}/{version}", filename
    if entry["scope"] == "task":
        # Task 层无版本（引用命令/特性不绑版本）；路径 {type}/{nf}/{id}.md。
        # 注意用 type 名（AtomTask/CompoundTask/FeatureTask）而非 entry['layer']（"Task"）：
        # 磁盘真实布局是 type 名做顶层目录（与 fs.py 上传、前端 LAYERS 一致）；
        # entry['layer'] 仅作 DB/UI 分组语义（"Task"→UI 任务层）。
        return f"{typ}/{nf}", filename
    # cross
    layer = entry["layer"]
    parts = [layer]
    for field in entry.get("path_fields", []):
        v = frontmatter.get(field)
        if not v:
            raise ValueError(f"跨NF类 {typ} 缺 frontmatter.{field}（id={id_!r}）")
        parts.append(v)
    return "/".join(parts), filename
