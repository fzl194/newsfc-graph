import os
from pathlib import Path

# 资产库根（可用 GAP_DATA_DIR 环境变量覆盖，e2e/多实例部署用）。默认 ./platform-data
DATA_DIR = Path(os.environ.get("GAP_DATA_DIR",
                               str(Path(__file__).resolve().parents[2] / "platform-data")))
ASSETS_DIR = DATA_DIR / "assets"
# 原始产品文档导出 md（「上传产品文档」留存；**不进 DB/图谱**，前端只读浏览）。
# 与 assets 同级而非其内——store.list_md 会 rglob 全部 md，放 assets 下会被索引进图谱。
OUTPUT_DIR = DATA_DIR / "output"
TESTS_DIR = DATA_DIR / "tests"  # 测试用例管理子系统（独立于 assets，隔离）
DB_PATH = DATA_DIR / "platform.db"  # SQLite 持久化（索引 + 用户 + 打点 + tests + trash）
TRASH_DIR = DATA_DIR / ".trash"  # 回收站（软删除）：assets 同级，绝不能放进 assets 内（list_md rglob 会扫回）
DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent / "default_registry.yaml"

# —— 运营打点（按 level 分文件：object 少/统计用，request 多/轨迹用）——
TELEMETRY_DIR = DATA_DIR / "telemetry"
TELEMETRY_OBJECTS_FILE = TELEMETRY_DIR / "objects.jsonl"
TELEMETRY_REQUESTS_FILE = TELEMETRY_DIR / "requests.jsonl"

# —— 用户体系（多用户，明文 KEY，不入 git）——
USERS_FILE = DATA_DIR / "users.json"
