from io import BytesIO
from pypdf import PdfReader


def extract_text(pdf_bytes: bytes) -> tuple:
    if not pdf_bytes:
        return "", "failed"
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        full_text = "\n".join(pages_text).strip()
    except Exception:
        return "", "failed"
    if not full_text:
        return "", "failed"
    return full_text, "ok"
