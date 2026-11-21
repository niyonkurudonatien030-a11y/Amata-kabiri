"""Helpers for building the AmataShield project book PDF (reportlab + pygments)."""
import os
from pygments import lex
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.token import Comment, Keyword, Name, Number, String
from reportlab.graphics.shapes import Drawing, Ellipse, Line, Polygon, Rect, String as GStr
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Table, TableStyle, XPreformatted

DEEP, FRESH, GOLD, NAVY = colors.HexColor("#0B5D3B"), colors.HexColor("#3FB950"), colors.HexColor("#F2B705"), colors.HexColor("#0F1F3D")
PALE, LINE = colors.HexColor("#EAF4EE"), colors.HexColor("#C9DACF")

S = {
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.6, leading=13.4, spaceAfter=5),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=10.5, textColor=colors.HexColor("#4a5a50")),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=DEEP, spaceBefore=4, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=NAVY, spaceBefore=12, spaceAfter=5, keepWithNext=1),
    "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=DEEP, spaceBefore=7, spaceAfter=3, keepWithNext=1),
    "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=9.6, leading=13, leftIndent=14, bulletIndent=3, spaceAfter=2),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.3, leading=10.6),
    "cellb": ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=8.3, leading=10.6, textColor=colors.white),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=6.4, leading=7.7),
    "fname": ParagraphStyle("fname", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.white),
    "toc1": ParagraphStyle("toc1", fontName="Helvetica-Bold", fontSize=10, leading=15, leftIndent=0),
    "toc2": ParagraphStyle("toc2", fontName="Helvetica", fontSize=8.8, leading=12, leftIndent=14),
}


def x(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def P(t, style="body"):
    return Paragraph(t, S[style])


def bullets(items):
    return [Paragraph(i, S["bullet"], bulletText="\u2022") for i in items]


def table(rows, widths, header=True, zebra=True):
    data = [[Paragraph(str(c), S["cellb"] if (header and r == 0) else S["cell"]) for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), DEEP))
    if zebra:
        for r in range(1 if header else 0, len(rows)):
            if r % 2 == 0:
                st.append(("BACKGROUND", (0, r), (-1, r), PALE))
    t.setStyle(TableStyle(st))
    return t


def callout(text, kind="note"):
    bg, bar = {"note": (colors.HexColor("#FFF8DD"), GOLD), "warn": (colors.HexColor("#FDE7E4"), colors.HexColor("#C0392B")),
               "ok": (PALE, FRESH)}[kind]
    t = Table([[Paragraph(text, S["body"])]], colWidths=[172 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


# ---------------------------------------------------------------- diagrams
class Diagram:
    def __init__(self, w=172, h=90):
        self.w, self.h = w * mm, h * mm
        self.d = Drawing(self.w, self.h)

    def box(self, x0, y0, w, h, text, fill=PALE, stroke=DEEP, color=colors.black, size=7.2, bold=False, round_=True):
        r = Rect(x0 * mm, y0 * mm, w * mm, h * mm, rx=3 if round_ else 0, ry=3 if round_ else 0, fillColor=fill, strokeColor=stroke, strokeWidth=1)
        self.d.add(r)
        lines = text.split("\n")
        top = y0 * mm + h * mm / 2 + (len(lines) - 1) * size * 0.6
        for i, ln in enumerate(lines):
            self.d.add(GStr(x0 * mm + w * mm / 2, top - i * (size + 1.6) - size * 0.35, ln, fontName="Helvetica-Bold" if (bold or i == 0 and len(lines) > 1) else "Helvetica",
                            fontSize=size, fillColor=color, textAnchor="middle"))

    def oval(self, cx, cy, rx, ry, text, fill=colors.white, size=6.6):
        self.d.add(Ellipse(cx * mm, cy * mm, rx * mm, ry * mm, fillColor=fill, strokeColor=NAVY, strokeWidth=0.9))
        lines = text.split("\n")
        for i, ln in enumerate(lines):
            self.d.add(GStr(cx * mm, cy * mm + (len(lines) - 1) * size * 0.55 - i * (size + 1) - size * 0.3, ln, fontName="Helvetica", fontSize=size, textAnchor="middle"))

    def text(self, x0, y0, t, size=7, color=colors.black, anchor="middle", bold=False):
        self.d.add(GStr(x0 * mm, y0 * mm, t, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size, fillColor=color, textAnchor=anchor))

    def arrow(self, x1, y1, x2, y2, color=NAVY, label=None, head=True, dash=False):
        ln = Line(x1 * mm, y1 * mm, x2 * mm, y2 * mm, strokeColor=color, strokeWidth=1)
        if dash:
            ln.strokeDashArray = [3, 2]
        self.d.add(ln)
        if head:
            import math
            a = math.atan2((y2 - y1), (x2 - x1))
            L, W = 2.2 * mm, 1.1 * mm
            px, py = x2 * mm, y2 * mm
            pts = [px, py, px - L * math.cos(a) + W * math.sin(a), py - L * math.sin(a) - W * math.cos(a),
                   px - L * math.cos(a) - W * math.sin(a), py - L * math.sin(a) + W * math.cos(a)]
            self.d.add(Polygon(pts, fillColor=color, strokeColor=color, strokeWidth=0.3))
        if label:
            self.text((x1 + x2) / 2, (y1 + y2) / 2 + 1.6, label, size=6, color=colors.HexColor("#333333"))

    def flow(self):
        return self.d


# ---------------------------------------------------------------- source code
def _style(tok):
    if tok in Comment:
        return "#6B7280", "i"
    if tok in Keyword:
        return "#7B1FA2", "b"
    if tok in String:
        return "#B45309", ""
    if tok in Name.Function or tok in Name.Class or tok in Name.Tag or tok in Name.Decorator:
        return "#1D4ED8", ""
    if tok in Number:
        return "#0F766E", ""
    return None, ""


def _clean(s):
    return s.encode("cp1252", errors="replace").decode("cp1252")


def code_flowable(path, text, width=118):
    out_lines = []
    for raw in text.expandtabs(4).splitlines():
        raw = _clean(raw)
        while len(raw) > width:
            out_lines.append(raw[:width])
            raw = "      " + raw[width:]
        out_lines.append(raw)
    src = "\n".join(out_lines) + "\n"
    try:
        lexer = get_lexer_for_filename(path)
    except Exception:
        lexer = TextLexer()
    chunks = []
    for tok, val in lex(src, lexer):
        color, fmt = _style(tok)
        parts = val.split("\n")
        for i, part in enumerate(parts):
            if part:
                e = x(part)
                if fmt:
                    e = f"<{fmt}>{e}</{fmt}>"
                if color:
                    e = f'<font color="{color}">{e}</font>'
                chunks.append(e)
            if i < len(parts) - 1:
                chunks.append("\n")
    return XPreformatted("".join(chunks).rstrip("\n"), S["code"])


def file_header(path, note):
    t = Table([[Paragraph(x(path), S["fname"])], [Paragraph(x(note), S["small"])]], colWidths=[172 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("BACKGROUND", (0, 1), (-1, 1), PALE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t
