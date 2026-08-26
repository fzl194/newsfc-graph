"""md_fts（FTS5 trigram）读写：随 objects 写路径增量同步 + 查询。

同步语义（对抗审查 C1）：文件内 id/版本变更时，旧 (id,version) 行必须一并删除
——调用方从 ``objects_repo.delete_by_source`` 拿到旧集合后调 ``delete_many``，
不留"幽灵命中"。

删除走 ``md_fts_map`` 伴生映射按 rowid 删（v7，2026-08-25）：按 UNINDEXED 列
DELETE 是全 FTS 扫（含全部正文页），批量 reindex 每文件一扫成 O(N²) 主因；
map 缺失（存量/直写行）回退全扫删保正确。

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
    cur = conn.execute(
        "INSERT INTO md_fts(obj_id, version, body) VALUES(?,?,?)",
        (obj_id, version, body),
    )
    # 伴生映射（v7）：下次 delete 走 rowid（O(log n)）而非 UNINDEXED 全扫
    conn.execute(
        "INSERT OR REPLACE INTO md_fts_map(obj_id, version, fts_rowid) VALUES(?,?,?)",
        (obj_id, version, cur.lastrowid),
    )


def delete(conn: sqlite3.Connection, obj_id: str, version) -> None:
    """按 (obj_id,version) 删一行：map 命中走 rowid；缺失（存量/直写行）回退
    UNINDEXED 全扫删——正确性网底，慢但准。"""
    version = "" if version is None else version
    rid = conn.execute(
        "SELECT fts_rowid FROM md_fts_map WHERE obj_id=? AND version=?",
        (obj_id, version),
    ).fetchone()
    if rid is not None:
        conn.execute("DELETE FROM md_fts WHERE rowid=?", (rid[0],))
        conn.execute(
            "DELETE FROM md_fts_map WHERE obj_id=? AND version=?", (obj_id, version))
        return
    conn.execute(
        "DELETE FROM md_fts WHERE obj_id=? AND version=?", (obj_id, version))


def delete_many(conn: sqlite3.Connection, pairs: list) -> None:
    """批量删（旧 (id,version) 集合；逐条走 delete 的 map 快路径）。"""
    for oid, over in pairs:
        delete(conn, oid, over)


def rebuild_from_objects(conn: sqlite3.Connection, chunk: int = 5000) -> int:
    """全量重建：清空后从 objects 分块灌入 + 重灌 map。返回行数。

    **分块提交**（2026-08-26）：原单事务全量重建在 10 万+ 对象库上持 WAL 写锁
    数分钟——期间 telemetry/jobs 等独立连接全部饿死超时（database is locked，
    内网现场）。改为每 chunk 行一个事务，块间释放写锁；重建期间一致性由调用方
    的 ``fts_rebuilding`` 标志保证（search_md 明确报错不返回残缺）。
    """
    conn.execute("DELETE FROM md_fts")
    conn.execute("DELETE FROM md_fts_map")
    conn.commit()
    total = 0
    # (id, version) 复合游标（PK 序）：同 id 多版本被 LIMIT 切开时不丢尾块
    last_id, last_ver = "", ""
    while True:
        rows = conn.execute(
            "SELECT id, version, body_md FROM objects "
            "WHERE id > ? OR (id = ? AND version > ?) "
            "ORDER BY id, version LIMIT ?",
            (last_id, last_id, last_ver, chunk),
        ).fetchall()
        if not rows:
            break
        max_rid = conn.execute("SELECT COALESCE(MAX(rowid), 0) FROM md_fts").fetchone()[0]
        conn.executemany(
            "INSERT INTO md_fts(obj_id, version, body) VALUES(?,?,?)",
            [(r["id"], r["version"] or "", r["body_md"]) for r in rows],
        )
        # 本块新行的 rowid 必然 > max_rid（FTS5 自增 rowid）→ 直接回填 map
        conn.execute(
            "INSERT INTO md_fts_map(obj_id, version, fts_rowid) "
            "SELECT obj_id, version, rowid FROM md_fts WHERE rowid > ?",
            (max_rid,),
        )
        conn.commit()
        total += len(rows)
        last_id, last_ver = rows[-1]["id"], rows[-1]["version"] or ""
    return total


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
