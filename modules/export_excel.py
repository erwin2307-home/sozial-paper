from io import BytesIO
import openpyxl

COLUMNS = [
    "title", "authors", "year", "source",
    "forschungsfrage", "theoretischer_rahmen", "methodik", "stichprobe",
    "datenerhebung", "ergebnisse", "limitationen", "implikationen",
]


def build_workbook(papers: list) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Berichte"
    ws.append(COLUMNS)
    for paper in papers:
        report = paper.get("report") or {}
        row = [paper.get("title", ""), paper.get("authors", ""), paper.get("year", ""), paper.get("source", "")]
        row += [report.get(field, "") for field in COLUMNS[4:]]
        ws.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
