#!/usr/bin/env python3
"""审计 Feature 文档实际配置命令是否有同 NF 的 AtomTask。

这是 Atom Part A 与 Task Part B 之间的覆盖门禁：扫描 Feature 文档中的
数据规划表中的 ``[[{nf}@MMLCommand@CMD]]`` 及实际脚本行，筛选配置类命令，
再与 AtomTask 同 NF 文件名比对。普通原理/参考链接不构成配置证据。
默认只读；可选 ``--output`` 写 JSON 报告，``--strict`` 在有缺口时返回 1。
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
CONFIG_VERBS = frozenset({"ADD", "MOD", "SET", "DEL", "RMV", "LOD"})
COMMAND_FILE_RE = re.compile(r"^(?P<nf>[^@]+)@MMLCommand@(?P<cmd>.+)\.md$")
FEATURE_DIR_RE = re.compile(r"^[^@]+@Feature@(?P<code>[A-Z]+FD-\d+)")
SCRIPT_COMMAND_RE = re.compile(
    r"^\s*`?\s*([A-Z][A-Z0-9]{1,}(?:[ \t]+[A-Za-z0-9_/+.-]+)*):")
LINKED_SCRIPT_RE = re.compile(
    r"(?:\*\*)?\[\[(?P<nf>[^@\]\n]+)@MMLCommand@(?P<cmd>[^\]\n]+)\]\](?:\*\*)?\s*:")
WIKILINK_RE = re.compile(r"\[\[(?P<nf>[^@\]\n]+)@MMLCommand@(?P<cmd>[^\]\n]+)\]\]")


def storage_root(storage: str) -> Path:
    path = Path(storage)
    return path if path.is_absolute() else REPO / path


def feature_code_of(path: Path) -> str | None:
    for part in path.parts:
        match = FEATURE_DIR_RE.match(part)
        if match:
            return match.group("code")
    return None


def command_names(storage: Path, nf: str, version: str) -> set[str]:
    base = storage / "Command" / nf / version
    names: set[str] = set()
    for path in base.glob("*.md") if base.exists() else []:
        match = COMMAND_FILE_RE.match(path.name)
        if match and match.group("nf") == nf:
            names.add(match.group("cmd"))
    return names


def atom_exists(storage: Path, nf: str, version: str, command: str) -> bool:
    """AtomTask 无版本（v0.19.0）：路径 {storage}/AtomTask/{nf}/。version 仅保留签名兼容。"""
    return (storage / "AtomTask" / nf / f"{nf}@AtomTask@{command}.md").exists()


def is_config_command(command: str, include_str: bool) -> bool:
    """仅纳入 SOP 要求的配置命令；STR 需先由人工确认是否持久化。"""
    verb = command.split(maxsplit=1)[0] if command else ""
    return verb in CONFIG_VERBS or (include_str and verb == "STR")


def config_evidence_on_line(line: str, nf: str) -> list[tuple[str, str]]:
    """返回该行的强配置证据 ``(命令, 证据类型)``。

    命令链接只有出现在 Markdown 表格行中才算数据规划；非表格链接必须带
    ``:`` 才算脚本。这排除了概述、原理和参考信息中的普通命令引用。
    """
    evidence: list[tuple[str, str]] = []
    stripped = line.strip()
    if stripped.startswith("|") and stripped.endswith("|"):
        evidence.extend((m.group("cmd").strip(), "data_plan") for m in WIKILINK_RE.finditer(line)
                        if m.group("nf") == nf)
    evidence.extend((m.group("cmd").strip(), "linked_script") for m in LINKED_SCRIPT_RE.finditer(line)
                    if m.group("nf") == nf)
    raw_script = SCRIPT_COMMAND_RE.match(line)
    if raw_script:
        evidence.append((raw_script.group(1).strip(), "script"))
    return list(dict.fromkeys(evidence))


def collect_feature_atom_coverage(
    storage: str,
    nf: str,
    version: str,
    scope: str = "all",
    include_str: bool = False,
) -> dict:
    """一次扫描 Feature 文档，返回配置命令到同 NF AtomTask 的覆盖真值。"""
    root = storage_root(storage)
    commands = command_names(root, nf, version)
    feature_base = root / "Feature" / nf / version
    references: dict[str, list[dict[str, object]]] = defaultdict(list)
    docs_scanned = 0
    for path in feature_base.rglob("*.md") if feature_base.exists() else []:
        feature_code = feature_code_of(path)
        if not feature_code:
            continue
        docs_scanned += 1
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, 1):
            for command, evidence_type in config_evidence_on_line(line, nf):
                if command not in commands or not is_config_command(command, include_str):
                    continue
                references[command].append({
                    "feature_code": feature_code,
                    "path": str(path.relative_to(root)),
                    "line": line_number,
                    "evidence": evidence_type,
                })

    covered = sorted(command for command in references if atom_exists(root, nf, version, command))
    missing = {
        command: references[command]
        for command in sorted(references)
        if command not in covered
    }
    return {
        "nf": nf,
        "version": version,
        "scope": scope,
        "include_str": include_str,
        "feature_documents_scanned": docs_scanned,
        "config_command_count": len(references),
        "covered_count": len(covered),
        "missing_count": len(missing),
        "covered": covered,
        "missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nf", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--storage", default="三层图谱资产")
    parser.add_argument("--scope", choices=("all",), default="all",
                        help="扫描全部 Feature 文档；配置资格由表格/脚本强证据判定")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", help="可选 JSON 输出文件；默认不写文件")
    parser.add_argument("--strict", action="store_true", help="发现缺 AtomTask 时返回 1")
    parser.add_argument("--include-str", action="store_true",
                        help="临时将 STR 也纳入；仅在已确认其为持久化配置后使用")
    args = parser.parse_args()

    report = collect_feature_atom_coverage(
        args.storage, args.nf, args.version, args.scope, include_str=args.include_str,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = (Path(args.output) if Path(args.output).is_absolute() else REPO / args.output).resolve()
        try:
            output.relative_to(REPO.resolve())
        except ValueError:
            parser.error("--output 必须位于仓库目录内")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")

    if args.format == "json":
        print(payload)
    else:
        print(
            f"Feature→Atom 覆盖 · {args.nf} {args.version} · scope={args.scope}\n"
            f"  Feature md={report['feature_documents_scanned']}  配置命令={report['config_command_count']}\n"
            f"  已覆盖={report['covered_count']}  缺 Atom={report['missing_count']}"
        )
        for command, locations in report["missing"].items():
            first = locations[0]
            print(f"  MISSING {command}  ← {first['feature_code']} {first['path']}:{first['line']}")

    return 1 if args.strict and report["missing_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
