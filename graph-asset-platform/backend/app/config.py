import os
from pathlib import Path


def win_long(path: Path) -> Path:
    """Windows 上把绝对路径转为 ``\\\\?\\`` 前缀形式，突破 MAX_PATH(260) 限制。

    供**纯文件系统调用**（mkdir/write/copy2/move/rmtree/**枚举 rglob/walk**——
    普通路径对 >260 条目不报错而是静默漏扫）使用；返回值勿用于相对路径计算
    或链接映射（``os.path.relpath`` 对 ``\\\\?\\`` 前缀会算错）。
    非 Windows 或已是 ``\\\\?\\`` 前缀时原样返回；UNC（``\\\\server\\share``）
    转 ``\\\\?\\UNC\\server\\share`` 形式（直接拼 ``\\\\?\\`` 是非法路径）。
    """
    if os.name != "nt":
        return path
    s = str(path)
    if s.startswith("\\\\?\\"):
        return path
    p = os.path.abspath(s)
    if p.startswith("\\\\"):  # UNC 网络路径（GAP_DATA_DIR 挂网络盘场景）
        return Path("\\\\?\\UNC\\" + p[2:])
    return Path("\\\\?\\" + p)


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
