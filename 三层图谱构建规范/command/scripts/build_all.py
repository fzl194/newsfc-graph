#!/usr/bin/env python3
"""
命令层端到端编排器
输入：原始产品文档归档(.hwics/.hdx) 或已解压目录 或已导出的 MML 命令 md 目录
输出：{storage}/ 下 Command/ + ConfigObject/ + Parameter/ + output/(若导出)

流程：
  (0 导出，仅当 --product-doc)  → {storage}/output/
  (1 命令)   build_commands.py     → {storage}/Command/{nf}/{ver}/
  (2 配置对象) build_configobjects.py → {storage}/ConfigObject/{nf}/{ver}/
注：参数不单独建 md（参数说明表已在命令 md 原文里）。

用法:
  # A. 已解压目录（产品文档已导出 md），直接指定 MML 命令目录
  python build_all.py --nf UDG --version 20.15.2 \
      --mml-dir "output/UDG_Product_Documentation_CH_20.15.2/OM参考/命令/UDG MML命令" \
      --storage "三层图谱资产"

  # B. 原始归档/已解压产品文档，自动导出到 {storage}/output/ 再构建
  python build_all.py --nf UDG --version 20.15.2 \
      --product-doc "xxx.hwics" --storage "三层图谱资产"
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPORTER_DIR = HERE.parent.parent / "scripts"  # 三层图谱构建规范/scripts/
SOP_VERSION = "0.7.0"


def run(cmd: list[str]) -> None:
    print(">> " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def export_product_doc(product_doc: str, nf: str) -> str:
    """导出原始产品文档到临时目录（不进资产），返回 MML 命令目录路径。"""
    import tempfile
    out_root = Path(tempfile.mkdtemp(prefix="cmddoc_export_"))
    sys.path.insert(0, str(EXPORTER_DIR))
    import product_doc_md_exporter_optimized as exp  # 延迟导入（需 chardet/bs4）

    src = Path(product_doc).resolve()
    if src.is_file():
        extracted = exp.extract_hdx_file(str(src))  # 解压归档 → 临时目录
        exp.main_from_extracted(extracted, str(out_root))
    else:
        exp.main_from_extracted(str(src), str(out_root))

    # 定位 MML 命令目录：output/.../命令/{nf} MML命令
    cands = [p for p in out_root.rglob("*MML命令") if p.is_dir()]
    if not cands:
        cands = [p for p in out_root.rglob("命令") if p.is_dir()]
    for c in cands:
        if nf in c.name:
            return str(c)
    if cands:
        return str(cands[0])
    sys.exit(f"导出后在 {out_root} 未找到 MML 命令目录，请用 --mml-dir 手动指定")


def main() -> int:
    ap = argparse.ArgumentParser(description="命令层端到端编排器")
    ap.add_argument("--nf", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--storage", default="三层图谱资产")
    ap.add_argument("--mml-dir", default=None, help="已导出的 MML 命令 md 目录（与 --product-doc 二选一）")
    ap.add_argument("--product-doc", default=None, help="原始归档(.hwics/.hdx) 或已解压产品文档目录；自动导出到 {storage}/output/")
    ap.add_argument("--intranet-edges", default=None, help="内网命令关联图谱 json（传给命令构建器）")
    args = ap.parse_args()

    if not args.mml_dir and not args.product_doc:
        sys.exit("需要 --mml-dir 或 --product-doc 之一")
    storage = Path(args.storage).resolve()
    py = sys.executable

    mml_dir = args.mml_dir
    if args.product_doc:
        mml_dir = export_product_doc(args.product_doc, args.nf)
        print(f"MML 命令目录（导出到临时目录，不进资产）：{mml_dir}")

    # 1. 命令
    cmd = [py, str(HERE / "build_commands.py"),
           "--nf", args.nf, "--version", args.version,
           "--storage", str(storage), "--mml-dir", mml_dir]
    if args.intranet_edges:
        cmd += ["--intranet-edges", args.intranet_edges]
    run(cmd)
    # 2. 配置对象（读 Command/，反向边闭环）
    run([py, str(HERE / "build_configobjects.py"),
         "--nf", args.nf, "--version", args.version, "--storage", str(storage)])

    print(f"\n端到端完成 → {storage}/{{Command,ConfigObject}}/{args.nf}/{args.version}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
