from io import BytesIO
import openpyxl
from modules.export_excel import build_workbook, COLUMNS

def test_build_workbook_has_header_and_rows():
    papers = [
        {"title": "Paper A", "authors": "Max Muster", "year": 2021, "source": "upload",
         "report": {"forschungsfrage": "Frage A", "ergebnisse": "Ergebnis A"}},
        {"title": "Paper B", "authors": "", "year": None, "source": "core", "report": None},
    ]
    xlsx_bytes = build_workbook(papers)
    wb = openpyxl.load_workbook(BytesIO(xlsx_bytes))
    ws = wb.active
    header = [cell.value for cell in ws[1]]
    assert header == COLUMNS
    row_a = [cell.value for cell in ws[2]]
    assert row_a[0] == "Paper A"
    assert row_a[COLUMNS.index("forschungsfrage")] == "Frage A"
    row_b = [cell.value for cell in ws[3]]
    assert row_b[0] == "Paper B"
    assert row_b[COLUMNS.index("forschungsfrage")] in ("", None)
