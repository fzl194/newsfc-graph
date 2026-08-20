#!/usr/bin/env python3
"""read_text_auto 编码判定回归测试（v0.24.0：确定性判据优先，chardet 兜底）。

覆盖真实产品文档的四种形态。核心回归点：无 BOM 的 UTF-8 文本（旧实现被
chardet 误判 GBK 族 → 整文件乱码的场景）必须直接命中 utf-8 严格解码。
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("product_doc_md_exporter_optimized.py")
SPEC = importlib.util.spec_from_file_location("exporter_enc", SCRIPT)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = exporter  # @dataclass 按 __module__ 查 sys.modules，必须注册
SPEC.loader.exec_module(exporter)

CN = "增加NITZ策略命令功能说明：移动性管理参数"


class ReadTextAutoTests(unittest.TestCase):
    def _write(self, data: bytes, suffix: str = ".html") -> Path:
        f = self.td / f"case{suffix}"
        f.write_bytes(data)
        return f

    def setUp(self) -> None:
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_utf8_no_bom(self) -> None:
        """无 BOM UTF-8（乱码 bug 主场景）：必须 utf-8 严格命中，不进 chardet。"""
        p = self._write(f"<html><body>{CN}</body></html>".encode("utf-8"))
        self.assertEqual(exporter.read_text_auto(str(p)), f"<html><body>{CN}</body></html>")

    def test_utf8_bom(self) -> None:
        p = self._write(b"\xef\xbb\xbf" + CN.encode("utf-8"))
        self.assertEqual(exporter.read_text_auto(str(p)), CN)

    def test_utf16_bom(self) -> None:
        p = self._write(b"\xff\xfe" + CN.encode("utf-16-le"))
        self.assertEqual(exporter.read_text_auto(str(p)), CN)

    def test_gbk_with_meta(self) -> None:
        html = f'<html><head><meta charset="gb2312"></head><body>{CN}</body></html>'
        p = self._write(html.encode("gb18030"))
        self.assertEqual(exporter.read_text_auto(str(p)),
                         f'<html><head><meta charset="gb2312"></head><body>{CN}</body></html>')

    def test_gbk_no_meta_falls_back(self) -> None:
        """无声明 GBK：utf-8 严格失败 → meta 无 → chardet/序贯兜底命中。"""
        p = self._write(CN.encode("gb18030"), suffix=".txt")
        self.assertEqual(exporter.read_text_auto(str(p)), CN)


if __name__ == "__main__":
    unittest.main()
