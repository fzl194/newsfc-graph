"""统计页三视图（/api/v1/stats/*）端到端测试。

种子为合成小数据，期望值按《图谱平台统计页面需求说明书》§4/§5/§7 口径手算，
用例编号映射 §11 验收 Case 1-10 的语义（合并取大、UPCF 别名、版本归一、
逻辑网元仅作用 B1/B2、导出三格式）。老 GET /api/v1/stats 的回归由
test_api_assets.test_stats_ui_layer_aggregation 覆盖。
"""
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
         domain="business-awareness", scenario="access-control")
    _obj(conn, "NetworkScenario@NS_1", "", "NetworkScenario", layer="Business",
         domain="apn-domain", scenario="apn-access")
    _obj(conn, "BusinessDomain@BD_0", "", "BusinessDomain", layer="Business",
         domain="business-awareness")
    _obj(conn, "BusinessDomain@BD_1", "", "BusinessDomain", layer="Business",
         domain="apn-domain")


def _seed_edges(conn):
    # 命令图谱出边：参见1；操作配置对象3 / 被操作2（成对应取大=3，Case 8）
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
    # 语法规则表：UPCF 20.10.2 (2 命令 3 参数) + UDG 20.10.2 (1 命令 2 参数)
    rows = [
        ("CMD_A", "1", "UPCF", "20.10.2"), ("CMD_A", "2", "UPCF", "20.10.2"),
        ("CMD_B", "1", "UPCF", "20.10.2"),
        ("CMD_X", "1", "UDG", "20.10.2"), ("CMD_X", "2", "UDG", "20.10.2"),
    ]
    conn.executemany(
        'INSERT INTO "B_AI_COMMAND_SYNTAX_CHECK_RULES"("CMD_NAME","PARAM_ID",'
        '"NE_TYPE","NE_VERSION") VALUES(?,?,?,?)', rows)
    # 逻辑网元：UNC/SMF→{CMD_A}；UNC/AMF→{CMD_Z}
    conn.executemany(
        'INSERT INTO "B_AI_CONFIG_CHECK_LOGICAL_NE_CMD_T"("PHYSICAL_NE_TYPE",'
        '"LOGICAL_NE_TYPE","NE_VERSION","COMMAND_NAME") VALUES(?,?,?,?)',
        [("UNC", "SMF", "20.10.2", "CMD_A"), ("UNC", "AMF", "20.10.2", "CMD_Z")])
    # 五类规则：graph3 / repeat2 / mod1 / set2 / delete1 → five_total=9
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
    # 版本映射：UPCF 20.10.2→23.1.0；20.16.2→26.0.0 与 26.0.1（多海外版并列）；UDG 20.10.2→22.1.0
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


# ---------- Case 1/2：命令总览 + 网元×版本矩阵 ----------

def test_command_overview_full(seeded):
    d = _get("/api/v1/stats/command")
    assert d["knowledge"] == {"MMLCommand": 7, "ConfigObject": 3, "points": 10}
    # 出边合并取大：参见1 + 操作配置对象/被操作 max(3,2)=3 → 4
    merged = dict(d["edges"]["merged"])
    assert merged["操作配置对象/被操作"] == 3
    assert merged["参见"] == 1
    assert d["edges"]["merged_total"] == 4
    raw = dict(d["edges"]["raw"])
    assert raw["被操作"] == 2 and raw["操作配置对象"] == 3
    # 入边（跨图谱）：使用命令2 + 对应命令1 + 复用命令1（FT→命令）；
    # 图谱内部边（参见/操作配置对象/被操作）已在 A4 出边计，不入 A5
    inbound = dict(d["inbound"]["raw"])
    assert inbound == {"使用命令": 2, "对应命令": 1, "复用命令": 1}
    # B 区
    assert d["rules"]["syntax"] == {
        "cmd_count": 3, "param_count": 5, "cmd_count_by_group_sum": 3}
    assert d["rules"]["graph"] == 3
    assert d["rules"]["repeat"] == 2
    assert d["rules"]["mod"] == 1
    assert d["rules"]["set"] == 2
    assert d["rules"]["delete"] == 1
    assert d["five_total"] == 9


def test_command_matrix_and_syntax_matrix(seeded):
    d = _get("/api/v1/stats/command")
    m = {(r["nf"], r["version"]): r for r in d["matrix"]}
    assert m[("PCF", "20.10.2")]["MMLCommand"] == 3
    assert m[("PCF", "20.10.2")]["ConfigObject"] == 2
    assert m[("PCF", "20.10.2")]["total"] == 5
    assert m[("PCF", "20.16.2")]["total"] == 2
    assert m[("UDG", "20.10.2")]["total"] == 3
    sm = {(r["ne"], r["version"]): r for r in d["syntax_matrix"]}
    upcf_row = sm[("UPCF", "20.10.2")]
    assert upcf_row["cmd_count"] == 2 and upcf_row["param_count"] == 3
    assert upcf_row["version_display"] == "20.10.2"
    assert sm[("UDG", "20.10.2")]["cmd_count"] == 1
    gm = {(r["ne"], r["version"]): r["count"] for r in d["rule_matrix"]["graph"]}
    assert gm == {("UPCF", "20.10.2"): 2, ("UDG", "20.10.2"): 1}


# ---------- Case 8/10：双向合并 + UPCF 别名 ----------

def test_upcf_alias_filter(seeded):
    d = _get("/api/v1/stats/command?nfs=UPCF")
    assert d["knowledge"] == {"MMLCommand": 5, "ConfigObject": 2, "points": 7}
    assert d["rules"]["syntax"]["cmd_count"] == 2   # CMD_X(UDG) 排除
    assert d["rules"]["graph"] == 2
    assert {r["nf"] for r in d["matrix"]} == {"PCF"}
    assert all(r["nf_display"] == "UPCF" for r in d["matrix"])  # 展示归一


def test_version_filter_cross_sources(seeded):
    d = _get("/api/v1/stats/command?versions=20.16.2")
    assert d["knowledge"]["points"] == 2            # 仅 PCF 20.16.2 两命令
    assert d["rules"]["syntax"]["param_count"] == 0  # 规则表同受版本筛选
    assert d["rules"]["graph"] == 0


def test_relation_filter(seeded):
    d = _get("/api/v1/stats/feature?relations=使用命令")
    assert dict(d["edges"]["raw"]) == {"使用命令": 2}
    assert d["edges"]["merged_total"] == 2


def test_rule_types_filter(seeded):
    d = _get("/api/v1/stats/command?rule_types=graph")
    assert set(d["rules"]) == {"graph"}
    assert d["rules"]["graph"] == 3
    assert d["five_total"] == 3
    assert set(d["rule_matrix"]) == {"graph"}


def test_object_types_filter(seeded):
    d = _get("/api/v1/stats/command?object_types=MMLCommand")
    assert d["knowledge"] == {"MMLCommand": 7, "ConfigObject": 0, "points": 7}


def test_relation_filter_single_pair_member(seeded):
    """成对关系只筛一侧：合并键取该侧计数（§7.1 单侧成员路径）。"""
    d = _get("/api/v1/stats/command?relations=被操作")
    assert dict(d["edges"]["raw"]) == {"被操作": 2}
    assert dict(d["edges"]["merged"]) == {"操作配置对象/被操作": 2}
    assert d["edges"]["merged_total"] == 2


def test_object_types_empty_intersection(seeded):
    """对象类型筛选与视图类型集交集为空 → 1=0 短路（不 500）。"""
    d = _get("/api/v1/stats/command?object_types=Feature")
    assert d["knowledge"] == {"MMLCommand": 0, "ConfigObject": 0, "points": 0}
    assert d["matrix"] == []
    assert d["edges"]["merged_total"] == 0


# ---------- Case 5/6：特性图谱 ----------

def test_feature_view(seeded):
    d = _get("/api/v1/stats/feature")
    assert d["totals"] == {"feature_codes": 4, "feature_knowledge": 5,
                           "license_codes": 1, "license_knowledge": 2}
    m = {(r["nf"], r["version"]): r for r in d["matrix"]}
    assert m[("UDG", "20.10.2")]["feature_codes"] == 2
    assert m[("UDG", "20.10.2")]["feature_knowledge"] == 3
    assert m[("UDG", "20.10.2")]["license_codes"] == 1
    assert m[("UDG", "20.10.2")]["license_knowledge"] == 2
    assert m[("PCF", "20.16.2")]["feature_codes"] == 2
    assert m[("PCF", "20.16.2")]["license_knowledge"] == 0
    # 合并：包含子文档/属于特性 max(2,1)=2
    merged = dict(d["edges"]["merged"])
    assert merged["包含子文档/属于特性"] == 2
    assert d["edges"]["merged_total"] == 2 + 2 + 1 + 1 + 1  # 使用命令2+合并2+依赖/对应/License
    assert d["prefixes"] == ["GWFD", "WHFD"]


# ---------- Case 7：业务图谱 ----------

def test_business_view(seeded):
    d = _get("/api/v1/stats/business")
    c = d["counts"]
    assert c["domains"] == 2 and c["scenarios"] == 2 and c["solutions"] == 3
    assert c["atom_tasks"] == 3 and c["feature_tasks"] == 2 and c["compound_tasks"] == 1
    assert c["task_cmd_edges"] == 1 and c["task_feature_edges"] == 1
    sm = {(r["domain"], r["scenario"]): r for r in d["solutions_matrix"]}
    assert sm[("business-awareness", "access-control")]["count"] == 2
    assert set(sm[("business-awareness", "access-control")]["solutions"]) == {
        "策略匹配基础", "URL 过滤"}
    tm = {(r["type"], r["nf"]): r["count"] for r in d["tasks_matrix"]}
    assert tm[("AtomTask", "UNC")] == 2 and tm[("AtomTask", "UDG")] == 1
    assert tm[("FeatureTask", "UDG")] == 1
    g = d["edges"]["groups"]
    assert g["编排关系"] == 4
    assert g["组成/复用"] == 3
    assert g["上下游/引用"] == 7          # 上游/下游2 + 场景对1 + 域对1 + 引用3
    assert g["跨图谱任务关联"] == 2
    assert d["edges"]["merged_total"] == 16


def test_business_domain_and_solution_filter(seeded):
    d = _get("/api/v1/stats/business?domain=business-awareness")
    assert d["counts"]["solutions"] == 2
    assert all(r["domain"] == "business-awareness" for r in d["solutions_matrix"])
    d2 = _get("/api/v1/stats/business?solution=地址分配")
    assert len(d2["solutions_matrix"]) == 1
    assert d2["solutions_matrix"][0]["count"] == 1


# ---------- Case 9：版本归一（国内→海外展示） ----------

def test_overseas_display(seeded):
    d = _get("/api/v1/stats/command?overseas=true")
    m = {(r["nf"], r["version"]): r for r in d["matrix"]}
    assert m[("PCF", "20.10.2")]["version_display"] == "23.1.0"
    assert m[("PCF", "20.16.2")]["version_display"] == "26.0.0/26.0.1"  # 多海外并列
    assert m[("UDG", "20.10.2")]["version_display"] == "22.1.0"
    sm = {(r["ne"], r["version"]): r for r in d["syntax_matrix"]}
    assert sm[("UPCF", "20.10.2")]["version_display"] == "23.1.0"
    # UDG 20.16.2 无映射行 → 显原值（本种子 UDG 只有 20.10.2，用特性矩阵补验）
    f = _get("/api/v1/stats/feature?overseas=true")
    fm = {(r["nf"], r["version"]): r for r in f["matrix"]}
    assert fm[("PCF", "20.16.2")]["version_display"] == "26.0.0/26.0.1"


def test_overseas_filter_still_local(seeded):
    """筛选恒用国内号：overseas 开着也按 20.10.2 命中。"""
    d = _get("/api/v1/stats/command?overseas=true&versions=20.10.2")
    assert d["knowledge"]["points"] == 8  # PCF5 + UDG3


# ---------- 逻辑网元（§6.2，仅作用 B1/B2） ----------

def test_logical_ne_filter_only_affects_rules(seeded):
    d = _get("/api/v1/stats/command?logical_ne=SMF")
    assert d["rules"]["syntax"] == {
        "cmd_count": 1, "param_count": 2, "cmd_count_by_group_sum": 1}  # 仅 CMD_A
    assert d["knowledge"]["points"] == 10  # A 区不受逻辑网元影响
    assert d["rules"]["graph"] == 3        # 五类规则同样不受影响（仅语法表）


# ---------- /filters ----------

def test_filters_options(seeded):
    d = _get("/api/v1/stats/filters")
    assert "UDG" in d["nfs"] and "UPCF" in d["nfs"] and "UNC" in d["nfs"]
    assert "20.10.2" in d["versions"] and "20.16.2" in d["versions"]
    assert d["logical_nes"] == {"UNC": ["AMF", "SMF"]}
    assert "MMLCommand" in d["object_types"] and "BusinessDomain" in d["object_types"]
    assert "操作配置对象" in d["relations"] and "上游域" in d["relations"]
    assert {x["key"] for x in d["rule_types"]} == {
        "syntax", "graph", "repeat", "mod", "set", "delete"}
    assert set(d["domains"]) == {"business-awareness", "apn-domain"}
    assert len(d["solutions"]) == 3
    assert d["table_rows"]["B_AI_MML_GRAPH_RULE_T"] == 3
    assert d["table_rows"]["B_AI_COMMAND_SYNTAX_CHECK_RULES"] == 5


def test_filters_empty_rule_tables():
    d = _get("/api/v1/stats/filters")
    assert d["table_rows"]["B_AI_COMMAND_SYNTAX_CHECK_RULES"] == 0
    r = client.get("/api/v1/stats/command")
    assert r.status_code == 200
    assert r.json()["rules"]["syntax"]["cmd_count"] == 0  # 空表不报错


# ---------- 导出（§2：CSV / Excel / Markdown） ----------

def test_export_csv(seeded):
    r = client.get("/api/v1/stats/export?view=command&format=csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    text = r.text
    assert text.startswith("﻿")  # BOM：Excel 双击打开不乱码
    assert "# 命令图谱·汇总" in text
    assert "命令知识条数(A1)" in text and "7" in text
    assert "# 出边按关系·合并取大" in text
    assert "# 知识下钻·网元×版本" in text


def test_export_md(seeded):
    r = client.get("/api/v1/stats/export?view=business&format=md")
    assert r.status_code == 200
    assert "## 业务图谱·汇总" in r.text
    assert "业务域→场景→方案" in r.text
    assert "策略匹配基础" in r.text


def test_export_xlsx(seeded):
    import io
    r = client.get("/api/v1/stats/export?view=feature&format=xlsx")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert "[Content_Types].xml" in names
    assert "xl/workbook.xml" in names
    wb = z.read("xl/workbook.xml").decode("utf-8")
    assert "特性图谱·汇总" in wb
    sheet1 = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "特性编号数(C1)" in sheet1 and "inlineStr" in sheet1


def test_export_bad_params(seeded):
    assert client.get("/api/v1/stats/export?view=nope").status_code == 400
    assert client.get("/api/v1/stats/export?view=command&format=pdf").status_code == 400


def test_export_respects_filters(seeded):
    r = client.get("/api/v1/stats/export?view=command&format=csv&nfs=UPCF")
    assert "命令知识条数(A1)" in r.text
    lines = [ln for ln in r.text.splitlines() if ln.startswith("命令知识条数")]
    assert lines and lines[0].endswith(",5")  # UPCF 筛选后 A1=5
