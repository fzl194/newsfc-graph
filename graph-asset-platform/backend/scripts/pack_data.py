#!/usr/bin/env python3
"""平台数据打包/校验（跨机迁移用，配合 deploy/README-部署与数据迁移.md）。

打包 = 整个 GAP_DATA_DIR（platform-data/）成单个 zip：
  assets（图谱资产）/ output（原始产品文档）/ platform.db（索引+用户+任务历史）
  / users.json / tests（测试用例）/ telemetry
排除：.pdoc_*、.pdoc_up_*、output/.tmp_*（孤儿临时目录，无迁移价值）。

用法（**先停平台**，避免 SQLite WAL 半写）：
  python scripts/pack_data.py                # 默认打 ../platform-data → graph-asset-data-<日期>.zip
  python scripts/pack_data.py -o D:/bak.zip  # 指定输出
  python scripts/pack_data.py --check D:/bak.zip   # 校验包完整性（列结构/大小/条目数）
恢复（目标机）：解压到 deploy/platform-data/（与 docker-compose 的卷映射一致）即可。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
import zipfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# 不迁移的内容（临时/可再生的孤儿）
_EXCLUDE_NAMES = {".trash_old"}
_EXCLUDE_PREFIXES = (".pdoc_", ".pdoc_up_", ".tmp_")


def _load_config():
    spec = importlib.util.spec_from_file_location(
        "pack_cfg", BACKEND / "app" / "config.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _excluded(p: Path) -> bool:
    return any(p.name.startswith(pre) for pre in _EXCLUDE_PREFIXES)


def pack(data_dir: Path, out: Path) -> dict:
    files = [p for p in data_dir.rglob("*")
             if p.is_file() and not _excluded(p)
             and not any(part != p and part.name.startswith(_EXCLUDE_PREFIXES)
                         for part in [p] + list(p.parents))]
    total = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            z.write(p, p.relative_to(data_dir).as_posix())
            total += p.stat().st_size
    return {"zip": str(out), "entries": len(files),
            "raw_bytes": total, "zip_bytes": out.stat().st_size}


def check(archive: Path) -> dict:
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        must = ["platform.db", "users.json"]
        top = sorted({n.split("/", 1)[0] for n in names})
        missing = [m for m in must if m not in names]
    return {"entries": len(names), "top_dirs": top,
            "missing_required": missing, "ok": not missing}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="平台数据打包/校验")
    ap.add_argument("-o", "--out", default=None, help="输出 zip 路径（默认当前目录）")
    ap.add_argument("--check", metavar="ZIP", help="校验已有包而非打包")
    ap.add_argument("--data-dir", default=None, help="覆盖数据目录（默认 app 配置）")
    args = ap.parse_args()

    if args.check:
        info = check(Path(args.check))
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0 if info["ok"] else 1

    if args.data_dir:
        data = Path(args.data_dir)
    else:
        cfg = _load_config()
        data = cfg.DATA_DIR
    if not data.is_dir():
        print(f"[错误] 数据目录不存在: {data}")
        return 1
    out = Path(args.out) if args.out else Path(
        f"graph-asset-data-{time.strftime('%Y%m%d-%H%M')}.zip")
    print(f"打包 {data} → {out}（排除临时目录）…")
    info = pack(data, out)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    print("恢复：目标机解压到 deploy/platform-data/ 后 docker compose up -d")
    return 0


if __name__ == "__main__":
    sys.exit(main())
