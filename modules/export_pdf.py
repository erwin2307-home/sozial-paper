# -*- coding: utf-8 -*-
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

_REPLACEMENTS = {
    "‘": "'", "’": "'",
    "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "-", "…": "...",
}


def _sanitize(text: str) -> str:
    text = text or ""
    for src, dst in _REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def build_report_pdf(title: str, report: dict) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    # fpdf2 2.8.9: multi_cell(0, ...) fails with "Not enough horizontal space" on consecutive calls
    # because width=0 means "use remaining width on current line", and multi_cell doesn't auto-newline.
    # Use width=190 (A4 with default margins) instead for reliable text wrapping.
    pdf.multi_cell(190, 10, _sanitize(title))
    for field in SCHEMA_FIELDS:
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(190, 8, _sanitize(FIELD_LABELS.get(field, field)))
        pdf.set_font("Helvetica", "", 12)
        pdf.multi_cell(190, 8, _sanitize(report.get(field, "nicht angegeben")))
        pdf.ln(2)
    return bytes(pdf.output())


def build_text_report_pdf(title: str, body_text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(190, 10, _sanitize(title))
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(190, 8, _sanitize(body_text))
    return bytes(pdf.output())
