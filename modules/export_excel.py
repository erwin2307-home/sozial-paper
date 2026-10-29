from io import BytesIO
import openpyxl

COLUMNS = [
    "title", "authors", "year", "source",
    "forschungsfrage", "theoretischer_rahmen", "methodik", "stichprobe",
    "datenerhebung", "ergebnisse", "limitationen", "implikationen",
]

_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _sanitize_cell(value):
    """Prevent formula injection in Excel cells by prefixing formula-like strings with '."""
    text = str(value) if value is not None else ""
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def build_workbook(papers: list) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Berichte"
    ws.append(COLUMNS)
    for paper in papers:
        report = paper.get("report") or {}
        row = [paper.get("title", ""), paper.get("authors", ""), paper.get("year", ""), paper.get("source", "")]
        row += [report.get(field, "") for field in COLUMNS[4:]]
        # Sanitize all cell values to prevent formula injection
        sanitized_row = [_sanitize_cell(value) for value in row]
        ws.append(sanitized_row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
