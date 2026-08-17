#!/usr/bin/env python3
"""
特性层端到端编排器
特性目录 + license 目录 → Feature/ + License/ 资产。

用法:
  python build_all.py --nf UDG --version 20.15.2 \
      --feature-dir "output/UDG.../特性部署/特性指南/UDG特性指南" \
      --license-dir "output/UDG.../特性部署/特性指南/UDG License描述" \
      --storage "三层图谱资产"
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOP_VERSION = "0.10.0"


def run(cmd: list[str]) -> None:
    print(">> " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="特性层端到端编排器")
    ap.add_argument("--nf", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--storage", default="三层图谱资产")
    ap.add_argument("--feature-dir", required=True, help="特性源目录（特性指南/UDG特性指南）")
    ap.add_argument("--license-dir", required=True, help="license 源目录（UDG License描述）")
    args = ap.parse_args()
    py = sys.executable

    # 1. 特性（文件夹模型）
    run([py, str(HERE / "build_features.py"),
         "--nf", args.nf, "--version", args.version,
         "--feature-dir", args.feature_dir, "--storage", args.storage])
    # 2. license（切段模型）
    run([py, str(HERE / "build_licenses.py"),
         "--nf", args.nf, "--version", args.version,
         "--license-dir", args.license_dir, "--storage", args.storage])

    print(f"\n特性层端到端完成 → {args.storage}/{{Feature,License}}/{args.nf}/{args.version}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
