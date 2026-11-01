# -*- coding: utf-8 -*-
from modules.export_pdf import build_report_pdf

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
