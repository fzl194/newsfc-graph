#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CompoundTask + FeatureTask 跨层一致性审计（task 层规范核查脚本）。

自动化预检 task/check.md 的 compound / feature_task 审查项里可机器判定的部分。
**不替代人工**——守住 check.md「核查独立性」纪律：脚本与 builder 共用正则有盲区，
脚本过=未必全对，脚本报错=一定有问题。

维度：
  D0 CompoundTask 的「## 边」必须是独立 Markdown 段标题                         [fail]
  D1 compound 结构（command_set 非空 / 边标签规范：组成/被引用于，非旧「含 atom」）   [fail]
  D2 →AtomTask 引用真实性（compound/feature_task 引用的 atom 是否存在）              [fail]
  D3 FeatureTask ↔ CompoundTask 反链一致（声明的「被引用于」== 实际反向引用集合）      [fail]
  D4 FeatureTask → Feature（ref / 对应特性）真实性                                  [fail]
  D5 AtomTask 被引用覆盖率 / 孤儿（信息级，不判 fail）                               [info]

用法：
  python audit_compound_feature.py --nf UDG [--feature-version 20.15.2]
  （Task 层无版本——v0.19.0 去版本，资产在 {layer}/{nf}/；--feature-version 指定特性层
   输入版本，用于 manifest 读取，不传则取该 nf 下唯一版本目录）
退出码：有 fail 级问题 → 非 0；全过 → 0。
"""
import os, re, glob, json, argparse, sys

BASE = os.environ.get("SFC_ASSET_ROOT", "三层图谱资产")


def layer_dir(layer, nf):
    """Task 层资产目录（无版本）。"""
    return os.path.join(BASE, layer, nf)


def feature_layer_dir(nf, ver):
    """特性层输入目录（带版本）。"""
    return os.path.join(BASE, "Feature", nf, ver)


RE_ATOM = re.compile(r'\[\[%s@AtomTask@([^\]]+)\]\]' % r'(?P<nf>[A-Z]+)')
RE_ATOM_G = lambda nf: re.compile(r'\[\[%s@AtomTask@([^\]]+)\]\]' % nf)
RE_COMP_G = lambda nf: re.compile(r'\[\[%s@CompoundTask@([^\]]+)\]\]' % nf)
RE_FT_G = lambda nf: re.compile(r'\[\[%s@FeatureTask@([^\]]+)\]\]' % nf)
RE_FE_G = lambda nf: re.compile(r'\[\[%s@Feature@([^\]]+)\]\]' % nf)


def files(d):
    return glob.glob(os.path.join(d, "*.md"))


def main():
    ap = argparse.ArgumentParser(description="CompoundTask + FeatureTask 跨层审计")
    ap.add_argument("--nf", required=True, help="网元，如 UDG / UNC")
    ap.add_argument("--feature-version", default=None,
                    help="特性层输入版本（读 manifest 用）；不传则取该 nf 下唯一版本目录")
    args = ap.parse_args()
    nf = args.nf

    FT = layer_dir("FeatureTask", nf)
    CT = layer_dir("CompoundTask", nf)
    AT = layer_dir("AtomTask", nf)
    fe_ver = args.feature_version
    if not fe_ver:
        vers = [d for d in os.listdir(os.path.join(BASE, "Feature", nf))
                if os.path.isdir(os.path.join(BASE, "Feature", nf, d))]
        if len(vers) == 1:
            fe_ver = vers[0]
        else:
            sys.exit(f"特性层存在多个版本目录 {vers}，请用 --feature-version 指定")
    FE = feature_layer_dir(nf, fe_ver)
    MANIFEST = os.path.join(FE, "_build_manifest.json")

    re_atom = RE_ATOM_G(nf); re_comp = RE_COMP_G(nf)
    re_ft = RE_FT_G(nf); re_fe = RE_FE_G(nf)

    def has_atom(x): return os.path.exists(os.path.join(AT, f"{nf}@AtomTask@{x}.md"))
    def has_comp(x): return os.path.exists(os.path.join(CT, f"{nf}@CompoundTask@{x}.md"))
    def has_ft(x): return os.path.exists(os.path.join(FT, f"{nf}@FeatureTask@{x}.md"))

    # Feature 全集（manifest）
    all_codes, fe_docs = set(), set()
    if os.path.exists(MANIFEST):
        man = json.load(open(MANIFEST, encoding='utf-8'))
        fe_docs = set(man.get('docs', []))
        for d in fe_docs:
            m = re.search(r'[A-Z]+FD-\d{6}', d)
            if m: all_codes.add(m.group(0))

    atom_files = {os.path.basename(f).replace(f'{nf}@AtomTask@', '').replace('.md', '') for f in files(AT)}
    comp_files = {os.path.basename(f).replace(f'{nf}@CompoundTask@', '').replace('.md', '') for f in files(CT) if not os.path.basename(f).startswith('_')}
    ft_files = {os.path.basename(f).replace(f'{nf}@FeatureTask@', '').replace('.md', '') for f in files(FT)}

    fail_count = 0
    print("=" * 70)
    print(f"task 层跨层审计 · {nf}（Task 层无版本；Feature 输入 {fe_ver}）")
    print(f"  AtomTask={len(atom_files)}  CompoundTask={len(comp_files)}  FeatureTask={len(ft_files)}  Feature codes={len(all_codes)}")

    # 收集引用
    comp_refs, ft_refs = {}, {}
    for f in files(CT):
        if os.path.basename(f).startswith('_'): continue
        t = open(f, encoding='utf-8').read()
        n = os.path.basename(f).replace(f'{nf}@CompoundTask@', '').replace('.md', '')
        comp_refs[n] = {'atoms': set(re_atom.findall(t)), 'fts': set(re_ft.findall(t))}
    for f in files(FT):
        t = open(f, encoding='utf-8').read()
        n = os.path.basename(f).replace(f'{nf}@FeatureTask@', '').replace('.md', '')
        ft_refs[n] = {'atoms': set(re_atom.findall(t)), 'comps': set(re_comp.findall(t)), 'fes': set(re_fe.findall(t))}

    # ---- D0 CompoundTask 边段标题 ----
    print("\n" + "=" * 70)
    print("D0 · CompoundTask 边段标题独立性 [fail]")
    d0 = []
    for f in files(CT):
        if os.path.basename(f).startswith('_'): continue
        t = open(f, encoding='utf-8').read()
        n = os.path.basename(f).replace(f'{nf}@CompoundTask@', '').replace('.md', '')
        if not re.search(r'^## 边\s*$', t, re.M):
            d0.append(n)
    print(f"  边段标题非独立: {len(d0)} {d0[:10]}")
    fail_count += len(d0)

    # ---- D1 compound 结构 ----
    print("\n" + "=" * 70)
    print("D1 · compound 结构（command_set 非空 / 边标签规范）[fail]")
    d1_no_cs, d1_drift = [], []
    for f in files(CT):
        if os.path.basename(f).startswith('_'): continue
        t = open(f, encoding='utf-8').read()
        n = os.path.basename(f).replace(f'{nf}@CompoundTask@', '').replace('.md', '')
        st = re.search(r'^status:\s*"?(\w+)"?', t, re.M)
        is_foundation = st and st.group(1) == 'foundation'
        if not re.search(r'^command_set:', t, re.M) and not is_foundation:
            d1_no_cs.append(n)
        e = re.search(r'## 边\s*\n(.*?)(?:\n## |\Z)', t, re.S)
        if e and '含 atom' in e.group(1):
            d1_drift.append(n)
    print(f"  缺 command_set（非 foundation）: {len(d1_no_cs)} {d1_no_cs[:10]}")
    print(f"  边标签漂移（含 atom）: {len(d1_drift)} {d1_drift[:10]}")
    fail_count += len(d1_no_cs) + len(d1_drift)

    # ---- D2 →atom ----
    print("\n" + "=" * 70)
    print("D2 · →AtomTask 引用真实性 [fail]")
    d2 = []
    for src, refs in [('Compound', comp_refs), ('FeatureTask', ft_refs)]:
        for owner, d in refs.items():
            for a in d['atoms']:
                if not has_atom(a):
                    d2.append((src, owner, a))
    print(f"  断链: {len(d2)}")
    for s, o, a in d2[:20]: print(f"    [{s}] {o} → AtomTask@{a} ✗")
    fail_count += len(d2)

    # ---- D3 FT↔compound 反链 ----
    print("\n" + "=" * 70)
    print("D3 · FeatureTask ↔ CompoundTask 反链一致 [fail]")
    d3_ft, d3_comp = [], []
    for ft, d in ft_refs.items():
        for c in d['comps']:
            if not has_comp(c): d3_ft.append((ft, c))
    actual_used_by = {c: set() for c in comp_refs}
    for ft, d in ft_refs.items():
        for c in d['comps']:
            if c in actual_used_by: actual_used_by[c].add(ft)
    mismatch = []
    for c in comp_refs:
        declared = comp_refs[c]['fts']
        actual = actual_used_by[c]
        if declared != actual:
            mismatch.append((c, sorted(declared), sorted(actual)))
    print(f"  FT→不存在 compound: {len(d3_ft)}  {d3_ft[:10]}")
    print(f"  反链不一致（声明被引用于 != 实际）: {len(mismatch)}")
    for c, dec, act in mismatch[:10]:
        print(f"    {c}: 声明{dec} 实际{act}")
    fail_count += len(d3_ft) + len(mismatch)

    # ---- D4 →Feature ----
    print("\n" + "=" * 70)
    print("D4 · FeatureTask → Feature（ref/对应特性）[fail]")
    d4_ref, d4_edge = [], []

    def feature_doc_exists(fe_local: str) -> bool:
        """特性对象存在性：概述 code 查 manifest/代码集；子文档 code-slug 查磁盘。

        子文档 ID = {code}-{slug}（v0.13.0），文件 = Feature/{nf}/{ver}/{nf}@Feature@{code}/{slug}.md。
        manifest 构建早于 v0.18.0 手工回填的子文档，不能只查 manifest（盲区）。
        """
        m = re.match(r'^([A-Z]+FD-\d{6})-(.+)$', fe_local)
        if not m:
            return fe_local in all_codes or f"{nf}@Feature@{fe_local}" in fe_docs
        code, slug = m.group(1), m.group(2)
        return os.path.exists(os.path.join(FE, f"{nf}@Feature@{code}", f"{slug}.md"))

    for f in files(FT):
        t = open(f, encoding='utf-8').read()
        n = os.path.basename(f).replace(f'{nf}@FeatureTask@', '').replace('.md', '')
        mr = re.search(r'^ref:\s*"([^"]+)"', t, re.M)
        if mr:
            rl = mr.group(1).replace(f'{nf}@Feature@', '')
            if not feature_doc_exists(rl):
                d4_ref.append((n, rl))
        for fe in ft_refs[n]['fes']:
            if not feature_doc_exists(fe):
                d4_edge.append((n, fe))
    print(f"  ref 断链: {len(d4_ref)} {d4_ref[:10]}")
    print(f"  边引用断链: {len(d4_edge)} {d4_edge[:10]}")
    fail_count += len(d4_ref) + len(d4_edge)

    # ---- D5 atom 覆盖（info）----
    print("\n" + "=" * 70)
    print("D5 · AtomTask 被引用覆盖 [info，不判 fail]")
    used = set()
    for d in list(comp_refs.values()) + list(ft_refs.values()):
        used |= d['atoms']
    used &= atom_files
    orphan = atom_files - used
    print(f"  被引用: {len(used)}/{len(atom_files)}；待接线（孤儿）: {len(orphan)}（正常——其特性尚未建到 FeatureTask 层）")

    # ---- 汇总 ----
    print("\n" + "=" * 70)
    print(f"汇总：fail 级问题 = {fail_count}" + ("  ✅ 全过" if fail_count == 0 else "  ❌ 需修"))
    sys.exit(1 if fail_count else 0)


if __name__ == '__main__':
    main()
