#!/usr/bin/env python3
"""
Generate the professional PDF user manual for Haysey's Astrostacker.

Run from the project root:
    python3 make_manual_pdf.py

Outputs USER_MANUAL.pdf in the project root.
"""

import math
import random
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

# ── Colour palette (matches the app's dark/bronze theme) ─────────────────────
C_BG_DARK    = colors.HexColor("#0D0F1A")   # Cover background
C_BG_CARD    = colors.HexColor("#1A1E2E")   # Card panels
C_BRONZE     = colors.HexColor("#CD7F32")   # Bronze accent
C_ORANGE     = colors.HexColor("#E8A044")   # Light orange accent
C_TEXT_MAIN  = colors.HexColor("#E0E8F0")   # Cover text
C_HEADING    = colors.HexColor("#1C2240")   # Interior section headings
C_SUBHEAD    = colors.HexColor("#2E3560")   # Subsection headings
C_BODY       = colors.HexColor("#1A1A2A")   # Body text
C_DIM        = colors.HexColor("#5A6080")   # Captions / labels
C_CODE_BG    = colors.HexColor("#F0F2F8")   # Code block background
C_CODE_TEXT  = colors.HexColor("#1A1A2A")   # Code text
C_TABLE_HDR  = colors.HexColor("#1C2240")   # Table header background
C_TABLE_ALT  = colors.HexColor("#F4F6FC")   # Table alternate row
C_RULE       = colors.HexColor("#D0D4E8")   # Horizontal rules
C_TIP_BORDER = colors.HexColor("#E8A044")   # Tip/callout left border
C_TIP_BG     = colors.HexColor("#FFFBF2")   # Tip background
C_WARN_BG    = colors.HexColor("#FFF2F2")   # Warning/problem background
C_WARN_BORDER= colors.HexColor("#CC4444")   # Problem left border

# ── Page geometry ─────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN_L = 22 * mm
MARGIN_R = 22 * mm
MARGIN_T = 18 * mm
MARGIN_B = 18 * mm
HDR_H    = 10 * mm
FTR_H    = 10 * mm
BODY_W   = PAGE_W - MARGIN_L - MARGIN_R

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT = Path(__file__).parent
SRC_TXT = PROJECT / "USER_MANUAL.txt"
ICON    = PROJECT / "icon.png"
OUT_PDF = PROJECT / "USER_MANUAL.pdf"

# ─────────────────────────────────────────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────────────────────────────────────────

def build_styles():
    s = getSampleStyleSheet()
    base = dict(fontName="Helvetica", textColor=C_BODY, leading=14)

    def P(name, **kw):
        merged = {**base, **kw}
        return ParagraphStyle(name, **merged)

    return {
        "body":    P("body",    fontSize=10.5, leading=15, alignment=TA_JUSTIFY,
                     spaceAfter=4),
        "bullet":  P("bullet",  fontSize=10.5, leading=15, leftIndent=14,
                     firstLineIndent=-10, spaceAfter=3,
                     bulletIndent=4),
        "h1":      P("h1",      fontName="Helvetica-Bold", fontSize=17,
                     textColor=C_HEADING, leading=22,
                     spaceBefore=14, spaceAfter=6),
        "h2":      P("h2",      fontName="Helvetica-Bold", fontSize=12,
                     textColor=C_SUBHEAD, leading=16,
                     spaceBefore=10, spaceAfter=4),
        "h3":      P("h3",      fontName="Helvetica-BoldOblique", fontSize=10.5,
                     textColor=C_SUBHEAD, leading=14,
                     spaceBefore=7, spaceAfter=3),
        "code":    P("code",    fontName="Courier", fontSize=9,
                     textColor=C_CODE_TEXT, leading=13,
                     leftIndent=8, rightIndent=8),
        "toc1":    P("toc1",    fontName="Helvetica-Bold", fontSize=10.5,
                     textColor=C_HEADING, leading=15, spaceAfter=2),
        "toc2":    P("toc2",    fontSize=10, textColor=C_DIM,
                     leading=14, leftIndent=14, spaceAfter=1),
        "caption": P("caption", fontSize=9, textColor=C_DIM,
                     leading=12, alignment=TA_CENTER),
        "prob":    P("prob",    fontName="Helvetica-Bold", fontSize=10.5,
                     textColor=colors.HexColor("#882222"), leading=14,
                     spaceAfter=2),
        "sol":     P("sol",     fontSize=10.5, leading=15, spaceAfter=4,
                     leftIndent=6),
        "gloss_term": P("gloss_term", fontName="Helvetica-Bold", fontSize=10.5,
                        textColor=C_HEADING, leading=14, spaceAfter=1),
        "gloss_def":  P("gloss_def",  fontSize=10, leading=14,
                        leftIndent=12, spaceAfter=6),
        "cover_title": ParagraphStyle("cover_title",
                        fontName="Helvetica-Bold", fontSize=38,
                        textColor=C_TEXT_MAIN, leading=44, alignment=TA_CENTER),
        "cover_sub":   ParagraphStyle("cover_sub",
                        fontName="Helvetica", fontSize=18,
                        textColor=C_ORANGE, leading=24, alignment=TA_CENTER),
        "cover_ver":   ParagraphStyle("cover_ver",
                        fontName="Helvetica", fontSize=12,
                        textColor=colors.HexColor("#8899AA"),
                        leading=16, alignment=TA_CENTER),
    }

# ─────────────────────────────────────────────────────────────────────────────
# HEADER / FOOTER CANVAS CALLBACKS
# ─────────────────────────────────────────────────────────────────────────────

class ManualDoc(BaseDocTemplate):
    """Custom doc template that tracks the current section for the header."""

    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self.current_section = ""

    def handle_flowable(self, flowable):
        if hasattr(flowable, "_section_name"):
            self.current_section = flowable._section_name
        super().handle_flowable(flowable)


class SectionMarker(Spacer):
    """Zero-height spacer that carries section name metadata for the header."""
    def __init__(self, name):
        super().__init__(0, 0)
        self._section_name = name


def draw_header_footer(canvas, doc, is_cover=False):
    if is_cover:
        return
    canvas.saveState()
    page = canvas.getPageNumber()
    section = getattr(doc, "current_section", "")

    # ── top rule + section name ────────────────────────────────────────────
    y_top = PAGE_H - MARGIN_T + 2 * mm
    canvas.setStrokeColor(C_ORANGE)
    canvas.setLineWidth(1.2)
    canvas.line(MARGIN_L, y_top, PAGE_W - MARGIN_R, y_top)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(C_DIM)
    canvas.drawString(MARGIN_L, y_top + 2 * mm,
                      "HAYSEY'S ASTROSTACKER  —  USER MANUAL")
    if section:
        canvas.drawRightString(PAGE_W - MARGIN_R, y_top + 2 * mm, section)

    # ── bottom rule + page number ──────────────────────────────────────────
    y_bot = MARGIN_B - 4 * mm
    canvas.setStrokeColor(C_RULE)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN_L, y_bot, PAGE_W - MARGIN_R, y_bot)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(C_DIM)
    canvas.drawCentredString(PAGE_W / 2, y_bot - 4 * mm, f"— {page} —")
    canvas.drawString(MARGIN_L, y_bot - 4 * mm, "© 2025 Andrew Hayes")
    canvas.drawRightString(PAGE_W - MARGIN_R, y_bot - 4 * mm,
                           "github.com/haysey/astrostacker")

    canvas.restoreState()


def draw_cover(canvas, doc):
    """Draw the full cover page."""
    canvas.saveState()
    W, H = PAGE_W, PAGE_H

    # ── dark background ────────────────────────────────────────────────────
    canvas.setFillColor(C_BG_DARK)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)

    # ── star field ────────────────────────────────────────────────────────
    rng = random.Random(42)
    for _ in range(340):
        x = rng.uniform(5, W - 5)
        y = rng.uniform(5, H - 5)
        r = rng.choice([0.4, 0.4, 0.6, 0.6, 0.9, 1.2])
        alpha = rng.uniform(0.25, 0.9)
        canvas.setFillColor(colors.Color(1, 1, 1, alpha=alpha))
        canvas.circle(x, y, r, fill=1, stroke=0)

    # ── Southern Cross constellation (decorative, lower-right) ────────────
    sc = [  # (dx, dy) offsets from anchor
        (0,   0),    # Acrux  (bottom)
        (8,  28),    # Mimosa (right)
        (-14, 46),   # Gamma  (top)
        (-30, 26),   # Delta  (left)
        (-6,  22),   # Epsilon (centre)
    ]
    ax, ay = W - 55 * mm, 38 * mm
    star_sizes = [2.2, 1.8, 1.6, 1.4, 0.9]
    canvas.setFillColor(colors.Color(1.0, 0.843, 0.118, alpha=0.90))
    for (dx, dy), sz in zip(sc, star_sizes):
        canvas.circle(ax + dx, ay + dy, sz, fill=1, stroke=0)
    # draw cross lines
    canvas.setStrokeColor(colors.Color(1.0, 0.843, 0.118, alpha=0.25))
    canvas.setLineWidth(0.5)
    pts = [(ax + dx, ay + dy) for dx, dy in sc[:4]]
    canvas.line(pts[0][0], pts[0][1], pts[2][0], pts[2][1])
    canvas.line(pts[1][0], pts[1][1], pts[3][0], pts[3][1])

    # ── centre panel ──────────────────────────────────────────────────────
    panel_w = 140 * mm
    panel_h = 170 * mm
    panel_x = (W - panel_w) / 2
    panel_y = (H - panel_h) / 2 + 8 * mm

    canvas.setFillColor(colors.Color(0.12, 0.14, 0.24, alpha=0.85))
    canvas.setStrokeColor(C_BRONZE)
    canvas.setLineWidth(1.2)
    _rounded_rect(canvas, panel_x, panel_y, panel_w, panel_h, 6 * mm)

    # ── app icon ──────────────────────────────────────────────────────────
    if ICON.exists():
        icon_size = 54 * mm
        icon_x = (W - icon_size) / 2
        icon_y = panel_y + panel_h - icon_size - 14 * mm
        canvas.drawImage(str(ICON), icon_x, icon_y,
                         width=icon_size, height=icon_size,
                         preserveAspectRatio=True, mask="auto")

    # ── title text ────────────────────────────────────────────────────────
    text_cx = W / 2
    title_y  = panel_y + panel_h - 82 * mm

    canvas.setFont("Helvetica", 13)
    canvas.setFillColor(colors.HexColor("#8899AA"))
    canvas.drawCentredString(text_cx, title_y, "HAYSEY'S")

    canvas.setFont("Helvetica-Bold", 30)
    canvas.setFillColor(C_TEXT_MAIN)
    canvas.drawCentredString(text_cx, title_y - 18 * mm, "ASTROSTACKER")

    # bronze divider
    dw = 80 * mm
    dy = title_y - 24 * mm
    canvas.setStrokeColor(C_BRONZE)
    canvas.setLineWidth(1.5)
    canvas.line((W - dw) / 2, dy, (W + dw) / 2, dy)

    # "USER MANUAL"
    canvas.setFont("Helvetica-Bold", 18)
    canvas.setFillColor(C_ORANGE)
    canvas.drawCentredString(text_cx, dy - 10 * mm, "USER MANUAL")

    # version + codename
    canvas.setFont("Helvetica", 11)
    canvas.setFillColor(colors.HexColor("#7788AA"))
    canvas.drawCentredString(text_cx, dy - 20 * mm, "Version 1.0.0  ·  Beta Bronze")

    # decorative star row
    stars_y = dy - 27 * mm
    canvas.setFillColor(C_BRONZE)
    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(text_cx, stars_y, "✦  ✦  ✦")

    # feature list
    features = [
        "Full calibration pipeline  ·  9 stacking methods",
        "PSF frame rejection  ·  Drizzle super-resolution",
        "Star reduction  ·  Colour balance  ·  Crop tool",
        "Plate solving & WCS embedding  ·  Mosaic builder",
        "Non-Local Means denoise  ·  PSF-informed sharpening",
    ]
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#8899BB"))
    fy = stars_y - 9 * mm
    for feat in features:
        canvas.drawCentredString(text_cx, fy, feat)
        fy -= 6 * mm

    # copyright strip at bottom of panel
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#556677"))
    canvas.drawCentredString(text_cx, panel_y + 7 * mm,
                             "© 2025 Andrew Hayes  ·  Free for personal non-commercial use")

    # ── bottom tagline ────────────────────────────────────────────────────
    canvas.setFont("Helvetica-Oblique", 9)
    canvas.setFillColor(colors.HexColor("#445566"))
    canvas.drawCentredString(W / 2, 14 * mm,
                             "github.com/haysey/astrostacker")

    canvas.restoreState()


def _rounded_rect(canvas, x, y, w, h, r):
    """Draw a filled + stroked rounded rectangle."""
    from reportlab.graphics.shapes import Rect
    p = canvas.beginPath()
    p.moveTo(x + r, y)
    p.lineTo(x + w - r, y)
    p.arcTo(x + w - 2*r, y, x + w, y + 2*r, -90, 90)
    p.lineTo(x + w, y + h - r)
    p.arcTo(x + w - 2*r, y + h - 2*r, x + w, y + h, 0, 90)
    p.lineTo(x + r, y + h)
    p.arcTo(x, y + h - 2*r, x + 2*r, y + h, 90, 90)
    p.lineTo(x, y + r)
    p.arcTo(x, y, x + 2*r, y + 2*r, 180, 90)
    p.close()
    canvas.drawPath(p, fill=1, stroke=1)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FLOWABLES
# ─────────────────────────────────────────────────────────────────────────────

def section_rule():
    return HRFlowable(width="100%", thickness=1.5, color=C_ORANGE,
                      spaceAfter=4, spaceBefore=2)


def light_rule():
    return HRFlowable(width="100%", thickness=0.5, color=C_RULE,
                      spaceAfter=3, spaceBefore=3)


def tip_box(text, style, is_problem=False):
    """Orange-bordered callout box."""
    bg    = C_WARN_BG   if is_problem else C_TIP_BG
    bdr   = C_WARN_BORDER if is_problem else C_TIP_BORDER
    inner = Table([[Paragraph(text, style)]], colWidths=[BODY_W - 20])
    inner.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), bg),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("LINEAFTER",    (0, 0), (0, -1),  0, colors.white),
    ]))
    outer = Table([[" ", inner]], colWidths=[4, BODY_W - 4])
    outer.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, -1),  bdr),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))
    return outer


def code_box(lines, styles):
    text = "\n".join(lines)
    p = Preformatted(text, styles["code"])
    t = Table([[p]], colWidths=[BODY_W])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), C_CODE_BG),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("BOX",          (0, 0), (-1, -1), 0.5, C_RULE),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [3]),
    ]))
    return t


def styled_table(rows, col_widths, has_header=True):
    t = Table(rows, colWidths=col_widths, repeatRows=1 if has_header else 0)
    style = [
        ("FONTNAME",     (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9.5),
        ("LEADING",      (0, 0), (-1, -1), 13),
        ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("GRID",         (0, 0), (-1, -1), 0.4, C_RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_TABLE_ALT]),
    ]
    if has_header:
        style += [
            ("BACKGROUND",   (0, 0), (-1, 0), C_TABLE_HDR),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, 0), 9.5),
        ]
    t.setStyle(TableStyle(style))
    return t


# ─────────────────────────────────────────────────────────────────────────────
# CONTENT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_content(styles):
    story = []
    txt = SRC_TXT.read_text(encoding="utf-8")
    lines = txt.splitlines()

    # State
    in_code_block   = False
    code_lines      = []
    in_problem      = False
    problem_lines   = []
    solution_lines  = []
    pending_section = ""
    i = 0

    def flush_code():
        nonlocal in_code_block, code_lines
        if code_lines:
            story.append(Spacer(1, 2 * mm))
            story.append(code_box(code_lines, styles))
            story.append(Spacer(1, 2 * mm))
        in_code_block = False
        code_lines = []

    def flush_problem():
        nonlocal in_problem, problem_lines, solution_lines
        if problem_lines:
            prob_text = " ".join(problem_lines)
            sol_text  = " ".join(solution_lines)
            block = [
                Paragraph("⚠  " + prob_text, styles["prob"]),
                Paragraph(sol_text,           styles["sol"]),
            ]
            story.append(KeepTogether([tip_box(
                "⚠  " + prob_text + "<br/>" + sol_text,
                styles["body"],
                is_problem=True,
            ), Spacer(1, 2*mm)]))
        in_problem    = False
        problem_lines = []
        solution_lines = []

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # ── Skip the top/bottom banner and blank lines between ─────────────
        if re.match(r"^={50,}", stripped):
            i += 1
            continue

        # ── Top-level section heading: "N.  TITLE" ─────────────────────────
        m = re.match(r"^(\d+)\.\s{1,3}([A-Z][A-Z &/'.—–-]+)$", stripped)
        if m:
            flush_code()
            flush_problem()
            sec_num  = m.group(1)
            sec_name = m.group(2).strip()
            full     = f"{sec_num}.  {sec_name}"
            pending_section = full

            # Page break before each major section (except first content)
            if sec_num != "1":
                story.append(PageBreak())

            story.append(SectionMarker(full))
            story.append(section_rule())
            story.append(Paragraph(
                f'<font color="{C_ORANGE.hexval()}">{sec_num}.</font>  {sec_name}',
                styles["h1"]))
            story.append(Spacer(1, 2 * mm))
            i += 1
            continue

        # ── Subsection: "── N.N  TITLE ───" ──────────────────────────────
        m = re.match(r"^──\s+(\d+\.\d+)\s+(.+?)\s*─*$", stripped)
        if m:
            flush_code()
            flush_problem()
            sub_num  = m.group(1)
            sub_name = m.group(2).strip()
            story.append(Spacer(1, 3 * mm))
            story.append(light_rule())
            story.append(Paragraph(
                f'<font color="{C_ORANGE.hexval()}">{sub_num}</font>  '
                f'<b>{sub_name}</b>',
                styles["h2"]))
            story.append(Spacer(1, 1 * mm))
            i += 1
            continue

        # ── Subsection without number: "── TITLE ─────" ───────────────────
        m = re.match(r"^──\s+([A-Z][^─]+?)\s*─+$", stripped)
        if m:
            flush_code()
            flush_problem()
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph(f'<b>{m.group(1).strip()}</b>', styles["h2"]))
            story.append(Spacer(1, 1 * mm))
            i += 1
            continue

        # ── PROBLEM / SOLUTION pairs ───────────────────────────────────────
        if stripped.startswith("PROBLEM:"):
            flush_code()
            flush_problem()
            in_problem = True
            problem_lines  = [stripped[len("PROBLEM:"):].strip()]
            solution_lines = []
            i += 1
            continue
        if in_problem and stripped.startswith("SOLUTION:"):
            solution_lines = [stripped[len("SOLUTION:"):].strip()]
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                if nxt.startswith("PROBLEM:") or not nxt:
                    break
                if not nxt.startswith("SOLUTION:"):
                    solution_lines.append(nxt)
                i += 1
            flush_problem()
            continue

        # ── ASCII diagram / code block ─────────────────────────────────────
        # Detect the interface diagram
        if stripped.startswith("┌") or stripped.startswith("├") or \
           stripped.startswith("│") or stripped.startswith("└") or \
           (len(raw) > 2 and raw[0] == " " and raw[1] == " " and
            any(c in raw for c in "┌│├└┤┬┴┼─")):
            if not in_code_block:
                in_code_block = True
                code_lines = []
            code_lines.append(raw.rstrip())
            i += 1
            continue
        else:
            if in_code_block:
                flush_code()

        # ── Tables (ASCII table with ─── separators) ──────────────────────
        # Detect "  Frame  Best method(s)" style tables
        if re.match(r"^\s{2,}[\w/\-]+\s{2,}", raw) and not stripped.startswith("-"):
            # check if this looks like a data table (multiple spaces between cols)
            pass  # handle inline below

        # ── Blank lines ────────────────────────────────────────────────────
        if not stripped:
            if in_code_block:
                code_lines.append("")
            i += 1
            continue

        # ── Glossary terms (bold term followed by definition) ──────────────
        # Pattern: "TermName" on its own line, definition indented on next
        if (re.match(r"^[A-Z][A-Za-z /()]+$", stripped) and
                len(stripped) < 45 and
                i + 1 < len(lines) and
                lines[i + 1].startswith("  ")):
            flush_code()
            story.append(KeepTogether([
                Paragraph(stripped, styles["gloss_term"]),
                Paragraph(lines[i + 1].strip(), styles["gloss_def"]),
            ]))
            i += 2
            # Consume continuation lines of definition
            while i < len(lines) and lines[i].startswith("  ") and \
                  not re.match(r"^[A-Z][A-Za-z /()]+$", lines[i].strip()):
                story.append(Paragraph(lines[i].strip(), styles["gloss_def"]))
                i += 1
            continue

        # ── Bullet points ─────────────────────────────────────────────────
        if re.match(r"^\s{0,6}-\s+", raw) or re.match(r"^\s{0,6}·\s+", raw):
            flush_code()
            text = re.sub(r"^\s*[-·]\s+", "", stripped)
            text = _fmt(text)
            story.append(Paragraph("•  " + text, styles["bullet"]))
            i += 1
            continue

        # ── Indented sub-bullets ───────────────────────────────────────────
        if re.match(r"^\s{6,}-\s+", raw):
            flush_code()
            text = _fmt(re.sub(r"^\s*-\s+", "", stripped))
            story.append(Paragraph("   ◦  " + text, styles["bullet"]))
            i += 1
            continue

        # ── Inline code / preformatted looking lines (heavy indent) ────────
        if re.match(r"^\s{4,}\S", raw) and not re.match(r"^\s{4,}-", raw):
            # Could be a code snippet or table row
            if any(c in raw for c in ["/", "\\", ".", "=", "→", "~"]) or \
               raw.count(" ") > 3:
                if not in_code_block:
                    in_code_block = True
                    code_lines = []
                code_lines.append(raw.rstrip())
                i += 1
                continue
            else:
                if in_code_block:
                    flush_code()

        # ── SNR / method tables (aligned cols with ──── separator rows) ────
        if re.match(r"^\s*[─]+\s*$", stripped):
            i += 1
            continue  # skip pure rule lines in tables

        # ── Regular body paragraph ─────────────────────────────────────────
        flush_code()
        text = _fmt(stripped)
        if text:
            story.append(Paragraph(text, styles["body"]))
        i += 1

    flush_code()
    flush_problem()
    return story


def _fmt(text: str) -> str:
    """Apply inline markup: backticks → code font, bold markers."""
    # Escape XML special chars first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # Backtick code
    text = re.sub(r"`([^`]+)`", r'<font face="Courier" size="9">\1</font>', text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# BUILT-IN TABLES (inserted as proper ReportLab tables)
# ─────────────────────────────────────────────────────────────────────────────

def snr_table(styles):
    rows = [
        ["Frames", "SNR improvement"],
        ["2",   "1.4×"],
        ["5",   "2.2×"],
        ["10",  "3.2×"],
        ["20",  "4.5×"],
        ["50",  "7.1×"],
        ["100", "10.0×"],
    ]
    return styled_table(rows, [60 * mm, 90 * mm])


def method_table(styles):
    rows = [
        ["Frame count",      "Recommended method(s)"],
        ["Any number",       "Median — safe default"],
        ["3–10 frames",      "Percentile Clipping or Winsorized Sigma"],
        ["10–20 frames",     "Winsorized Sigma or Percentile Clipping"],
        ["20+ frames",       "Sigma Clipping (best SNR)"],
        ["30+ frames",       "Sigma Clipping or Weighted Mean"],
        ["Varying quality",  "Weighted Mean or Noise-Weighted Mean"],
        ["Very clean data",  "Mean (Average) — maximum SNR"],
    ]
    return styled_table(rows, [65 * mm, BODY_W - 65 * mm])


def cal_table(styles):
    rows = [
        ["Frame type",   "Minimum", "Recommended", "Purpose"],
        ["Darks",        "0",       "15–20",        "Remove thermal noise, hot pixels"],
        ["Flats",        "0",       "15–20",        "Remove vignetting, dust spots"],
        ["Dark Flats",   "0",       "10–15",        "Calibrate flats more accurately"],
    ]
    return styled_table(rows,
                        [35 * mm, 22 * mm, 32 * mm, BODY_W - 89 * mm])


def pixel_table(styles):
    rows = [
        ["Camera",                    "Pixel size (µm)"],
        ["ZWO ASI294MC Pro",          "4.63"],
        ["ZWO ASI2600MC Pro",         "3.76"],
        ["ZWO ASI183MC Pro",          "2.40"],
        ["ZWO ASI071MC Pro",          "4.78"],
        ["Canon EOS R5",              "4.40"],
        ["Canon EOS 600D (T3i)",      "4.30"],
        ["Nikon D7500",               "4.23"],
        ["Sony A7 IV",                "5.95"],
        ["Altair 26C",                "3.76"],
        ["Player One Neptune-C II",   "2.90"],
    ]
    return styled_table(rows, [100 * mm, BODY_W - 100 * mm])


# ─────────────────────────────────────────────────────────────────────────────
# TABLE OF CONTENTS PAGE
# ─────────────────────────────────────────────────────────────────────────────

SECTIONS = [
    ("1",  "Introduction"),
    ("2",  "System Requirements & Supported File Formats"),
    ("3",  "Interface Overview"),
    ("4",  "First-Run Setup Wizard"),
    ("5",  "The Stacking Tab — Loading Your Frames"),
    ("6",  "Settings Panel — Camera & Processing"),
    ("7",  "Processing Options"),
    ("8",  "Running the Pipeline"),
    ("9",  "Preview Panel & Histogram"),
    ("10", "Post-Processing Window"),
    ("11", "Plate Solve Tab"),
    ("12", "Mosaic Tab"),
    ("13", "Tools Menu"),
    ("14", "File Menu"),
    ("15", "Stacking Strategy Guide"),
    ("16", "Troubleshooting"),
    ("17", "Glossary"),
]


def build_toc_page(styles):
    story = []
    story.append(SectionMarker("Table of Contents"))
    story.append(section_rule())
    story.append(Paragraph(
        f'<font color="{C_ORANGE.hexval()}">✦</font>  TABLE OF CONTENTS',
        styles["h1"]))
    story.append(Spacer(1, 4 * mm))

    for num, title in SECTIONS:
        row = [[
            Paragraph(f'<b>{num}.</b>', ParagraphStyle(
                "tn", fontName="Helvetica-Bold", fontSize=10.5,
                textColor=C_ORANGE, leading=15)),
            Paragraph(title, styles["toc1"]),
        ]]
        t = Table(row, colWidths=[14 * mm, BODY_W - 14 * mm])
        t.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",   (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
        ]))
        story.append(t)

    story.append(PageBreak())
    return story


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"Reading:  {SRC_TXT}")
    print(f"Writing:  {OUT_PDF}")

    styles = build_styles()

    # ── Document template ─────────────────────────────────────────────────
    doc = ManualDoc(
        str(OUT_PDF),
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T + HDR_H,
        bottomMargin=MARGIN_B + FTR_H,
    )

    cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id="cover",
                        leftPadding=0, rightPadding=0,
                        topPadding=0, bottomPadding=0)
    body_frame  = Frame(MARGIN_L, MARGIN_B + FTR_H,
                        BODY_W, PAGE_H - MARGIN_T - HDR_H - MARGIN_B - FTR_H,
                        id="body")

    cover_tpl = PageTemplate(id="Cover", frames=[cover_frame],
                             onPage=draw_cover)
    body_tpl  = PageTemplate(id="Body",  frames=[body_frame],
                             onPage=draw_header_footer)
    doc.addPageTemplates([cover_tpl, body_tpl])

    # ── Story ─────────────────────────────────────────────────────────────
    from reportlab.platypus import NextPageTemplate

    story = []

    # Cover page (uses Cover template — no flowables needed, drawn by callback)
    story.append(NextPageTemplate("Body"))
    story.append(PageBreak())

    # Table of Contents
    story.extend(build_toc_page(styles))

    # Main content parsed from the .txt file
    story.extend(build_content(styles))

    # ── Build ─────────────────────────────────────────────────────────────
    doc.build(story)
    print(f"Done!  ->  {OUT_PDF}")
    print(f"           {OUT_PDF.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
