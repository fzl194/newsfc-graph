#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 CompoundTask 复用库 _index.md（task 层规范构建脚本）。

SOP §B.0/§B.4 要求 CompoundTask/{nf}/_index.md 存在；新建 compound 前必查此表
按 command_set 算 Jaccard 判复用。本脚本可重生——compound 变更后重跑即可刷新。
Task 层无版本（v0.19.0 去版本）：资产在 {layer}/{nf}/。

被引用数 = 从 FeatureTask 实际编排反推（reflective，永远是当前真值）。
各 compound 文件自身的「被引用于」边由 builder 维护；若与 _index 不一致，audit_compound_feature.py D3 会 flag。

用法：
  python gen_compound_index.py --nf UDG
"""
import os, re, glob, argparse

BASE = os.environ.get("SFC_ASSET_ROOT", "三层图谱资产")


def main():
    ap = argparse.ArgumentParser(description="生成 CompoundTask _index.md 复用库")
    ap.add_argument("--nf", required=True)
    args = ap.parse_args()
    nf = args.nf

    CT = os.path.join(BASE, "CompoundTask", nf)
    FT = os.path.join(BASE, "FeatureTask", nf)
    re_comp = re.compile(r'\[\[%s@CompoundTask@([^\]]+)\]\]' % nf)

    # 反算被引用于
    used_by = {}
    for f in glob.glob(os.path.join(CT, "*.md")):
        if os.path.basename(f).startswith('_'): continue
        local = os.path.basename(f).replace(f'{nf}@CompoundTask@', '').replace('.md', '')
        used_by[local] = set()
    for f in glob.glob(os.path.join(FT, "*.md")):
        t = open(f, encoding='utf-8').read()
        ft = os.path.basename(f).replace(f'{nf}@FeatureTask@', '').replace('.md', '')
        for c in re_comp.findall(t):
            if c in used_by: used_by[c].add(ft)

    rows = []
    for f in sorted(glob.glob(os.path.join(CT, "*.md"))):
        if os.path.basename(f).startswith('_'): continue
        t = open(f, encoding='utf-8').read()
        y = t.split('---')[1]
        def g(k):
            m = re.search(rf'^{k}:\s*"?(.*?)"?\s*$', y, re.M)
            return m.group(1) if m else ''
        csm = re.search(r'^command_set:\s*\[(.*?)\]', y, re.M)
        cmds = re.findall(r'"([^"]+)"', csm.group(1)) if csm else []
        cid = g('id') or os.path.basename(f).replace('.md', '')
        local = cid.replace(f'{nf}@CompoundTask@', '')
        refs = sorted(used_by.get(local, []))
        rows.append((local, g('name_zh'), g('status'), len(cmds), cmds, len(refs), refs))

    out = ["---",
           f'id: "{nf}@CompoundTask@_index"',
           'type: "CompoundIndex"',
           'name: "_index"',
           'name_zh: "CompoundTask 复用库"',
           f'nf: "{nf}"',
           f'compound_count: {len(rows)}',
           'sop_version: "0.19.0"',
           'status: "active"',
           "---", "",
           f"# CompoundTask 复用库（{nf}）", "",
           "> 新建 compound 前必查此表：按 command_set 算 Jaccard（SOP §B.4）。",
           "> - Jaccard ≥ 0.75 且相位同义 → 复用；0.4–0.75 → reference；< 0.4 → 新建。",
           "> - `被引用数` = 该 compound 被 FeatureTask 实际编排的次数（reflective，本脚本重生时刷新）。", "",
           "| compound | name_zh | status | cmds | command_set | 被引用数 | 被引用于 |",
           "|---|---|---|---|---|---|---|"]
    for local, name_zh, status, ncmd, cmds, nref, refs in rows:
        cs = ", ".join(cmds) if cmds else "_(foundation 骨架，无命令)_"
        ref_str = ", ".join(refs) if refs else "—"
        out.append(f"| `{local}` | {name_zh} | {status} | {ncmd} | {cs} | {nref} | {ref_str} |")

    tgt = os.path.join(CT, "_index.md")
    open(tgt, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print(f"_index.md 已生成: {tgt}")
    print(f"  compound 数: {len(rows)}  command_set 总条目: {sum(r[3] for r in rows)}  foundation(无命令): {sum(1 for r in rows if r[3]==0)}  被引用≥2: {sum(1 for r in rows if r[5]>=2)}")


if __name__ == '__main__':
    main()
