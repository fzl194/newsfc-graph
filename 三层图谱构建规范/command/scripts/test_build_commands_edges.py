#!/usr/bin/env python3
"""edge_cmdref_body 全文锚定扫描的回归测试（v0.20.0 参见边重写）。

真实语料实证的 4 种引用模式（触发词/顿号串/md互链/裸文本）必须全部命中；
代码块、TOC、自身提及不建边；最长匹配与边界守卫防前缀误切。
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("build_commands.py")
SPEC = importlib.util.spec_from_file_location("build_commands", SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

NAMES = {
    "ADD CELLBINDGRP", "ADD IMSIBINDGRP", "ADD TOPOLICYCFG",
    "SET DNSINFO", "GEN DNSTASKID", "EXC DNSCFGTASK",
    "DSP DBGSTAT", "LST ACLGROUP", "LST ACLGROUP6", "ADD ZONE",
}
CTX = {"command_names": NAMES}


def refs(md: str, name: str) -> set[str]:
    edges = builder.edge_cmdref_body(md, name, "UDG", CTX)
    return {tgt.split("@")[-1] for rel, tgt in edges if rel == "参见"}


class TriggeredReferenceTests(unittest.TestCase):
    """旧触发词模式（v0.8.2 唯一来源）不能回归。"""

    def test_trigger_word_reference(self) -> None:
        md = "参数说明：参见LST ACLGROUP的参数说明。"
        self.assertEqual(refs(md, "ADD ZONE"), {"LST ACLGROUP"})

    def test_trigger_word_via(self) -> None:
        md = "通过SET DNSINFO命令完成初始化。"
        self.assertEqual(refs(md, "ADD ZONE"), {"SET DNSINFO"})


class BareTextReferenceTests(unittest.TestCase):
    """无触发词裸文本（参数说明/注意事项，2026-08-18 实测丢失大头）。"""

    def test_parameter_generated_by_command(self) -> None:
        md = "配置原则：该参数使用ADD CELLBINDGRP命令配置生成。 |"
        self.assertEqual(refs(md, "ADD ZONE"), {"ADD CELLBINDGRP"})

    def test_dunhao_command_chain(self) -> None:
        md = "- 在依次执行SET DNSINFO、GEN DNSTASKID、EXC DNSCFGTASK初始化MML命令后，可以开始使用ADD ZONE命令。"
        self.assertEqual(refs(md, "ADD ZONE"), {"SET DNSINFO", "GEN DNSTASKID", "EXC DNSCFGTASK"})

    def test_md_hyperlink_reference(self) -> None:
        md = "参见<br>**[DSP DBGSTAT](查询调试信息（DSP DBGSTAT）_29627109.md)**<br>输入参数补充说明。"
        self.assertEqual(refs(md, "ADD ZONE"), {"DSP DBGSTAT"})

    def test_reference_info_section_command(self) -> None:
        md = "可使用如下命令获取c16规格的Pod名称：DSP DBGSTAT: TYPE=byType;"
        self.assertEqual(refs(md, "ADD ZONE"), {"DSP DBGSTAT"})


class ExclusionTests(unittest.TestCase):
    """代码块 / TOC / 自身提及不建边。"""

    def test_code_block_excluded(self) -> None:
        md = "#### [使用实例]\n\n```\nSET DNSINFO: MODE=1;\nGEN DNSTASKID:;\n```"
        self.assertEqual(refs(md, "ADD ZONE"), set())

    def test_toc_line_excluded(self) -> None:
        md = "- [DSP DBGSTAT](#ZH-CN_CONCEPT_0000201106523902__1.3.1.1)"
        self.assertEqual(refs(md, "ADD ZONE"), set())

    def test_self_reference_excluded(self) -> None:
        md = "# 增加区域（ADD ZONE）\n\n该命令与ADD ZONE命令配合使用。"
        self.assertEqual(refs(md, "ADD ZONE"), set())


class MatcherPrecisionTests(unittest.TestCase):
    """最长匹配 + 边界守卫。"""

    def test_longest_match_wins(self) -> None:
        md = "参见LST ACLGROUP6的参数说明。"
        self.assertEqual(refs(md, "ADD ZONE"), {"LST ACLGROUP6"})

    def test_prefix_not_mismatched(self) -> None:
        # ADD CELLBINDGRPX 不是命令：既不能把 ADD CELLBINDGRP 误配出来，也不建边
        md = "该参数使用ADD CELLBINDGRPX命令配置生成。"
        self.assertEqual(refs(md, "ADD ZONE"), set())

    def test_unknown_command_no_edge(self) -> None:
        md = "参见ADD NOSUCHCMD的参数说明。"
        self.assertEqual(refs(md, "ADD ZONE"), set())

    def test_dedup_repeated_mentions(self) -> None:
        md = "受ADD CELLBINDGRP控制，且ADD CELLBINDGRP优先级更高。"
        edges = builder.edge_cmdref_body(md, "ADD ZONE", "UDG", CTX)
        self.assertEqual(len(edges), 1)


if __name__ == "__main__":
    unittest.main()
