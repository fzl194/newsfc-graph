#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for CompoundTask edge-section validation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("audit_compound_feature.py")
NF = "UDG"
FEATURE_VERSION = "20.15.2"
FEATURE_CODE = "GWFD-000001"


class CompoundEdgeSectionAuditTests(unittest.TestCase):
    def run_audit(self, edge_heading: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            atom_dir = root / "AtomTask" / NF
            compound_dir = root / "CompoundTask" / NF
            feature_task_dir = root / "FeatureTask" / NF
            feature_dir = root / "Feature" / NF / FEATURE_VERSION
            for directory in (atom_dir, compound_dir, feature_task_dir, feature_dir):
                directory.mkdir(parents=True)

            (atom_dir / f"{NF}@AtomTask@ADD SAMPLE.md").write_text("# atom\n", encoding="utf-8")
            (feature_dir / "_build_manifest.json").write_text(
                json.dumps({"docs": [f"{NF}@Feature@{FEATURE_CODE}"]}), encoding="utf-8"
            )
            (compound_dir / f"{NF}@CompoundTask@sample-step.md").write_text(
                f"""---
command_set: [\"ADD SAMPLE\"]
status: \"draft\"
---
# sample
{edge_heading}
- 组成: [[{NF}@AtomTask@ADD SAMPLE]]
- 被引用于: [[{NF}@FeatureTask@{FEATURE_CODE}]]
""",
                encoding="utf-8",
            )
            (feature_task_dir / f"{NF}@FeatureTask@{FEATURE_CODE}.md").write_text(
                f"""---
ref: \"{NF}@Feature@{FEATURE_CODE}\"
---
# feature task
## 边
- 对应特性: [[{NF}@Feature@{FEATURE_CODE}]]
- 编排: [[{NF}@CompoundTask@sample-step]]
""",
                encoding="utf-8",
            )
            environment = {**os.environ, "SFC_ASSET_ROOT": str(root)}
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--nf", NF],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
            )

    def test_rejects_edge_heading_joined_to_prior_text(self) -> None:
        result = self.run_audit("partial constraint## 边")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("边段标题非独立", result.stdout)

    def test_accepts_standalone_edge_heading(self) -> None:
        result = self.run_audit("## 边")

        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
