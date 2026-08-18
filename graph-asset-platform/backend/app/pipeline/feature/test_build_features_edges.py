#!/usr/bin/env python3
"""特性层边提取回归测试（v0.21.0：依赖特性全文锚定 + 使用命令边 + License 校验）。

覆盖：全文码扫描（含 md 互链 URL 中的码）、代码块/TOC/自身排除、悬空过滤、
使用命令子文档各自建、License 码集工具。
"""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

HERE = Path(__file__).parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


common = _load("_common")
features = _load("build_features")

FC_RE = common.FEATURE_CODE_RE
LKV_RE = common.LICENSE_CODE_RE


class ScanCodesTests(unittest.TestCase):
    """scan_codes：全文锚定 + 排除项。"""

    def test_plain_text_code(self) -> None:
        md = "详细信息请参见 GWFD-020421 基于位置的地址分配。"
        self.assertEqual(common.scan_codes(md, FC_RE), {"GWFD-020421"})

    def test_md_hyperlink_url_code(self) -> None:
        md = "请仔细阅读 [GWFD-020421 基于位置的地址分配](../../../基本接入功能/GWFD-020421 基于位置的地址分配_02846765.md) 。"
        self.assertEqual(common.scan_codes(md, FC_RE), {"GWFD-020421"})

    def test_code_block_excluded(self) -> None:
        md = "```\nGWFD-020421\n```"
        self.assertEqual(common.scan_codes(md, FC_RE), set())

    def test_toc_line_excluded(self) -> None:
        md = "- [GWFD-020421 概述](#ZH-CN_xxx)"
        self.assertEqual(common.scan_codes(md, FC_RE), set())

    def test_self_code_excluded(self) -> None:
        md = "# GWFD-020404 IPv6在线计费\n\n本特性（GWFD-020404）与 GWFD-020300 原理一致。"
        self.assertEqual(common.scan_codes(md, FC_RE, exclude="GWFD-020404"), {"GWFD-020300"})


class OverviewEdgesTests(unittest.TestCase):
    """build_overview_edges：聚合 + 校验后集合直接落边。"""

    def test_dep_license_include_composition(self) -> None:
        edges = features.build_overview_edges(
            "UDG", "GWFD-020404",
            sibling_ids=["UDG@Feature@GWFD-020404-实现原理"],
            dep_codes={"GWFD-020300"}, lic_codes={"LKVA1234567"})
        rels = [(rel, tgt) for rel, tgt in edges]
        self.assertIn(("依赖特性", "UDG@Feature@GWFD-020300"), rels)
        self.assertIn(("所需License", "UDG@License@LKVA1234567"), rels)
        self.assertIn(("包含子文档", "UDG@Feature@GWFD-020404-实现原理"), rels)

    def test_validated_sets_are_caller_responsibility(self) -> None:
        # 调用方负责悬空过滤（cand ∩ 合法集）；本函数不再二次判断
        edges = features.build_overview_edges(
            "UDG", "GWFD-020404", sibling_ids=[], dep_codes=set(), lic_codes=set())
        self.assertEqual([rel for rel, _ in edges], [])


class UseCommandEdgeTests(unittest.TestCase):
    """rewrite_doc_refs 返回 cmd_targets → 子文档各自建「使用命令」边。"""

    def test_cmd_targets_collected(self) -> None:
        md = "配置参见 [增加URR（ADD URR）](增加URR（ADD URR）_001.md) 与 LST ACLGROUP。"
        _new_md, stats = common.rewrite_doc_refs(
            md, "UDG", {"ADD URR", "LST ACLGROUP"}, set(), None)
        self.assertEqual(stats["cmd_targets"], ["ADD URR"])

    def test_bare_label_command_resolved(self) -> None:
        md = "执行 [LST ACLGROUP](xxx.md) 查看。"
        _new_md, stats = common.rewrite_doc_refs(md, "UDG", {"LST ACLGROUP"}, set(), None)
        self.assertEqual(stats["cmd_targets"], ["LST ACLGROUP"])

    def test_unknown_command_not_in_targets(self) -> None:
        md = "参见 [增加XX（ADD NOPE）](x.md)。"
        _new_md, stats = common.rewrite_doc_refs(md, "UDG", {"ADD URR"}, set(), None)
        self.assertEqual(stats["cmd_targets"], [])

    def test_duplicate_targets_deduped_in_targets(self) -> None:
        md = "见 [A（ADD URR）](a.md) 与 [B（ADD URR）](b.md)。"
        _new_md, stats = common.rewrite_doc_refs(md, "UDG", {"ADD URR"}, set(), None)
        self.assertEqual(stats["cmd_targets"], ["ADD URR"])


class LicenseCodesTests(unittest.TestCase):
    """License 码集/源组码工具。"""

    def test_license_codes_regex(self) -> None:
        self.assertEqual(common.parse_license_codes("LKV100001 与 LKV2000022，重复 LKV100001"),
                         ["LKV100001", "LKV2000022"])

    def test_group_feature_codes_by_deepest(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "A功能" / "GWFD-010101 A").mkdir(parents=True)
            (root / "A功能" / "GWFD-010101 A" / "GWFD-010101 A特性概述_1.md").write_text("x", encoding="utf-8")
            (root / "A功能" / "GWFD-010101 A" / "实现原理_2.md").write_text("x", encoding="utf-8")
            (root / "孤儿.md").write_text("x", encoding="utf-8")
            self.assertEqual(common.group_feature_codes(root), {"GWFD-010101"})


if __name__ == "__main__":
    unittest.main()
