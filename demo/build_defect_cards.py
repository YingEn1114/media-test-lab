# -*- coding: utf-8 -*-
"""从 defects.json 生成可打印的缺陷卡片 DOCX（A4，3 张/页）。"""

import json
import os

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "zgnews-tests", "defects.json")
OUT = os.path.join(HERE, "Defect-Cards.docx")

INK = RGBColor(0x20, 0x25, 0x2D)
MUTED = RGBColor(0x7B, 0x77, 0x6D)
ACCENT = RGBColor(0x12, 0x3B, 0x5E)
RED = RGBColor(0xB6, 0x42, 0x32)
EAST = "PingFang SC"
LATIN = "Arial"


def font(run, size=8.4, bold=False, color=INK, mono=False):
    name = "Menlo" if mono else LATIN
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), EAST)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)


def shade(element, fill):
    pr = element.get_or_add_pPr() if hasattr(element, "get_or_add_pPr") else element
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    pr.append(shd)


def cell_shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def table_border(table, color="C7D0D6", size=8):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(size))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        borders.append(el)
    tbl_pr.append(borders)


def table_width(table, cm):
    tbl_pr = table._tbl.tblPr
    w = OxmlElement("w:tblW")
    w.set(qn("w:w"), str(int(cm * 567)))
    w.set(qn("w:type"), "dxa")
    tbl_pr.append(w)


def cell_margins(cell, top=80, bottom=80, left=110, right=110):
    tc_pr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for name, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{name}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tc_pr.append(mar)


def no_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    tr_pr.append(el)


def para(cell, text="", size=8.4, color=INK, bold=False, before=0, after=1.5, mono=False):
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.06
    r = p.add_run(text)
    font(r, size=size, bold=bold, color=color, mono=mono)
    return p


def labeled(cell, label, value, label_color=INK, value_color=INK, size=8.4):
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(1.2)
    p.paragraph_format.line_spacing = 1.06
    r = p.add_run(label)
    font(r, size=size, bold=True, color=label_color)
    r = p.add_run(value)
    font(r, size=size, color=value_color)
    return p


def add_card(doc, d):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table_border(table)
    table_width(table, 18.3)
    row = table.rows[0]
    no_split(row)
    cell = row.cells[0]
    cell.width = Cm(18.3)
    cell_margins(cell)

    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.05
    r = p.add_run(f"{d['id']}　")
    font(r, size=10.5, bold=True, color=ACCENT)
    r = p.add_run(d["title"])
    font(r, size=10.5, bold=True)

    p = cell.add_paragraph()
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.05
    chips = f"P{d['priority'][-1]} ｜ 严重 {d['severity']} ｜ {d['status']} ｜ 关联 {d['caseId']}"
    r = p.add_run(chips)
    font(r, size=7.8, color=MUTED)

    meta = (
        f"组件 {d['component']}　·　负责人 {d['owner']}　·　目标 {d['target']}　"
        f"·　复核 {d['lastChecked']}"
    )
    p = cell.add_paragraph()
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.05
    r = p.add_run(meta)
    font(r, size=7.8, color=MUTED)

    steps = "　".join(f"{i + 1}) {s}" for i, s in enumerate(d["steps"]))
    labeled(cell, "复现　", steps)

    labeled(cell, "期望　", d["expected"])
    labeled(cell, "实际　", d["actual"], label_color=RED, value_color=INK)
    labeled(cell, "影响　", d["impact"])

    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.line_spacing = 1.06
    shade(p._p, "F4F6F8")
    r = p.add_run("建议　")
    font(r, size=8.4, bold=True, color=RGBColor(0x2F, 0x6F, 0x68))
    r = p.add_run(d["suggestion"])
    font(r, size=8.4)

    ev = d.get("evidence") or {}
    ev_text = ev.get("text", "")
    ev_img = ev.get("image") or "—"
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.05
    r = p.add_run(f"证据　{ev_img}")
    font(r, size=7.4, color=MUTED, mono=True)
    r = p.add_run(f"　｜　{ev_text}")
    font(r, size=7.4, color=MUTED)
    r = p.add_run(f"　｜　{d['test']}")
    font(r, size=7.2, color=MUTED, mono=True)

    gap = doc.add_paragraph()
    gap.paragraph_format.space_before = Pt(0)
    gap.paragraph_format.space_after = Pt(0)
    gap.paragraph_format.line_spacing = 1.0
    r = gap.add_run("")
    font(r, size=5)


def add_summary(doc, items):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table_border(table, color="C7D0D6", size=8)
    table_width(table, 18.3)
    row = table.rows[0]
    no_split(row)
    cell = row.cells[0]
    cell.width = Cm(18.3)
    cell_margins(cell, top=110, bottom=110)
    cell_shade(cell, "F4F6F8")

    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("汇总与回归")
    font(r, size=10.5, bold=True, color=ACCENT)

    counts = {
        "total": len(items),
        "p1": sum(1 for i in items if i["priority"] == "P1"),
        "p2": sum(1 for i in items if i["priority"] == "P2"),
        "todo": sum(1 for i in items if i["status"] == "待修复"),
    }
    labeled(cell, "问题总数　", f"{counts['total']} 条（P1 {counts['p1']} · P2 {counts['p2']}）· 待修复 {counts['todo']} 条")

    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.06
    r = p.add_run("口径　")
    font(r, size=8.4, bold=True)
    r = p.add_run("有效用例 = passed + failed；xfail 单列、不计入通过率分母。5 条问题即当前 5 条 xfail。")
    font(r, size=8.4)

    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("修复流程　")
    font(r, size=8.4, bold=True)
    r = p.add_run("① 修复 → ② 删除用例中的 pytest.xfail(...) → ③ 重跑全量 → ④ 平台“已知问题”与 Allure skipped 同步下降。")
    font(r, size=8.4)

    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run("入口　")
    font(r, size=8.4, bold=True)
    r = p.add_run("平台 /defects ｜ 证据包 demo/evidence/index.html ｜ 一页纸 demo/QA-Capability-Brief.pdf")
    font(r, size=8, color=MUTED)


def main():
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])

    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(1.15)
    sec.bottom_margin = Cm(1.05)
    sec.left_margin = Cm(1.35)
    sec.right_margin = Cm(1.35)

    normal = doc.styles["Normal"]
    normal.font.name = LATIN
    normal.font.size = Pt(8.4)
    normal.font.color.rgb = INK
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), EAST)

    # 页眉标题
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(1)
    r = p.add_run("缺陷卡片 · 正观新闻")
    font(r, size=16, bold=True, color=RGBColor(0x1B, 0x22, 0x2A))

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(
        f"{len(items)} 条已确认问题 ｜ P1 2 · P2 3 ｜ 全部待修复 ｜ "
        f"导出 {data.get('generatedAt', '')} ｜ 对应测试套件 5 条 xfail"
    )
    font(r, size=8, color=MUTED)

    # 页脚页码
    footer_p = sec.footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = footer_p.add_run("正观新闻 · 缺陷卡片 · 2026-11-06 · 第 ")
    font(r, size=7, color=MUTED)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run_el = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "1"
    run_el.append(t)
    fld.append(run_el)
    footer_p._p.append(fld)
    r = footer_p.add_run(" 页")
    font(r, size=7, color=MUTED)

    for idx, d in enumerate(items):
        add_card(doc, d)
        if idx == 2:
            doc.add_page_break()

    add_summary(doc, items)

    core = doc.core_properties
    core.title = "缺陷卡片 · 正观新闻"
    core.subject = "5 条已确认问题"
    core.author = "QA"
    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
