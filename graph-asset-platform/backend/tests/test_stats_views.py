"""统计页三视图端点测试（2026-09-02 改版：卡片/表格分离 + 服务端分页 + MOP）。

种子为合成小数据，期望值按《图谱平台统计页面需求说明书》§4/§5/§7 口径手算。
导出端点（保留未动）一并覆盖；老 GET /api/v1/stats 的回归由
test_api_assets.test_stats_ui_layer_aggregation 覆盖。
"""
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ---------- 种子 ----------

def _obj(conn, oid, version, type_, *, layer="", nf=None, domain=None,
         scenario=None, fm: dict | None = None, name=""):
    conn.execute(
        "INSERT OR REPLACE INTO objects(id,version,type,layer,scope,nf,domain,"
        "scenario,source_path,name,frontmatter_json,body_md,raw_md,mtime) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (oid, version, type_, layer, "", nf, domain, scenario,
         f"src/{oid}.md", name or oid,
         json.dumps(fm, ensure_ascii=False) if fm else None, "", "", 0.0))


def _edge(conn, fid, fver, rel, to):
    conn.execute(
        "INSERT OR REPLACE INTO edges(from_id,from_version,relation,\"to\") "
        "VALUES(?,?,?,?)", (fid, fver, rel, to))


def _seed_objects(conn):
    # 命令图谱：PCF 20.10.2 (3 cmd + 2 cfg) / PCF 20.16.2 (2 cmd) / UDG 20.10.2 (2 cmd + 1 cfg)
    for i in range(3):
        _obj(conn, f"MMLCommand@CMD_{i}", "20.10.2", "MMLCommand",
             layer="Command", nf="PCF")
    for i in range(2):
        _obj(conn, f"MMLCommand@CMDX_{i}", "20.16.2", "MMLCommand",
             layer="Command", nf="PCF")
    for i in range(2):
        _obj(conn, f"MMLCommand@UCMD_{i}", "20.10.2", "MMLCommand",
             layer="Command", nf="UDG")
    _obj(conn, "ConfigObject@CFG_0", "20.10.2", "ConfigObject", layer="Command", nf="PCF")
    _obj(conn, "ConfigObject@CFG_1", "20.10.2", "ConfigObject", layer="Command", nf="PCF")
    _obj(conn, "ConfigObject@UCFG_0", "20.10.2", "ConfigObject", layer="Command", nf="UDG")
    # 特性图谱：UDG 20.10.2 特性 3 条（编号 2 个）、PCF 20.16.2 特性 2 条（2 个）
    _obj(conn, "Feature@F_0", "20.10.2", "Feature", layer="Feature", nf="UDG",
         fm={"feature_code": "WHFD-1"})
    _obj(conn, "Feature@F_1", "20.10.2", "Feature", layer="Feature", nf="UDG",
         fm={"feature_code": "WHFD-1"})
    _obj(conn, "Feature@F_2", "20.10.2", "Feature", layer="Feature", nf="UDG",
         fm={"feature_code": "WHFD-2"})
    _obj(conn, "Feature@P_0", "20.16.2", "Feature", layer="Feature", nf="PCF",
         fm={"feature_code": "WHFD-3"})
    _obj(conn, "Feature@P_1", "20.16.2", "Feature", layer="Feature", nf="PCF",
         fm={"feature_code": "GWFD-9"})
    _obj(conn, "License@L_0", "20.10.2", "License", layer="Feature", nf="UDG",
         fm={"license_code": "LIC-1"})
    _obj(conn, "License@L_1", "20.10.2", "License", layer="Feature", nf="UDG",
         fm={"license_code": "LIC-1"})
    # 业务图谱：任务（UNC/UDG，version 空串）+ 域/场景/方案
    _obj(conn, "AtomTask@A_0", "", "AtomTask", layer="Business", nf="UNC",
         domain="business-awareness", scenario="access-control")
    _obj(conn, "AtomTask@A_1", "", "AtomTask", layer="Business", nf="UNC",
         domain="business-awareness", scenario="access-control")
    _obj(conn, "AtomTask@A_2", "", "AtomTask", layer="Business", nf="UDG",
         domain="apn-domain", scenario="apn-access")
    _obj(conn, "FeatureTask@FT_0", "", "FeatureTask", layer="Business", nf="UNC",
         domain="business-awareness", scenario="access-control")
    _obj(conn, "FeatureTask@FT_1", "", "FeatureTask", layer="Business", nf="UDG",
         domain="apn-domain", scenario="apn-access")
    _obj(conn, "CompoundTask@CT_0", "", "CompoundTask", layer="Business", nf="UNC",
         domain="business-awareness", scenario="access-control")
    _obj(conn, "ConfigurationSolution@S_0", "", "ConfigurationSolution",
         layer="Business", domain="business-awareness", scenario="access-control",
         name="策略匹配基础")
    _obj(conn, "ConfigurationSolution@S_1", "", "ConfigurationSolution",
         layer="Business", domain="business-awareness", scenario="access-control",
         name="URL 过滤")
    _obj(conn, "ConfigurationSolution@S_2", "", "ConfigurationSolution",
         layer="Business", domain="apn-domain", scenario="apn-access", name="地址分配")
    _obj(conn, "NetworkScenario@NS_0", "", "NetworkScenario", layer="Business",
         domain="business-awareness", scenario="access-control", name="访问控制")
    _obj(conn, "NetworkScenario@NS_1", "", "NetworkScenario", layer="Business",
         domain="apn-domain", scenario="apn-access", name="APN 接入")
    _obj(conn, "BusinessDomain@BD_0", "", "BusinessDomain", layer="Business",
         domain="business-awareness", name="业务感知")
    _obj(conn, "BusinessDomain@BD_1", "", "BusinessDomain", layer="Business",
         domain="apn-domain", name="APN 域")


def _seed_edges(conn):
    # 命令图谱出边：参见1；操作配置对象3 / 被操作2（成对应取大=3）
    _edge(conn, "MMLCommand@CMD_0", "20.10.2", "参见", "MMLCommand@CMD_1")
    for f, t in (("MMLCommand@CMD_0", "ConfigObject@CFG_0"),
                 ("MMLCommand@CMD_0", "ConfigObject@CFG_1"),
                 ("MMLCommand@CMD_1", "ConfigObject@CFG_0")):
        _edge(conn, f, "20.10.2", "操作配置对象", t)
    for t in ("MMLCommand@CMD_0", "MMLCommand@CMD_1"):
        _edge(conn, "ConfigObject@CFG_0", "20.10.2", "被操作", t)
    # 特性图谱出边：使用命令2 / 属于特性1 / 包含子文档2（合并取大=2）/ 依赖1 / 对应1 / License1
    _edge(conn, "Feature@F_0", "20.10.2", "使用命令", "MMLCommand@CMD_0")
    _edge(conn, "Feature@F_1", "20.10.2", "使用命令", "MMLCommand@CMD_1")
    _edge(conn, "Feature@F_0", "20.10.2", "属于特性", "Feature@F_2")
    _edge(conn, "Feature@F_2", "20.10.2", "包含子文档", "Feature@F_0")
    _edge(conn, "Feature@F_2", "20.10.2", "包含子文档", "Feature@F_1")
    _edge(conn, "Feature@F_1", "20.10.2", "依赖特性", "Feature@F_0")
    _edge(conn, "Feature@F_0", "20.10.2", "对应特性", "Feature@F_1")
    _edge(conn, "Feature@F_0", "20.10.2", "所需License", "License@L_0")
    # 业务图谱出边：对应命令1 / 对应特性(任务→特性)1 / 编排4 / 组成复用3 / 上下游引用7 / 合并计 16
    _edge(conn, "AtomTask@A_0", "", "对应命令", "MMLCommand@CMD_0")
    _edge(conn, "FeatureTask@FT_0", "", "对应特性", "Feature@F_0")
    _edge(conn, "CompoundTask@CT_0", "", "编排", "AtomTask@A_0")
    _edge(conn, "CompoundTask@CT_0", "", "编排 atom", "AtomTask@A_1")
    _edge(conn, "ConfigurationSolution@S_0", "", "编排 compound", "CompoundTask@CT_0")
    _edge(conn, "FeatureTask@FT_0", "", "编排特性", "Feature@F_2")
    _edge(conn, "ConfigurationSolution@S_0", "", "组成", "CompoundTask@CT_0")
    _edge(conn, "FeatureTask@FT_0", "", "复用步骤", "CompoundTask@CT_0")
    _edge(conn, "FeatureTask@FT_0", "", "复用命令", "MMLCommand@CMD_1")
    _edge(conn, "BusinessDomain@BD_0", "", "上游", "NetworkScenario@NS_0")
    _edge(conn, "BusinessDomain@BD_1", "", "上游", "NetworkScenario@NS_1")
    _edge(conn, "NetworkScenario@NS_0", "", "下游", "BusinessDomain@BD_0")
    _edge(conn, "NetworkScenario@NS_0", "", "上游场景", "ConfigurationSolution@S_0")
    _edge(conn, "ConfigurationSolution@S_0", "", "下游方案", "NetworkScenario@NS_0")
    _edge(conn, "BusinessDomain@BD_0", "", "下游场景", "NetworkScenario@NS_0")
    _edge(conn, "NetworkScenario@NS_0", "", "上游域", "BusinessDomain@BD_0")
    _edge(conn, "CompoundTask@CT_0", "", "被引用于", "ConfigurationSolution@S_0")
    _edge(conn, "FeatureTask@FT_0", "", "直接引用 atom", "AtomTask@A_0")
    _edge(conn, "FeatureTask@FT_0", "", "依赖条件", "FeatureTask@FT_1")


def _seed_rules(conn):
    rows = [
        ("CMD_A", "1", "UPCF", "20.10.2"), ("CMD_A", "2", "UPCF", "20.10.2"),
        ("CMD_B", "1", "UPCF", "20.10.2"),
        ("CMD_X", "1", "UDG", "20.10.2"), ("CMD_X", "2", "UDG", "20.10.2"),
        ("CMD_A", "3", "UNC", "20.10.2"),
    ]
    conn.executemany(
        'INSERT INTO "B_AI_COMMAND_SYNTAX_CHECK_RULES"("CMD_NAME","PARAM_ID",'
        '"NE_TYPE","NE_VERSION") VALUES(?,?,?,?)', rows)
    conn.executemany(
        'INSERT INTO "B_AI_CONFIG_CHECK_LOGICAL_NE_CMD_T"("PHYSICAL_NE_TYPE",'
        '"LOGICAL_NE_TYPE","NE_VERSION","COMMAND_NAME") VALUES(?,?,?,?)',
        [("UNC", "SMF", "20.10.2", "CMD_A"), ("UNC", "AMF", "20.10.2", "CMD_Z")])
    conn.executemany(
        'INSERT INTO "B_AI_MML_GRAPH_RULE_T"("PHYSICAL_NE_TYPE","NE_VERSION",'
        '"COMMAND_NAME") VALUES(?,?,?)',
        [("UPCF", "20.10.2", "CMD_A"), ("UPCF", "20.10.2", "CMD_B"),
         ("UDG", "20.10.2", "CMD_X")])
    conn.executemany(
        'INSERT INTO "B_AI_MML_REPEAT_CHECK_RULE_T"("PHYSICAL_NE_TYPE","NE_VERSION",'
        '"COMMAND_NAME") VALUES(?,?,?)',
        [("UPCF", "20.10.2", "CMD_A"), ("UPCF", "20.10.2", "CMD_B")])
    conn.execute(
        'INSERT INTO "B_AI_MOD_RULE_T"("NE_TYPE","NE_VERSION","MOD_CMD") '
        'VALUES(?,?,?)', ("UDG", "20.10.2", "MOD MMASI"))
    conn.executemany(
        'INSERT INTO "B_AI_MML_SET_CHECK_RULE_T"("NE_TYPE","NE_VERSION","CMD_NAME") '
        'VALUES(?,?,?)', [("UPCF", "20.10.2", "SET DEFNCC")] * 2)
    conn.execute(
        'INSERT INTO "B_AI_DELETE_RULE_V2_T"("NE_TYPE","NE_VERSION","EXCUTE_CMD") '
        'VALUES(?,?,?)', ("UDG", "20.10.2", "RMV MGWPATH"))
    conn.executemany(
        'INSERT INTO "B_AI_NE_VERSION_MAPPING_T"("PHYSICAL_NE_TYPE","LOGICAL_NE_TYPE",'
        '"LOCAL_VERSION","OVERSEAS_VERSION") VALUES(?,?,?,?)',
        [("UPCF", "PCF", "20.10.2", "23.1.0"),
         ("UPCF", "PCF", "20.16.2", "26.0.0"),
         ("UPCF", "PCF", "20.16.2", "26.0.1"),
         ("UDG", "UPF", "20.10.2", "22.1.0")])
    conn.commit()


@pytest.fixture
def seeded():
    import app.db as dbmod
    conn = dbmod.get_shared_db()
    _seed_objects(conn)
    _seed_edges(conn)
    _seed_rules(conn)
    return conn


client = TestClient(app)


def _get(path: str) -> dict:
    r = client.get(path)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 命令图谱：卡片摘要 ----------

def test_command_summary_full(seeded):
    d = _get("/api/v1/stats/command/summary")
    assert d["knowledge"] == {"MMLCommand": 7, "ConfigObject": 3, "points": 10}
    merged = dict(d["edges"]["merged"])
    assert merged["操作配置对象/被操作"] == 3
    assert d["edges"]["merged_total"] == 4
    inbound = dict(d["inbound"]["raw"])
    assert inbound == {"使用命令": 2, "对应命令": 1, "复用命令": 1}  # 跨图谱入边
    assert "syntax" not in d["rules"]  # 命令/参数卡片已删（数值进规则表类型维度）
    assert d["rules"]["graph"] == 3
    assert d["five_total"] == 9


def test_command_summary_upcf_and_version(seeded):
    d = _get("/api/v1/stats/command/summary?nfs=UPCF")
    assert d["knowledge"] == {"MMLCommand": 5, "ConfigObject": 2, "points": 7}
    assert d["rules"]["graph"] == 2  # 规则表系原生命名直配（UDG 行剔除）
    d2 = _get("/api/v1/stats/command/summary?versions=20.16.2")
    assert d2["knowledge"]["points"] == 2
    assert d2["rules"]["graph"] == 0


def test_old_view_endpoints_removed(seeded):
    """2026-09-02 改版：旧 /command /feature /business 整体端点已拆分为 summary/表。"""
    assert client.get("/api/v1/stats/command").status_code == 404
    assert client.get("/api/v1/stats/feature").status_code == 404
    assert client.get("/api/v1/stats/business").status_code == 404


# ---------- 命令图谱：知识统计表（含出/入边并入 + 分页）----------

def test_command_knowledge_rows(seeded):
    d = _get("/api/v1/stats/command/knowledge")
    m = {(r["nf"], r["version"]): r for r in d["rows"]}
    p = m[("PCF", "20.10.2")]
    # 出边=6（参见1+操作3+被操作2，from 都在 PCF/20.10.2）；
    # 入边=10（参见1+操作3+被操作2+使用命令2+对应命令1+复用命令1，按 id 落槽位）
    assert (p["cmd_knowledge"], p["cfg_knowledge"], p["total_knowledge"]) == (3, 2, 5)
    assert (p["out_edges"], p["in_edges"]) == (6, 10)
    assert p["nf_display"] == "UPCF"
    assert m[("UDG", "20.10.2")]["total_knowledge"] == 3
    assert m[("UDG", "20.10.2")]["out_edges"] == 0
    assert m[("PCF", "20.16.2")]["in_edges"] == 0
    assert d["total"] == 3


def test_command_knowledge_pagination_and_sort(seeded):
    d = _get("/api/v1/stats/command/knowledge?page=1&size=2&sort=-total")
    assert len(d["rows"]) == 2 and d["total"] == 3
    assert d["rows"][0]["total_knowledge"] == 5  # 降序
    d2 = _get("/api/v1/stats/command/knowledge?page=2&size=2&sort=-total")
    assert len(d2["rows"]) == 1


def test_command_knowledge_filters(seeded):
    d = _get("/api/v1/stats/command/knowledge?nfs=UPCF")
    assert {r["nf"] for r in d["rows"]} == {"PCF"}
    assert d["total"] == 2
    d2 = _get("/api/v1/stats/command/knowledge?versions=20.16.2")
    assert d2["total"] == 1
    assert d2["rows"][0]["total_knowledge"] == 2


def test_command_knowledge_overseas_display(seeded):
    d = _get("/api/v1/stats/command/knowledge?overseas=true")
    m = {(r["nf"], r["version"]): r for r in d["rows"]}
    assert m[("PCF", "20.10.2")]["version_display"] == "23.1.0"
    assert m[("PCF", "20.16.2")]["version_display"] == "26.0.0/26.0.1"


# ---------- 命令图谱：语法规则统计总表（mode 切换 + 分页）----------

def test_command_rules_long_table(seeded):
    """规则长表（2026-09-02 需求 6）：网元/逻辑网元/版本/类型/数量；
    类型=命令数量|参数数量|五类；逻辑网元按映射表分行（物理级行 logical=''）。"""
    d = _get("/api/v1/stats/command/rules")
    m = {(r["ne"], r["logical"], r["version"], r["type"]): r["count"] for r in d["rows"]}
    # 物理级语法行 ×3 网元（每网元 命令+参数 两行）
    assert m[("UPCF", "", "20.10.2", "命令数量")] == 2
    assert m[("UPCF", "", "20.10.2", "参数数量")] == 3
    assert m[("UDG", "", "20.10.2", "命令数量")] == 1
    assert m[("UNC", "", "20.10.2", "命令数量")] == 1
    assert m[("UNC", "", "20.10.2", "参数数量")] == 1
    # 逻辑网元行：UNC/SMF→{CMD_A} 命中语法 1 命令 1 参数；AMF→CMD_Z 未命中无行
    assert m[("UNC", "SMF", "20.10.2", "命令数量")] == 1
    assert m[("UNC", "SMF", "20.10.2", "参数数量")] == 1
    assert not any(r["logical"] == "AMF" for r in d["rows"])
    # 五类行
    assert m[("UPCF", "", "20.10.2", "图规则")] == 2
    assert m[("UDG", "", "20.10.2", "删除规则")] == 1
    assert d["total"] == 14  # 3 物理级语法×2 + SMF 逻辑×2 + 五类 6


def test_command_rules_modes(seeded):
    d = _get("/api/v1/stats/command/rules?mode=ne")
    m = {(r["ne"], r["type"]): r["count"] for r in d["rows"]}
    assert m[("UPCF", "命令数量")] == 2 and m[("UPCF", "参数数量")] == 3
    assert m[("UNC", "命令数量")] == 1
    assert not any(r["logical"] for r in d["rows"])  # 汇总模式无逻辑维度
    d2 = _get("/api/v1/stats/command/rules?mode=all")
    m2 = {r["type"]: r["count"] for r in d2["rows"]}
    assert (m2["命令数量"], m2["参数数量"]) == (3, 6)  # 全局 DISTINCT=3，行数=6
    assert m2["图规则"] == 3
    assert d2["total"] == 7


def test_command_rules_filters(seeded):
    # 类型筛选：只看命令数量 → 3 物理级 + 1 逻辑行
    d = _get("/api/v1/stats/command/rules?rule_types=cmd")
    assert d["total"] == 4
    assert {r["type"] for r in d["rows"]} == {"命令数量"}
    # 逻辑网元筛选：语法行只剩该逻辑网元行，五类不受影响
    d2 = _get("/api/v1/stats/command/rules?logical_ne=SMF")
    syn = [r for r in d2["rows"] if r["type"] in ("命令数量", "参数数量")]
    assert {(r["ne"], r["logical"], r["type"], r["count"]) for r in syn} == {
        ("UNC", "SMF", "命令数量", 1), ("UNC", "SMF", "参数数量", 1)}
    assert sum(1 for r in d2["rows"] if r["type"] == "图规则") == 2
    # 版本筛选
    assert _get("/api/v1/stats/command/rules?versions=20.16.2")["total"] == 0
    # 分页
    d3 = _get("/api/v1/stats/command/rules?page=2&size=5")
    assert len(d3["rows"]) == 5 and d3["total"] == 14


def test_cache_refresh(seeded):
    d = _get("/api/v1/stats/command/summary")
    assert d["cache"]["built_at"] > 0
    r = client.post("/api/v1/stats/cache/refresh")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # 重建后（同步等待或短暂轮询）数据仍可用且口径不变
    for _ in range(50):
        if not _get("/api/v1/stats/filters")["cache"]["building"]:
            break
        import time as _t
        _t.sleep(0.1)
    d2 = _get("/api/v1/stats/command/summary")
    assert d2["knowledge"]["points"] == 10


# ---------- 特性图谱：默认不去重 ----------

def test_feature_summary_default_no_dedupe(seeded):
    d = _get("/api/v1/stats/feature/summary")
    assert d["feature_count"] == 5     # 不去重（知识条数）
    assert d["feature_codes"] == 4     # 去重为次级数字
    assert d["license_count"] == 2
    assert d["license_codes"] == 1
    assert dict(d["edges"]["merged"])["包含子文档/属于特性"] == 2


def test_feature_matrix_paginated(seeded):
    d = _get("/api/v1/stats/feature/matrix")
    assert d["total"] == 2
    m = {(r["nf"], r["version"]): r for r in d["rows"]}
    u = m[("UDG", "20.10.2")]
    assert (u["feature_codes"], u["feature_knowledge"],
            u["license_codes"], u["license_knowledge"]) == (2, 3, 1, 2)
    d2 = _get("/api/v1/stats/feature/matrix?nfs=UPCF&page=1&size=1")
    assert d2["total"] == 1
    assert d2["rows"][0]["nf"] == "PCF"


# ---------- 业务图谱：无筛选 + 无 D7/D7b ----------

def test_business_overview(seeded):
    d = _get("/api/v1/stats/business/overview")
    c = d["counts"]
    assert c["domains"] == 2 and c["scenarios"] == 2 and c["solutions"] == 3
    assert c["atom_tasks"] == 3 and c["feature_tasks"] == 2 and c["compound_tasks"] == 1
    assert "task_cmd_edges" not in c and "task_feature_edges" not in c  # 已删
    assert "filters" not in d
    sm = {(r["domain"], r["scenario"]): r for r in d["solutions_matrix"]}
    assert sm[("business-awareness", "access-control")]["count"] == 2
    tm = {(r["type"], r["nf"]): r["count"] for r in d["tasks_matrix"]}
    assert tm[("AtomTask", "UNC")] == 2
    g = d["edges"]["groups"]
    assert (g["编排关系"], g["组成/复用"], g["上下游/引用"], g["跨图谱任务关联"]) == (4, 3, 7, 2)


# ---------- /filters + 空表 ----------

def test_filters_options(seeded):
    d = _get("/api/v1/stats/filters")
    assert "UDG" in d["nfs"] and "UPCF" in d["nfs"] and "UNC" in d["nfs"]
    assert d["logical_nes"] == {"UNC": ["AMF", "SMF"]}
    assert {x["key"] for x in d["rule_types"]} == {
        "cmd", "param", "graph", "repeat", "mod", "set", "delete"}
    assert d["table_rows"]["B_AI_MML_GRAPH_RULE_T"] == 3


def test_filters_empty_rule_tables():
    d = _get("/api/v1/stats/filters")
    assert d["table_rows"]["B_AI_COMMAND_SYNTAX_CHECK_RULES"] == 0
    assert _get("/api/v1/stats/command/summary")["five_total"] == 0


# ---------- MOP 动网变更场景统计 ----------

_MOP_ROWS = [
    ("核心网改造", "5GC扩容", "AMF扩容"),
    ("核心网改造", "5GC扩容", "SMF扩容"),
    ("核心网改造", "语音改造", ""),
    ("传输调整", "", ""),
]


def _mop_xlsx_inline() -> bytes:
    """inlineStr 版 xlsx（用我们自己的 export.render_xlsx 生成——写读互证）。"""
    from app.stats.export import render_xlsx
    headers = ["编号", "L1场景", "L2场景", "L3场景", "备注"]
    rows = [[str(i), r[0], r[1], r[2], ""] for i, r in enumerate(_MOP_ROWS)]
    return render_xlsx([("MOP", headers, rows)])


def _mop_xlsx_shared() -> bytes:
    """sharedStrings 版最小 xlsx（真实 Excel 的常见形态）。"""
    strings = ["编号", "L1场景", "L2场景", "L3场景", "备注"]
    cells = []
    si = len(strings)
    for i, r in enumerate(_MOP_ROWS, start=2):
        strings.extend([str(i), r[0], r[1], r[2]])
        cells.append(f'<row r="{i}">'
                     f'<c r="A{i}" t="s"><v>{si}</v></c>'
                     f'<c r="B{i}" t="s"><v>{si + 1}</v></c>'
                     f'<c r="C{i}" t="s"><v>{si + 2}</v></c>'
                     f'<c r="D{i}" t="s"><v>{si + 3}</v></c>'
                     f"</row>")
        si += 4
    ss = ('<?xml version="1.0" encoding="UTF-8"?>'
          '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
          + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
    sheet = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetData><row r="1">'
             + "".join(f'<c r="{ch}1" t="s"><v>{j}</v></c>'
                       for j, ch in enumerate("ABCDE", start=0))
             + "</row>" + "".join(cells) + "</sheetData></worksheet>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/sharedStrings.xml", ss)
    return buf.getvalue()


@pytest.mark.parametrize("maker", [_mop_xlsx_inline, _mop_xlsx_shared],
                         ids=["inlineStr", "sharedStrings"])
def test_mop_aggregate(tmp_data_dir, maker):
    (tmp_data_dir.parent / "mop_scenarios.xlsx").write_bytes(maker())
    d = _get("/api/v1/stats/mop?level=1")
    assert d["available"] and d["total"] == 4 and d["max_level"] == 3
    assert d["rows"] == [
        {"path": ["核心网改造"], "count": 3, "ratio": 0.75},
        {"path": ["传输调整"], "count": 1, "ratio": 0.25},
    ]
    d2 = _get("/api/v1/stats/mop?level=2")
    assert d2["rows"][0] == {"path": ["核心网改造", "5GC扩容"], "count": 2, "ratio": 0.5}
    assert {"path": ["传输调整", ""], "count": 1, "ratio": 0.25} in d2["rows"]
    d3 = _get("/api/v1/stats/mop?level=4")  # 超过 max_level 聚合到 L3 值（L4 空）
    assert any(r["path"] == ["核心网改造", "5GC扩容", "AMF扩容", ""]
               for r in d3["rows"])


def test_mop_csv_and_missing(tmp_data_dir):
    (tmp_data_dir.parent / "mop_scenarios.csv").write_bytes(
        "编号,L1场景,L2场景\n1,割接,主设备\n2,割接,传输\n".encode("utf-8"))
    d = _get("/api/v1/stats/mop")
    assert d["available"] and d["total"] == 2 and d["max_level"] == 2
    assert d["rows"][0]["path"] == ["割接"]
    d2 = _get("/api/v1/stats/mop?level=2")
    assert {(r["path"][1], r["count"]) for r in d2["rows"]} == {("主设备", 1), ("传输", 1)}


def test_mop_not_uploaded(tmp_data_dir):
    d = _get("/api/v1/stats/mop")
    assert d["available"] is False and d["rows"] == []


def test_mop_upload_admin_and_errors(tmp_data_dir, monkeypatch):
    # 非 admin 403（真中间件：state.user_obj 来自 authenticate）
    from app.middleware import auth as auth_mod
    monkeypatch.setattr(auth_mod, "authenticate", lambda key: {
        "username": "u", "can_frontend": True, "is_admin": False})
    r = client.put("/api/v1/stats/mop/source?filename=a.xlsx", content=b"x")
    assert r.status_code == 403
    # 恢复 admin（conftest 的 stub）再上传
    monkeypatch.setattr(auth_mod, "authenticate", lambda key: {
        "username": "admin", "can_frontend": True, "is_admin": True})
    r2 = client.put("/api/v1/stats/mop/source?filename=底表.xlsx",
                    content=_mop_xlsx_inline())
    assert r2.status_code == 200, r2.text
    assert r2.json() == {"ok": True, "saved": "mop_scenarios.xlsx",
                         "mop_total": 4, "levels_found": [1, 2, 3]}
    assert _get("/api/v1/stats/mop?level=1")["total"] == 4
    # 换 csv：xlsx 旧文件被清掉
    csv_bytes = "编号,L1场景\n1,割接\n".encode("utf-8")
    r3 = client.put("/api/v1/stats/mop/source?filename=b.csv", content=csv_bytes)
    assert r3.status_code == 200
    assert not (tmp_data_dir.parent / "mop_scenarios.xlsx").exists()
    # 坏文件 400（无 L1场景 列）
    bad = ("编号,其他\n1,x\n").encode("utf-8")
    assert client.put("/api/v1/stats/mop/source?filename=c.csv",
                      content=bad).status_code == 400
    assert client.put("/api/v1/stats/mop/source?filename=c.txt",
                      content=b"").status_code == 400


# ---------- 导出（保留端点，前端入口已隐藏）----------

def test_export_csv(seeded):
    r = client.get("/api/v1/stats/export?view=command&format=csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "# 命令图谱·汇总" in r.text
    assert "命令知识条数(A1)" in r.text


def test_export_xlsx(seeded):
    r = client.get("/api/v1/stats/export?view=feature&format=xlsx")
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert "xl/workbook.xml" in z.namelist()
    assert "特性编号数(C1)" in z.read("xl/worksheets/sheet1.xml").decode("utf-8")


def test_export_bad_params(seeded):
    assert client.get("/api/v1/stats/export?view=nope").status_code == 400
    assert client.get("/api/v1/stats/export?view=command&format=pdf").status_code == 400
