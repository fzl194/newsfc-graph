"""md_fts（FTS5 trigram）读写：随 objects 写路径增量同步 + 查询。

同步语义（对抗审查 C1）：文件内 id/版本变更时，旧 (id,version) 行必须一并删除
——调用方从 ``objects_repo.delete_by_source`` 拿到旧集合后调 ``delete_many``，
不留"幽灵命中"。

查询转义（对抗审查 C2）：FTS5 MATCH 有自身语法（AND/OR/NEAR/*/-/引号，含空格的
查询如 ``ADD URR`` 会语法错误）——统一包装为短语查询（内层引号翻倍）。

索引的是 ``objects.body_md``（正文），不含 frontmatter 与 ## 边段——元数据检索
是 search_objects 的职责，正文召回是本表职责。
"""
import sqlite3

# 防御性上限：无过滤常见词（如网元名）可能命中全库；截断保内存，total 如实报告截断后计数
SCAN_CAP = 5000


def escape_phrase(q: str) -> str:
    """用户输入 → FTS5 短语查询（防语法错误/操作符劫持）。"""
    return '"' + q.replace('"', '""') + '"'


def upsert(conn: sqlite3.Connection, *, obj_id: str, version, body: str) -> None:
    version = "" if version is None else version
    delete(conn, obj_id, version)
    conn.execute(
        "INSERT INTO md_fts(obj_id, version, body) VALUES(?,?,?)",
        (obj_id, version, body),
    )


def delete(conn: sqlite3.Connection, obj_id: str, version) -> None:
    conn.execute(
        "DELETE FROM md_fts WHERE obj_id=? AND version=?",
        (obj_id, "" if version is None else version),
    )


def delete_many(conn: sqlite3.Connection, pairs: list) -> None:
    """批量删（旧 (id,version) 集合；单条 delete 走 UNINDEXED 列过滤）。"""
    conn.executemany(
        "DELETE FROM md_fts WHERE obj_id=? AND version=?",
        [(oid, "" if over is None else over) for oid, over in pairs],
    )


def rebuild_from_objects(conn: sqlite3.Connection) -> int:
    """全量重建：清空后从 objects 表灌入（单事务，原子替换）。返回行数。"""
    conn.execute("DELETE FROM md_fts")
    cur = conn.execute(
        "INSERT INTO md_fts(obj_id, version, body) "
        "SELECT id, version, body_md FROM objects"
    )
    return cur.rowcount or 0


def integrity_ok(conn: sqlite3.Connection) -> bool:
    """对账：行数 + 正文总字节双校验（count 相同但内容漂移也能查出，审查 C4）。"""
    o = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(LENGTH(body_md)),0) FROM objects").fetchone()
    f = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(LENGTH(body)),0) FROM md_fts").fetchone()
    return (o[0], o[1]) == (f[0], f[1])


def search_match(conn: sqlite3.Connection, q: str) -> list:
    """MATCH 路径（q ≥3 字符）：相关度 bm25 排序 + snippet 高亮。

    返回 [{obj_id, version, score, snippet}]（已按 score 升序=越相关越前，
    bm25 返回值越小越相关）。不过滤元数据/版本——调用方（service）join 内存
    索引做过滤（layer/type/nf/version + 最新版语义）。
    """
    phrase = escape_phrase(q)
    rows = conn.execute(
        "SELECT obj_id, version, bm25(md_fts) AS score, "
        "snippet(md_fts, 2, '【', '】', '…', 48) AS snip "
        "FROM md_fts WHERE md_fts MATCH ? LIMIT ?",
        (phrase, SCAN_CAP),
    ).fetchall()
    return [{"obj_id": r["obj_id"], "version": r["version"],
             "score": r["score"], "snippet": r["snip"]} for r in rows]


def search_like(conn: sqlite3.Connection, q: str) -> list:
    """LIKE 路径（q <3 字符，trigram 下限）：走 trigram 索引（非全表扫）。

    无相关度（按 obj_id 排序），snippet 由调用方用 body 自行截取
    （FTS5 snippet() 仅对 MATCH 有效）。
    """
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = conn.execute(
        "SELECT obj_id, version, body FROM md_fts "
        "WHERE body LIKE ? ESCAPE '\\' ORDER BY obj_id LIMIT ?",
        (f"%{esc}%", SCAN_CAP),
    ).fetchall()
    return [{"obj_id": r["obj_id"], "version": r["version"], "body": r["body"]}
            for r in rows]
