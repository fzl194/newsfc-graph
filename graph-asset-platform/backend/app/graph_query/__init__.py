"""图谱查询共享核心包（2026-09-08 三工具重构）。

MCP 工具与 REST /domains、/md 的业务实现唯一来源（需求 §4/§10）：
- contracts：错误模型/错误码、输入输出 Pydantic 模型、护栏常量；
- read：get_domains_core / get_md_core / 全文引用提取；
- catalog（M2）：动态 filter 合法值；
- search（M2）：统一搜索 search_graph_core。
"""
