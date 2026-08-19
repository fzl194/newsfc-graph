"""产品文档包（bundle）：output/{nf}_{version}/ 的 md 留存 + bundle.json 元信息。

- **只留最终 md**（html/原件在 .pdoc_ 临时目录随解压任务删除——用户决策 2026-08-19，
  推翻早期"全保留"设想）；bundle.json 为 KB 级追溯元信息（原文件名/sha256/上传人/
  时间/exporter 版本/转换统计）
- **原子替换**：转换先写 `output/.tmp_{nf}_{version}`，成功后 旧目录 move `.trash`、
  新目录 rename 正式（失败不动旧包——修评审清单 D10）
- **旧格式兼容**：无 bundle.json 的既有目录视为 legacy done（可挖掘），挖过一次补写
- 命名白名单（评审清单 D1）：nf/version 由 router 校验，此处再校验一次（纵深防御）
"""
import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from .. import config

_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,31}$")

META_NAME = "bundle.json"


def is_valid_name(s: str) -> bool:
    """nf/version 白名单（D1：防路径穿越；version 允许点号如 20.15.2）。"""
    return bool(_NAME_RE.fullmatch(s or ""))


def bundle_dir(nf: str, version: str) -> Path:
    return config.OUTPUT_DIR / f"{nf}_{version}"


def tmp_bundle_dir(nf: str, version: str) -> Path:
    return config.OUTPUT_DIR / f".tmp_{nf}_{version}"


def write_meta(d: Path, meta: dict) -> None:
    (d / META_NAME).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def read_meta(d: Path) -> dict | None:
    p = d / META_NAME
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def file_sha256(p: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _assets_flags(nf: str, version: str) -> dict:
    """该 nf+version 四层图谱资产是否已存在（前端「依赖强制锁定」UI 数据源）。"""
    out: dict[str, bool] = {}
    for layer in ("Command", "ConfigObject", "Feature", "License"):
        d = config.ASSETS_DIR / layer / nf / version
        out[layer] = d.is_dir() and next(d.rglob("*.md"), None) is not None
    return out


def list_bundles() -> list:
    """包列表（抽取页数据源）：output/ 下每目录 → 元信息（无 meta 视为 legacy done）。"""
    root = config.OUTPUT_DIR
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir(), key=lambda x: x.name):
        if not d.is_dir() or d.name.startswith("."):
            continue
        meta = read_meta(d)
        name = d.name
        nf_ver = name.split("_", 1)
        nf = meta.get("nf") if meta else nf_ver[0]
        version = meta.get("version") if meta else (nf_ver[1] if len(nf_ver) > 1 else "")
        out.append({
            "nf": nf,
            "version": version,
            "dir": name,
            "status": (meta or {}).get("status", "done"),
            "legacy": meta is None,          # 旧格式（仅 md，无元信息）仍可挖掘
            "uploaded_at": (meta or {}).get("uploaded_at", ""),
            "uploaded_by": (meta or {}).get("uploaded_by", ""),
            "source_name": (meta or {}).get("source_name", ""),
            "md_count": (meta or {}).get("md_count"),
            "convert_failed": (meta or {}).get("convert_failed", 0),
            "mode_id": (meta or {}).get("mode_id", ""),   # 最近一次挖掘用的模式
            "assets": _assets_flags(nf, version),          # 依赖锁定 UI 数据源
        })
    return out


def get_bundle(nf: str, version: str) -> dict | None:
    if not is_valid_name(nf) or not is_valid_name(version):
        return None
    d = bundle_dir(nf, version)
    if not d.is_dir():
        return None
    for b in list_bundles():
        if b["dir"] == d.name:
            return b
    return None


def md_tree(nf: str, version: str) -> Path | None:
    """包内 md 树根（当前布局=包目录本身；保留函数以便未来 md/ 子层演进）。"""
    d = bundle_dir(nf, version)
    return d if d.is_dir() else None


def atomic_replace(nf: str, version: str, tmp_dir: Path) -> Path:
    """tmp_dir（已含 bundle.json）→ 正式包目录；旧包 move DATA_DIR/.trash（可回滚）。

    失败抛异常且**不动旧包**（D10：转换失败=双输 的修复）。
    """
    formal = bundle_dir(nf, version)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    old_backup = None
    if formal.exists():
        trash = config.DATA_DIR / ".trash"
        trash.mkdir(parents=True, exist_ok=True)
        old_backup = trash / f"bundle_{nf}_{version}_{time.strftime('%Y%m%d%H%M%S')}"
        shutil.move(str(formal), str(old_backup))
    try:
        shutil.move(str(tmp_dir), str(formal))
    except Exception:
        if old_backup is not None and not formal.exists():
            shutil.move(str(old_backup), str(formal))  # 回滚
        raise
    return formal


def sweep_orphan_tmp() -> int:
    """启动清扫（评审清单 D16）：硬 kill 遗留的 .pdoc_/.pdoc_up_/output/.tmp_* 孤儿。"""
    n = 0
    for pat, root in ((".pdoc_*", config.DATA_DIR),
                      (".pdoc_up_*", config.DATA_DIR),
                      (".tmp_*", config.OUTPUT_DIR)):
        if not root.is_dir():
            continue
        for p in root.glob(pat):
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink(missing_ok=True)
                n += 1
            except OSError:
                pass
    return n
