#!/usr/bin/env python3
"""Feature 配置命令到同 NF AtomTask 覆盖审计的回归测试。"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("audit_feature_atom_coverage.py")
SPEC = importlib.util.spec_from_file_location("audit_feature_atom_coverage", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class FeatureAtomCoverageTests(unittest.TestCase):
    def test_reports_only_same_nf_missing_config_atoms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = Path(temp_dir) / "assets"
            command_dir = storage / "Command" / "UNC" / "20.15.2"
            feature_dir = storage / "Feature" / "UNC" / "20.15.2" / "UNC@Feature@IPFD-012001"
            atom_dir = storage / "AtomTask" / "UNC"
            command_dir.mkdir(parents=True)
            feature_dir.mkdir(parents=True)
            atom_dir.mkdir(parents=True)

            for command in (
                "ADD PRESENT", "ADD MISSING", "ADD PROSE_ONLY", "MOD SCRIPT_ONLY", "MOD BOLD_SCRIPT",
                "STR EPHEMERAL", "LST QUERY",
            ):
                (command_dir / f"UNC@MMLCommand@{command}.md").write_text("# command\n", encoding="utf-8")
            (atom_dir / "UNC@AtomTask@ADD PRESENT.md").write_text("# atom\n", encoding="utf-8")
            (feature_dir / "概述.md").write_text(
                "协议原理参见 [[UNC@MMLCommand@ADD PROSE_ONLY]]。\n",
                encoding="utf-8",
            )
            (feature_dir / "创建示例.md").write_text(
                "| 参数 | 取值 | 相关命令 |\n"
                "|---|---|---|\n"
                "| 名称 | demo | [[UNC@MMLCommand@ADD PRESENT]] |\n"
                "| 规则 | permit | [[UNC@MMLCommand@ADD MISSING]] |\n"
                "MOD SCRIPT_ONLY: SWITCH=TRUE;\n"
                "**[[UNC@MMLCommand@MOD BOLD_SCRIPT]]** : SWITCH=TRUE;\n"
                "STR EPHEMERAL: SWITCH=TRUE;\n"
                "[[UNC@MMLCommand@LST QUERY]]\n"
                "[[UDG@MMLCommand@ADD OTHER_NF]]\n",
                encoding="utf-8",
            )

            report = audit.collect_feature_atom_coverage(str(storage), "UNC", "20.15.2")

            self.assertEqual(report["config_command_count"], 4)
            self.assertEqual(report["covered_count"], 1)
            self.assertEqual(set(report["missing"]), {"ADD MISSING", "MOD SCRIPT_ONLY", "MOD BOLD_SCRIPT"})
            self.assertEqual(report["missing"]["ADD MISSING"][0]["feature_code"], "IPFD-012001")

    def test_includes_str_only_when_explicitly_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = Path(temp_dir) / "assets"
            command_dir = storage / "Command" / "UNC" / "20.15.2"
            feature_dir = storage / "Feature" / "UNC" / "20.15.2" / "UNC@Feature@IPFD-012002"
            command_dir.mkdir(parents=True)
            feature_dir.mkdir(parents=True)
            (command_dir / "UNC@MMLCommand@STR PERSISTENT.md").write_text("# command\n", encoding="utf-8")
            (feature_dir / "配置.md").write_text("STR PERSISTENT: SWITCH=TRUE;\n", encoding="utf-8")

            default_report = audit.collect_feature_atom_coverage(str(storage), "UNC", "20.15.2")
            str_report = audit.collect_feature_atom_coverage(
                str(storage), "UNC", "20.15.2", include_str=True,
            )

            self.assertEqual(default_report["config_command_count"], 0)
            self.assertEqual(set(str_report["missing"]), {"STR PERSISTENT"})


if __name__ == "__main__":
    unittest.main()
