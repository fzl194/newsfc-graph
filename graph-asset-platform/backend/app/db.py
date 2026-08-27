"""SQLite 持久化层：连接管理 + schema 初始化。

单文件 ``platform.db``，WAL 模式（读写并发），``foreign_keys=ON``（tests 级联删除）。
单连接 ``check_same_thread=False``，写事务由 ``service.import_lock`` / ``tests.test_lock``
保护（避免并发写触发 SQLite BUSY）。

迁移版本记在 ``meta.schema_version``，未来 schema 演进在此 bump + 加迁移逻辑。
"""
import sqlite3
from pathlib import Path

from .config import DB_PATH

SCHEMA_VERSION = "10"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS objects(
  id TEXT, version TEXT, type TEXT, layer TEXT, scope TEXT,
  nf TEXT, domain TEXT, scenario TEXT,
  source_path TEXT, name TEXT, frontmatter_json TEXT,
  body_md TEXT, raw_md TEXT, mtime REAL,
  PRIMARY KEY(id, version)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_objects_nf ON objects(nf);
CREATE INDEX IF NOT EXISTS idx_objects_type ON objects(type);
-- source_path 索引（v7，2026-08-25）：reindex_path 每文件 delete_by_source 原为
-- 全表扫（连带 body_md/raw_md 正文页）——批量增量索引 O(N²) 的主因之一
CREATE INDEX IF NOT EXISTS idx_objects_source ON objects(source_path);

CREATE TABLE IF NOT EXISTS edges(
  from_id TEXT, from_version TEXT, relation TEXT, "to" TEXT,
  PRIMARY KEY(from_id, from_version, relation, "to")
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges("to");

CREATE TABLE IF NOT EXISTS meta(
  key TEXT PRIMARY KEY, value TEXT
);

CREATE TABLE IF NOT EXISTS import_jobs(
  job_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
  nf TEXT DEFAULT '', version TEXT DEFAULT '',
  status TEXT NOT NULL, added INTEGER DEFAULT 0,
  updated INTEGER DEFAULT 0, skipped INTEGER DEFAULT 0,
  steps TEXT DEFAULT '[]', result TEXT DEFAULT '{}', warnings TEXT DEFAULT '[]',
  error TEXT DEFAULT '', started_at REAL NOT NULL, finished_at REAL DEFAULT 0,
  child_pids TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_import_jobs_started ON import_jobs(started_at);

CREATE TABLE IF NOT EXISTS users(
  username TEXT PRIMARY KEY, key TEXT,
  can_frontend INT, can_assets INT, can_upload INT, can_test INT, can_skill INT, is_admin INT,
  created_at TEXT
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS trash(
  id TEXT PRIMARY KEY, original_path TEXT, is_dir INT,
  md_count INT, deleted_at TEXT, deleted_by TEXT
);

CREATE TABLE IF NOT EXISTS telemetry(
  ts TEXT, level TEXT, caller TEXT, endpoint TEXT,
  obj_id TEXT, obj_type TEXT, user TEXT, operator TEXT,
  session_id TEXT DEFAULT '', params TEXT DEFAULT '', result TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tel_stats ON telemetry(level, caller, endpoint, ts);
CREATE INDEX IF NOT EXISTS idx_tel_user ON telemetry(user, level, ts);

-- 正文全文索引（MCP search_md，CR：MCP 服务化 2026-08-24）。trigram 分词：
-- 中英文统一子串语义，且 LIKE/GLOB 可走 trigram 索引（<3 字符查询的回退路径）。
-- 独立表（objects 是 WITHOUT ROWID，external-content 方案不适用）。
CREATE VIRTUAL TABLE IF NOT EXISTS md_fts USING fts5(
  obj_id UNINDEXED, version UNINDEXED, body,
  tokenize='trigram'
);

-- md_fts 伴生映射（v7，2026-08-25）：(obj_id,version)→fts rowid。按 UNINDEXED 列
-- DELETE 是全 FTS 扫（含全部正文页）——批量 reindex 每文件一扫成 O(N²) 主因；
-- 改按 rowid 删。fts_repo 维护；init_schema 对存量行一次性回填（map 空且 fts
-- 非空时）。map 缺失时 fts_repo 回退全扫删（正确性网底）。
CREATE TABLE IF NOT EXISTS md_fts_map(
  obj_id TEXT NOT NULL, version TEXT NOT NULL, fts_rowid INTEGER NOT NULL,
  PRIMARY KEY(obj_id, version)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS test_cases(
  id TEXT PRIMARY KEY, domain TEXT, scenario TEXT, name TEXT,
  status TEXT, solution TEXT, author TEXT, created_at TEXT,
  body_md TEXT, raw_md TEXT, source_path TEXT, frontmatter_json TEXT
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS test_runs(
  id TEXT PRIMARY KEY, case_id TEXT REFERENCES test_cases(id) ON DELETE CASCADE,
  name TEXT, runner TEXT, run_at TEXT, status TEXT, latest_verdict TEXT,
  body_md TEXT, raw_md TEXT, source_path TEXT, frontmatter_json TEXT
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS test_reviews(
  id TEXT PRIMARY KEY, run_id TEXT REFERENCES test_runs(id) ON DELETE CASCADE,
  reviewer TEXT, reviewed_at TEXT, verdict TEXT,
  body_md TEXT, raw_md TEXT, source_path TEXT, frontmatter_json TEXT
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS test_review_problems(
  id INTEGER PRIMARY KEY, review_id TEXT REFERENCES test_reviews(id) ON DELETE CASCADE,
  idx INT, description TEXT, attribution_json TEXT, objects_json TEXT
);

CREATE TABLE IF NOT EXISTS test_artifacts(
  id INTEGER PRIMARY KEY, owner_type TEXT, owner_id TEXT,
  path TEXT, kind TEXT, size INT
);

-- MCP 工具配置（admin 前端可配，2026-08-25）：enabled=0 隐藏+拦截；description
-- ''=用代码默认（docstring）。服务总体说明存 meta 表 key='mcp_instructions'。
CREATE TABLE IF NOT EXISTS mcp_tools(
  tool_name TEXT PRIMARY KEY,
  enabled INT NOT NULL DEFAULT 1,
  description TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT '',
  updated_by TEXT NOT NULL DEFAULT ''
);
-- 抽取产物清单（v9，抽取任务化 2026-08-26）：入图闸门 confirm 后写入，按任务回退
-- （revert）的依据。op: add=本次新增（回退=软删进回收站）；modify=本次覆盖（回退=
-- 还原 originals 备份）。sha256=应用后内容摘要（回退前比对磁盘，防后续任务已覆盖）。
CREATE TABLE IF NOT EXISTS extract_files(
  job_id TEXT NOT NULL, path TEXT NOT NULL,
  op TEXT NOT NULL, sha256 TEXT NOT NULL,
  layer TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(job_id, path)
);
CREATE INDEX IF NOT EXISTS idx_extract_files_job ON extract_files(job_id);

CREATE INDEX IF NOT EXISTS idx_runs_case ON test_runs(case_id);
CREATE INDEX IF NOT EXISTS idx_reviews_run ON test_reviews(run_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_owner ON test_artifacts(owner_type, owner_id);
"""


def get_db(path: Path = None) -> sqlite3.Connection:
    """打开/创建 SQLite 连接（WAL + NORMAL + foreign_keys + Row 工厂）。

    synchronous=NORMAL（WAL 下）：commit 不再逐条 fsync（reindex 逐文件 commit 曾
    因此每小时多花几十秒）。代价仅 OS 崩溃/断电丢最近提交——图谱索引可由 md
    全量重建（mtime 对账/全量重建兜底），users/trash/jobs 等元数据丢最后一笔
    可接受；应用崩溃不丢（WAL 特性）。
    """
    conn = sqlite3.connect(str(path or DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """建表（IF NOT EXISTS）+ 记录 schema_version。幂等。"""
    conn.executescript(_SCHEMA)
    # v2 迁移：users.can_assets（资产目录权限）。旧库补列 + admin 回填
    # （check_perm 对 is_admin 短路全权，回填使 DB 位与实际效力一致）。幂等。
    cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    if "can_assets" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN can_assets INT DEFAULT 0")
    conn.execute("UPDATE users SET can_assets=1 WHERE is_admin=1 AND can_assets=0")
    # v3 迁移：import_jobs.child_pids（jobs 独立连接记子进程 PID，sweep 终止孤儿用）。幂等。
    jcols = {r[1] for r in conn.execute("PRAGMA table_info(import_jobs)")}
    if jcols and "child_pids" not in jcols:
        conn.execute("ALTER TABLE import_jobs ADD COLUMN child_pids TEXT DEFAULT '[]'")
    # v10：ImportJob.updated/skipped 原只存内存，重启后丢失。
    if jcols and "updated" not in jcols:
        conn.execute("ALTER TABLE import_jobs ADD COLUMN updated INTEGER DEFAULT 0")
    if jcols and "skipped" not in jcols:
        conn.execute("ALTER TABLE import_jobs ADD COLUMN skipped INTEGER DEFAULT 0")
    # v4 迁移（MCP 服务化 2026-08-24）：① telemetry.session_id（会话ID 打点新列，
    # 历史行为 ''）② md_fts 存量回填（旧库 objects 有数据而 FTS 空表 → 一次性灌入）。
    tcols = {r[1] for r in conn.execute("PRAGMA table_info(telemetry)")}
    if tcols and "session_id" not in tcols:
        conn.execute("ALTER TABLE telemetry ADD COLUMN session_id TEXT DEFAULT ''")
    # v5 迁移（MCP 参数留痕 2026-08-24）：telemetry.params/result（tool 级行的
    # 入参 JSON + 出参摘要 JSON，截断 2KB；用户要求输入输出都记录）。
    if tcols and "params" not in tcols:
        conn.execute("ALTER TABLE telemetry ADD COLUMN params TEXT DEFAULT ''")
    if tcols and "result" not in tcols:
        conn.execute("ALTER TABLE telemetry ADD COLUMN result TEXT DEFAULT ''")
    if conn.execute("SELECT COUNT(*) FROM md_fts").fetchone()[0] == 0:
        n = conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
        if n:
            conn.execute(
                "INSERT INTO md_fts(obj_id, version, body) "
                "SELECT id, version, body_md FROM objects"
            )
    # v7 迁移：md_fts_map 存量回填（一次性——仅 map 空且 fts 非空；此后由
    # fts_repo 维护）。单遍扫描，老库首启多花秒级。
    if conn.execute("SELECT COUNT(*) FROM md_fts_map").fetchone()[0] == 0:
        n = conn.execute("SELECT COUNT(*) FROM md_fts").fetchone()[0]
        if n:
            conn.execute(
                "INSERT INTO md_fts_map(obj_id, version, fts_rowid) "
                "SELECT obj_id, version, rowid FROM md_fts"
            )
    # v8 迁移（打点瘦身 2026-08-26·方案B）：一次性清理历史 request 级行——
    # 任务面板轮询/浏览读请求曾占绝对大头且无统计价值（object/tool 级保留）。
    # 此后 request 级仅剩 fs/import 写操作审计行（各 router 自行 _record）。
    if not conn.execute(
        "SELECT value FROM meta WHERE key='telemetry_request_purged'"
    ).fetchone():
        conn.execute("DELETE FROM telemetry WHERE level='request'")
        conn.execute("INSERT INTO meta(key, value) VALUES('telemetry_request_purged','1')")
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
        (SCHEMA_VERSION,),
    )
    conn.commit()


_shared: "sqlite3.Connection | None" = None


def get_shared_db() -> sqlite3.Connection:
    """全局共享连接单例（service / users / store / telemetry 共用，避免多连接写冲突）。

    首次调用打开 ``DB_PATH`` 并 ``init_schema``；之后复用。测试通过 ``monkeypatch``
    把 ``db._shared`` 指向 tmp 连接来隔离。
    """
    global _shared
    if _shared is None:
        _shared = get_db()
        init_schema(_shared)
    return _shared
