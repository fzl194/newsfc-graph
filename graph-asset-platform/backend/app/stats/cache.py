"""统计预聚合缓存（2026-09-02 晚，用户反馈"筛选仍然很卡"）。

内网百万行级（语法表 466 万 / edges 41 万）每次筛选都跑 GROUP BY 仍是秒级——
而图谱数据平时不变。方案（用户拍板）：**启动后台预热全量聚合 + 「更新缓存」
按钮重建**，筛选请求只在内存聚合结果上做行级过滤：

- 分组键都是 (网元,版本[,逻辑网元],类型)，nf/版本筛选天然可对聚合行过滤；
- **DISTINCT 指标**（命令数量 / 特性编号）用**集合（set）缓存**，任意筛选/
  汇总粒度由集合并集推导，不再回表；
- 逻辑网元粒度的语法统计一趟 JOIN 预计算（2026-09-02 需求 6：规则长表带
  逻辑网元维度）。

构建在后台线程进行，完成后**原子换新**（单一赋值），期间继续服务旧数据；
首次启动（无旧数据）时第一个请求同步等待构建完成。测试通过 ``reset()``
隔离（conftest 每 test 重建，从 monkeypatch 的 tmp 连接聚合）。
"""
import threading
import time

from . import core
from .spec import (
    COMMAND_TYPES, FEATURE_TYPES, Filters, RULE_TABLES, expand_nf_filter,
    merge_relations,
)

_lock = threading.Lock()
_build_thread: threading.Thread | None = None
_state: dict = {"data": None, "building": False, "built_at": 0.0, "error": "",
                "gen": 0}

# 规则长表的 7 个类型（键→标签）：命令/参数（语法表派生）+ 五类规则
RULE_TYPES: tuple[tuple[str, str], ...] = (
    ("cmd", "命令数量"), ("param", "参数数量"),
    *((k, RULE_TABLES[k][3]) for k in RULE_TABLES),
)


def status() -> dict:
    return {"building": _state["building"], "built_at": _state["built_at"],
            "error": _state["error"]}


def reset() -> None:
    """测试隔离：清空缓存并递增代数——仍在跑的旧构建线程完成后**不回写**
    （防上一个 test 的 lifespan 预热线程把空数据写进下一个 test 的缓存）。"""
    with _lock:
        _state["data"] = None
        _state["building"] = False
        _state["built_at"] = 0.0
        _state["error"] = ""
        _state["gen"] += 1


def refresh_async() -> bool:
    """触发后台重建；已在构建中返回 False。"""
    global _build_thread
    with _lock:
        if _state["building"]:
            return False
        _state["building"] = True
        _state["error"] = ""
        gen = _state["gen"]
    _build_thread = threading.Thread(target=_build_safe, args=(gen,), daemon=True)
    _build_thread.start()
    return True


def _build_safe(gen: int) -> None:
    try:
        data = _build()
        with _lock:
            if gen == _state["gen"]:
                _state["data"] = data
                _state["built_at"] = data["built_at"]
    except Exception as e:  # noqa: BLE001 —— 构建失败保留旧数据，错误经 status 暴露
        with _lock:
            if gen == _state["gen"]:
                _state["error"] = f"{type(e).__name__}: {e}"
    finally:
        with _lock:
            if gen == _state["gen"]:
                _state["building"] = False


def _build() -> dict:
    """全量聚合（无筛选）。积木全部来自 core（复用口径与索引）。"""
    conn = core.get_conn()
    f = Filters()
    # 出/入边按 槽位×关系（供筛选后重组 merged 计数；知识行的出/入边合计由此求和）
    edges_out = core.edges_out_by_slot_rel(conn, COMMAND_TYPES)
    edges_in = core.edges_in_by_slot_rel(conn, COMMAND_TYPES)              # 跨图谱（A5 卡）
    edges_in_all = core.edges_in_by_slot_rel(conn, COMMAND_TYPES, cross_only=False)  # 全量（知识表入边列）
    out_map = {s: sum(rels.values()) for s, rels in edges_out.items()}
    in_map = {s: sum(rels.values()) for s, rels in edges_in_all.items()}
    # 知识行（含出/入边并入）
    knowledge = core.objects_matrix(conn, f, COMMAND_TYPES)
    for r in knowledge:
        key = (r["nf"], r["version"])
        r["out_edges"] = out_map.get(key, 0)
        r["in_edges"] = in_map.get(key, 0)
    # 语法：(NE,版本) → (命令集合, 参数行数)；其余粒度由集合推导
    syntax_nv: dict[tuple[str, str], dict] = {}
    for r in core.syntax_group_rows(conn):
        cell = syntax_nv.setdefault(
            (r["ne"] or "", r["ver"] or ""), {"cmds": set(), "params": 0})
        cell["cmds"].add(r["cmd"] or "")
        cell["params"] += r["n"] or 0
    lne_rows = core.lne_syntax_counts(conn)
    # 五类规则：各表 (NE,版本) 计数
    five_nv = {k: {(r["ne"], r["version"]): r["count"]
                   for r in core.rule_matrix(conn, f, k)} for k in RULE_TABLES}
    # 特性/License：(nf,版本) → (编号集合, 知识条数)
    feature: dict[tuple[str, str], dict] = {}
    for type_, ckey, fset, kkey in (("Feature", "feature_code", "fc", "fk"),
                                    ("License", "license_code", "lc", "lk")):
        for r in core.codes_set_rows(conn, type_, ckey):
            cell = feature.setdefault(
                (r["nf"] or "", r["ver"] or ""),
                {"fc": set(), "fk": 0, "lc": set(), "lk": 0})
            cell[fset].add(r["code"] or "")
            cell[kkey] += r["n"] or 0
    feature_edges = core.edges_out_by_slot_rel(conn, FEATURE_TYPES)
    return {
        "built_at": time.time(),
        "knowledge": knowledge,
        "edges_out": edges_out, "edges_in": edges_in, "edges_in_all": edges_in_all,
        "syntax_nv": syntax_nv, "lne_rows": lne_rows,
        "five_nv": five_nv,
        "feature": feature, "feature_edges": feature_edges,
        "business": core.business_view(conn, f),
        "filters": core.filters_options(conn),
        "vmap": core.overseas_map(conn),
    }


def get() -> dict:
    """取缓存。首启后台预热未完成时**等待**（不返回空数据）；未预热也未触发过
    则同步构建一次（等价旧行为：第一个请求慢）。"""
    if _state["data"] is None and _state["building"]:
        while _state["building"] and _state["data"] is None:
            time.sleep(0.05)
        return _state["data"] or {}
    if _state["data"] is None:
        with _lock:
            if _state["data"] is None and not _state["building"]:
                _state["building"] = True
                try:
                    data = _build()
                    _state["data"] = data
                    _state["built_at"] = data["built_at"]
                finally:
                    _state["building"] = False
    return _state["data"] or {}


# ---------- 行级过滤工具 ----------

def _nf_match_obj(f: Filters, nf: str) -> bool:
    """objects 系网元匹配（UPCF 展开）。"""
    return not f.nfs or nf in expand_nf_filter(f.nfs)


def _nf_match_rule(f: Filters, ne: str) -> bool:
    """规则表系网元匹配（原生命名直配，UPCF 不展开）。"""
    return not f.nfs or ne in f.nfs


def _ver_match(f: Filters, ver: str) -> bool:
    return not f.versions or ver in f.versions


def _dress(rows: list[dict], data: dict, f: Filters, nf_is_objects: bool) -> list[dict]:
    return core._dress_rows(rows, data["vmap"], f, nf_is_objects)


# ---------- 视图 serve（筛选在缓存上做）----------

def command_summary(f: Filters) -> dict:
    d = get()
    rows = [r for r in d["knowledge"]
            if _nf_match_obj(f, r["nf"]) and _ver_match(f, r["version"])]
    a1 = sum(r["MMLCommand"] for r in rows)
    a2 = sum(r["ConfigObject"] for r in rows)
    slots = {(r["nf"], r["version"]) for r in rows}
    out_raw: dict[str, int] = {}
    in_raw: dict[str, int] = {}
    for s in slots:
        for rel, n in d["edges_out"].get(s, {}).items():
            out_raw[rel] = out_raw.get(rel, 0) + n
        for rel, n in d["edges_in"].get(s, {}).items():
            in_raw[rel] = in_raw.get(rel, 0) + n
    merged, merged_total = merge_relations(out_raw)
    five: dict[str, int] = {}
    for k in RULE_TABLES:
        five[k] = sum(n for (ne, ver), n in d["five_nv"][k].items()
                      if _nf_match_rule(f, ne) and _ver_match(f, ver))
    return {
        "view": "command", "cache": status(),
        "knowledge": {"MMLCommand": a1, "ConfigObject": a2, "points": a1 + a2},
        "edges": {
            "raw": sorted(out_raw.items(), key=lambda kv: -kv[1]),
            "merged": sorted(merged.items(), key=lambda kv: -kv[1]),
            "merged_total": merged_total,
        },
        "inbound": {"raw": sorted(in_raw.items(), key=lambda kv: -kv[1])},
        "rules": five, "five_total": sum(five.values()),
    }


_KNOWLEDGE_SORT = {"nf": "nf", "version": "version", "cmd": "cmd_knowledge",
                   "cfg": "cfg_knowledge", "total": "total_knowledge",
                   "out": "out_edges", "in": "in_edges"}


def command_knowledge(f: Filters, page: int = 1, size: int = 20,
                      sort: str = "-total") -> dict:
    d = get()
    rows = [{
        "nf": r["nf"], "version": r["version"],
        "cmd_knowledge": r["MMLCommand"], "cfg_knowledge": r["ConfigObject"],
        "total_knowledge": r["total"],
        "out_edges": r["out_edges"], "in_edges": r["in_edges"],
    } for r in d["knowledge"]
        if _nf_match_obj(f, r["nf"]) and _ver_match(f, r["version"])]
    _dress(rows, d, f, True)
    rows = core._sort_rows(rows, sort, _KNOWLEDGE_SORT)
    paged, total = core._paginate(rows, page, size)
    return {"rows": paged, "total": total}


_RULES_SORT = {"ne": "ne", "logical": "logical", "version": "version",
               "type": "type", "count": "count"}


def _selected_types(f: Filters) -> tuple[str, ...]:
    if not f.rule_types:
        return tuple(k for k, _ in RULE_TYPES)
    return tuple(k for k in f.rule_types if k in dict(RULE_TYPES))


def command_rules(f: Filters, mode: str = "ne_version", page: int = 1,
                  size: int = 20, sort: str = "-count") -> dict:
    """规则长表（2026-09-02 需求 6）：网元/逻辑网元/版本/类型/数量。
    类型 = 命令数量 | 参数数量 | 五类规则；DISTINCT 由缓存集合并集推导。

    逻辑网元语义：网元×版本模式下，语法类行按 (物理网元, 逻辑网元, 版本) 分行
    展示（物理级行为 logical=''，逻辑行为映射表粒度）；设了逻辑网元筛选则只看
    该逻辑网元的行 + 五类行（物理级语法行剔除，避免口径混淆）。其余汇总模式
    逻辑维度不存在，折叠到物理级。"""
    d = get()
    sel = _selected_types(f)
    rows: list[dict] = []

    def _syntax_rows(granularity: str) -> None:
        """granularity: nv=网元×版本(含逻辑行) / ne=仅网元 / version=仅版本 / all。"""
        if "cmd" not in sel and "param" not in sel:
            return
        if granularity == "nv":
            for (ne, ver), cell in d["syntax_nv"].items():
                if not (_nf_match_rule(f, ne) and _ver_match(f, ver)):
                    continue
                base = {"ne": ne, "logical": "", "version": ver}
                if f.logical_ne:
                    continue  # 逻辑筛选下物理级行剔除（逻辑行在下方）
                if "cmd" in sel:
                    rows.append({**base, "type": "命令数量", "count": len(cell["cmds"])})
                if "param" in sel:
                    rows.append({**base, "type": "参数数量", "count": cell["params"]})
            for r in d["lne_rows"]:
                if f.logical_ne and r["logi"] != f.logical_ne:
                    continue
                if not (_nf_match_rule(f, r["phys"]) and _ver_match(f, r["ver"])):
                    continue
                base = {"ne": r["phys"], "logical": r["logi"], "version": r["ver"]}
                if "cmd" in sel:
                    rows.append({**base, "type": "命令数量", "count": r["cmds"]})
                if "param" in sel:
                    rows.append({**base, "type": "参数数量", "count": r["params"]})
            return
        # 仅网元 / 仅版本 / 总计：集合并集推导 DISTINCT
        buckets: dict[str, dict] = {}
        for (ne, ver), cell in d["syntax_nv"].items():
            if not (_nf_match_rule(f, ne) and _ver_match(f, ver)):
                continue
            key = {"ne": ne, "version": ver, "all": ""}[granularity]
            b = buckets.setdefault(key, {"cmds": set(), "params": 0})
            b["cmds"] |= cell["cmds"]
            b["params"] += cell["params"]
        for key, b in buckets.items():
            base = {"ne": key if granularity == "ne" else "",
                    "logical": "", "version": key if granularity == "version" else ""}
            if "cmd" in sel:
                rows.append({**base, "type": "命令数量", "count": len(b["cmds"])})
            if "param" in sel:
                rows.append({**base, "type": "参数数量", "count": b["params"]})

    def _five_rows(granularity: str) -> None:
        for k, label in RULE_TYPES[2:]:
            if k not in sel:
                continue
            agg: dict[str, int] = {}
            for (ne, ver), n in d["five_nv"][k].items():
                if not (_nf_match_rule(f, ne) and _ver_match(f, ver)):
                    continue
                key = {"nv": f"{ne}\x00{ver}", "ne": ne, "version": ver, "all": ""}[granularity]
                agg[key] = agg.get(key, 0) + n
            for key, n in agg.items():
                if granularity == "nv":
                    ne, ver = key.split("\x00")
                    rows.append({"ne": ne, "logical": "", "version": ver,
                                 "type": label, "count": n})
                else:
                    rows.append({"ne": key if granularity == "ne" else "",
                                 "logical": "",
                                 "version": key if granularity == "version" else "",
                                 "type": label, "count": n})

    gran = {"ne_version": "nv", "ne": "ne", "version": "version", "all": "all"}.get(mode, "nv")
    _syntax_rows(gran)
    _five_rows(gran)
    _dress(rows, d, f, False)
    rows = core._sort_rows(rows, sort, _RULES_SORT)
    paged, total = core._paginate(rows, page, size)
    return {"rows": paged, "total": total, "cache": status()}


def feature_summary(f: Filters) -> dict:
    """特性卡片：数量默认不去重（知识条数），编号并集数为次级数字。"""
    d = get()
    fc: set = set()
    lc: set = set()
    fk = lk = 0
    for (nf, ver), cell in d["feature"].items():
        if not (_nf_match_obj(f, nf) and _ver_match(f, ver)):
            continue
        fc |= cell["fc"]
        lc |= cell["lc"]
        fk += cell["fk"]
        lk += cell["lk"]
    raw: dict[str, int] = {}
    for (nf, ver), rels in d["feature_edges"].items():
        if _nf_match_obj(f, nf) and _ver_match(f, ver):
            for rel, n in rels.items():
                raw[rel] = raw.get(rel, 0) + n
    merged, merged_total = merge_relations(raw)
    return {
        "view": "feature", "cache": status(),
        "feature_count": fk, "feature_codes": len(fc),
        "license_count": lk, "license_codes": len(lc),
        "edges": {
            "raw": sorted(raw.items(), key=lambda kv: -kv[1]),
            "merged": sorted(merged.items(), key=lambda kv: -kv[1]),
            "merged_total": merged_total,
        },
    }


_MATRIX_SORT = {"nf": "nf", "version": "version", "fcodes": "feature_codes",
                "fk": "feature_knowledge", "lcodes": "license_codes",
                "lk": "license_knowledge"}


def feature_matrix(f: Filters, page: int = 1, size: int = 20, sort: str = "-fk") -> dict:
    d = get()
    rows = [{
        "nf": nf, "version": ver,
        "feature_codes": len(cell["fc"]), "feature_knowledge": cell["fk"],
        "license_codes": len(cell["lc"]), "license_knowledge": cell["lk"],
    } for (nf, ver), cell in d["feature"].items()
        if _nf_match_obj(f, nf) and _ver_match(f, ver)]
    rows.sort(key=lambda r: (r["nf"], r["version"]))
    _dress(rows, d, f, True)
    rows = core._sort_rows(rows, sort, _MATRIX_SORT)
    paged, total = core._paginate(rows, page, size)
    return {"rows": paged, "total": total}


def business_overview() -> dict:
    d = get()
    out = dict(d["business"])
    out["counts"] = {k: v for k, v in out.get("counts", {}).items()
                     if k not in ("task_cmd_edges", "task_feature_edges")}
    out.pop("filters", None)
    out["cache"] = status()
    return out


def filters_options() -> dict:
    d = get()
    out = dict(d["filters"])
    out["cache"] = status()
    return out
