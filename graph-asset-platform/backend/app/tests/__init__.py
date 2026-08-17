"""测试用例管理子系统（数据飞轮·数据层）。

与图谱资产（app/store.py / app/index.py / app/service.py）**完全隔离**：
- 只读写 platform-data/tests/，绝不碰 platform-data/assets/。
- 不 import 任何图谱 app 代码（md 解析器在本包自备一份）。
- 独立索引、独立锁、独立 Service 单例。
"""
