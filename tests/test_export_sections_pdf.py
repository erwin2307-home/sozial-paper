from io import BytesIO

from pypdf import PdfReader

from modules.export_pdf import build_sections_pdf


def test_build_sections_pdf_returns_valid_pdf_with_all_sections():
    pdf_bytes = build_sections_pdf("Titel", [("Abstract", "Text äöü."), ("Schlusswort", "Ende.")])
    assert pdf_bytes.startswith(b"%PDF")
    text = "".join(page.extract_text() for page in PdfReader(BytesIO(pdf_bytes)).pages)
    assert text.index("Abstract") < text.index("Schlusswort")
    assert "Text äöü." in text
