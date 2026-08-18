"""产品文档导入 pipeline（.hwics → 图谱资产 + 原始 md 留存）。

脚本拷贝自《三层图谱构建规范》（权威），字节一致便于同步——见 README.md。
编排入口：``runner.run_product_doc_import``（由 routers/productdoc.py 后台调用）。
"""
