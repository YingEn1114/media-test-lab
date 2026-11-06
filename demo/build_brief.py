# -*- coding: utf-8 -*-
"""生成一页纸《自动化测试能力说明》DOCX。"""

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

INK = RGBColor(0x20, 0x25, 0x2D)
MUTED = RGBColor(0x7B, 0x77, 0x6D)
ACCENT = RGBColor(0x12, 0x3B, 0x5E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
EAST = "PingFang SC"
LATIN = "Arial"


def set_run_font(run, size=9.5, bold=False, color=INK, east=EAST, latin=LATIN):
    run.font.name = latin
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), east)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)


def shade(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def table_borders(table, color="E4DDD0", size=6):
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(size))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        borders.append(el)
    tbl_pr.append(borders)


def cell_margins(table, top=22, bottom=22, left=70, right=70):
    tbl_pr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for name, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{name}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tbl_pr.append(mar)


def cell_text(cell, text, bold=False, size=8.0, color=INK):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, color=color)


def heading(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    set_run_font(run, size=10, bold=True, color=ACCENT)
    p_pr = p._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "2")
    bottom.set(qn("w:color"), "E4DDD0")
    borders.append(bottom)
    p_pr.append(borders)
    return p


def body(doc, text, size=9.0, bold=False, color=INK, before=0, after=1.5, indent=0):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.12
    if indent:
        p.paragraph_format.left_indent = Cm(indent)
        p.paragraph_format.first_line_indent = Cm(-0.3)
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, color=color)
    return p


def bullet(doc, text):
    return body(doc, "•  " + text, indent=0.35)


def build():
    doc = Document()

    # 页面与默认字体
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(1.15)
    sec.bottom_margin = Cm(0.95)
    sec.left_margin = Cm(1.55)
    sec.right_margin = Cm(1.55)

    normal = doc.styles["Normal"]
    normal.font.name = LATIN
    normal.font.size = Pt(9.5)
    normal.font.color.rgb = INK
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), EAST)
    rfonts.set(qn("w:ascii"), LATIN)
    rfonts.set(qn("w:hAnsi"), LATIN)

    # 标题
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(1)
    run = p.add_run("自动化测试能力说明")
    set_run_font(run, size=17, bold=True, color=RGBColor(0x1B, 0x22, 0x2A))

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("正观新闻 · 媒体站质量保障　｜　Playwright + pytest + Allure　｜　2026-11")
    set_run_font(run, size=8, color=MUTED)

    heading(doc, "一、能力概述")
    body(
        doc,
        "以 Playwright + pytest 为核心，建立“用例资产 + 执行平台 + 报告体系”：38 条用例覆盖 12 个测试域，"
        "全量约 2–3 分钟，一次运行产出 pytest HTML、Allure 与趋势数据；用例即代码，可 review、可复用、可进 CI。",
    )

    heading(doc, "二、覆盖范围（38 条 / 12 个测试域）")
    rows = [
        ("层级", "覆盖内容", "用例数"),
        ("UI 功能", "首页、导航、列表、详情、搜索弹层、H5、搜索边界", "8"),
        ("内容与组件", "频道、首页栏目、专题、分享、页脚、登录弹层、下载页、SEO、结构化数据", "11"),
        ("接口与资源", "HTTP 契约、HEAD、robots、静态/图片 CDN、软 404、链接可用性", "8"),
        ("视频与播放器", "列表、元数据、播放/暂停、seek、音量、控件、MP4 Range、移动端布局", "8"),
        ("性能/安全/可访问性", "DCL、资源数、安全响应头、标题层级、图片 alt、输入框", "3"),
        ("合计", "场景覆盖，非代码覆盖率", "38"),
    ]
    table = doc.add_table(rows=len(rows), cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table_borders(table)
    cell_margins(table)
    widths = (Cm(3.1), Cm(12.2), Cm(2.1))
    for r_idx, row in enumerate(rows):
        for c_idx, text in enumerate(row):
            cell = table.cell(r_idx, c_idx)
            cell.width = widths[c_idx]
            header = r_idx == 0
            total = r_idx == len(rows) - 1
            cell_text(
                cell,
                text,
                bold=header or total,
                size=8.0,
                color=WHITE if header else INK,
            )
            if header:
                shade(cell, "123B5E")
            elif total:
                shade(cell, "E9EDF0")
    for row in table.rows:
        for c_idx, width in enumerate(widths):
            row.cells[c_idx].width = width

    heading(doc, "三、执行方式与产出")
    bullet(doc, "平台一键执行：勾选 / 全量、实时日志、运行取消、headed 慢动作；用例自动发现。")
    bullet(doc, "命令行/CI 可接入：pytest 直接跑；同时生成 pytest HTML（单文件可离线）与 Allure（交互式），失败自动截图。")
    bullet(doc, "效率：全量 154.1 秒；冒烟 8 条约 20–40 秒，适合提交前快速反馈。")

    heading(doc, "四、结果口径")
    body(doc, "33 passed + 5 xfail = 38；有效通过率 33/33 = 100%。", bold=True, after=0.5)
    body(
        doc,
        "有效用例 = passed + failed；xfail 为已确认的站点缺陷，单独展示，不计入通过率分母，"
        "避免“算成失败”或“算成通过”两种误读。",
        size=8.4,
    )

    heading(doc, "五、已发现的 5 个问题（附截图/响应）")
    issues = [
        ("编号", "问题", "关键证据"),
        ("A06", "搜索结果被重定向到客户端下载页", "302 → /down.html，无搜索结果页"),
        ("A19", "未知路径返回 HTTP 200 + 404 内容", "软 404，正文仅 22 字节"),
        ("A20", "sitemap.xml 返回 HTTP 200 + HTML 404", "Content-Type: text/html"),
        ("A29", "特殊字符搜索同样跳转 /down.html", "与 A06 同路径，输入被吞"),
        ("V08", "390 视口下播放器固定 1240px", "页面横向滚动宽度 1412px"),
    ]
    t2 = doc.add_table(rows=len(issues), cols=3)
    t2.alignment = WD_TABLE_ALIGNMENT.CENTER
    t2.autofit = False
    table_borders(t2)
    cell_margins(t2)
    w2 = (Cm(1.6), Cm(8.8), Cm(7.0))
    for r_idx, row in enumerate(issues):
        for c_idx, text in enumerate(row):
            cell = t2.cell(r_idx, c_idx)
            cell.width = w2[c_idx]
            header = r_idx == 0
            cell_text(cell, text, bold=header, size=7.9, color=WHITE if header else INK)
            if header:
                shade(cell, "123B5E")
    for row in t2.rows:
        for c_idx, width in enumerate(w2):
            row.cells[c_idx].width = width

    heading(doc, "六、价值与下一步")
    bullet(doc, "价值：发布前几分钟完成回归；问题可复现、可追溯；报告可直接归档与分享。")
    bullet(doc, "下一步：缺陷卡片已建；CI 工作流已就绪（平台单测 + 每日冒烟）→ 通知 → 接口层扩展。")

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(5)
    run = p.add_run(
        "平台 127.0.0.1:8090　｜　证据包 demo/evidence/index.html　｜　"
        "2026-11-06 实测 33 passed / 5 xfail / 154.1s"
    )
    set_run_font(run, size=7.2, color=MUTED)

    core = doc.core_properties
    core.title = "自动化测试能力说明"
    core.subject = "正观新闻 · 媒体站质量保障"
    core.author = "QA"
    core.comments = "一页纸能力说明，数据截至 2026-11-06"

    out = "QA-Capability-Brief.docx"
    doc.save(out)
    print("saved", out)


if __name__ == "__main__":
    build()
