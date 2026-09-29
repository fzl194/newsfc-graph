"""files 户口册读写（spec 2026-09-29 §4.1/§4.2）。

- 行 = 文件或目录（is_dir）；path 相对 assets 根、正斜杠、磁盘真实大小写。
- 点文件/点目录不入册（与 store.list_children 一致）。
- 删除一律走 files_fts_map 按 rowid（同 md_fts_map 教训：按 UNINDEXED 列删是
  全 FTS 扫）。map 缺失行回退 path 全扫删（正确性网底）。
- 纯 SQL 函数不 commit（调用方事务内使用）；rebuild_all 自管分块提交。
- ⚠️ 路径计算约定（win_long 的 docstring 禁忌）：目录枚举根与 relative_to 的
  基准必须**同为 win_long 前缀或同为普通路径**——混用会 ValueError。
- integrity_ok 当前仅测试消费（启动对账走「表空→bootstrap」启发，spec §4.2）。
"""
import sqlite3
from pathlib import Path

from ..config import win_long
from .graph_search_repo import normalize_search_text

_CHUNK = 5000


def upsert_entry(conn: sqlite3.Connection, *, path: str, name: str, ext: str,
                 is_dir: int, size: int, mtime: float) -> None:
    """UPSERT 单行（值由调用方给定）+ 同步 FTS（先按 map rowid 删旧行）。"""
    rid = conn.execute(
        "SELECT fts_rowid FROM files_fts_map WHERE path=?", (path,)).fetchone()
    if rid is not None:
        conn.execute("DELETE FROM files_fts WHERE rowid=?", (rid[0],))
    conn.execute(
        "INSERT INTO files(path, name, ext, is_dir, size, mtime) VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(path) DO UPDATE SET name=excluded.name, ext=excluded.ext, "
        "is_dir=excluded.is_dir, size=excluded.size, mtime=excluded.mtime",
        (path, name, ext, is_dir, size, mtime))
    cur = conn.execute(
        "INSERT INTO files_fts(path, name) VALUES(?,?)",
        (path, normalize_search_text(name)))
    conn.execute("INSERT OR REPLACE INTO files_fts_map(path, fts_rowid) VALUES(?,?)",
                 (path, cur.lastrowid))


def upsert_from_disk(conn: sqlite3.Connection, store, rel: str) -> None:
    """磁盘 stat 单路径 → UPSERT；磁盘不存在 → 删行（自愈语义，调用方 commit）。"""
    try:
        p = win_long(store.abspath(rel))
        if not p.exists():
            remove_path(conn, rel)
            return
        is_dir = 1 if p.is_dir() else 0
        st = p.stat()
        suffix = Path(rel).suffix.lower()
        upsert_entry(conn, path=rel, name=Path(rel).name,
                     ext=suffix.lstrip(".") if suffix else "",
                     is_dir=is_dir, size=0 if is_dir else st.st_size,
                     mtime=st.st_mtime)
    except (OSError, ValueError):
        remove_path(conn, rel)  # stat 失败/路径非法 → 按不存在处理


def remove_path(conn: sqlite3.Connection, rel: str) -> None:
    """删单行 + FTS（map 命中走 rowid；缺失回退 path 删，正确性网底）。"""
    rid = conn.execute(
        "SELECT fts_rowid FROM files_fts_map WHERE path=?", (rel,)).fetchone()
    if rid is not None:
        conn.execute("DELETE FROM files_fts WHERE rowid=?", (rid[0],))
        conn.execute("DELETE FROM files_fts_map WHERE path=?", (rel,))
    else:
        conn.execute("DELETE FROM files_fts WHERE path=?", (rel,))
    conn.execute("DELETE FROM files WHERE path=?", (rel,))


def remove_prefix(conn: sqlite3.Connection, prefix: str) -> int:
    """删 prefix 目录行自身 + 其下全部行。'/' 的下一码位是 '0'：半开区间覆盖
    prefix/ 下任意 Unicode 文件名（同 service.reindex_prefixes 的技巧）。"""
    low, high = prefix + "/", prefix + "0"
    paths = [r[0] for r in conn.execute(
        "SELECT path FROM files WHERE path>=? AND path<?", (low, high))]
    paths.append(prefix)
    for p in paths:
        remove_path(conn, p)
    return len(paths)


def upsert_tree(conn: sqlite3.Connection, store, rel: str) -> None:
    """rel 自身（文件或目录行）+ 子树全量 UPSERT（回收站还原后重建册用）。"""
    root = win_long(store.abspath(rel))
    if not root.exists():
        remove_path(conn, rel)
        return
    upsert_from_disk(conn, store, rel)
    if not root.is_dir():
        return
    base = win_long(store.root.resolve())  # 与枚举根同为 win_long 前缀
    for p in root.rglob("*"):
        rel_parts = p.relative_to(base).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        try:
            upsert_from_disk(conn, store, "/".join(rel_parts))
        except (OSError, ValueError):
            continue


def rebuild_all(conn: sqlite3.Connection, store, chunk: int = _CHUNK) -> int:
    """全量重建（清空重灌，分块提交——同 graph_search_repo.rebuild_from_objects
    的分块节奏，防长事务饿死独立连接）。返回行数（文件+目录）。"""
    conn.execute("DELETE FROM files")
    conn.execute("DELETE FROM files_fts")
    conn.execute("DELETE FROM files_fts_map")
    conn.commit()
    base = win_long(store.root.resolve())  # 枚举根与 relpath 基准同为前缀形式
    total = 0
    batch: list = []
    for p in base.rglob("*"):
        rel_parts = p.relative_to(base).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        is_dir = 1 if p.is_dir() else 0
        try:
            st = p.stat()
        except OSError:
            continue
        suffix = p.suffix.lower()
        batch.append(("/".join(rel_parts), p.name,
                      suffix.lstrip(".") if suffix else "",
                      is_dir, 0 if is_dir else st.st_size, st.st_mtime,
                      normalize_search_text(p.name)))
        if len(batch) >= chunk:
            _insert_batch(conn, batch)
            total += len(batch)
            batch = []
    if batch:
        _insert_batch(conn, batch)
        total += len(batch)
    return total


def _insert_batch(conn: sqlite3.Connection, batch: list) -> None:
    conn.executemany(
        "INSERT INTO files(path, name, ext, is_dir, size, mtime) VALUES(?,?,?,?,?,?)",
        [b[:6] for b in batch])
    cur_rowid = conn.execute(
        "SELECT COALESCE(MAX(rowid), 0) FROM files_fts").fetchone()[0]
    conn.executemany(
        "INSERT INTO files_fts(path, name) VALUES(?,?)", [(b[0], b[6]) for b in batch])
    conn.execute(
        "INSERT INTO files_fts_map(path, fts_rowid) "
        "SELECT path, rowid FROM files_fts WHERE rowid>?", (cur_rowid,))
    conn.commit()


def integrity_ok(conn: sqlite3.Connection) -> bool:
    """对账：files 与 files_fts 行集合双向一致（缺行/多行都可查出）。"""
    miss = conn.execute(
        "SELECT COUNT(*) FROM (SELECT path FROM files "
        "EXCEPT SELECT path FROM files_fts)").fetchone()[0]
    if miss:
        return False
    extra = conn.execute(
        "SELECT COUNT(*) FROM (SELECT path FROM files_fts "
        "EXCEPT SELECT path FROM files)").fetchone()[0]
    return not extra
