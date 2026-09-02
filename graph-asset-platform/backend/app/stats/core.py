"""统计聚合查询：platform.db 只读 SQL（objects/edges + 8 张规则表）。

口径注释里的 A1-A5/B1-B8/C1-C6/D1-D11 编号对应需求说明书 §5 的指标清单；
Case N 对应 §11 验收基准。全部查询参数化（防注入），多值筛选空 tuple = 不筛。
"""
import sqlite3

from .. import db
from .spec import (
    ALL_TYPES, BUSINESS_EDGE_GROUPS, BUSINESS_TYPES, COMMAND_TYPES,
    FEATURE_TYPES, LOGICAL_NE_TABLE, MAPPING_TABLE, RULE_TABLES, SYNTAX_TABLE,
    TASK_TYPES, Filters, expand_nf_filter, merge_relations, nf_display,
)

Conn = sqlite3.Connection


# ---------- 筛选解析 ----------

def _split(s: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in s.split(",") if x.strip()) if s else ()


def parse_filters(*, nfs: str = "", versions: str = "", logical_ne: str = "",
                  object_types: str = "", relations: str = "", rule_types: str = "",
                  domain: str = "", scenario: str = "", solution: str = "",
                  overseas: bool = False) -> Filters:
    """查询串（逗号分隔）→ Filters；未知对象类型剔除（防手输导致空集）。"""
    ots = tuple(t for t in _split(object_types) if t in ALL_TYPES)
    return Filters(
        nfs=_split(nfs), versions=_split(versions),
        logical_ne=logical_ne.strip(), object_types=ots,
        relations=_split(relations), rule_types=_split(rule_types),
        domain=domain.strip(), scenario=scenario.strip(),
        solution=solution.strip(), overseas=bool(overseas),
    )


def _effective_types(f: Filters, types: tuple[str, ...] | None) -> tuple[str, ...] | None:
    """视图类型集 ∩ 对象类型筛选。None = 不限类型（无子句）。"""
    if not f.object_types:
        return types
    if types is None:
        return f.object_types
    return tuple(t for t in types if t in f.object_types)


def _ph(n: int) -> str:
    return ",".join("?" * n) if n else ""


def _obj_where(f: Filters, types: tuple[str, ...] | None, alias: str = "o") -> tuple[str, list]:
    """objects 系 WHERE 片段（类型/网元[UPCF 展开]/版本/域/场景）。"""
    clauses: list[str] = []
    params: list = []
    eff = _effective_types(f, types)
    if eff is not None:
        if not eff:
            return "1=0", []
        clauses.append(f"{alias}.type IN ({_ph(len(eff))})")
        params.extend(eff)
    nfs = expand_nf_filter(f.nfs)
    if nfs:
        clauses.append(f"{alias}.nf IN ({_ph(len(nfs))})")
        params.extend(nfs)
    if f.versions:
        clauses.append(f"{alias}.version IN ({_ph(len(f.versions))})")
        params.extend(f.versions)
    if f.domain:
        clauses.append(f"{alias}.domain = ?")
        params.append(f.domain)
    if f.scenario:
        clauses.append(f"{alias}.scenario = ?")
        params.append(f.scenario)
    return " AND ".join(clauses) or "1=1", params


def _rule_where(f: Filters, ne_col: str, ver_col: str) -> tuple[str, list]:
    """规则表系 WHERE 片段（§6.1：网元列名两套由调用方传入）。UPCF 不展开——
    规则表列值本身就是 UPCF。"""
    clauses: list[str] = []
    params: list = []
    if f.nfs:
        clauses.append(f'"{ne_col}" IN ({_ph(len(f.nfs))})')
        params.extend(f.nfs)
    if f.versions:
        clauses.append(f'"{ver_col}" IN ({_ph(len(f.versions))})')
        params.extend(f.versions)
    return " AND ".join(clauses) or "1=1", params


def _logical_ne_subquery(f: Filters) -> tuple[str, list]:
    """逻辑网元 → 命令集合子查询（§6.2，仅作用语法规则表 B1/B2）。"""
    sql = f'SELECT DISTINCT "COMMAND_NAME" FROM "{LOGICAL_NE_TABLE}" WHERE "LOGICAL_NE_TYPE" = ?'
    params: list = [f.logical_ne]
    if f.nfs:
        sql += f' AND "PHYSICAL_NE_TYPE" IN ({_ph(len(f.nfs))})'
        params.extend(f.nfs)
    if f.versions:
        sql += f' AND "NE_VERSION" IN ({_ph(len(f.versions))})'
        params.extend(f.versions)
    return sql, params


# ---------- objects 系 ----------

def objects_count(conn: Conn, f: Filters, types: tuple[str, ...]) -> int:
    where, params = _obj_where(f, types)
    return conn.execute(
        f"SELECT COUNT(*) FROM objects o WHERE {where}", params).fetchone()[0]


def objects_matrix(conn: Conn, f: Filters, types: tuple[str, ...]) -> list[dict]:
    """网元×版本 下钻（Case 2）：每行含各类型计数与合计。"""
    where, params = _obj_where(f, types)
    sums = ", ".join(f"SUM(o.type=?) AS t{i}" for i in range(len(types)))
    rows = conn.execute(
        f"SELECT o.nf, o.version, {sums}, COUNT(*) AS total FROM objects o "
        f"WHERE {where} GROUP BY o.nf, o.version ORDER BY o.nf, o.version",
        # SELECT 子句的 SUM(o.type=?) 占位符在 SQL 文本中先于 WHERE → 参数序 = 类型 + where
        [*types, *params]).fetchall()
    return [
        {"nf": r["nf"] or "", "version": r["version"] or "",
         **{t: r[f"t{i}"] or 0 for i, t in enumerate(types)},
         "total": r["total"]}
        for r in rows
    ]


def codes_stats(conn: Conn, f: Filters, type_: str, code_key: str) -> dict:
    """编号去重统计（C1-C4）：全局 DISTINCT 编号数 + 知识条数（Case 5 口径）。"""
    where, params = _obj_where(f, (type_,))
    r = conn.execute(
        f"SELECT COUNT(DISTINCT json_extract(o.frontmatter_json,'$.{code_key}')) AS codes, "
        f"COUNT(*) AS n FROM objects o WHERE {where}", params).fetchone()
    return {"codes": r["codes"] or 0, "knowledge": r["n"] or 0}


def codes_matrix(conn: Conn, f: Filters, type_: str, code_key: str) -> list[dict]:
    where, params = _obj_where(f, (type_,))
    rows = conn.execute(
        f"SELECT o.nf, o.version, "
        f"COUNT(DISTINCT json_extract(o.frontmatter_json,'$.{code_key}')) AS codes, "
        f"COUNT(*) AS n FROM objects o WHERE {where} "
        f"GROUP BY o.nf, o.version ORDER BY o.nf, o.version", params).fetchall()
    return [{"nf": r["nf"] or "", "version": r["version"] or "",
             "codes": r["codes"] or 0, "knowledge": r["n"] or 0} for r in rows]


def feature_prefixes(conn: Conn, f: Filters) -> list[str]:
    """C6：feature_code 前缀类（WSFD/WHFD/GWFD/IPFD/SFFD/NPFD…）。"""
    where, params = _obj_where(f, ("Feature",))
    rows = conn.execute(
        "SELECT DISTINCT substr(json_extract(o.frontmatter_json,'$.feature_code'),1,4) AS p "
        f"FROM objects o WHERE {where} AND p IS NOT NULL ORDER BY p", params).fetchall()
    return [r["p"] for r in rows]


# ---------- edges 系 ----------

def edges_raw(conn: Conn, f: Filters, from_types: tuple[str, ...]) -> dict[str, int]:
    """出边按 relation 原值计数（图谱归属=from 类型，Case 6/7）。"""
    where, params = _obj_where(f, from_types)
    sql = (f"SELECT e.relation AS rel, COUNT(*) AS cnt FROM edges e "
           f"JOIN objects o ON o.id=e.from_id AND o.version=e.from_version "
           f"WHERE {where}")
    if f.relations:
        sql += f" AND e.relation IN ({_ph(len(f.relations))})"
        params.extend(f.relations)
    return {r["rel"]: r["cnt"] for r in conn.execute(sql + " GROUP BY e.relation", params)}


def edges_inbound(conn: Conn, f: Filters, to_types: tuple[str, ...]) -> dict[str, int]:
    """被引用入边（A5）：**跨图谱**入边——to 指向本图谱节点且 from 不属本图谱
    （图谱内部边已在 A4 出边侧计入，重复计会双份）。文档 A5 期望 79,051 =
    使用命令 77,166 + 对应命令 1,885，恰为跨图谱构成。edges.to 无版本列——
    EXISTS 按 id 去重多版本目标。"""
    where, params = _obj_where(f, to_types)
    ne_ph = _ph(len(to_types))
    sql = (f"SELECT e.relation AS rel, COUNT(*) AS cnt FROM edges e "
           f'WHERE EXISTS(SELECT 1 FROM objects o WHERE o.id=e."to" AND {where}) '
           f"AND NOT EXISTS(SELECT 1 FROM objects o2 WHERE o2.id=e.from_id "
           f"AND o2.type IN ({ne_ph}))")
    params = [*params, *to_types]
    if f.relations:
        sql += f" AND e.relation IN ({_ph(len(f.relations))})"
        params.extend(f.relations)
    return {r["rel"]: r["cnt"] for r in conn.execute(sql + " GROUP BY e.relation", params)}


def edges_block(conn: Conn, f: Filters, from_types: tuple[str, ...]) -> dict:
    """出边 raw + 成对合并（§7.1 取大）+ 合并总数。"""
    raw = edges_raw(conn, f, from_types)
    merged, total = merge_relations(raw)
    return {
        "raw": sorted(raw.items(), key=lambda kv: -kv[1]),
        "merged": sorted(merged.items(), key=lambda kv: -kv[1]),
        "merged_total": total,
    }


# ---------- 规则表系 ----------

def _selected_rule_keys(f: Filters) -> tuple[str, ...]:
    """rule_types 筛选为空 = 全部（syntax + 五类）。"""
    if not f.rule_types:
        return ("syntax", *RULE_TABLES)
    return tuple(k for k in ("syntax", *RULE_TABLES) if k in f.rule_types)


def syntax_stats(conn: Conn, f: Filters) -> dict:
    """B1/B2（§7.3 权威定义）：命令数=DISTINCT CMD_NAME，参数数=行数。
    cmd_count_by_group_sum=按 (NE_TYPE,NE_VERSION) 分组求和（跨组重复计入）。"""
    where, params = _rule_where(f, "NE_TYPE", "NE_VERSION")
    if f.logical_ne:
        sub, sub_params = _logical_ne_subquery(f)
        where += f' AND "CMD_NAME" IN ({sub})'
        params.extend(sub_params)
    r = conn.execute(
        f'SELECT COUNT(DISTINCT "CMD_NAME"), COUNT(*) FROM "{SYNTAX_TABLE}" '
        f'WHERE {where}', params).fetchone()
    return {"cmd_count": r[0] or 0, "param_count": r[1] or 0}


def syntax_matrix(conn: Conn, f: Filters) -> list[dict]:
    """命令/参数按语法表 NE×版本 下钻（Case 3）。NE_TYPE 为本表自有命名
    （UEG-M/vSE2980_4U 等），与 objects.nf 不做映射（需求说明书 §9.1）。"""
    where, params = _rule_where(f, "NE_TYPE", "NE_VERSION")
    if f.logical_ne:
        sub, sub_params = _logical_ne_subquery(f)
        where += f' AND "CMD_NAME" IN ({sub})'
        params.extend(sub_params)
    rows = conn.execute(
        f'SELECT "NE_TYPE" AS ne, "NE_VERSION" AS version, '
        f'COUNT(DISTINCT "CMD_NAME") AS cmd_count, COUNT(*) AS param_count '
        f'FROM "{SYNTAX_TABLE}" WHERE {where} '
        f'GROUP BY "NE_TYPE", "NE_VERSION" ORDER BY "NE_TYPE", "NE_VERSION"',
        params).fetchall()
    return [dict(r) for r in rows]


def rule_count(conn: Conn, f: Filters, key: str) -> int:
    table, ne_col, ver_col, _ = RULE_TABLES[key]
    where, params = _rule_where(f, ne_col, ver_col)
    return conn.execute(
        f'SELECT COUNT(*) FROM "{table}" WHERE {where}', params).fetchone()[0]


def rule_matrix(conn: Conn, f: Filters, key: str) -> list[dict]:
    """五类规则按 网元×版本 下钻（Case 4：注意网元列名两套）。"""
    table, ne_col, ver_col, _ = RULE_TABLES[key]
    where, params = _rule_where(f, ne_col, ver_col)
    rows = conn.execute(
        f'SELECT "{ne_col}" AS ne, "{ver_col}" AS version, COUNT(*) AS count '
        f'FROM "{table}" WHERE {where} '
        f'GROUP BY "{ne_col}", "{ver_col}" ORDER BY "{ne_col}", "{ver_col}"',
        params).fetchall()
    return [dict(r) for r in rows]


# ---------- 版本归一（§7.2） ----------

def overseas_map(conn: Conn) -> dict[tuple[str, str], tuple[str, ...]]:
    """(物理网元, 国内版本) → 海外版本集合（同键多条并列）。"""
    m: dict[tuple[str, str], set[str]] = {}
    for r in conn.execute(
            f'SELECT "PHYSICAL_NE_TYPE", "LOCAL_VERSION", "OVERSEAS_VERSION" '
            f'FROM "{MAPPING_TABLE}"'):
        if r[0] and r[1] and r[2]:
            m.setdefault((r[0], r[1]), set()).add(r[2])
    return {k: tuple(sorted(v)) for k, v in m.items()}


def _display(vmap: dict, f: Filters, ne_key: str, local: str) -> str:
    """展示版本：overseas 开关开→映射海外号（多值并列 / 连接，映射不到显原值）。"""
    if not f.overseas:
        return local
    vs = vmap.get((ne_key, local))
    return "/".join(vs) if vs else local


def _dress_rows(rows: list[dict], vmap: dict, f: Filters, nf_is_objects: bool) -> list[dict]:
    """给下钻行加 nf_display/version_display。objects 系先归一 PCF→UPCF 再查
    映射（映射表 PHYSICAL_NE_TYPE='UPCF'）；规则表系列值即 UPCF 命名。"""
    for r in rows:
        # objects 矩阵列名 nf；规则表矩阵（syntax/rule）列名 ne
        nd = nf_display(r["nf"]) if nf_is_objects else r.get("ne", r.get("nf", ""))
        r["nf_display"] = nd
        r["version_display"] = _display(vmap, f, nd, r["version"])
    return rows


# ---------- 三视图组装 ----------

def command_view(conn: Conn, f: Filters) -> dict:
    """命令图谱（§5.1）：知识维度 A1-A5 + 规则维度 B1-B8 + 三张下钻。"""
    vmap = overseas_map(conn)
    a1 = objects_count(conn, f, ("MMLCommand",))
    a2 = objects_count(conn, f, ("ConfigObject",))
    rules: dict = {}
    five_total = 0
    syntax_sum = 0
    sel = _selected_rule_keys(f)
    if "syntax" in sel:
        st = syntax_stats(conn, f)
        syntax_sum = sum(r["cmd_count"] for r in syntax_matrix(conn, f))
        rules["syntax"] = {**st, "cmd_count_by_group_sum": syntax_sum}
    for key in RULE_TABLES:
        if key in sel:
            rules[key] = rule_count(conn, f, key)
            five_total += rules[key]
    matrix = _dress_rows(objects_matrix(conn, f, COMMAND_TYPES), vmap, f, True)
    return {
        "view": "command", "filters": f.echo(),
        "knowledge": {"MMLCommand": a1, "ConfigObject": a2, "points": a1 + a2},
        "edges": edges_block(conn, f, COMMAND_TYPES),
        "inbound": {
            "raw": sorted(edges_inbound(conn, f, COMMAND_TYPES).items(),
                          key=lambda kv: -kv[1]),
        },
        "rules": rules, "five_total": five_total,
        "matrix": matrix,
        "syntax_matrix": _dress_rows(syntax_matrix(conn, f), vmap, f, False),
        "rule_matrix": {k: _dress_rows(rule_matrix(conn, f, k), vmap, f, False)
                        for k in RULE_TABLES if k in sel},
    }


def feature_view(conn: Conn, f: Filters) -> dict:
    """特性图谱（§5.2）：C1-C4 总量 + 四列矩阵（Case 5）+ C5 出边 + C6 前缀。"""
    vmap = overseas_map(conn)
    ft = codes_stats(conn, f, "Feature", "feature_code")
    lc = codes_stats(conn, f, "License", "license_code")
    frows = codes_matrix(conn, f, "Feature", "feature_code")
    lrows = codes_matrix(conn, f, "License", "license_code")
    lmap = {(r["nf"], r["version"]): r for r in lrows}
    matrix: dict[tuple[str, str], dict] = {
        (r["nf"], r["version"]): {
            "nf": r["nf"], "version": r["version"],
            "feature_codes": r["codes"], "feature_knowledge": r["knowledge"],
            "license_codes": 0, "license_knowledge": 0}
        for r in frows}
    for r in lrows:
        cell = matrix.setdefault((r["nf"], r["version"]), {
            "nf": r["nf"], "version": r["version"], "feature_codes": 0,
            "feature_knowledge": 0, "license_codes": 0, "license_knowledge": 0})
        cell["license_codes"] = r["codes"]
        cell["license_knowledge"] = r["knowledge"]
    return {
        "view": "feature", "filters": f.echo(),
        "totals": {
            "feature_codes": ft["codes"], "feature_knowledge": ft["knowledge"],
            "license_codes": lc["codes"], "license_knowledge": lc["knowledge"],
        },
        "matrix": _dress_rows(
            sorted(matrix.values(), key=lambda r: (r["nf"], r["version"])),
            vmap, f, True),
        "edges": edges_block(conn, f, FEATURE_TYPES),
        "prefixes": feature_prefixes(conn, f),
    }


def business_view(conn: Conn, f: Filters) -> dict:
    """业务图谱（§5.3）：D1-D3 主线 + D4-D7b 任务资产 + D8-D11 边归组。"""
    d = {t: objects_count(conn, f, (t,)) for t in TASK_TYPES}
    sol_where, sol_params = _obj_where(f, ("ConfigurationSolution",))
    if f.solution:
        sol_where += " AND o.name = ?"
        sol_params.append(f.solution)
    # 方案名列表：两查询 zip（不用 GROUP_CONCAT——方案名含分隔符会被拆断，
    # 且 DISTINCT 聚合不支持自定义分隔符）；COUNT 保持按对象行计（Case 7 口径）
    sol_counts = {(r["domain"] or "", r["scenario"] or ""): r["n"] for r in conn.execute(
        f"SELECT o.domain, o.scenario, COUNT(*) AS n FROM objects o WHERE {sol_where} "
        f"GROUP BY o.domain, o.scenario", sol_params)}
    sol_names: dict[tuple[str, str], list[str]] = {}
    for r in conn.execute(
            f"SELECT DISTINCT o.domain, o.scenario, o.name FROM objects o "
            f"WHERE {sol_where} ORDER BY o.domain, o.scenario, o.name", sol_params):
        sol_names.setdefault((r["domain"] or "", r["scenario"] or ""), []).append(r["name"] or "")
    solutions_matrix = [
        {"domain": k[0], "scenario": k[1], "solutions": names,
         "count": sol_counts.get(k, 0)}
        for k, names in sorted(sol_names.items())
    ]
    task_where, task_params = _obj_where(f, TASK_TYPES)
    tasks_matrix = [
        dict(r) for r in conn.execute(
            f"SELECT o.type AS type, o.nf AS nf, COUNT(*) AS count FROM objects o "
            f"WHERE {task_where} GROUP BY o.type, o.nf ORDER BY o.type, o.nf",
            task_params)]
    block = edges_block(conn, f, BUSINESS_TYPES)
    merged = dict(block["merged"])
    groups = {label: sum(merged.get(rel, 0) for rel in members if merged.get(rel))
              for label, members in BUSINESS_EDGE_GROUPS}
    atom_edges = edges_raw(conn, f, ("AtomTask",))
    ft_edges = edges_raw(conn, f, ("FeatureTask",))
    return {
        "view": "business", "filters": f.echo(),
        "counts": {
            "domains": objects_count(conn, f, ("BusinessDomain",)),
            "scenarios": objects_count(conn, f, ("NetworkScenario",)),
            "solutions": objects_count(conn, f, ("ConfigurationSolution",)),
            "atom_tasks": d["AtomTask"], "feature_tasks": d["FeatureTask"],
            "compound_tasks": d["CompoundTask"],
            # D7/D7b：任务→命令/特性 跨图谱出边
            "task_cmd_edges": atom_edges.get("对应命令", 0),
            "task_feature_edges": ft_edges.get("对应特性", 0),
        },
        "solutions_matrix": solutions_matrix,
        "tasks_matrix": tasks_matrix,
        "edges": {**block, "groups": groups},
    }


VIEW_FN = {"command": command_view, "feature": feature_view, "business": business_view}


def view_payload(conn: Conn, view: str, f: Filters) -> dict:
    fn = VIEW_FN.get(view)
    if fn is None:
        raise KeyError(f"未知统计视图: {view}")
    return fn(conn, f)


# ---------- 筛选下拉选项（/filters） ----------

def _distinct(conn: Conn, sql: str, params: list | None = None) -> list[str]:
    return sorted({r[0] for r in conn.execute(sql, params or []) if r[0]})


def filters_options(conn: Conn) -> dict:
    """下拉选项：网元=objects ∪ 各规则表网元列（PCF 归一 UPCF）；
    版本=objects ∪ 规则表；逻辑网元按物理网元分组；表行数供 UI 提示未导入。"""
    nfs: set[str] = {nf_display(n) for n in _distinct(
        conn, "SELECT DISTINCT nf FROM objects")}
    versions: set[str] = set(_distinct(
        conn, "SELECT DISTINCT version FROM objects"))
    for table, ne_col, ver_col, _ in RULE_TABLES.values():
        try:
            nfs.update(_distinct(conn, f'SELECT DISTINCT "{ne_col}" FROM "{table}"'))
            versions.update(_distinct(
                conn, f'SELECT DISTINCT "{ver_col}" FROM "{table}"'))
        except sqlite3.OperationalError:  # 表未建（旧库未重启）——跳过
            continue
    logical: dict[str, list[str]] = {}
    try:
        for r in conn.execute(
                f'SELECT DISTINCT "PHYSICAL_NE_TYPE", "LOGICAL_NE_TYPE" '
                f'FROM "{LOGICAL_NE_TABLE}"'):
            if r[0] and r[1]:
                logical.setdefault(r[0], []).append(r[1])
    except sqlite3.OperationalError:
        pass
    solutions = [
        {"domain": r["domain"] or "", "scenario": r["scenario"] or "", "name": r["name"] or ""}
        for r in conn.execute(
            "SELECT DISTINCT domain, scenario, name FROM objects "
            "WHERE type='ConfigurationSolution' ORDER BY domain, scenario, name")
    ]
    table_rows: dict[str, int] = {}
    all_rule_tables = (SYNTAX_TABLE, LOGICAL_NE_TABLE, MAPPING_TABLE,
                       *(m[0] for m in RULE_TABLES.values()))
    for t in all_rule_tables:
        try:
            table_rows[t] = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except sqlite3.OperationalError:
            table_rows[t] = -1  # 表不存在
    return {
        "nfs": sorted(nfs),
        "versions": sorted(versions),
        "logical_nes": {k: sorted(v) for k, v in logical.items()},
        "object_types": list(ALL_TYPES),
        "relations": _distinct(conn, "SELECT DISTINCT relation FROM edges"),
        "rule_types": [{"key": k, "label": v} for k, v in
                       (("syntax", "语法规则"), *((kk, RULE_TABLES[kk][3]) for kk in RULE_TABLES))],
        "domains": _distinct(conn, "SELECT DISTINCT domain FROM objects"),
        "scenarios": _distinct(conn, "SELECT DISTINCT scenario FROM objects"),
        "solutions": solutions,
        "table_rows": table_rows,
    }


def get_conn() -> Conn:
    return db.get_shared_db()
