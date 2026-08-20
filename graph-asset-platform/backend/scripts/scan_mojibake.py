#!/usr/bin/env python3
"""内网乱码扫描（配合 v0.24.0 exporter 编码修复，CR-20260820-002）。

扫描存量 md 找"整文件乱码"文件（UTF-8 原文被误当 GBK 族读的典型形态），只读不改。

判定原理（可逆性）：正确中文按 GBK 回编码后几乎不可能再合法解成 UTF-8；
而乱码文本（utf-8 被当 gbk 读）能大面积还原。对每文件前 8KB 的中文段做该测试，
还原成功率 > 0.3 判疑似；另检测 Latin 系 mojibake（æ/Ã/å/ç 连串）与替换符 �。

用法（内网，任意有 python3 的机器）：
  python scan_mojibake.py                      # 默认扫 ../platform-data/{output,assets}
  python scan_mojibake.py --root D:/某目录      # 自定义根（可多个）
输出：疑似清单 + 计数；--json 输出机器可读清单。

矫正方式（脚本不改文件）：更新平台（v0.24.0）后对受影响包重新解压（同 nf+version
覆盖）→ md 重转即净；已被挖掘进 assets 的乱码资产按需重抽该层。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

MOJIBAKE_LATIN = re.compile(r"[æÃåç]{2,}")
REPLACEMENT = "�"


def reversal_score(t: str) -> tuple:
    """(gbk 回编码→utf-8 解码还原成功率, 参与检测段数)。"""
    ok = total = 0
    for i in range(0, min(len(t), 8192), 4096):
        chunk = t[i:i + 4096]
        cjk = [c for c in chunk if "一" <= c <= "鿿"]
        if len(cjk) < 20:  # 中文段太短不参与（避免导航/目录页误报）
            continue
        total += 1
        try:
            "".join(cjk).encode("gbk", errors="strict").decode("utf-8", errors="strict")
            ok += 1
        except Exception:
            pass
    return (ok / total if total else 0.0), total


def scan(root: Path) -> list:
    hits = []
    n = 0
    for p in root.rglob("*.md"):
        n += 1
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not t.strip():
            continue
        score, segs = reversal_score(t)
        latin = len(MOJIBAKE_LATIN.findall(t[:8192])) > 3
        repl = t.count(REPLACEMENT) > 5
        if score > 0.3 or latin or repl:
            kind = ("gbk-misread-utf8" if score > 0.3
                    else "latin-misread" if latin else "replacement-chars")
            hits.append({"file": str(p.relative_to(root)), "kind": kind,
                         "score": round(score, 2), "segments": segs})
    return hits


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="存量乱码 md 扫描（只读）")
    ap.add_argument("--root", action="append", default=None,
                    help="扫描根（可多个；默认 platform-data 的 output 与 assets）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 清单")
    args = ap.parse_args()

    roots = [Path(r) for r in args.root] if args.root else [
        BACKEND.parent / "platform-data" / "output",
        BACKEND.parent / "platform-data" / "assets",
    ]
    all_hits = []
    for root in roots:
        if not root.is_dir():
            print(f"[跳过] 目录不存在: {root}")
            continue
        hits = scan(root)
        all_hits.extend({"root": str(root), **h} for h in hits)
        print(f"[{root}] 疑似乱码 {len(hits)} 个")

    if args.json:
        print(json.dumps(all_hits, ensure_ascii=False, indent=2))
    else:
        for h in all_hits[:80]:
            print(f"  [{h['kind']} score={h['score']}] {h['root']}/{h['file']}")
        if len(all_hits) > 80:
            print(f"  … 共 {len(all_hits)} 个")
    print("矫正：更新平台(v0.24.0) → 对受影响包重新解压覆盖 → 按需重抽受影响层")
    return 0


if __name__ == "__main__":
    sys.exit(main())
