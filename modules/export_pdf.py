# -*- coding: utf-8 -*-
import re
from pathlib import Path

from fpdf import FPDF

from modules.report_schema import SCHEMA_FIELDS

FIELD_LABELS = {
    "forschungsfrage": "Forschungsfrage",
    "theoretischer_rahmen": "Theoretischer Rahmen",
    "methodik": "Methodik",
    "stichprobe": "Stichprobe",
    "datenerhebung": "Datenerhebung",
    "ergebnisse": "Ergebnisse",
    "limitationen": "Limitationen",
    "implikationen": "Implikationen",
}

_FONT_DIR = Path(__file__).resolve().parent.parent / "content" / "fonts"
_FONT = "DejaVu"
_QUESTION_LINE = re.compile(r"^Frage \d+:")


def is_question_line(paragraph: str) -> bool:
    return bool(_QUESTION_LINE.match(paragraph))


def _new_pdf() -> FPDF:
    pdf = FPDF()
    # The core PDF fonts only cover Latin-1; this one also covers e.g. Turkish.
    pdf.add_font(_FONT, "", _FONT_DIR / "DejaVuSans.ttf")
    pdf.add_font(_FONT, "B", _FONT_DIR / "DejaVuSans-Bold.ttf")
    pdf.add_page()
    return pdf


def _write(pdf: FPDF, text: str, height: float, size: int, bold: bool = False) -> None:
    pdf.set_font(_FONT, "B" if bold else "", size)
    # Without new_x, multi_cell leaves the cursor at the right edge and the next call draws off the page.
    pdf.multi_cell(0, height, text or "", new_x="LMARGIN", new_y="NEXT")


def build_report_pdf(title: str, report: dict) -> bytes:
    pdf = _new_pdf()
    _write(pdf, title, 10, 16, bold=True)
    for field in SCHEMA_FIELDS:
        pdf.ln(2)
        _write(pdf, FIELD_LABELS.get(field, field), 8, 12, bold=True)
        _write(pdf, report.get(field, "nicht angegeben"), 7, 11)
    return bytes(pdf.output())


def build_sections_pdf(title: str, sections: list) -> bytes:
    pdf = _new_pdf()
    _write(pdf, title, 10, 16, bold=True)
    for heading, body in sections:
        pdf.ln(5)
        _write(pdf, heading, 8, 13, bold=True)
        for paragraph in re.split(r"\n\s*\n", body or ""):
            if paragraph.strip():
                pdf.ln(2)
                _write(pdf, paragraph.strip(), 6, 11, bold=is_question_line(paragraph))
    return bytes(pdf.output())
