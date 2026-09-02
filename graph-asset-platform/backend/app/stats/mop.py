"""MOP 动网变更场景统计（2026-09-02 用户需求）。

数据源是**Excel 底表**（不走数据库——内容随时变化，用户在内网维护），放
``DATA_DIR/mop_scenarios.xlsx``（或 .csv）。平台只读聚合：
- 底表很多列，只认列头含 ``L1场景``…``L5场景`` 的列（宽松匹配：含 L<i> 且含"场景"）；
- 每个数据行 = 1 条 MOP（L1 非空才计入总数）；更细层级可为空（有 L1、L2 没 L3…）；
- 按粒度聚合（前端最多用到 L4）：选 L2 时按 (L1,L2) 分组计数，占比 = 组数/总数。

xlsx 解析纯 stdlib（zip + ElementTree，读 sharedStrings + 第一个 sheet），
与 export.render_xlsx 同族（我们写出的文件必须能被自己读回——测试互证）。
上传（PUT /stats/mop/source，admin）先在内存解析校验再落盘，坏文件不入库。
"""
import csv
import io
import re
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .. import config

MAX_LEVEL = 4          # 前端展示最深粒度（底表可到 L5，聚合只用 1..4）
_XLSX_MAGIC = b"PK\x03\x04"
_FILE_NAMES = ("mop_scenarios.xlsx", "mop_scenarios.csv")


def mop_path() -> Path | None:
    """当前生效的底表路径（xlsx 优先）；都不存在 → None。"""
    for name in _FILE_NAMES:
        p = Path(config.DATA_DIR) / name
        if p.is_file():
            return p
    return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _col_index(ref: str) -> int:
    """'B7' → 1（列字母转 0 基下标）。"""
    m = re.match(r"([A-Z]+)", ref or "")
    if not m:
        return 0
    n = 0
    for ch in m.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


_SHARED: dict[str, str] = {}


def _cell_text(c) -> str:
    """单元格文本：t=s 共享串 / inlineStr / str / n。"""
    t = c.get("t")
    if t == "inlineStr":
        return "".join(node.text or "" for node in c.iter() if _local(node.tag) == "t")
    v = next((node for node in c if _local(node.tag) == "v"), None)
    if v is None or v.text is None:
        return ""
    if t == "s":
        return _SHARED.get(v.text, "")
    return v.text


def _load_shared_strings(z: zipfile.ZipFile) -> None:
    global _SHARED
    _SHARED = {}
    try:
        data = z.read("xl/sharedStrings.xml")
    except KeyError:
        return
    root = ET.fromstring(data)
    for i, si in enumerate(node for node in root if _local(node.tag) == "si"):
        _SHARED[str(i)] = "".join(
            t.text or "" for t in si.iter() if _local(t.tag) == "t")


def _first_sheet_name(z: zipfile.ZipFile) -> str:
    """workbook 第一个 sheet 的目标路径（默认 sheet1.xml）。"""
    try:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rid = None
        for sheet in wb.iter():
            if _local(sheet.tag) == "sheet":
                rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                break
        if rid:
            rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            for rel in rels.iter():
                if _local(rel.tag) == "Relationship" and rel.get("Id") == rid:
                    target = rel.get("Target", "").lstrip("/")
                    return target if target.startswith("xl/") else f"xl/{target}"
    except (KeyError, ET.ParseError):
        pass
    return "xl/worksheets/sheet1.xml"


def _parse_xlsx(data: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        _load_shared_strings(z)
        root = ET.fromstring(z.read(_first_sheet_name(z)))
        rows: list[list[str]] = []
        for row in (node for node in root.iter() if _local(node.tag) == "row"):
            cells: dict[int, str] = {}
            for c in (node for node in row if _local(node.tag) == "c"):
                cells[_col_index(c.get("r", ""))] = _cell_text(c).strip()
            width = max(cells, default=-1) + 1
            rows.append([cells.get(i, "") for i in range(width)])
        return rows


def _parse_csv(data: bytes) -> list[list[str]]:
    return [[(c or "").strip() for c in row]
            for row in csv.reader(io.StringIO(data.decode("utf-8-sig")))]


def _find_level_columns(header: list[str]) -> dict[int, int]:
    """列头 → {层级: 列下标}。宽松匹配：含 L<i> 且含 '场景'（大小写不敏感）。"""
    out: dict[int, int] = {}
    for idx, name in enumerate(header):
        n = (name or "").strip()
        if "场景" not in n:
            continue
        m = re.match(r"^L([1-5])", n, re.IGNORECASE)
        if m:
            out[int(m.group(1))] = idx
    return out


def parse_rows(name: str, data: bytes) -> tuple[list[dict], dict[int, int]]:
    """解析底表字节 → (MOP 行 [{l1..l5}], 列映射)。抛 ValueError（中文可读）。"""
    if name.lower().endswith(".xlsx"):
        if not data.startswith(_XLSX_MAGIC):
            raise ValueError("xlsx 文件损坏（缺少 ZIP 头）")
        grid = _parse_xlsx(data)
    elif name.lower().endswith(".csv"):
        try:
            grid = _parse_csv(data)
        except UnicodeDecodeError as e:
            raise ValueError(f"CSV 编码错误（需 UTF-8）：{e}") from e
    else:
        raise ValueError("仅支持 .xlsx / .csv 底表")
    if not grid:
        raise ValueError("底表为空")
    cols = _find_level_columns(grid[0])
    if 1 not in cols:
        raise ValueError("首行未找到 'L1场景' 列（列头需含 L1…L5 与'场景'字样）")
    rows: list[dict] = []
    for raw in grid[1:]:
        if not any((c or "").strip() for c in raw):
            continue  # 整行空跳过
        rec = {f"l{i}": "" for i in range(1, 6)}
        for lv in range(1, 6):
            ci = cols.get(lv)
            rec[f"l{lv}"] = (raw[ci].strip() if ci is not None and ci < len(raw) else "")
        if rec["l1"]:
            rows.append(rec)
    if not rows:
        raise ValueError("没有有效数据行（L1场景 列全为空）")
    return rows, cols


def _load_rows() -> tuple[list[dict], Path | None]:
    p = mop_path()
    if p is None:
        return [], None
    rows, _ = parse_rows(p.name, p.read_bytes())
    return rows, p


def _max_level(rows: list[dict]) -> int:
    return max((i for i in range(1, 6)
                if any(r.get(f"l{i}") for r in rows)), default=1)


def aggregate(level: int = 1) -> dict:
    """GET /stats/mop 的负载：按粒度分组计数 + 占比（默认数量降序）。"""
    rows, p = _load_rows()
    if not rows:
        return {"available": False, "total": 0, "max_level": 0,
                "levels": [], "rows": [], "source": p.name if p else "",
                "updated_at": ""}
    level = max(1, min(level, MAX_LEVEL))
    max_lv = min(_max_level(rows), MAX_LEVEL)
    groups: dict[tuple[str, ...], int] = {}
    for r in rows:
        path = tuple(r.get(f"l{i}") or "" for i in range(1, level + 1))
        groups[path] = groups.get(path, 0) + 1
    total = len(rows)
    out = [{"path": list(path), "count": n, "ratio": round(n / total, 6)}
           for path, n in groups.items()]
    out.sort(key=lambda g: (-g["count"], g["path"]))
    return {
        "available": True, "total": total, "max_level": max_lv,
        "levels": list(range(1, max_lv + 1)),
        "rows": out, "source": p.name if p else "",
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S",
                                    time.localtime(p.stat().st_mtime)) if p else "",
    }


def save_source(name: str, data: bytes) -> dict:
    """PUT 上传底表（admin）：内存解析校验 → 落盘（互斥另一个后缀的旧文件）。"""
    rows, cols = parse_rows(name, data)
    ext = ".xlsx" if name.lower().endswith(".xlsx") else ".csv"
    target = Path(config.DATA_DIR) / f"mop_scenarios{ext}"
    target.write_bytes(data)
    for other in _FILE_NAMES:
        if other != target.name:
            stale = Path(config.DATA_DIR) / other
            if stale.is_file():
                stale.unlink()
    return {"ok": True, "saved": target.name, "mop_total": len(rows),
            "levels_found": sorted(cols.keys())}
