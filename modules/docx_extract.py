from io import BytesIO

from docx import Document


def extract_text(docx_bytes: bytes) -> tuple:
    if not docx_bytes:
        return "", "failed"
    try:
        document = Document(BytesIO(docx_bytes))
        full_text = "\n".join(p.text for p in document.paragraphs).strip()
    except Exception:
        return "", "failed"
    if not full_text:
        return "", "failed"
    return full_text, "ok"
