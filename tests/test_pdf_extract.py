from pathlib import Path
from modules.pdf_extract import extract_text

FIXTURE_PDF = Path(__file__).resolve().parents[1] / "original" / "paper.pdf"

def test_extract_text_from_real_pdf_succeeds():
    pdf_bytes = FIXTURE_PDF.read_bytes()
    text, status = extract_text(pdf_bytes)
    assert status == "ok"
    assert len(text) > 100

def test_extract_text_from_garbage_bytes_fails():
    text, status = extract_text(b"this is not a pdf")
    assert status == "failed"
    assert text == ""

def test_extract_text_from_empty_bytes_fails():
    text, status = extract_text(b"")
    assert status == "failed"
    assert text == ""
