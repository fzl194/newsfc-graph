"""edges 表数据访问。

from_version 可能 None（cross 类节点出边），同 objects 用空串占位（None ↔ ""）。
边无独立稳定主键（联合 PK = from_id+from_version+relation+to），节点内容变时按
from 节点整批替换（DELETE + INSERT）。
"""
import sqlite3
from typing import Optional


def _v_in(v: Optional[str]) -> str:
    return v if v is not None else ""


def _v_out(v) -> Optional[str]:
    return v if v != "" else None


def replace_for_node(conn: sqlite3.Connection, from_id: str,
                     from_version: Optional[str], edges: list) -> None:
    """删该 from 节点的所有边，重新插入。edges: list[Edge]。"""
    conn.execute(
        "DELETE FROM edges WHERE from_id=? AND from_version=?",
        (from_id, _v_in(from_version)),
    )
    if edges:
        conn.executemany(
            'INSERT OR IGNORE INTO edges(from_id, from_version, relation, "to") '
            "VALUES(?,?,?,?)",
            [(e.from_id, _v_in(e.from_version), e.relation, e.to) for e in edges],
        )


def delete_for_node(conn: sqlite3.Connection, from_id: str,
                    from_version: Optional[str]) -> None:
    conn.execute(
        "DELETE FROM edges WHERE from_id=? AND from_version=?",
        (from_id, _v_in(from_version)),
    )


def load_all(conn: sqlite3.Connection) -> list:
    out = []
    for r in conn.execute("SELECT * FROM edges").fetchall():
        d = dict(r)
        d["from_version"] = _v_out(d["from_version"])
        out.append(d)
    return out
