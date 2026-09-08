"""graph_search_fts（统一搜索索引）读写（需求 §7.3/§12.2）。

- 写入文本统一 ``normalize_search_text``（NFKC → strip → casefold；先 NFKC 再
  strip 是为覆盖全角空格 U+3000 → 半角空格的归一）。
- ``metadata_text`` = 规范化 id/name/name_zh 换行连接；``body_text`` = 规范化
  正文（原始 body_md 留在 objects，snippet 由 search core 从原文截取）。
- 同步语义与 md_fts/fts_repo 相同（同事务双 FTS 维护、伴生 map 按 rowid 删）。
"""
import sqlite3
import unicodedata


def normalize_search_text(s) -> str:
    """搜索文本规范化（§7.3）：NFKC → strip → casefold。None 安全。"""
    if s is None:
        return ""
    return unicodedata.normalize("NFKC", str(s)).strip().casefold()


def metadata_text_of(obj_id, name, name_zh) -> str:
    parts = [normalize_search_text(x) for x in (obj_id, name, name_zh)]
    return "\n".join(p for p in parts if p)


def _v(version) -> str:
    return version if version is not None else ""


def insert(conn: sqlite3.Connection, *, obj_id: str, version, name, name_zh,
           body_md: str) -> None:
    """纯插入 FTS + map（调用方已删除旧键时用本函数，不可再走 upsert 的删除
    步骤——否则 map 被第一次删掉后第二次 delete 退化全扫，同 fts_repo 教训）。"""
    ver = _v(version)
    cur = conn.execute(
        "INSERT INTO graph_search_fts(obj_id, version, metadata_text, body_text) "
        "VALUES(?,?,?,?)",
        (obj_id, ver, metadata_text_of(obj_id, name, name_zh),
         normalize_search_text(body_md)),
    )
    conn.execute(
        "INSERT OR REPLACE INTO graph_search_map(obj_id, version, fts_rowid) "
        "VALUES(?,?,?)", (obj_id, ver, cur.lastrowid))


def delete_mapped(conn: sqlite3.Connection, obj_id: str, version) -> bool:
    ver = _v(version)
    rid = conn.execute(
        "SELECT fts_rowid FROM graph_search_map WHERE obj_id=? AND version=?",
        (obj_id, ver)).fetchone()
    if rid is not None:
        conn.execute("DELETE FROM graph_search_fts WHERE rowid=?", (rid[0],))
        conn.execute(
            "DELETE FROM graph_search_map WHERE obj_id=? AND version=?",
            (obj_id, ver))
        return True
    return False


def delete(conn: sqlite3.Connection, obj_id: str, version) -> None:
    """按 (obj_id,version) 删：map 命中走 rowid；缺失（存量/直写行）回退
    UNINDEXED 全扫删（正确性网底，慢但准）。"""
    if delete_mapped(conn, obj_id, version):
        return
    conn.execute("DELETE FROM graph_search_fts WHERE obj_id=? AND version=?",
                 (obj_id, _v(version)))


def delete_many(conn: sqlite3.Connection, pairs: list) -> None:
    for oid, over in pairs:
        delete(conn, oid, over)


def upsert(conn: sqlite3.Connection, *, obj_id: str, version, name, name_zh,
           body_md: str) -> None:
    delete(conn, obj_id, version)
    insert(conn, obj_id=obj_id, version=version, name=name, name_zh=name_zh,
           body_md=body_md)


def rebuild_from_objects(conn: sqlite3.Connection, chunk: int = 5000) -> int:
    """全量重建：清空后从 objects 分块灌入（name_zh 走 json_extract，与写路径
    frontmatter 同源）。分块提交，避免大库长事务饿死独立连接（同 v7 教训）。"""
    conn.execute("DELETE FROM graph_search_fts")
    conn.execute("DELETE FROM graph_search_map")
    conn.commit()
    total = 0
    last_id, last_ver = "", ""
    while True:
        rows = conn.execute(
            "SELECT id, version, name, "
            "json_extract(frontmatter_json, '$.name_zh') AS name_zh, body_md "
            "FROM objects WHERE id > ? OR (id = ? AND version > ?) "
            "ORDER BY id, version LIMIT ?",
            (last_id, last_id, last_ver, chunk),
        ).fetchall()
        if not rows:
            break
        max_rid = conn.execute(
            "SELECT COALESCE(MAX(rowid), 0) FROM graph_search_fts").fetchone()[0]
        conn.executemany(
            "INSERT INTO graph_search_fts(obj_id, version, metadata_text, body_text) "
            "VALUES(?,?,?,?)",
            [(r["id"], r["version"] or "",
              metadata_text_of(r["id"], r["name"], r["name_zh"]),
              normalize_search_text(r["body_md"])) for r in rows],
        )
        conn.execute(
            "INSERT INTO graph_search_map(obj_id, version, fts_rowid) "
            "SELECT obj_id, version, rowid FROM graph_search_fts WHERE rowid > ?",
            (max_rid,),
        )
        conn.commit()
        total += len(rows)
        last_id, last_ver = rows[-1]["id"], rows[-1]["version"] or ""
    return total


def integrity_ok(conn: sqlite3.Connection) -> bool:
    """对账：objects 与 FTS 的 (id,version) 行集合双向一致（缺行/多行都可查出）。"""
    miss = conn.execute(
        "SELECT COUNT(*) FROM (SELECT id AS obj_id, version FROM objects "
        "EXCEPT SELECT obj_id, version FROM graph_search_fts)").fetchone()[0]
    if miss:
        return False
    extra = conn.execute(
        "SELECT COUNT(*) FROM (SELECT obj_id, version FROM graph_search_fts "
        "EXCEPT SELECT id, version FROM objects)").fetchone()[0]
    return not extra
