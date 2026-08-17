"""数据访问层（repos）：纯函数模块，接 sqlite3 连接，无业务逻辑。

- objects_repo / edges_repo：图谱索引
- users_repo / telemetry_repo / tests_repo：分别在阶段 4/5/6 加入
"""
from . import objects_repo, edges_repo, users_repo, telemetry_repo, tests_repo  # noqa: F401
