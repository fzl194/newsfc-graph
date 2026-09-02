"""统计结果导出：CSV / Excel(xlsx) / Markdown（汇总 + 明细多节）。

- 与视图端点共用同一份 payload（core.*_view），保证导出=页面所见。
- xlsx 用 stdlib zipfile 手写最小 OOXML（inlineStr，无样式）——免新增依赖；
  结构为 [Content_Types].xml + _rels + workbook + 每节一个 worksheet。
"""
import csv
import io
import zipfile
from xml.sax.saxutils import escape

from .spec import RULE_TABLES

# 一节 = (标题, 表头, 行数据[与表头同宽的基本类型])
Section = tuple[str, list[str], list[list]]


def _kv_section(title: str, pairs: list[tuple[str, object]]) -> Section:
    return (title, ["指标", "数值"], [[k, v if isinstance(v, (int, float)) else str(v)]
                                      for k, v in pairs])


def _rule_label(key: str) -> str:
    return RULE_TABLES[key][3] if key in RULE_TABLES else key


def sections_for(view: str, p: dict) -> list[Section]:
    """视图 payload → 导出节列表（顺序即展示顺序）。"""
    sections: list[Section] = []
    if view == "command":
        rules = p["rules"]
        summary: list[tuple[str, object]] = [
            ("命令知识条数(A1)", p["knowledge"]["MMLCommand"]),
            ("配置对象知识条数(A2)", p["knowledge"]["ConfigObject"]),
            ("点(A3)", p["knowledge"]["points"]),
            ("知识关联边数·合并(A4)", p["edges"]["merged_total"]),
            ("被引用入边合计(A5)", sum(v for _, v in p["inbound"]["raw"])),
        ]
        if "syntax" in rules:
            summary += [
                ("命令数量(B1)", rules["syntax"]["cmd_count"]),
                ("命令数量·分组求和口径(B1)", rules["syntax"]["cmd_count_by_group_sum"]),
                ("参数数量(B2)", rules["syntax"]["param_count"]),
            ]
        for key in RULE_TABLES:
            if key in rules:
                summary.append((f"{_rule_label(key)}(B)", rules[key]))
        summary.append(("五类规则合计(B8)", p["five_total"]))
        sections.append(_kv_section("命令图谱·汇总", summary))
        sections.append(("出边按关系·原始", ["关系", "计数"],
                         [[k, v] for k, v in p["edges"]["raw"]]))
        sections.append(("出边按关系·合并取大", ["关系", "计数"],
                         [[k, v] for k, v in p["edges"]["merged"]]))
        sections.append(("入边按关系", ["关系", "计数"],
                         [[k, v] for k, v in p["inbound"]["raw"]]))
        sections.append(("知识下钻·网元×版本", ["网元", "版本(国内)", "版本(展示)",
                                             "命令知识条数", "配置对象知识条数", "点"],
                         [[r["nf_display"], r["version"], r["version_display"],
                           r["MMLCommand"], r["ConfigObject"], r["total"]]
                          for r in p["matrix"]]))
        if "syntax" in rules:
            sections.append(("语法规则下钻·网元×版本", ["网元", "版本(国内)", "版本(展示)",
                                                     "命令数", "参数数"],
                             [[r["ne"], r["version"], r["version_display"],
                               r["cmd_count"], r["param_count"]]
                              for r in p["syntax_matrix"]]))
        for key, rows in p["rule_matrix"].items():
            sections.append((f"{_rule_label(key)}下钻·网元×版本",
                             ["网元", "版本(国内)", "版本(展示)", "规则数"],
                             [[r["ne"], r["version"], r["version_display"], r["count"]]
                              for r in rows]))
    elif view == "feature":
        t = p["totals"]
        sections.append(_kv_section("特性图谱·汇总", [
            ("特性编号数(C1)", t["feature_codes"]),
            ("License编号数(C2)", t["license_codes"]),
            ("特性知识条数(C3)", t["feature_knowledge"]),
            ("License知识条数(C4)", t["license_knowledge"]),
            ("知识关联边数·合并(C5)", p["edges"]["merged_total"]),
            ("特性业务类型数(C6)", len(p["prefixes"])),
        ]))
        sections.append(("业务类型前缀(C6)", ["前缀"],
                         [[x] for x in p["prefixes"]]))
        sections.append(("出边按关系·原始", ["关系", "计数"],
                         [[k, v] for k, v in p["edges"]["raw"]]))
        sections.append(("出边按关系·合并取大", ["关系", "计数"],
                         [[k, v] for k, v in p["edges"]["merged"]]))
        sections.append(("下钻·网元×版本", ["网元", "版本(国内)", "版本(展示)",
                                         "特性编号数", "特性知识条数",
                                         "License编号数", "License知识条数"],
                         [[r["nf_display"], r["version"], r["version_display"],
                           r["feature_codes"], r["feature_knowledge"],
                           r["license_codes"], r["license_knowledge"]]
                          for r in p["matrix"]]))
    else:  # business
        c = p["counts"]
        g = p["edges"]["groups"]
        sections.append(_kv_section("业务图谱·汇总", [
            ("业务域数(D1)", c["domains"]), ("场景数(D2)", c["scenarios"]),
            ("方案数(D3)", c["solutions"]),
            ("原子任务知识条数(D4)", c["atom_tasks"]),
            ("特性任务知识条数(D5)", c["feature_tasks"]),
            ("步骤任务知识条数(D6)", c["compound_tasks"]),
            ("任务关联命令数(D7)", c["task_cmd_edges"]),
            ("任务关联特性数(D7b)", c["task_feature_edges"]),
            ("编排关系边数(D8)", g["编排关系"]),
            ("组成/复用边数(D9)", g["组成/复用"]),
            ("上下游/引用边数(D10)", g["上下游/引用"]),
            ("跨图谱任务关联(D11)", g["跨图谱任务关联"]),
            ("知识关联边数·合并", p["edges"]["merged_total"]),
        ]))
        sections.append(("业务域→场景→方案", ["业务域", "场景", "方案数", "方案列表"],
                         [[r["domain"], r["scenario"], r["count"],
                           "、".join(r["solutions"])] for r in p["solutions_matrix"]]))
        sections.append(("任务资产·类型×网元", ["任务类型", "网元", "条数"],
                         [[r["type"], r["nf"], r["count"]] for r in p["tasks_matrix"]]))
        sections.append(("出边按关系·原始", ["关系", "计数"],
                         [[k, v] for k, v in p["edges"]["raw"]]))
        sections.append(("出边按关系·合并取大", ["关系", "计数"],
                         [[k, v] for k, v in p["edges"]["merged"]]))
    return sections


# ---------- 渲染器 ----------

def _csv_cell(v) -> str:
    """CSV 公式注入防护：=+-@ 开头的值前缀 '（Excel 会被当公式执行）。"""
    s = str(v)
    return "'" + s if s and s[0] in "=+-@" else s


def render_csv(sections: list[Section]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    for title, headers, rows in sections:
        w.writerow([f"# {title}"])
        w.writerow([_csv_cell(h) for h in headers])
        w.writerows([[_csv_cell(c) for c in row] for row in rows])
        w.writerow([])
    return buf.getvalue()


def render_md(sections: list[Section]) -> str:
    out: list[str] = []
    for title, headers, rows in sections:
        out.append(f"## {title}\n")
        out.append("| " + " | ".join(str(h) for h in headers) + " |")
        out.append("|" + "---|" * len(headers))
        for row in rows:
            out.append("| " + " | ".join(
                str(c).replace("|", "\\|") for c in row) + " |")
        out.append("")
    return "\n".join(out)


def _col_letter(i: int) -> str:
    """0→A, 25→Z, 26→AA。"""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(ref: str, v) -> str:
    if isinstance(v, bool):
        return f'<c r="{ref}" t="b"><v>{1 if v else 0}</v></c>'
    if isinstance(v, (int, float)):
        return f'<c r="{ref}"><v>{v}</v></c>'
    return (f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">'
            f'{escape(str(v))}</t></is></c>')


def _sheet_xml(headers: list[str], rows: list[list]) -> str:
    body: list[str] = []
    all_rows = [list(headers), *rows]
    for ri, row in enumerate(all_rows, start=1):
        cells = "".join(
            _cell(f"{_col_letter(ci)}{ri}", v) for ci, v in enumerate(row))
        body.append(f'<row r="{ri}">{cells}</row>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(body)}</sheetData></worksheet>')


def _safe_sheet_name(name: str, used: set[str]) -> str:
    """Excel sheet 名约束：≤31 字符，禁 :\\/?*[]。截 24 字（中文按 1 字计）+
    序号，避免重名。"""
    cleaned = "".join(ch for ch in name if ch not in ':\\/?*[]')[:24] or "Sheet"
    candidate, i = cleaned, 1
    while candidate in used:
        i += 1
        candidate = f"{cleaned[:22]}({i})"
    used.add(candidate)
    return candidate


def render_xlsx(sections: list[Section]) -> bytes:
    """最小合法 xlsx（zip + inlineStr）。"""
    used: set[str] = set()
    sheets = [(title, _safe_sheet_name(title, used), _sheet_xml(headers, rows))
              for title, headers, rows in sections]
    # escape() 默认不转义引号——属性值需额外转 " 防止标题含引号时 XML 失效
    q = {'"': "&quot;"}
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType='
        '"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1))
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType='
        '"application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType='
        '"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f'{overrides}</Types>')
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument'
        '/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    sheet_tags = "".join(
        f'<sheet name="{escape(name, q)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, (_, name, _) in enumerate(sheets, start=1))
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{sheet_tags}</sheets></workbook>')
    wb_rels_items = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/'
        f'officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, len(sheets) + 1))
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{wb_rels_items}</Relationships>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        for i, (_, _, xml) in enumerate(sheets, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", xml)
    return buf.getvalue()
