#!/usr/bin/env python3
"""
atom 构建输入采集器：扫已构建的命令层 + 特性层资产 + 原始产品文档，按命令归集"配置示例"，
输出 per-命令汇总 md（atom 构建的工作底稿，**非资产**，git ignore）。

对应: task/SKILL.md A.5 第一步。

输入（已构建资产 + 原始产品文档；前置：Command + Feature 层已构建）:
  - 命令层: {storage}/Command/{nf}/{ver}/{nf}@MMLCommand@{cmd}.md     ← 命令真相（① 全文 verbatim）
  - 特性层: {storage}/Feature/{nf}/{ver}/{nf}@Feature@{code}/*.md     ← 命令的真实配置示例（②-A）
  - 原始产品文档: --doc-root 下的语义目录（业务专题/网络部署）*.md   ← 端到端方案/部署配置样例（②-B，丰富源）

输出（中间态·非资产）:
  {storage}/_intermediates/atom-input/{nf}/{cmd}.md
  （AtomTask 无版本——v0.19.0 Task 层去版本；--version 仅是命令/特性层输入的选择器）

汇总 md 四段（agent 读它归纳 atom，不进 atom md）:
  ① 命令真相（命令层资产 md **全文** verbatim，不只选片段）
  ② 配置范式: ②-A 特性层命中 + ②-B 原始产品文档命中（数据规划行/任务脚本/操作步骤上下文）
  ③ 配置方法差异汇总（自动派生：每参数取值分布 → DP 线索；特性层 + 原始文档合并）
  ④ 数据源

泛化约定（task/SKILL.md A.5）:
  - 原始文档检索按 **语义目录名**（业务专题/网络部署）自动发现，**不硬编码路径**。
    不同网元/版本产品文档结构不一致（UDG 业务专题在"特性部署/"下，UNC 在"网络部署/"下），
    脚本在 --doc-root 下递归找这些目录名，无视层级，自动适配。
  - 产品文档根由 --doc-root 显式指定（各版本根目录命名不同，无法自动推断）。
   - 命中正则兼容命令引用的三种形式：`[[NF@MMLCommand@CMD]]`、特性层 `**CMD**`
     与原始文档 `[**CMD**](url)` 链接。

用法:
  # 单命令（启用原始文档检索，推荐）
  python collect_command_examples.py --nf UDG --version 20.15.2 --cmd "ADD URR" \\
      --doc-root output/UDG_Product_Documentation_CH_20.15.2

  # 全量（扫命令层资产发现所有命令）
  python collect_command_examples.py --nf UDG --version 20.15.2 --all \\
      --doc-root output/UDG_Product_Documentation_CH_20.15.2

  # 干跑（只统计命中，不写）
  python collect_command_examples.py --nf UDG --version 20.15.2 --all --dry-run \\
      --doc-root output/UDG_Product_Documentation_CH_20.15.2

  # 旧行为（只扫特性层，不扫原始文档）
  python collect_command_examples.py --nf UDG --version 20.15.2 --all --no-raw
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# 三层图谱构建规范/task/scripts/ → SFCGraph/
REPO = Path(__file__).resolve().parents[3]
DEFAULT_STORAGE = "三层图谱资产"
INTERMEDIATE_TPL = "{storage}/_intermediates/atom-input/{nf}/{cmd}.md"
NOHIT_TPL = "{storage}/_intermediates/atom-input/{nf}/_no-hit.txt"

# 原始产品文档检索的语义目录名清单（可被 --raw-dirs 覆盖）。
# 按目录名在 --doc-root 下递归发现，不硬编码层级路径，适配不同网元/版本结构差异。
RAW_DOC_DIR_NAMES = ["业务专题", "网络部署"]

# 命令文件名: {nf}@MMLCommand@{cmd}.md → 提 {cmd}（local 保留空格）
_CMD_FILE_RE = re.compile(r"^(?P<nf>[^@]+)@MMLCommand@(?P<cmd>.+)\.md$")
# 特性文件夹: {nf}@Feature@{code}
# 通用前缀 [A-Z]+FD（覆盖 GWFD/WSFD/IPFD/NPFD/SFFD 及任何未来前缀，避免硬编码漏扫）
_FEATURE_DIR_RE = re.compile(r"^[^@]+@Feature@(?P<code>[A-Z]+FD-\d+)")
_WIKILINK_COMMAND_RE = re.compile(r"\[\[(?:[^@\]\n]+)@MMLCommand@([^\]\n]+)\]\]")
_BOLD_COMMAND_RE = re.compile(r"\*\*([^*\n]+?)\*\*")
_SCRIPT_COMMAND_RE = re.compile(
    r"^[ \t]*`?([A-Z][A-Z0-9]{1,}(?:[ \t]+[A-Za-z0-9_/+.-]+)*):", re.M)


# ---------- 路径 ----------
def storage_root(storage: str) -> Path:
    p = Path(storage)
    return p if p.is_absolute() else REPO / p


def doc_root_path(doc_root: str) -> Path:
    """--doc-root 解析为绝对路径（相对路径相对 REPO 解析，与 --storage 一致）。"""
    p = Path(doc_root)
    return p if p.is_absolute() else REPO / p


def _rel_to(p: Path, base: Path) -> str:
    """p 相对 base 的路径字符串；p 不在 base 下时回退为绝对/原样字符串。"""
    try:
        return str(p.relative_to(base))
    except ValueError:
        return str(p)


def command_dir(storage: str, nf: str, ver: str) -> Path:
    return storage_root(storage) / "Command" / nf / ver


def feature_dir(storage: str, nf: str, ver: str) -> Path:
    return storage_root(storage) / "Feature" / nf / ver


def command_md_path(storage: str, nf: str, ver: str, cmd: str) -> Path:
    """命令层资产 md：文件名 = {nf}@MMLCommand@{cmd}.md（local 保留空格）。"""
    return command_dir(storage, nf, ver) / f"{nf}@MMLCommand@{cmd}.md"


def atomtask_path(storage: str, nf: str, ver: str, cmd: str) -> Path:
    """已建 AtomTask md：{nf}@AtomTask@{cmd}.md（与命令同名做锚）。

    AtomTask 无版本（v0.19.0 Task 层去版本）：路径 {storage}/AtomTask/{nf}/，ver 参数仅保留
    签名兼容（输入层 Command/Feature 仍带版本），不参与本路径。
    """
    return storage_root(storage) / "AtomTask" / nf / f"{nf}@AtomTask@{cmd}.md"


def atomtask_exists(storage: str, nf: str, ver: str, cmd: str) -> bool:
    """该命令的 AtomTask 是否已建（用于 --skip-built，避免给已建命令重复生成中间态）。"""
    return atomtask_path(storage, nf, ver, cmd).exists()


def output_path(storage: str, nf: str, ver: str, cmd: str) -> Path:
    """中间态输出路径（AtomTask 无版本，ver 仅保留签名兼容）。"""
    rel = INTERMEDIATE_TPL.format(storage=storage, nf=nf, cmd=cmd)
    return REPO / rel


def validate_command_name(cmd: str) -> str:
    """命令名用于输出文件名，拒绝路径片段以避免写出中间层目录。"""
    if not cmd or any(token in cmd for token in ("/", "\\", "\x00")) or ".." in cmd:
        raise argparse.ArgumentTypeError("--cmd 不能包含路径分隔符、.. 或空字符")
    return cmd


# ---------- 命令发现 ----------
def discover_commands(storage: str, nf: str, ver: str) -> dict[str, Path]:
    """扫命令层资产，从文件名提命令全名。返回 {命令名 → md 路径}。"""
    base = command_dir(storage, nf, ver)
    cmds: dict[str, Path] = {}
    if not base.exists():
        return cmds
    for md in base.glob("*.md"):
        m = _CMD_FILE_RE.match(md.name)
        if m and m.group("nf") == nf:
            cmds.setdefault(m.group("cmd"), md)
    return cmds


# ---------- 特性资产预读（缓存，万级命令复用） ----------
_FEATURE_CACHE: dict[tuple[str, str, str], list[dict]] = {}


def load_feature_docs(storage: str, nf: str, ver: str) -> list[dict]:
    """特性层资产预读缓存。返回 [{path, feature_code, text}, ...]。

    扫 Feature/{nf}/{ver}/{nf}@Feature@{code}/*.md 全部子文档。
    """
    key = (storage, nf, ver)
    if key in _FEATURE_CACHE:
        return _FEATURE_CACHE[key]
    base = feature_dir(storage, nf, ver)
    docs: list[dict] = []
    if base.exists():
        for md in base.rglob("*.md"):
            code = _feature_code_of(md)
            if not code:
                continue
            try:
                text = md.read_text(encoding="utf-8")
            except Exception:
                continue
            docs.append({"path": md, "feature_code": code, "text": text})
    _FEATURE_CACHE[key] = docs
    return docs


def _feature_code_of(path: Path) -> str | None:
    """从路径段 {nf}@Feature@{code} 提 feature_code。"""
    for part in path.parts:
        m = _FEATURE_DIR_RE.match(part)
        if m:
            return m.group("code")
    return None


# ---------- 原始产品文档预读（缓存，按语义目录名自动发现） ----------
def _doc_group(md_path: Path, names: set[str]) -> str:
    """md 所属的最具体语义目录名（从 md 路径由深到浅找第一个匹配段）。"""
    for part in reversed(md_path.parts):
        if part in names:
            return part
    return "其他"


def discover_raw_dirs(doc_root: Path, names: list[str]) -> list[tuple[Path, str]]:
    """在 doc_root 下递归查找目录名 ∈ names 的目录（去重，无视层级）。

    泛化：UDG 的"业务专题"在 特性部署/ 下、UNC 的在 网络部署/ 下，都能被发现。
    """
    key = (str(doc_root.resolve()), tuple(names))
    if key in _RAW_DIR_CACHE:
        return _RAW_DIR_CACHE[key]

    names_set = set(names)
    found: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    if not doc_root.exists():
        return found
    for d in doc_root.rglob("*"):
        if d.is_dir() and d.name in names_set and d not in seen:
            seen.add(d)
            found.append((d, d.name))
    _RAW_DIR_CACHE[key] = found
    return found


_RAW_DIR_CACHE: dict[tuple[str, tuple[str, ...]], list[tuple[Path, str]]] = {}
_RAW_CACHE: dict[tuple[str, tuple[str, ...]], list[dict]] = {}


def load_raw_docs(doc_root: Path, names: list[str]) -> list[dict]:
    """原始产品文档预读缓存。返回 [{path, rel, group, text}, ...]。

    对每个语义目录 rglob *.md，**按 md 路径全局去重**（UNC 下"网络部署"会包住
    "网络部署/业务专题"，去重避免同一 md 被两个目录各读一次）。
    """
    resolved_root = doc_root.resolve()
    key = (str(resolved_root), tuple(names))
    if key in _RAW_CACHE:
        return _RAW_CACHE[key]
    names_set = set(names)
    docs: list[dict] = []
    seen_paths: set[Path] = set()
    for d, _name in discover_raw_dirs(resolved_root, names):
        for md in d.rglob("*.md"):
            if md in seen_paths:
                continue
            seen_paths.add(md)
            try:
                text = md.read_text(encoding="utf-8")
            except Exception:
                continue
            docs.append({
                "path": md,
                "rel": _rel_to(md, REPO),
                "group": _doc_group(md, names_set),
                "text": text,
            })
    _RAW_CACHE[key] = docs
    return docs


# ---------- 倒排索引（避免 O(命令×文档) 暴力扫描） ----------
def build_command_index(docs: list[dict], commands_set: set[str]) -> dict[str, list[int]]:
    """倒排索引：扫每个文档一次，提取它引用的命令，返回 {cmd: [doc_idx]}。

    用通用正则提取候选命令短语（wikilink / 粗体 / 脚本行首），与命令集合交集——
    避免对每个命令线性扫所有文档做子串检测（O(命令×文档) → O(文档×候选提取)）。
    候选提取覆盖三种强证据形式：`[[NF@MMLCommand@CMD]]`、
    `**CMD**`/`[**CMD**](url)` 粗体、`CMD:..;` 脚本。
    """
    index: dict[str, list[int]] = defaultdict(list)
    for i, doc in enumerate(docs):
        text = doc["text"]
        candidates: set[str] = set()
        for m in _WIKILINK_COMMAND_RE.finditer(text):
            candidates.add(m.group(1).strip())
        for m in _BOLD_COMMAND_RE.finditer(text):
            candidates.add(m.group(1).strip())
        for m in _SCRIPT_COMMAND_RE.finditer(text):
            candidates.add(m.group(1).strip())
        for cand in candidates:
            if cand in commands_set:
                index[cand].append(i)
    return dict(index)


# ---------- 命中判定 + 提取 ----------
def cmd_token_re(cmd: str) -> str:
    """命令名匹配片段：兼容三种引用形式。

    - Feature / 特性层资产: `[[NF@MMLCommand@CMD]]`
    - 特性层资产: `**CMD**`（纯粗体）
    - 原始产品文档: `[**CMD**](url)`（粗体 + markdown 链接，url 指向 OM参考/命令/.../增加X(CMD)_id.md）

    命令名前后允许可选的 `[` / `]` 与 `(url)`，统一匹配三种。
    """
    c = re.escape(cmd)
    wikilink = r"(?:\*\*)?\[\[[^@\]\n]+@MMLCommand@" + c + r"\]\](?:\*\*)?"
    bold_link = r"\[?\s*\*\*\s*" + c + r"\s*\*\*\s*\]?(?:\([^)]*\))?"
    return r"(?:" + wikilink + r"|" + bold_link + r")"


def command_script_re(cmd: str) -> str:
    """命令脚本匹配：接受裸/链接式命令及参数跨行的脚本。"""
    reference = cmd_token_re(cmd)
    raw = re.escape(cmd)
    # 参数允许换行，但限定在一个合理的脚本块内，避免缺分号的脏文档跨页回溯。
    return r"^\s*`?\s*(?:" + reference + r"|" + raw + r")\s*[:\s][^;\n]*(?:\n[^;\n]*){0,20};`?"


def detect_signals(text: str, cmd: str) -> dict[str, bool]:
    """信号检测（表中任意列 / 任务脚本行首 / 段落弱信号）。"""
    tok = cmd_token_re(cmd)
    rec = re.escape(cmd)
    data_plan = re.search(r"^\|(?=[^\n]*" + tok + r")[^\n]*\|[ \t]*$", text, re.M)
    task_example = re.search(command_script_re(cmd), text, re.M)
    prose = re.search(r"(?:通过|使用)\s*" + tok, text)
    return {"data_plan": bool(data_plan), "task_example": bool(task_example), "prose": bool(prose)}


def extract_data_plan_rows(text: str, cmd: str) -> list[str]:
    tok = cmd_token_re(cmd)
    rows = re.findall(r"^\|(?=[^\n]*" + tok + r")[^\n]*\|[ \t]*$", text, re.M)
    return list(dict.fromkeys(rows))  # 去重保序


def extract_task_examples(text: str, cmd: str) -> list[str]:
    examples = re.findall(command_script_re(cmd), text, re.M)
    seen, unique = set(), []
    for e in examples:
        norm = e.strip("`").strip()
        if norm and norm not in seen:
            seen.add(norm)
            unique.append(norm)
    return unique


def extract_step_contexts(text: str, cmd: str, window: int = 2, src_path: str = "") -> list[dict]:
    """操作步骤上下文：表格任意列命令引用或链接/裸脚本命中，合并相邻段。"""
    tok = cmd_token_re(cmd)
    data_plan_pat = re.compile(r"^\|(?=[^\n]*" + tok + r")[^\n]*\|[ \t]*$")
    cmd_inline_pat = re.compile(command_script_re(cmd))
    lines = text.split("\n")
    hit_idx = [i for i, ln in enumerate(lines) if data_plan_pat.search(ln) or cmd_inline_pat.match(ln)]
    if not hit_idx:
        return []
    # 合并为段（间距 ≤ 2*window）
    segments: list[tuple[int, int]] = []
    seg_start, prev = hit_idx[0], hit_idx[0]
    for idx in hit_idx[1:]:
        if idx - prev <= 2 * window:
            prev = idx
            continue
        segments.append((max(0, seg_start - window) + 1, min(len(lines), prev + window)))
        seg_start, prev = idx, idx
    segments.append((max(0, seg_start - window) + 1, min(len(lines), prev + window)))
    contexts = []
    for start, end in segments:
        kept = [(n, lines[n - 1]) for n in range(start, end + 1)
                if data_plan_pat.search(lines[n - 1]) or cmd_inline_pat.match(lines[n - 1])]
        if not kept:
            continue
        contexts.append({
            "src_path": src_path,
            "start_line": kept[0][0],
            "end_line": kept[-1][0],
            "context": "\n".join(f"{n:>4d}: {t}" for n, t in kept),
        })
    return contexts


# ---------- 命令真相（从命令层资产 md 提取，用于①全文后的投影提示） ----------
def _section(md: str, name: str) -> str:
    """取 `#### {name}` 到下一个 `####`/`## ` 之间的正文。"""
    lines = md.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("####") and name in ln:
            start = i + 1
            break
    if start is None:
        return ""
    body = []
    for ln in lines[start:]:
        if ln.startswith("#"):
            break
        body.append(ln)
    return "\n".join(body).strip()


def extract_command_truth(cmd_md: Path, repo: Path, text: str | None = None) -> dict:
    """从命令层资产 md 抽命令真相摘要（适用NF/功能/notes/参数真相表）。

    ① 段主体改为命令层 md **全文** verbatim；这里的摘要仅用于全文后的"自动识别投影提示"
    （帮 agent 快速定位 notes→约束、参数计数等），不替代全文。
    text 可传入已读全文，避免与①全文重复读盘。
    """
    if text is None:
        text = cmd_md.read_text(encoding="utf-8")
    out: dict = {"path": str(cmd_md.relative_to(repo)), "applicable_nf": "", "function": "",
                 "notes": [], "param_table": []}

    func_text = _section(text, "命令功能") or _section(text, "功能")
    if func_text:
        out["function"] = func_text
        m = re.search(r"\*\*适用NF[：:]\s*([^*\n]+)\*\*", func_text)
        if m:
            out["applicable_nf"] = m.group(1).strip()

    notes_text = _section(text, "注意事项") or _section(text, "说明")
    if notes_text:
        out["notes"] = [b.strip() for b in re.findall(r"^[-*]\s+(.+)$", notes_text, re.M)]

    param_text = _section(text, "参数说明") or _section(text, "参数")
    if param_text:
        rows = re.findall(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$", param_text, re.M)
        out["param_table"] = [
            {"param": c[0].strip(), "name": c[1].strip(), "desc": c[2].strip()}
            for c in rows if c[0].strip() and "参数标识" not in c[0] and not set(c[0].strip()) <= set("- :")
        ]
    return out


# ---------- 单命令汇总 ----------
def aggregate_for_command(
    storage: str,
    nf: str,
    ver: str,
    cmd: str,
    repo: Path,
    doc_root: Path | None = None,
    raw_names: list[str] | None = None,
    feature_index: dict[str, list[int]] | None = None,
    raw_index: dict[str, list[int]] | None = None,
) -> tuple[str, int, int]:
    """生成单命令汇总 md，返回 (md 文本, 特性层命中数, 原始文档命中数)。

    feature_index/raw_index 为预建倒排索引（--all 全量模式传入，避免 O(命令×文档) 暴力扫描）：
    传入时只扫该命令的候选文档；为 None（--cmd 单命令模式）则全扫。
    """
    raw_names = raw_names if raw_names is not None else list(RAW_DOC_DIR_NAMES)

    # ① 命令真相（命令层资产 md 全文 verbatim；读一次，truth 摘要复用同一文本）
    cmd_md = command_md_path(storage, nf, ver, cmd)
    cmd_md_exists = cmd_md.exists()
    cmd_md_full = cmd_md.read_text(encoding="utf-8") if cmd_md_exists else ""
    truth = extract_command_truth(cmd_md, repo, text=cmd_md_full) if cmd_md_exists else {
        "path": f"(未找到命令层资产: {cmd_md.name})", "applicable_nf": "", "function": "",
        "notes": [], "param_table": []}

    # ②-A 扫特性层资产（倒排索引候选 or 全扫），命中判定（按 feature_code 聚合）
    feature_docs = load_feature_docs(storage, nf, ver)
    feature_candidates = ([feature_docs[i] for i in feature_index.get(cmd, [])]
                          if feature_index is not None else feature_docs)
    hits_by_code: dict[str, dict] = {}
    for doc in feature_candidates:
        text = doc["text"]
        if cmd not in text:  # 倒排候选仍需确认（防候选提取误差）
            continue
        signals = detect_signals(text, cmd)
        if not (signals["data_plan"] or signals["task_example"]):
            continue  # 强证据：数据规划行或任务脚本（粗体/段落太弱，参考信息页会污染）
        code = doc["feature_code"]
        rel = str(doc["path"].relative_to(repo))
        hit = {
            "feature_code": code,
            "path": rel,
            "data_plan_rows": extract_data_plan_rows(text, cmd),
            "task_examples": extract_task_examples(text, cmd),
            "step_contexts": extract_step_contexts(text, cmd, src_path=rel),
        }
        if code not in hits_by_code:
            hits_by_code[code] = hit
        else:  # 同特性多子文档合并，保留证据更丰的作 primary
            cur = hits_by_code[code]
            cur_score = len(cur["data_plan_rows"]) + len(cur["task_examples"])
            new_score = len(hit["data_plan_rows"]) + len(hit["task_examples"])
            primary, secondary = (cur, hit) if cur_score >= new_score else (hit, cur)
            primary["data_plan_rows"] = list(dict.fromkeys(primary["data_plan_rows"] + secondary["data_plan_rows"]))
            primary["task_examples"] = list(dict.fromkeys(primary["task_examples"] + secondary["task_examples"]))
            seen = {(c["src_path"], c["start_line"], c["end_line"]) for c in primary["step_contexts"]}
            for c in secondary["step_contexts"]:
                k = (c["src_path"], c["start_line"], c["end_line"])
                if k not in seen:
                    seen.add(k)
                    primary["step_contexts"].append(c)
            hits_by_code[code] = primary
    hits = [hits_by_code[k] for k in sorted(hits_by_code.keys())]

    # 模板复用折叠（同指纹特性折叠，避免 activation 模板复用重复）
    def fingerprint(r: str) -> str:
        return re.sub(r"\s+", "", re.sub(r"\d+", "N", r))

    def fp_set(h: dict) -> frozenset:
        return frozenset([fingerprint(r) for r in h["data_plan_rows"]]
                         + [("EX:" + e) for e in h["task_examples"]])

    groups: dict[frozenset, list[dict]] = {}
    for h in hits:
        groups.setdefault(fp_set(h), []).append(h)
    for fs, group in groups.items():
        if len(group) <= 1 or len(fs) < 3:
            continue
        primary = group[0]
        for dup in group[1:]:
            dup["data_plan_rows"] = []
            dup["task_examples"] = []
            dup["template_of"] = primary["feature_code"]

    # ②-B 扫原始产品文档（业务专题/网络部署，语义目录名自动发现；倒排候选 or 全扫）
    raw_hits: list[dict] = []
    if doc_root is not None:
        raw_docs = load_raw_docs(doc_root, raw_names)
        raw_candidates = ([raw_docs[i] for i in raw_index.get(cmd, [])]
                          if raw_index is not None else raw_docs)
        for doc in raw_candidates:
            text = doc["text"]
            if cmd not in text:  # 倒排候选仍需确认
                continue
            signals = detect_signals(text, cmd)
            if not (signals["data_plan"] or signals["task_example"]):
                continue
            raw_hits.append({
                "group": doc["group"],
                "path": doc["rel"],
                "data_plan_rows": extract_data_plan_rows(text, cmd),
                "task_examples": extract_task_examples(text, cmd),
                "step_contexts": extract_step_contexts(text, cmd, src_path=doc["rel"]),
            })

    # ③ 配置方法差异汇总（特性层 + 原始文档的 data_plan_rows 合并派生）
    param_counter: dict[str, Counter] = defaultdict(Counter)

    def _accumulate(rows: list[str]) -> None:
        for row in rows:
            cells = [c.strip() for c in row.split("|")]
            if len(cells) >= 5:
                param = cells[2].replace("（", "(").replace("）", ")").strip()
                value = cells[3].strip()
                if param and value:
                    param_counter[param][value] += 1

    for h in hits:
        _accumulate(h["data_plan_rows"])
    for h in raw_hits:
        _accumulate(h["data_plan_rows"])

    # 拼装
    L: list[str] = []
    L.append(f"# atom 构建输入：{cmd} ({nf} {ver})")
    L.append(f"> 命令名: {cmd} | 特性层命中: {len(hits)} | 原始文档命中: {len(raw_hits)} | 命令层资产: {truth['path']}")
    L.append(f"> 工具: 三层图谱构建规范/task/scripts/collect_command_examples.py")
    L.append(f"> 生成时间: {datetime.now().isoformat(timespec='seconds')}")
    L.append("")
    L.append("> ⚠ 本文件是 atom 构建的**工作底稿**（非资产、不进 atom md、git ignore）。")
    L.append("> agent 读它归纳 atom 的 配置方法字典 / DP / 约束（见 task/SKILL.md A.5 第二步）。")
    L.append("")

    # ① 命令真相（命令层资产 md 全文）
    L.append("## ① 命令真相（命令层资产 md 全文 verbatim）")
    if not cmd_md_exists:
        L.append(f"- **⚠ 未找到命令层资产: {cmd_md.name}**")
    else:
        L.append(f"> 来源: {truth['path']}（以下为命令层 md 全文，含 frontmatter / 参数真相表 / 使用实例 / 边）")
        L.append("")
        L.append("````markdown")
        L.append(cmd_md_full.rstrip())
        L.append("````")
        hints: list[str] = []
        if truth["applicable_nf"]:
            hints.append(f"适用NF: {truth['applicable_nf']}")
        if truth["notes"]:
            hints.append(f"notes {len(truth['notes'])} 条（**应投影为 atom 约束**）")
        if truth["param_table"]:
            hints.append(f"参数 {len(truth['param_table'])} 个")
        if hints:
            L.append("")
            L.append("> 自动识别（辅助定位，不替代全文）: " + " | ".join(hints))
    L.append("")

    # ②-A 特性层命中
    L.append("## ② 配置范式")
    L.append("### ②-A 特性层命中")
    if not hits:
        L.append("- (特性层无命中——该命令未被任何特性文档实际使用)")
    else:
        for i, h in enumerate(hits, 1):
            L.append(f"#### 特性 {i}: {h['feature_code']}")
            L.append(f"**md: {h['path']}**")
            if h.get("template_of"):
                L.append(f"- ⚠ 数据规划模板复用：与 {h['template_of']} 同指纹，此处省略，详见该特性段")
            elif h["data_plan_rows"]:
                L.append("- 数据规划表行:")
                L.append("")
                for row in h["data_plan_rows"]:
                    L.append(f"  {row}")
                L.append("")
            if h["task_examples"]:
                L.append("- 任务示例脚本:")
                L.append("")
                for ex in h["task_examples"]:
                    L.append(f"  `{ex}`")
                L.append("")
            if h["step_contexts"]:
                L.append("- 操作步骤上下文（±2 行）:")
                for ctx in h["step_contexts"]:
                    L.append(f"  L{ctx['start_line']}-{ctx['end_line']}:")
                    for ln in ctx["context"].split("\n"):
                        L.append(f"    > {ln}")
                    L.append("")
            L.append("")

    # ②-B 原始产品文档命中
    L.append("### ②-B 原始产品文档命中（业务专题/网络部署，端到端方案与部署配置样例）")
    if doc_root is None:
        L.append("- (未启用原始文档检索；加 `--doc-root` 启用，可显著丰富配置样例)")
    elif not raw_hits:
        L.append("- (原始产品文档无命中)")
    else:
        for i, h in enumerate(raw_hits, 1):
            L.append(f"#### 原始文档 {i}: [{h['group']}] {h['path']}")
            if h["data_plan_rows"]:
                L.append("- 数据规划表行:")
                L.append("")
                for row in h["data_plan_rows"]:
                    L.append(f"  {row}")
                L.append("")
            if h["task_examples"]:
                L.append("- 任务示例脚本:")
                L.append("")
                for ex in h["task_examples"]:
                    L.append(f"  `{ex}`")
                L.append("")
            if h["step_contexts"]:
                L.append("- 操作步骤上下文（±2 行）:")
                for ctx in h["step_contexts"]:
                    L.append(f"  L{ctx['start_line']}-{ctx['end_line']}:")
                    for ln in ctx["context"].split("\n"):
                        L.append(f"    > {ln}")
                    L.append("")
            L.append("")

    # ③ 差异汇总
    L.append("## ③ 配置方法差异汇总（自动派生 → DP 线索；特性层 + 原始文档合并）")
    if param_counter:
        L.append("| 维度（参数） | 取值分布 |")
        L.append("|---|---|")
        for param, c in sorted(param_counter.items()):
            dist = ", ".join(f"{v} ×{n}" for v, n in c.most_common())
            L.append(f"| {param} | {dist} |")
    else:
        L.append("- (无数据规划行可汇总)")
    L.append("")

    # ④ 数据源
    L.append("## ④ 数据源")
    L.append(f"- 命令真相（① 全文）: {truth['path']}")
    L.append(f"- 特性层（②-A）: Feature/{nf}/{ver}/ 全树（{len(load_feature_docs(storage, nf, ver))} 个特性子文档）")
    if doc_root is not None:
        raw_dirs = discover_raw_dirs(doc_root, raw_names)
        L.append(f"- 原始产品文档（②-B）: {doc_root} 下语义目录 {raw_names}（发现 {len(raw_dirs)} 个目录，"
                 f"{len(load_raw_docs(doc_root, raw_names))} 个 md）")
    L.append(f"- 工具: collect_command_examples.py --nf {nf} --version {ver} --cmd \"{cmd}\""
             + (f" --doc-root {doc_root}" if doc_root else " --no-raw"))
    L.append("")

    return "\n".join(L), len(hits), len(raw_hits)


# ---------- CLI ----------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--nf", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--storage", default=DEFAULT_STORAGE, help=f"资产根（默认 {DEFAULT_STORAGE}）")
    ap.add_argument("--cmd", action="append", type=validate_command_name,
                    help="命令全名（可重复传入，批量时共享预读与倒排索引）")
    ap.add_argument("--all", action="store_true", help="全量：扫命令层资产发现所有命令")
    ap.add_argument("--limit", type=int, help="限制命令数（测试用）")
    ap.add_argument("--dry-run", action="store_true", help="干跑（只统计命中，不写）")
    ap.add_argument("--skip-existing", action="store_true", default=True, help="跳过已存在汇总（增量，默认开）")
    ap.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    ap.add_argument("--refresh", action="store_true",
                    help="以当前采集规则重建已有 atom-input（等价 --no-skip-existing）")
    ap.add_argument("--doc-root", help="原始产品文档根目录（如 output/UDG_Product_Documentation_CH_20.15.2）。"
                                       "启用后扫其中的业务专题/网络部署语义目录，丰富配置样例")
    ap.add_argument("--raw-dirs", help=f"覆盖默认语义目录名清单（逗号分隔，默认 {'/'.join(RAW_DOC_DIR_NAMES)}）")
    ap.add_argument("--no-raw", action="store_true", help="关闭原始文档检索（等价旧行为，只扫特性层）")
    ap.add_argument("--skip-built", action="store_true", default=True,
                    help="跳过已建 AtomTask 的命令（中间态只给待建缺口生成，默认开）")
    ap.add_argument("--no-skip-built", dest="skip_built", action="store_false",
                    help="不跳过已建 AtomTask（含已建命令也生成中间态，用于重建/全量统计）")
    args = ap.parse_args()

    if not args.cmd and not args.all:
        ap.error("需指定 --cmd 或 --all")
    if args.refresh:
        args.skip_existing = False

    # 解析原始文档检索配置
    raw_names = list(RAW_DOC_DIR_NAMES)
    if args.raw_dirs:
        raw_names = [s.strip() for s in args.raw_dirs.split(",") if s.strip()]
    doc_root = doc_root_path(args.doc_root) if args.doc_root else None
    use_raw = (not args.no_raw) and doc_root is not None and doc_root.exists()
    if args.doc_root and not use_raw:
        print(f"[WARN] --doc-root 无效或不存在: {doc_root}，本次仅扫特性层")
    feature_index: dict[str, list[int]] | None = None
    raw_index: dict[str, list[int]] | None = None

    def _prepare_raw_sources() -> None:
        """仅在确有待处理命令时加载原始文档，避免零增量时扫描整棵产品目录。"""
        if use_raw:
            found = discover_raw_dirs(doc_root, raw_names)  # type: ignore[arg-type]
            print(f"[INFO] 原始文档检索: doc-root={doc_root} | 语义目录 {raw_names} "
                  f"→ 发现 {len(found)} 个目录: {[_rel_to(d, doc_root) for d, _ in found]}")
            print(f"[INFO] 原始文档预读: {len(load_raw_docs(doc_root, raw_names))} 个 md 已缓存")  # type: ignore[arg-type]
        elif not args.no_raw and not args.doc_root:
            print("[INFO] 未传 --doc-root，仅扫特性层（传 --doc-root 启用原始文档检索，可显著丰富配置样例）")

    def _agg(cmd_name: str) -> tuple[str, int, int]:
        return aggregate_for_command(
            args.storage, args.nf, args.version, cmd_name, REPO,
            doc_root=doc_root if use_raw else None, raw_names=raw_names,
            feature_index=feature_index, raw_index=raw_index)

    if args.cmd:
        _prepare_raw_sources()
        requested = list(dict.fromkeys(args.cmd))
        if len(requested) > 1:
            feature_docs = load_feature_docs(args.storage, args.nf, args.version)
            feature_index = build_command_index(feature_docs, set(requested))
            if use_raw:
                raw_index = build_command_index(load_raw_docs(doc_root, raw_names), set(requested))  # type: ignore[arg-type]
            print(f"[INFO] 批量命令 {len(requested)} 条 | 特性候选 {len(feature_index)} | "
                  f"原始候选 {len(raw_index or {})}")
        for command in requested:
            md, fhits, rhits = _agg(command)
            out = output_path(args.storage, args.nf, args.version, command)
            if args.dry_run:
                print(f"[DRY-RUN] {command:25s} | 命中 {fhits}特性+{rhits}原始 | {out.relative_to(REPO)}")
                if len(requested) == 1:
                    print("--- 前 40 行预览 ---")
                    print("\n".join(md.split("\n")[:40]))
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(md, encoding="utf-8")
                print(f"[WRITE] {out.relative_to(REPO)} | 命中 {fhits}特性+{rhits}原始")
        return 0

    # 全量
    cmds = discover_commands(args.storage, args.nf, args.version)
    if not cmds:
        sys.exit(f"未发现命令层资产: {command_dir(args.storage, args.nf, args.version)}")
    print(f"[INFO] 命令层资产: {len(cmds)} 条命令")

    keys = sorted(cmds.keys())
    if args.limit:
        keys = keys[: args.limit]
        print(f"[INFO] --limit {args.limit}，仅处理前 {len(keys)} 条")

    written = nohit = failed = 0
    built_skipped = skipped = 0
    pending: list[str] = []
    for cmd in keys:
        if args.skip_built and atomtask_exists(args.storage, args.nf, args.version, cmd):
            built_skipped += 1
            continue
        out = output_path(args.storage, args.nf, args.version, cmd)
        if args.skip_existing and not args.dry_run and out.exists():
            skipped += 1
            continue
        pending.append(cmd)
    if not pending:
        print(f"[DONE] 无待处理命令 | 跳过已建atom {built_skipped} | 跳过已存在 {skipped} | 总 {len(keys)}")
        return 0

    _prepare_raw_sources()
    feature_docs = load_feature_docs(args.storage, args.nf, args.version)
    print(f"[INFO] 特性层资产预读: {len(feature_docs)} 个子文档已缓存")
    # 仅为待处理集合建索引，避免零/少量增量时支付全量后续处理成本。
    pending_set = set(pending)
    feature_index = build_command_index(feature_docs, pending_set)
    print(f"[INFO] 特性层倒排索引: {len(feature_index)} 个待处理命令有候选文档")
    if use_raw:
        raw_index = build_command_index(load_raw_docs(doc_root, raw_names), pending_set)  # type: ignore[arg-type]
        print(f"[INFO] 原始文档倒排索引: {len(raw_index)} 个待处理命令有候选文档")

    nohit_list: list[str] = []
    for i, cmd in enumerate(pending, 1):
        # 倒排索引预判：特性+原始都无候选 → 直接 no-hit，不 aggregate（省去读命令md/extract/拼装）
        if feature_index is not None:
            has_candidate = bool(feature_index.get(cmd)) or bool(raw_index and raw_index.get(cmd))
            if not has_candidate:
                nohit += 1
                nohit_list.append(cmd)
                if i <= 20 or i % 500 == 0:
                    print(f"  {i:5d}/{len(keys)} {cmd:30s} | 命中   0 (no-hit, 索引预判)")
                continue
        out = output_path(args.storage, args.nf, args.version, cmd)
        try:
            md, fhits, rhits = _agg(cmd)
        except Exception as e:  # noqa: BLE001
            failed += 1
            if i <= 20 or i % 200 == 0:
                print(f"  [FAIL] {cmd:30s} | {e}")
            continue
        if fhits == 0 and rhits == 0:
            nohit += 1
            nohit_list.append(cmd)
            if i <= 20 or i % 500 == 0:
                print(f"  {i:5d}/{len(keys)} {cmd:30s} | 命中   0 (no-hit)")
            continue
        if args.dry_run:
            if i <= 20 or i % 200 == 0:
                print(f"  {i:5d}/{len(keys)} {cmd:30s} | 命中 {fhits:3d}特性+{rhits:3d}原始")
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(md, encoding="utf-8")
            written += 1
            if i <= 20 or i % 200 == 0:
                print(f"  {i:5d}/{len(keys)} {cmd:30s} | 命中 {fhits:3d}特性+{rhits:3d}原始 | WRITE")

    if nohit_list and not args.dry_run:
        nh = REPO / NOHIT_TPL.format(storage=args.storage, nf=args.nf)
        nh.parent.mkdir(parents=True, exist_ok=True)
        nh.write_text(
            f"# {args.nf} {args.version} 无命中命令（{len(nohit_list)} 条，扫描于 "
            f"{datetime.now().isoformat(timespec='seconds')}）→ atom 走 SKILL A.2 第二类\n"
            + "\n".join(nohit_list) + "\n",
            encoding="utf-8",
        )
    print(f"\n[DONE] 写入 {written} | 跳过已建atom {built_skipped} | 跳过已存在 {skipped} | 无命中 {nohit} | 失败 {failed} | 总 {len(keys)}")
    if nohit_list:
        print(f"[NO-HIT] {len(nohit_list)} 条命令无配置示例（特性层+原始文档均无）→ atom 直接读命令层 md 梳理")
    return 0


if __name__ == "__main__":
    sys.exit(main())
