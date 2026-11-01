from io import BytesIO

from docx import Document
from docx.table import Table


def _table_lines(table: Table) -> list:
    lines = []
    for row in table.rows:
        seen = []
        cells = []
        for cell in row.cells:
            # Merged cells appear once per spanned column but share one element.
            if cell._tc not in seen:
                seen.append(cell._tc)
                cells.append(cell.text.strip())
        lines.append(" | ".join(text for text in cells if text))
    return lines


def extract_text(docx_bytes: bytes) -> tuple:
    if not docx_bytes:
        return "", "failed"
    try:
        document = Document(BytesIO(docx_bytes))
        lines = []
        for block in document.iter_inner_content():
            if isinstance(block, Table):
                lines.extend(_table_lines(block))
            else:
                lines.append(block.text)
        full_text = "\n".join(lines).strip()
    except Exception:
        return "", "failed"
    if not full_text:
        return "", "failed"
    return full_text, "ok"
