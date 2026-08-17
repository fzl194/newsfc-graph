#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AtomTask 全面质量审查脚本（按 task/check.md 核查项）。
扫描指定 nf 下某批 atom，逐项检查结构/格式/引用合规性，输出核查报告。
AtomTask 无版本（v0.19.0 Task 层去版本）：资产在 AtomTask/{nf}/；命令层输入在 Command/{nf}/{version}/。

用法:
  python audit_atoms.py --nf UNC --cmd-version 20.15.2 --prefixes RMV,MOD,SET
  （--cmd-version 指定命令层输入版本，用于 ref 真实性检查；不传则取该 nf 下唯一版本目录）
"""
import os, re, glob, argparse, sys

ROOT = r"d:\mywork\KnowledgeBase\NewSFCGraph\三层图谱资产"


def parse_frontmatter(content):
    """返回 (fm_dict, body) ；fm 解析失败返回 ({}, content)。"""
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
    if not m:
        return {}, content
    fm_text, body = m.group(1), m.group(2)
    fm = {}
    for line in fm_text.split('\n'):
        mm = re.match(r'^([A-Za-z_]+):\s*"?(.*?)"?\s*$', line)
        if mm:
            fm[mm.group(1)] = mm.group(2)
    return fm, body


def extract_section(body, title):
    """提取 ## {title} 段内容（到下一个 ## 或文末）。"""
    pat = re.compile(rf'^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)', re.DOTALL | re.MULTILINE)
    m = pat.search(body)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nf', default='UNC')
    ap.add_argument('--cmd-version', default=None,
                    help='命令层输入版本（Command/{nf}/{ver}/，ref 真实性检查用）；不传则取唯一版本目录')
    ap.add_argument('--prefixes', default='RMV,MOD,SET')
    args = ap.parse_args()

    atom_dir = os.path.join(ROOT, 'AtomTask', args.nf)
    # 命令层带版本：显式指定或自动发现唯一版本目录
    cmd_ver = args.cmd_version
    if not cmd_ver:
        vers = [d for d in os.listdir(os.path.join(ROOT, 'Command', args.nf))
                if os.path.isdir(os.path.join(ROOT, 'Command', args.nf, d))]
        if len(vers) == 1:
            cmd_ver = vers[0]
        else:
            sys.exit(f'命令层存在多个版本目录 {vers}，请用 --cmd-version 指定')
    cmd_dir = os.path.join(ROOT, 'Command', args.nf, cmd_ver)

    files = []
    for pfx in args.prefixes.split(','):
        files += glob.glob(os.path.join(atom_dir, f'{args.nf}@AtomTask@{pfx.strip()} *.md'))
    files = sorted(set(files))

    issues = []          # (severity, file, category, msg)
    severities = {'CRITICAL': [], 'HIGH': [], 'MEDIUM': [], 'LOW': []}
    cnt = {'total': 0, 'ok': 0}

    for path in files:
        cnt['total'] += 1
        fname = os.path.basename(path)
        name_no_ext = fname[:-3]
        file_ok = True
        try:
            with open(path, encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            issues.append(('CRITICAL', fname, '读取', f'读取失败: {e}'))
            continue

        fm, body = parse_frontmatter(content)
        if not fm:
            issues.append(('CRITICAL', fname, 'frontmatter', 'frontmatter 缺失或无法解析'))
            continue

        # --- 1. 字段必填（7 字段；version 已删——出现即 fail）---
        required = ['id', 'type', 'name', 'name_zh', 'nf', 'ref', 'status']
        for rf in required:
            if rf not in fm or not str(fm[rf]).strip():
                issues.append(('CRITICAL', fname, '字段必填', f'缺字段或空: {rf}'))
                file_ok = False
        if 'version' in fm:
            issues.append(('CRITICAL', fname, '字段必填', '含已删字段 version（v0.19.0 去版本）'))
            file_ok = False

        # --- 2. ID 格式（三段 {nf}@AtomTask@{local}，不含 version）---
        aid = fm.get('id', '')
        if not re.match(rf'^{args.nf}@AtomTask@.+$', aid):
            issues.append(('HIGH', fname, 'ID格式', f'id 非“{args.nf}@AtomTask@{{local}}”三段: {aid}'))
            file_ok = False
        if args.cmd_version and args.cmd_version in aid:
            issues.append(('HIGH', fname, 'ID格式', f'id 含 version: {aid}'))
            file_ok = False

        # --- 3. 文件名 ↔ ID ---
        if aid and aid != name_no_ext:
            issues.append(('CRITICAL', fname, '文件名↔ID', f'id({aid}) ≠ 文件名({name_no_ext})'))
            file_ok = False

        # --- type / nf / version / status 固定值 ---
        if fm.get('type') != 'AtomTask':
            issues.append(('HIGH', fname, 'type', f'type 非 AtomTask: {fm.get("type")}'))
            file_ok = False
        if fm.get('nf') != args.nf:
            issues.append(('HIGH', fname, 'nf', f'nf 非 {args.nf}: {fm.get("nf")}'))
            file_ok = False
        if fm.get('status') not in ('draft', 'active', 'stale'):
            issues.append(('MEDIUM', fname, 'status', f'status 异常: {fm.get("status")}'))
            file_ok = False

        # --- 4. ref 真实（命令层 md 存在）---
        ref = fm.get('ref', '')
        if ref:
            if not re.match(rf'^{args.nf}@MMLCommand@.+$', ref):
                issues.append(('HIGH', fname, 'ref格式', f'ref 非命令层 ID: {ref}'))
                file_ok = False
            cmd_path = os.path.join(cmd_dir, ref + '.md')
            if not os.path.exists(cmd_path):
                issues.append(('HIGH', fname, 'ref真实', f'ref 命令层 md 不存在: {ref}'))
                file_ok = False

        # --- 5. 正文 5 段（H1 + 引子 + 配置方法 + 决策点 + 约束）---
        if not re.search(r'^# .+', body, re.MULTILINE):
            issues.append(('HIGH', fname, '正文5段', '缺 H1 标题'))
            file_ok = False
        if '[[UNC@MMLCommand@' not in body and f'[[{args.nf}@MMLCommand@' not in body:
            issues.append(('HIGH', fname, '引子', '引子未链命令层 [[...@MMLCommand@...]]'))
            file_ok = False
        for sec in ['## 配置方法', '## 决策点', '## 约束', '## 边']:
            if sec not in body:
                issues.append(('HIGH', fname, '正文5段', f'缺正文段: {sec}'))
                file_ok = False

        # --- 6. ## 边 规定（atom 阶段只有对应命令；禁止 ConfigObject/License/CommandParameter）---
        edge = extract_section(body, '边')
        if edge is None:
            issues.append(('HIGH', fname, '边规定', '缺 ## 边 段'))
            file_ok = False
        else:
            edge_lines = [ln for ln in edge.split('\n') if re.match(r'^\s*-\s', ln)]
            if len(edge_lines) == 0:
                issues.append(('HIGH', fname, '边规定', '## 边 段无边行'))
                file_ok = False
            for ln in edge_lines:
                if '对应命令' not in ln:
                    issues.append(('CRITICAL', fname, '边规定', f'边段非“对应命令”: {ln.strip()[:80]}'))
                    file_ok = False
                else:
                    # 必须双方括号 [[...@MMLCommand@...]]
                    if not re.search(r'\[\[[^\]]*@MMLCommand@[^\]]*\]\]', ln):
                        issues.append(('HIGH', fname, '边引用', f'对应命令非双方括号: {ln.strip()[:80]}'))
                        file_ok = False
            # 边段不应出现禁止对象
            for bad in ['ConfigObject', 'License', 'CommandParameter', '操作配置对象', '对应特性', '组成', '被引用', '编排']:
                if bad in edge:
                    issues.append(('CRITICAL', fname, '边规定', f'边段含禁止对象: {bad}'))
                    file_ok = False

        # --- 7. 无证据 ---
        if '## 证据' in body:
            issues.append(('CRITICAL', fname, '无证据', '含 ## 证据 段'))
            file_ok = False
        if 'source_evidence_ids' in content:
            issues.append(('CRITICAL', fname, '无证据', '含 source_evidence_ids'))
            file_ok = False
        if 'source' in fm:
            issues.append(('CRITICAL', fname, '无证据', 'frontmatter 含 source 字段'))
            file_ok = False

        # --- 8. 引用形式（[[逻辑ID]] 双方括号；非 markdown 相对路径；无 # 锚点）---
        # 8a. markdown 相对路径引用 ](xxx.md)
        for bad in re.findall(r'\]\([^)]*\.md[^)]*\)', body):
            issues.append(('MEDIUM', fname, '引用形式', f'markdown 相对路径引用(应用[[]]): {bad[:60]}'))
            file_ok = False
        # 8b. [[...#...]] 含章节锚点
        for bad in re.findall(r'\[\[[^\]]*#[^\]]*\]\]', body):
            issues.append(('MEDIUM', fname, '引用形式', f'引用含 # 锚点: {bad[:60]}'))
            file_ok = False

        # --- 9. DP / 约束 不编号 ---
        for sec in ['决策点', '约束']:
            sec_text = extract_section(body, sec)
            if sec_text is None:
                continue
            for ln in sec_text.split('\n'):
                # 编号列表：行首 数字.
                if re.match(r'^\s*\d+\.\s', ln):
                    issues.append(('MEDIUM', fname, f'{sec}编号', f'{sec}段含编号: {ln.strip()[:60]}'))
                    file_ok = False

        # --- 10. 决策点 / 约束 显式说明（无分支/无约束需显式说明，不能空）---
        dp = extract_section(body, '决策点')
        cs = extract_section(body, '约束')
        if dp is not None and len(dp.strip()) < 5:
            issues.append(('HIGH', fname, 'DP齐', '## 决策点 段为空（无分支应显式说明）'))
            file_ok = False
        if cs is not None and len(cs.strip()) < 5:
            issues.append(('HIGH', fname, '约束齐', '## 约束 段为空（无约束应显式说明）'))
            file_ok = False

        # --- 11. name_zh 视角（配置动作名，不应以命令英文前缀开头）---
        nz = fm.get('name_zh', '')
        if nz and re.match(r'^(RMV|MOD|SET|ADD|LST|DSP|DEL)\s', nz):
            issues.append(('MEDIUM', fname, 'name_zh', f'name_zh 疑似带命令前缀: {nz[:40]}'))

        # --- 12. 联动引用可达性（[[UNC@MMLCommand@*]] 必须对应命令层 md）---
        for link in re.findall(r'\[\[([^\]]+@MMLCommand@[^\]]+)\]\]', body):
            cmd_path = os.path.join(cmd_dir, link + '.md')
            if not os.path.exists(cmd_path):
                issues.append(('CRITICAL', fname, '联动引用', f'正文 [[{link}]] 断链（命令层不存在）'))

        # --- 13. name_zh 与命令层对齐（建议一致；不一致标 LOW）---
        cmd_layer_path = os.path.join(cmd_dir, ref + '.md') if ref else None
        if cmd_layer_path and os.path.exists(cmd_layer_path):
            try:
                with open(cmd_layer_path, encoding='utf-8') as f:
                    cmd_text = f.read()
                cm = re.search(r'^name_zh:\s*"?(.+?)"?\s*$', cmd_text, re.MULTILINE)
                if cm and nz and cm.group(1).strip() != nz.strip():
                    issues.append(('LOW', fname, 'name_zh对齐', f'atom name_zh="{nz}" vs 命令层="{cm.group(1).strip()}"'))
            except Exception:
                pass

        if file_ok:
            cnt['ok'] += 1

    # === 输出报告 ===
    for sev, f, cat, msg in issues:
        severities.setdefault(sev, []).append((f, cat, msg))

    print('=' * 70)
    print(f'AtomTask 全面质量审查报告  nf={args.nf} cmd-version={cmd_ver} prefixes={args.prefixes}')
    print('=' * 70)
    print(f'扫描文件数: {cnt["total"]}')
    print(f'完全合规: {cnt["ok"]}  ({cnt["ok"]*100//max(cnt["total"],1)}%)')
    print(f'存在问题文件: {cnt["total"] - cnt["ok"]}')
    print(f'问题总数: {len(issues)}')
    print('-' * 70)
    for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        lst = severities.get(sev, [])
        if lst:
            print(f'\n【{sev}】{len(lst)} 条')
            # 按 category 汇总
            from collections import Counter
            cat_cnt = Counter(c for _, c, _ in lst)
            for cat, n in cat_cnt.most_common():
                print(f'  {cat}: {n}')
    print('-' * 70)
    # 详细列出 CRITICAL + HIGH
    detail = [x for x in issues if x[0] in ('CRITICAL', 'HIGH')]
    if detail:
        print(f'\n=== CRITICAL/HIGH 明细（前 80 条）===')
        for sev, f, cat, msg in detail[:80]:
            print(f'[{sev}] {f} | {cat} | {msg}')
        if len(detail) > 80:
            print(f'... 还有 {len(detail)-80} 条 CRITICAL/HIGH')
    else:
        print('\n=== 无 CRITICAL/HIGH 问题 ===')
    # MEDIUM 汇总（不逐条）
    med = severities.get('MEDIUM', [])
    if med:
        print(f'\n=== MEDIUM 明细（前 40 条）===')
        for f, cat, msg in med[:40]:
            print(f'[MED] {f} | {cat} | {msg}')


if __name__ == '__main__':
    main()
