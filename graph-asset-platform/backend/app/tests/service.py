"""测试子系统单例 Service + 写入锁。

``get_test_service`` 延迟构造；写审查（写盘）+ rebuild 必须串行化（``test_lock``），
独立于图谱 ``import_lock``，互不干扰。
"""
import threading
from typing import Optional

from ..config import TESTS_DIR
from ..db import get_shared_db
from .index import TestIndex
from .store import TestStore

# 模块级写入锁（独立于图谱 service.import_lock）
test_lock = threading.Lock()


class TestService:
    def __init__(self):
        self.store = TestStore(TESTS_DIR)
        self.db = get_shared_db()
        self._refresh()  # migrate_tests + load_from_db

    def _refresh(self) -> None:
        """全量扫 tests md → test_* 表 → 内存（tests 数据少，全量可接受）。"""
        from ..migrate import migrate_tests
        migrate_tests(self.db, self.store)
        self.index = TestIndex.load_from_db(self.db)

    def rebuild(self) -> None:
        """写盘后重建（写操作调用；migrate + load）。"""
        self._refresh()


_test_service: Optional[TestService] = None


def get_test_service() -> TestService:
    global _test_service
    if _test_service is None:
        _test_service = TestService()
    return _test_service
