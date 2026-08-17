#!/usr/bin/env python3
"""collect_command_examples 的命令引用识别回归测试。"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("collect_command_examples.py")
SPEC = importlib.util.spec_from_file_location("collect_command_examples", SCRIPT)
assert SPEC and SPEC.loader
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class CommandReferenceRecognitionTests(unittest.TestCase):
    """Feature 文档的真实 MML 链接格式必须进入 Atom 输入采集。"""

    def test_indexes_wikilink_command_in_data_plan_last_column(self) -> None:
        command = "ADD QOSIFTRUST"
        docs = [{
            "text": (
                "| QOSIFTRUST接口绑定DS域 | DS域名（DSNAME） | ds1 | 本端规划 | "
                "[[UNC@MMLCommand@ADD QOSIFTRUST]] |\n"
            )
        }]

        self.assertEqual(collector.build_command_index(docs, {command}), {command: [0]})

    def test_extracts_wikilink_data_plan_row_regardless_of_column(self) -> None:
        command = "ADD ACLRULEBAS4"
        text = (
            "| 增加基本ACL规则 | 源IP地址（ACLSOURCEIP） | 10.1.2.2 | 全网规划 | "
            "[[UNC@MMLCommand@ADD ACLRULEBAS4]] |\n"
        )

        signals = collector.detect_signals(text, command)
        self.assertTrue(signals["data_plan"])
        self.assertEqual(collector.extract_data_plan_rows(text, command), [text.rstrip()])

    def test_extracts_wikilink_command_script(self) -> None:
        command = "SET PKICRLCHECK"
        text = "[[UNC@MMLCommand@SET PKICRLCHECK]] : ISCRLENABLE=TRUE;\n"

        signals = collector.detect_signals(text, command)
        self.assertTrue(signals["task_example"])
        self.assertEqual(collector.extract_task_examples(text, command), [text.rstrip()])

    def test_extracts_multiline_command_script(self) -> None:
        command = "RMV DRCOMM"
        text = "RMV DRCOMM: DRINSTID=\n1, IPVERSION=COMM_IPV4;\n"

        signals = collector.detect_signals(text, command)
        self.assertTrue(signals["task_example"])
        self.assertEqual(collector.extract_task_examples(text, command), [text.rstrip()])

    def test_extracts_bold_wikilink_command_script(self) -> None:
        command = "RMV SQOSCAR"
        text = '**[[UNC@MMLCommand@RMV SQOSCAR]]** : BEHAVIORNAME="flow";\n'

        signals = collector.detect_signals(text, command)
        self.assertTrue(signals["task_example"])
        self.assertEqual(collector.extract_task_examples(text, command), [text.rstrip()])


if __name__ == "__main__":
    unittest.main()
