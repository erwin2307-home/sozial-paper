# -*- coding: utf-8 -*-
from modules.export_pdf import build_report_pdf, build_text_report_pdf, _sanitize

def test_build_report_pdf_returns_valid_pdf_bytes():
    report = {
        "forschungsfrage": "Wie wirkt sich Bildung auf Einkommen aus?",
        "theoretischer_rahmen": "Humankapitaltheorie",
        "methodik": "quantitativ",
        "stichprobe": "1.200 Befragte",
        "datenerhebung": "Online-Survey 2022",
        "ergebnisse": "Positiver Zusammenhang",
        "limitationen": "Querschnittsdaten",
        "implikationen": "Bildungsfoerderung sinnvoll",
    }
    pdf_bytes = build_report_pdf("Titel mit Umlaut – äöüß", report)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500

def test_build_report_pdf_handles_smart_quotes_without_crashing():
    report = {"forschungsfrage": "Er sagte „es funktioniert“ — angeblich."}
    pdf_bytes = build_report_pdf("Test", report)
    assert pdf_bytes.startswith(b"%PDF")


def test_sanitize_converts_smart_quotes_to_ascii_not_question_marks():
    # Covers all smart-quote/dash variants the _REPLACEMENTS table should map,
    # including the German low opening quote „ which the broken dict
    # (unescaped quotes mangled into no-op straight-quote keys) never had.
    text = "Müller's ‘Test’ — “Titel” „Titel“ … Ende"
    result = _sanitize(text)
    assert "?" not in result
    assert "'" in result
    assert '"' in result
    assert "-" in result
    assert "..." in result
    # the mangled dict left curly quotes untouched -> they'd get replaced
    # with "?" by the latin-1 encode step; confirm none of the original
    # curly characters survive either.
    for curly in ("‘", "’", "“", "”", "„", "–", "—", "…"):
        assert curly not in result


def test_build_text_report_pdf_returns_valid_pdf_bytes():
    pdf_bytes = build_text_report_pdf(
        "Aufgabe: Diversitaet und Intersektionalitaet",
        "Dies ist ein Fliesstext mit Umlauten: äöüß und mehreren Saetzen. " * 5,
    )
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500
