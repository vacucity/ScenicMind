"""Markdown → PDF 导出（reportlab Platypus，中文字体注册）。

报告下载为 PDF，标题/段落/列表/引用/分隔线均有视觉层级。
"""

from __future__ import annotations

import io
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

# ===== 中文字体注册（按可用性降级） =====
_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\simhei.ttf", "SimHei"),      # 黑体
    (r"C:\Windows\Fonts\msyh.ttc", "MSYH"),           # 微软雅黑
    (r"C:\Windows\Fonts\simsun.ttc", "SimSun"),       # 宋体
]
_FONT_NAME = "Helvetica"

for _path, _name in _FONT_CANDIDATES:
    try:
        pdfmetrics.registerFont(TTFont(_name, _path, subfontIndex=0))
        _FONT_NAME = _name
        pdfmetrics.registerFontFamily(_name, normal=_name, bold=_name, italic=_name, boldItalic=_name)
        break
    except Exception:
        continue

# ===== 配色（与前端 pine/sage 主题一致） =====
PINE_900 = colors.HexColor("#123c2c")
PINE_800 = colors.HexColor("#1f5a43")
PINE_700 = colors.HexColor("#316b51")
INK = colors.HexColor("#17231d")
MUTED = colors.HexColor("#68766e")
SAGE_BG = colors.HexColor("#e8f0ea")
SAGE_LINE = colors.HexColor("#91ae9b")
AMBER = colors.HexColor("#ad792d")
CORAL = colors.HexColor("#d85a30")


def _style(name, size, color=INK, leading=1.5, space_after=4, **kw):
    return ParagraphStyle(name, fontName=_FONT_NAME, fontSize=size, leading=size * leading,
                          textColor=color, spaceAfter=space_after, **kw)


STYLES = {
    "h1": _style("h1", 20, PINE_900, 1.3, 10, spaceBefore=4),
    "h2": _style("h2", 14, PINE_800, 1.4, 8, spaceBefore=14),
    "h3": _style("h3", 12, PINE_700, 1.4, 6, spaceBefore=10),
    "p": _style("p", 10.5, INK, 1.8, 6),
    "quote": _style("quote", 9.5, colors.HexColor("#4a5a50"), 1.6, 6, leftIndent=10),
    "li": _style("li", 10.5, INK, 1.7, 3),
}


def _inline(text: str) -> str:
    """处理 **加粗** 与 `行内代码`，转 reportlab 支持的标签。"""
    text = re.sub(r"\*\*(.+?)\*\*", lambda m: f'<font color="#123c2c"><b>{m.group(1)}</b></font>', text)
    text = re.sub(r"`(.+?)`", lambda m: f'<font name="Courier">{m.group(1)}</font>', text)
    return text


def markdown_to_pdf(markdown: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=22 * mm, bottomMargin=20 * mm,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            title="景区经营分析报告", author="ScenicMind Agent")
    story: list = []
    list_buffer: list[str] = []

    def flush_list():
        nonlocal list_buffer
        if list_buffer:
            items = [ListItem(Paragraph(_inline(i), STYLES["li"]), leftIndent=14, bulletColor=PINE_700) for i in list_buffer]
            story.append(ListFlowable(items, bulletType="bullet", start="•", bulletFontSize=9,
                                      bulletColor=PINE_700, leftIndent=14))
            list_buffer = []

    for raw in markdown.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            flush_list()
            continue
        if line.startswith("### "):
            flush_list(); story.append(Paragraph(_inline(line[4:]), STYLES["h3"]))
        elif line.startswith("## "):
            flush_list(); story.append(Paragraph(_inline(line[3:]), STYLES["h2"]))
            story.append(HRFlowable(width="100%", thickness=0.7, color=SAGE_LINE, spaceAfter=4))
        elif line.startswith("# "):
            flush_list(); story.append(Paragraph(_inline(line[2:]), STYLES["h1"]))
            story.append(HRFlowable(width="100%", thickness=1.5, color=PINE_900, spaceAfter=8))
        elif line.startswith("> "):
            flush_list()
            quote = Paragraph(_inline(line[2:]), STYLES["quote"])
            from reportlab.platypus import Table, TableStyle
            table = Table([[quote]], colWidths=[doc.width])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), SAGE_BG),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBEFORE", (0, 0), (0, -1), 3, SAGE_LINE),
            ]))
            story.append(table)
            story.append(Spacer(1, 6))
        elif re.match(r"^[-*] ", line):
            list_buffer.append(re.sub(r"^[-*] ", "", line))
        elif re.match(r"^\d+\. ", line):
            flush_list()
            item = Paragraph(_inline(re.sub(r"^\d+\. ", "", line)), STYLES["li"])
            story.append(ListFlowable([ListItem(item, leftIndent=14, bulletColor=PINE_700)],
                                      bulletType="1", leftIndent=14))
        else:
            flush_list(); story.append(Paragraph(_inline(line), STYLES["p"]))
    flush_list()

    doc.build(story)
    return buf.getvalue()
