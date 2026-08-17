"""objects 表数据访问：UPSERT / 删除 / 批量加载。

version 存原字符串（语义化排序在应用层 ``version.latest_version`` 做）。**跨 NF 类
version=None**——SQLite (id, version) 主键列不允许 NULL，故用空串 ``""`` 占位，
repo 层做 None ↔ "" 转换，对调用方透明。
"""
import json
import sqlite3
from typing import Optional


def _v_in(v: Optional[str]) -> str:
    """内存 version（可能 None）→ DB 占位（None → ""）。"""
    return v if v is not None else ""


def _v_out(v) -> Optional[str]:
    """DB version → 内存（"" → None）。"""
    return v if v != "" else None


def upsert(conn: sqlite3.Connection, *,
           id: str, version: Optional[str], type: str, layer: str, scope: str,
           nf: Optional[str], domain: Optional[str], scenario: Optional[str],
           source_path: str, name: Optional[str], frontmatter: dict,
           body_md: str, raw_md: str, mtime: float) -> None:
    """插入或更新一个节点（按 id+version 主键冲突时全字段更新）。"""
    conn.execute(
        """
        INSERT INTO objects(id, version, type, layer, scope, nf, domain, scenario,
                            source_path, name, frontmatter_json, body_md, raw_md, mtime)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id, version) DO UPDATE SET
          type=excluded.type, layer=excluded.layer, scope=excluded.scope,
          nf=excluded.nf, domain=excluded.domain, scenario=excluded.scenario,
          source_path=excluded.source_path, name=excluded.name,
          frontmatter_json=excluded.frontmatter_json, body_md=excluded.body_md,
          raw_md=excluded.raw_md, mtime=excluded.mtime
        """,
        (id, _v_in(version), type, layer, scope, nf, domain, scenario,
         source_path, name, json.dumps(frontmatter, ensure_ascii=False, default=str),
         body_md, raw_md, mtime),
    )


def delete(conn: sqlite3.Connection, id: str, version: Optional[str]) -> None:
    conn.execute("DELETE FROM objects WHERE id=? AND version=?", (id, _v_in(version)))


def delete_by_source(conn: sqlite3.Connection, source_path: str) -> list:
    """删某 md（source_path）对应的全部节点；返回被删的 [(id, version), ...]（version 已还原 None）。"""
    rows = conn.execute(
        "SELECT id, version FROM objects WHERE source_path=?", (source_path,)
    ).fetchall()
    conn.execute("DELETE FROM objects WHERE source_path=?", (source_path,))
    return [(r["id"], _v_out(r["version"])) for r in rows]


def load_all(conn: sqlite3.Connection) -> list:
    """全量加载（启动建内存 Index 用）。返回 list[dict]，version 已还原 None。"""
    out = []
    for r in conn.execute("SELECT * FROM objects").fetchall():
        d = dict(r)
        try:
            d["frontmatter"] = json.loads(d.pop("frontmatter_json"))
        except (ValueError, TypeError):
            d["frontmatter"] = {}
        d["version"] = _v_out(d["version"])
        out.append(d)
    return out


def get_mtime(conn: sqlite3.Connection, source_path: str) -> Optional[float]:
    """该 md（source_path）上次入库时的 mtime（一致性校验用）。无记录→None。"""
    row = conn.execute(
        "SELECT MAX(mtime) AS m FROM objects WHERE source_path=?", (source_path,)
    ).fetchone()
    return row["m"] if row and row["m"] is not None else None
