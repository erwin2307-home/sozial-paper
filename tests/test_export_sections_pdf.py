from io import BytesIO

from pypdf import PdfReader

from modules.export_pdf import build_report_pdf, build_sections_pdf


def _text(pdf_bytes):
    return "".join(page.extract_text() for page in PdfReader(BytesIO(pdf_bytes)).pages)


def _bold_lines(pdf_bytes):
    """Collect text drawn with the embedded bold font."""
    lines = []

    def visitor(text, _cm, _tm, font, _size):
        if font and "Bold" in str(font.get("/BaseFont", "")) and text.strip():
            lines.append(text.strip())

    for page in PdfReader(BytesIO(pdf_bytes)).pages:
        page.extract_text(visitor_text=visitor)
    return " ".join(lines)


def _assert_text_starts_at_left_margin(pdf_bytes):
    """Every line must start at the left margin: text can be extracted even when drawn off the page."""
    positions = []

    def visitor(text, _cm, tm, _font, _size):
        if text.strip():
            positions.append(tm[4])

    page = PdfReader(BytesIO(pdf_bytes)).pages[0]
    page.extract_text(visitor_text=visitor)
    assert positions
    assert max(positions) < float(page.mediabox.width) / 4


def test_sections_pdf_text_stays_on_the_page():
    _assert_text_starts_at_left_margin(build_sections_pdf("T", [("A", "Absatz eins.\n\nAbsatz zwei."), ("B", "Ende.")]))


def test_report_pdf_text_stays_on_the_page():
    _assert_text_starts_at_left_margin(build_report_pdf("T", {"forschungsfrage": "Antwort"}))


def test_build_sections_pdf_returns_valid_pdf_with_all_sections():
    pdf_bytes = build_sections_pdf("Titel", [("Abstract", "Text äöü."), ("Schlusswort", "Ende.")])
    assert pdf_bytes.startswith(b"%PDF")
    text = _text(pdf_bytes)
    assert text.index("Abstract") < text.index("Schlusswort")
    assert "Text äöü." in text


def test_sections_pdf_keeps_turkish_and_special_characters():
    text = _text(build_sections_pdf("Şule", [("Abschnitt", "İpek, ğ, ı, ş, ≈ und → sowie „Zitat“ – Ende…")]))
    assert "Şule" in text
    assert "İpek, ğ, ı, ş, ≈ und → sowie „Zitat“ – Ende…" in text
    assert "?" not in text


def test_sections_pdf_sets_question_lines_in_bold():
    pdf_bytes = build_sections_pdf("T", [("Hauptteil", "Frage 1: Was gilt?\n\nDie Antwort steht hier.")])
    assert "Frage 1: Was gilt?" in _bold_lines(pdf_bytes)
    assert "Die Antwort steht hier." not in _bold_lines(pdf_bytes)


def test_report_pdf_keeps_turkish_characters():
    assert "Şule ≈ ğ" in _text(build_report_pdf("T", {"forschungsfrage": "Şule ≈ ğ"}))
