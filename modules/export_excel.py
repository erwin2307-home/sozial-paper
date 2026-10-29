from io import BytesIO
import openpyxl

COLUMNS = [
    "title", "authors", "year", "source", "mode_used",
    "forschungsfrage", "theoretischer_rahmen", "methodik", "stichprobe",
    "datenerhebung", "ergebnisse", "limitationen", "implikationen",
]

_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _sanitize_cell(value):
    """Prevent formula injection in Excel cells by prefixing formula-like strings with '.

    Non-string values (e.g. an int ``year``) are passed through unchanged so
    they round-trip as their original type instead of being coerced to text.
    """
    if not isinstance(value, str):
        return value
    if value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def build_workbook(papers: list) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Berichte"
    ws.append(COLUMNS)
    for paper in papers:
        report = paper.get("report") or {}
        row = [
            paper.get("title", ""), paper.get("authors", ""), paper.get("year", ""),
            paper.get("source", ""), paper.get("mode_used", ""),
        ]
        row += [report.get(field, "") for field in COLUMNS[5:]]
        # Sanitize all cell values to prevent formula injection
        sanitized_row = [_sanitize_cell(value) for value in row]
        ws.append(sanitized_row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
