from unittest.mock import patch, MagicMock

import httpx
import anthropic
from streamlit.testing.v1 import AppTest

from modules import essay, library_state
from modules.claude_client import EmptyResponseError

# AppTest.from_file resolves a relative path against the directory of the
# file that calls it (tests/), not against the pytest invocation cwd. Use a
# path relative to this test file to reach the real app.py at the repo root.
APP_PATH = "../app.py"

# app.py transitively imports several heavy third-party packages (anthropic,
# openpyxl, fpdf2, rank_bm25, pypdf). On a cold interpreter that import alone
# can take longer than AppTest's 3s default timeout, failing the very first
# script run with an unrelated RuntimeError. Raise the timeout generously so
# the test genuinely exercises the login gate instead of flaking on import
# cost.
DEFAULT_TIMEOUT = 20


def _login(secrets=None):
    at = AppTest.from_file(APP_PATH, default_timeout=DEFAULT_TIMEOUT)
    for key, value in (secrets or {"APP_PASSWORD": "geheim123"}).items():
        at.secrets[key] = value
    at.run()
    at.text_input[0].input("geheim123").run()
    at.button[0].click().run()
    return at


def _goto(at, page):
    at.sidebar.radio[1].set_value(page).run()
    return at


def _library_with_paper(**overrides):
    lib = library_state.Library()
    defaults = dict(
        id="p1", title="Mein Paper", source="upload", extract_status="ok",
        full_text="Volltext " * 10,
    )
    defaults.update(overrides)
    lib.papers[defaults["id"]] = library_state.Paper(**defaults)
    return lib


def test_login_wrong_password_shows_error():
    at = AppTest.from_file(APP_PATH, default_timeout=DEFAULT_TIMEOUT)
    at.secrets["APP_PASSWORD"] = "geheim123"
    at.run()
    at.text_input[0].input("falsch").run()
    at.button[0].click().run()
    assert any("Falsches Passwort" in e.value for e in at.error)


def test_login_correct_password_reveals_sidebar_nav():
    at = AppTest.from_file(APP_PATH, default_timeout=DEFAULT_TIMEOUT)
    at.secrets["APP_PASSWORD"] = "geheim123"
    at.run()
    at.text_input[0].input("geheim123").run()
    at.button[0].click().run()
    assert len(at.sidebar.radio) >= 1


# ---------------------------------------------------------------------------
# C1: Claude-API errors must show a friendly st.error, never crash the page.
# ---------------------------------------------------------------------------

def test_analysis_missing_api_key_shows_error_not_exception():
    at = _login({"APP_PASSWORD": "geheim123"})  # no CLAUDE_API_KEY secret
    at.session_state["library"] = _library_with_paper()
    at.run()
    _goto(at, "Analyse")
    analysieren = [b for b in at.button if b.label == "Analysieren"][0]
    analysieren.click().run()
    assert not at.exception
    assert any("CLAUDE_API_KEY ist nicht konfiguriert" in e.value for e in at.error)


def test_analysis_rate_limit_error_shows_friendly_message_not_exception():
    at = _login({"APP_PASSWORD": "geheim123", "CLAUDE_API_KEY": "sk-test"})
    at.session_state["library"] = _library_with_paper()
    at.run()
    _goto(at, "Analyse")
    resp = httpx.Response(429, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    err = anthropic.RateLimitError("rate limited", response=resp, body=None)
    with patch("modules.analysis_direct.analyze", side_effect=err):
        analysieren = [b for b in at.button if b.label == "Analysieren"][0]
        analysieren.click().run()
    assert not at.exception
    assert any("Claude-API-Limit erreicht" in e.value for e in at.error)


def test_analysis_generic_api_error_shows_friendly_message_not_exception():
    at = _login({"APP_PASSWORD": "geheim123", "CLAUDE_API_KEY": "sk-test"})
    at.session_state["library"] = _library_with_paper()
    at.run()
    _goto(at, "Analyse")
    err = anthropic.APIConnectionError(request=httpx.Request("POST", "https://x"))
    with patch("modules.analysis_direct.analyze", side_effect=err):
        analysieren = [b for b in at.button if b.label == "Analysieren"][0]
        analysieren.click().run()
    assert not at.exception
    assert any("Claude-API-Fehler" in e.value for e in at.error)


def test_qa_missing_api_key_shows_error_not_exception():
    at = _login({"APP_PASSWORD": "geheim123"})  # no CLAUDE_API_KEY secret
    at.session_state["library"] = _library_with_paper()
    at.run()
    _goto(at, "Q&A")
    frage = [t for t in at.text_input if t.label == "Frage zum Paper"][0]
    frage.input("Was ist die Methode?").run()
    fragen_btn = [b for b in at.button if b.label == "Fragen"][0]
    fragen_btn.click().run()
    assert not at.exception
    assert any("CLAUDE_API_KEY ist nicht konfiguriert" in e.value for e in at.error)


# ---------------------------------------------------------------------------
# C2: adding a paper from search must download+extract its PDF, not leave it
# permanently full_text=None/pending.
# ---------------------------------------------------------------------------

def test_search_add_paper_downloads_and_extracts_pdf():
    at = _login({"APP_PASSWORD": "geheim123"})
    _goto(at, "Suche")
    fake_results = [{
        "id": "abc123", "title": "Ein Titel", "authors": "A. Autor", "year": 2020,
        "abstract": "Abstract", "pdf_url": "http://example.com/x.pdf", "source": "semanticscholar",
    }]
    at.session_state["search_results"] = fake_results
    at.run()
    fake_resp = MagicMock()
    fake_resp.content = b"%PDF-fake"
    fake_resp.is_redirect = False
    fake_resp.raise_for_status = MagicMock()
    with patch("socket.getaddrinfo", return_value=[(2, 0, 0, "", ("93.184.216.34", 0))]), \
         patch("app.requests.get", return_value=fake_resp) as mock_get, \
         patch("app.pdf_extract.extract_text", return_value=("extrahierter Text", "ok")):
        add_btn = [b for b in at.button if b.label == "In Bibliothek uebernehmen"][0]
        add_btn.click().run()
    mock_get.assert_called_once_with("http://example.com/x.pdf", timeout=30, allow_redirects=False)
    lib = at.session_state["library"]
    paper = library_state.get_paper(lib, "abc123")
    assert paper is not None
    assert paper.full_text == "extrahierter Text"
    assert paper.extract_status == "ok"


def test_search_add_paper_without_pdf_url_leaves_full_text_none():
    at = _login({"APP_PASSWORD": "geheim123"})
    _goto(at, "Suche")
    fake_results = [{
        "id": "noeurl", "title": "Kein PDF", "authors": "A", "year": 2021,
        "abstract": "x", "pdf_url": None, "source": "europepmc",
    }]
    at.session_state["search_results"] = fake_results
    at.run()
    add_btn = [b for b in at.button if b.label == "In Bibliothek uebernehmen"][0]
    add_btn.click().run()
    lib = at.session_state["library"]
    paper = library_state.get_paper(lib, "noeurl")
    assert paper.full_text is None
    assert paper.extract_status == "pending"


# ---------------------------------------------------------------------------
# SSRF addendum: pdf_url from a third-party search API must be validated
# before the server-side fetch (reject private/loopback/link-local/reserved
# IPs and non-http(s) schemes), so a malicious API response can't make the
# app fetch an internal/metadata address.
# ---------------------------------------------------------------------------

def test_search_add_paper_with_public_ip_pdf_url_proceeds_with_fetch():
    at = _login({"APP_PASSWORD": "geheim123"})
    _goto(at, "Suche")
    fake_results = [{
        "id": "pub1", "title": "Public", "authors": "A", "year": 2020,
        "abstract": "x", "pdf_url": "http://example.com/x.pdf", "source": "semanticscholar",
    }]
    at.session_state["search_results"] = fake_results
    at.run()
    fake_resp = MagicMock()
    fake_resp.is_redirect = False
    fake_resp.raise_for_status = MagicMock()
    with patch("socket.getaddrinfo", return_value=[(2, 0, 0, "", ("93.184.216.34", 0))]) as mock_dns, \
         patch("app.requests.get", return_value=fake_resp) as mock_get, \
         patch("app.pdf_extract.extract_text", return_value=("Text", "ok")):
        add_btn = [b for b in at.button if b.label == "In Bibliothek uebernehmen"][0]
        add_btn.click().run()
    assert mock_dns.called
    mock_get.assert_called_once_with("http://example.com/x.pdf", timeout=30, allow_redirects=False)
    lib = at.session_state["library"]
    paper = library_state.get_paper(lib, "pub1")
    assert paper.full_text == "Text"
    assert paper.extract_status == "ok"


def test_search_add_paper_with_private_ip_pdf_url_is_blocked():
    at = _login({"APP_PASSWORD": "geheim123"})
    _goto(at, "Suche")
    fake_results = [{
        "id": "priv1", "title": "Private", "authors": "A", "year": 2020,
        "abstract": "x", "pdf_url": "http://internal.example/x.pdf", "source": "semanticscholar",
    }]
    at.session_state["search_results"] = fake_results
    at.run()
    with patch("socket.getaddrinfo", return_value=[(2, 0, 0, "", ("127.0.0.1", 0))]), \
         patch("app.requests.get") as mock_get:
        add_btn = [b for b in at.button if b.label == "In Bibliothek uebernehmen"][0]
        add_btn.click().run()
    mock_get.assert_not_called()
    lib = at.session_state["library"]
    paper = library_state.get_paper(lib, "priv1")
    assert paper.full_text is None
    assert paper.extract_status == "pending"


def test_search_add_paper_with_non_http_scheme_pdf_url_is_blocked():
    at = _login({"APP_PASSWORD": "geheim123"})
    _goto(at, "Suche")
    fake_results = [{
        "id": "file1", "title": "FileScheme", "authors": "A", "year": 2020,
        "abstract": "x", "pdf_url": "file:///etc/passwd", "source": "semanticscholar",
    }]
    at.session_state["search_results"] = fake_results
    at.run()
    with patch("app.requests.get") as mock_get:
        add_btn = [b for b in at.button if b.label == "In Bibliothek uebernehmen"][0]
        add_btn.click().run()
    mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# I2: re-running the script while the file_uploader still holds a file must
# not re-add/overwrite a paper that already has an analysis report.
# ---------------------------------------------------------------------------

def test_upload_rerun_does_not_wipe_existing_report():
    at = _login({"APP_PASSWORD": "geheim123"})
    _goto(at, "Upload")
    with patch("app.pdf_extract.extract_text", return_value=("Volltext", "ok")):
        at.file_uploader[0].upload("paper1.pdf", b"%PDF-fake").run()
    lib = at.session_state["library"]
    library_state.set_report(lib, "paper1.pdf", {"forschungsfrage": "x"}, "A")
    at.session_state["library"] = lib
    # Simulate a rerun while the uploader still returns the same file.
    with patch("app.pdf_extract.extract_text", return_value=("Volltext", "ok")) as mock_extract:
        at.run()
    lib2 = at.session_state["library"]
    paper = library_state.get_paper(lib2, "paper1.pdf")
    assert paper.report == {"forschungsfrage": "x"}
    mock_extract.assert_not_called()


# ---------------------------------------------------------------------------
# I5 + M9: PDF export must not require visiting the Bibliothek page first,
# must export the paper actually selected (not a hardcoded papers[0]), and
# must sanitize the title before using it as a filename.
# ---------------------------------------------------------------------------

def test_export_pdf_available_without_visiting_library_page_and_uses_selection():
    at = _login({"APP_PASSWORD": "geheim123"})
    lib = library_state.Library()
    lib.papers["p1"] = library_state.Paper(
        id="p1", title="Erstes Paper", source="upload", extract_status="ok",
        report={"forschungsfrage": "Frage 1"}, mode_used="A",
    )
    lib.papers["p2"] = library_state.Paper(
        id="p2", title="Zweites Paper", source="upload", extract_status="ok",
        report={"forschungsfrage": "Frage 2"}, mode_used="B",
    )
    at.session_state["library"] = lib
    at.run()
    # Go straight to Export WITHOUT visiting Bibliothek first (library_view
    # session key is never set) -- the PDF section must still appear.
    with patch("app.export_pdf.build_report_pdf", return_value=b"%PDF-x") as mock_build:
        _goto(at, "Export")
        assert mock_build.call_args == (("Erstes Paper", {"forschungsfrage": "Frage 1"}),)
        sb = [s for s in at.selectbox if s.label == "Paper auswaehlen"][0]
        sb.set_value("Zweites Paper").run()
        assert mock_build.call_args == (("Zweites Paper", {"forschungsfrage": "Frage 2"}),)


def test_export_pdf_filename_is_sanitized():
    at = _login({"APP_PASSWORD": "geheim123"})
    lib = library_state.Library()
    lib.papers["p1"] = library_state.Paper(
        id="p1", title='Boeser/Titel:*?"<>|', source="upload", extract_status="ok",
        report={"forschungsfrage": "Frage 1"}, mode_used="A",
    )
    at.session_state["library"] = lib
    at.run()
    with patch("streamlit.download_button") as mock_dl:
        _goto(at, "Export")
    pdf_calls = [c for c in mock_dl.call_args_list if c.kwargs.get("file_name", "").endswith(".pdf")]
    assert len(pdf_calls) == 1
    file_name = pdf_calls[0].kwargs["file_name"]
    assert "/" not in file_name
    assert "*" not in file_name
    assert "?" not in file_name
    assert ":" not in file_name
    assert '"' not in file_name
    assert "<" not in file_name and ">" not in file_name
    assert "|" not in file_name


# ---------------------------------------------------------------------------
# M10: mode_used must be surfaced as an Excel export column.
# ---------------------------------------------------------------------------

def test_export_excel_rows_include_mode_used():
    at = _login({"APP_PASSWORD": "geheim123"})
    lib = library_state.Library()
    lib.papers["p1"] = library_state.Paper(
        id="p1", title="Paper A", source="upload", extract_status="ok",
        report={"forschungsfrage": "x"}, mode_used="B",
    )
    at.session_state["library"] = lib
    at.run()
    with patch("app.export_excel.build_workbook", return_value=b"PK") as mock_build:
        _goto(at, "Export")
    rows = mock_build.call_args[0][0]
    assert rows[0]["mode_used"] == "B"


# ---------------------------------------------------------------------------
# M3: Q&A must apply the same too-long-for-Modus-A fallback as Analyse.
# ---------------------------------------------------------------------------

def test_qa_falls_back_to_mode_b_for_too_long_paper():
    at = _login({"APP_PASSWORD": "geheim123", "CLAUDE_API_KEY": "sk-test"})
    long_text = "x" * 500_001
    at.session_state["library"] = _library_with_paper(full_text=long_text)
    at.run()
    # mode stays "A" (default) -- the fallback must kick in anyway.
    _goto(at, "Q&A")
    with patch("modules.qa_engine.call_claude", return_value="Antwort") as mock_call:
        frage = [t for t in at.text_input if t.label == "Frage zum Paper"][0]
        frage.input("Was ist die Methode?").run()
        fragen_btn = [b for b in at.button if b.label == "Fragen"][0]
        fragen_btn.click().run()
    prompt_used = mock_call.call_args[0][1]
    assert len(prompt_used) < len(long_text)
    assert any("Paper zu lang" in w.value for w in at.warning)


# ---------------------------------------------------------------------------
# M4: a search result with a missing id must be skipped, not crash the page
# with a duplicate widget key.
# ---------------------------------------------------------------------------

def test_search_results_with_missing_id_do_not_crash():
    at = _login({"APP_PASSWORD": "geheim123"})
    _goto(at, "Suche")
    fake_results = [
        {"id": None, "title": "Ohne ID 1", "authors": "A", "year": 2020, "abstract": "x", "pdf_url": None, "source": "europepmc"},
        {"id": None, "title": "Ohne ID 2", "authors": "B", "year": 2021, "abstract": "y", "pdf_url": None, "source": "europepmc"},
    ]
    at.session_state["search_results"] = fake_results
    at.run()
    assert not at.exception
    assert not any(b.label == "In Bibliothek uebernehmen" for b in at.button)


# ---------------------------------------------------------------------------
# M7: feedback for empty query / no sources / zero results instead of silence.
# ---------------------------------------------------------------------------

def test_search_empty_query_and_no_sources_shows_warning():
    at = _login({"APP_PASSWORD": "geheim123"})
    _goto(at, "Suche")
    suchen_btn = [b for b in at.button if b.label == "Suchen"][0]
    suchen_btn.click().run()
    assert any("Bitte Suchbegriff eingeben" in w.value for w in at.warning)


def test_search_zero_results_shows_info():
    at = _login({"APP_PASSWORD": "geheim123"})
    _goto(at, "Suche")
    with patch("app.search_aggregator.aggregate", return_value=[]):
        q = [t for t in at.text_input if t.label == "Suchbegriff"][0]
        q.input("nichts da").run()
        suchen_btn = [b for b in at.button if b.label == "Suchen"][0]
        suchen_btn.click().run()
    assert any("Keine Treffer" in i.value for i in at.info)


# ---------------------------------------------------------------------------
# M1: titles/abstracts from third-party search results must not be rendered
# as live Markdown (image/link injection).
# ---------------------------------------------------------------------------

def test_search_abstract_rendered_as_plain_text_not_markdown():
    at = _login({"APP_PASSWORD": "geheim123"})
    _goto(at, "Suche")
    fake_results = [{
        "id": "x1", "title": "Titel [mit] (Klammern)", "authors": "A", "year": 2020,
        "abstract": "![img](http://evil.example/x.png) [link](http://phish.example)",
        "pdf_url": None, "source": "semanticscholar",
    }]
    at.session_state["search_results"] = fake_results
    at.run()
    # the raw markdown-injection payload must show up as plain st.text, and
    # the expander label (built via an f-string) must have its markdown
    # special characters escaped.
    assert any(
        t.value == "![img](http://evil.example/x.png) [link](http://phish.example)"
        for t in at.text
    )
    assert any("\\[mit\\]" in e.label and "\\(Klammern\\)" in e.label for e in at.expander)


def test_library_page_escapes_markdown_in_title():
    at = _login({"APP_PASSWORD": "geheim123"})
    at.session_state["library"] = _library_with_paper(title="Evil [click me](http://phish.example)")
    at.run()
    _goto(at, "Bibliothek")
    assert any("\\[click me\\]\\(http://phish.example\\)" in m.value for m in at.markdown)


# ---------------------------------------------------------------------------
# Aufgaben: custom-question report generation (preset + personal-text merge).
# ---------------------------------------------------------------------------

def test_aufgaben_preset_generates_result_and_download_button():
    at = _login({"APP_PASSWORD": "geheim123", "CLAUDE_API_KEY": "sk-test"})
    at.session_state["library"] = _library_with_paper()
    at.run()
    _goto(at, "Aufgaben")
    with patch("modules.essay.generate_body", return_value="Generierte Antwort.") as mock_answer:
        erstellen = [b for b in at.button if b.label == "Bericht erstellen"][0]
        erstellen.click().run()
    assert not at.exception
    questions_arg, papers_arg, language_arg, _client_arg = mock_answer.call_args[0]
    assert len(questions_arg) == 3
    assert [p.id for p in papers_arg] == ["p1"]
    assert language_arg == "de"
    assert mock_answer.call_args.kwargs["personal_perspective"] is False
    ergebnis = [t for t in at.text_area if t.label == "Ergebnis"][0].value
    assert ergebnis.index("Ich bin eine muslimische Frau") < ergebnis.index("Generierte Antwort.")
    assert ergebnis.index("Generierte Antwort.") < ergebnis.index("Methodisch wurde diese Arbeit")
    labels = {b.label for b in at.download_button}
    assert {"Als PDF herunterladen", "Als Word herunterladen"} <= labels


def test_aufgaben_personal_perspective_checkbox_reaches_generation():
    at = _login({"APP_PASSWORD": "geheim123", "CLAUDE_API_KEY": "sk-test"})
    at.session_state["library"] = _library_with_paper()
    at.run()
    _goto(at, "Aufgaben")
    at.checkbox(key="personal_perspective").check().run()
    with patch("modules.essay.generate_body", return_value="Antwort.") as mock_answer:
        [b for b in at.button if b.label == "Bericht erstellen"][0].click().run()
    assert mock_answer.call_args.kwargs["personal_perspective"] is True


def test_aufgaben_warns_when_a_question_stayed_unanswered():
    at = _login({"APP_PASSWORD": "geheim123", "CLAUDE_API_KEY": "sk-test"})
    at.session_state["library"] = _library_with_paper()
    at.run()
    _goto(at, "Aufgaben")
    body = f"Frage 1: F?\n\n{essay.MISSING_ANSWER}"
    with patch("modules.essay.generate_body", return_value=body):
        [b for b in at.button if b.label == "Bericht erstellen"][0].click().run()
    assert any("nicht beantwortet" in w.value for w in at.warning)


def test_uploaded_questions_are_forgotten_when_document_is_removed():
    at = _login({"APP_PASSWORD": "geheim123", "CLAUDE_API_KEY": "sk-test"})
    at.session_state["library"] = _library_with_paper()
    at.session_state["aufgaben_raw_text"] = "Alte Frage?"
    at.run()
    _goto(at, "Aufgaben")
    source = [r for r in at.radio if r.label == "Fragen-Quelle"][0]
    source.set_value("Eigenes Fragen-Dokument hochladen").run()
    assert "aufgaben_raw_text" not in at.session_state


def test_aufgaben_merges_personal_text_into_result():
    at = _login({"APP_PASSWORD": "geheim123", "CLAUDE_API_KEY": "sk-test"})
    at.session_state["library"] = _library_with_paper()
    at.run()
    _goto(at, "Aufgaben")
    ergaenzung = [t for t in at.text_area if t.label == "Eigene Ergaenzung (z.B. persoenliche Perspektive)"][0]
    ergaenzung.input("Mein persoenlicher Text.").run()
    with patch("modules.essay.generate_body", return_value="KI-Antwort."):
        erstellen = [b for b in at.button if b.label == "Bericht erstellen"][0]
        erstellen.click().run()
    assert not at.exception
    ergebnis = [t for t in at.text_area if t.label == "Ergebnis"][0]
    assert "KI-Antwort." in ergebnis.value
    assert "Mein persoenlicher Text." in ergebnis.value


def test_aufgaben_missing_api_key_shows_error_not_exception():
    at = _login({"APP_PASSWORD": "geheim123"})  # no CLAUDE_API_KEY secret
    at.session_state["library"] = _library_with_paper()
    at.run()
    _goto(at, "Aufgaben")
    erstellen = [b for b in at.button if b.label == "Bericht erstellen"][0]
    erstellen.click().run()
    assert not at.exception
    assert any("CLAUDE_API_KEY ist nicht konfiguriert" in e.value for e in at.error)


# ---------------------------------------------------------------------------
# Abstract fallback: found papers without a downloadable PDF stay usable.
# ---------------------------------------------------------------------------

def test_search_add_paper_reports_abstract_fallback_when_no_pdf():
    at = _login({"APP_PASSWORD": "geheim123"})
    _goto(at, "Suche")
    at.session_state["search_results"] = [{
        "id": "n1", "title": "Ohne PDF", "authors": "A", "year": 2021,
        "abstract": "Der Abstract", "pdf_url": None, "source": "europepmc",
    }]
    at.run()
    [b for b in at.button if b.label == "In Bibliothek uebernehmen"][0].click().run()
    assert any("nur Abstract" in i.value for i in at.info)


def test_search_add_paper_reads_full_text_from_jats_xml():
    at = _login({"APP_PASSWORD": "geheim123"})
    _goto(at, "Suche")
    at.session_state["search_results"] = [{
        "id": "x1", "title": "XML", "authors": "A", "year": 2021, "abstract": "Abstract",
        "pdf_url": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC1/fullTextXML", "source": "europepmc",
    }]
    at.run()
    xml = b"<article><body><p>Volltext aus XML.</p></body></article>"
    with patch("app.paper_download.fetch_pdf", return_value=xml), \
         patch("app.paper_download.is_safe_url", return_value=True):
        [b for b in at.button if b.label == "In Bibliothek uebernehmen"][0].click().run()
    paper = at.session_state["library"].papers["x1"]
    assert paper.full_text == "Volltext aus XML."
    assert paper.pdf_bytes is None


def test_analysis_runs_on_abstract_when_no_full_text():
    at = _login({"APP_PASSWORD": "geheim123", "CLAUDE_API_KEY": "sk-test"})
    at.session_state["library"] = _library_with_paper(full_text=None, extract_status="pending", abstract="Der Abstract")
    at.run()
    _goto(at, "Analyse")
    with patch("app.analysis_direct.analyze", return_value={"methodik": "x"}) as mock_analyze:
        [b for b in at.button if b.label == "Analysieren"][0].click().run()
    assert mock_analyze.call_args[0][0] == "Der Abstract"


def test_analysis_blocked_without_full_text_and_abstract():
    at = _login({"APP_PASSWORD": "geheim123", "CLAUDE_API_KEY": "sk-test"})
    at.session_state["library"] = _library_with_paper(full_text=None, extract_status="failed")
    at.run()
    _goto(at, "Analyse")
    assert not [b for b in at.button if b.label == "Analysieren"]
    assert any("Weder Volltext noch Abstract" in w.value for w in at.warning)


def test_library_offers_download_of_fetched_pdf():
    at = _login({"APP_PASSWORD": "geheim123"})
    at.session_state["library"] = _library_with_paper(pdf_bytes=b"%PDF-1")
    at.run()
    _goto(at, "Bibliothek")
    assert any(b.label == "PDF speichern" for b in at.get("download_button"))


# ---------------------------------------------------------------------------
# Aufsatz: essay from selected papers, framed by the author's fixed texts.
# ---------------------------------------------------------------------------

def _essay_library():
    lib = _library_with_paper(selected=True)
    lib.papers["p2"] = library_state.Paper(id="p2", title="Gefunden", abstract="Abstract zwei", selected=True)
    lib.papers["p3"] = library_state.Paper(id="p3", title="Nicht gewaehlt", abstract="Abstract drei")
    return lib


def test_library_checkbox_selects_paper_for_essay():
    at = _login({"APP_PASSWORD": "geheim123"})
    at.session_state["library"] = _library_with_paper()
    at.run()
    _goto(at, "Bibliothek")
    at.checkbox(key="select_p1").check().run()
    assert at.session_state["library"].papers["p1"].selected is True


def test_library_checkbox_disabled_without_any_text():
    at = _login({"APP_PASSWORD": "geheim123"})
    at.session_state["library"] = _library_with_paper(full_text=None)
    at.run()
    _goto(at, "Bibliothek")
    assert at.checkbox(key="select_p1").disabled


def test_aufsatz_without_selection_prompts_to_select():
    at = _login({"APP_PASSWORD": "geheim123"})
    at.session_state["library"] = _library_with_paper()
    at.run()
    _goto(at, "Aufsatz")
    assert any("Bibliothek" in i.value for i in at.info)
    assert not [b for b in at.button if b.label == "Aufsatz erstellen"]


def test_aufsatz_uses_only_selected_papers_and_offers_both_downloads():
    at = _login({"APP_PASSWORD": "geheim123", "CLAUDE_API_KEY": "sk-test"})
    at.session_state["library"] = _essay_library()
    at.run()
    _goto(at, "Aufsatz")
    with patch("modules.essay.generate_body", return_value="Generierter Hauptteil.") as mock_body:
        [b for b in at.button if b.label == "Aufsatz erstellen"][0].click().run()
    assert not at.exception
    papers_arg = mock_body.call_args[0][1]
    assert [p.id for p in papers_arg] == ["p1", "p2"]
    preview = [t for t in at.text_area if t.label == "Aufsatz"][0].value
    assert preview.index("Ich bin eine muslimische Frau") < preview.index("Generierter Hauptteil.")
    assert preview.index("Generierter Hauptteil.") < preview.index("Methodisch wurde diese Arbeit")
    labels = {b.label for b in at.get("download_button")}
    assert {"Als PDF herunterladen", "Als Word herunterladen"} <= labels


def test_aufsatz_cut_off_response_shows_error_not_exception():
    at = _login({"APP_PASSWORD": "geheim123", "CLAUDE_API_KEY": "sk-test"})
    at.session_state["library"] = _essay_library()
    at.run()
    _goto(at, "Aufsatz")
    with patch("modules.essay.generate_body", side_effect=EmptyResponseError("Antwort abgeschnitten.")):
        [b for b in at.button if b.label == "Aufsatz erstellen"][0].click().run()
    assert not at.exception
    assert any("Antwort abgeschnitten." in e.value for e in at.error)


def test_aufsatz_missing_api_key_shows_error_not_exception():
    at = _login({"APP_PASSWORD": "geheim123"})
    at.session_state["library"] = _essay_library()
    at.run()
    _goto(at, "Aufsatz")
    [b for b in at.button if b.label == "Aufsatz erstellen"][0].click().run()
    assert not at.exception
    assert any("CLAUDE_API_KEY ist nicht konfiguriert" in e.value for e in at.error)


def test_logout_clears_essay_result():
    at = _login({"APP_PASSWORD": "geheim123"})
    at.session_state["essay_result"] = {"title": "T", "sections": [("A", "B")]}
    at.run()
    [b for b in at.sidebar.button if b.label == "Logout"][0].click().run()
    assert "essay_result" not in at.session_state
