import ipaddress
import re
import socket
from urllib.parse import urlparse

import anthropic
import requests
import streamlit as st

from modules import auth, library_state, pdf_extract, search_aggregator
from modules import analysis_direct, analysis_ragpipeline, qa_engine
from modules import export_excel, export_pdf
from modules import custom_report, docx_extract
from modules.claude_client import get_client

st.set_page_config(page_title="Sozialwissenschafts-Paper-Analyse", layout="wide")


def _init_state():
    if "library" not in st.session_state:
        st.session_state.library = library_state.Library()
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "mode" not in st.session_state:
        st.session_state.mode = "A"


def _escape_md(text) -> str:
    return str(text).replace("[", "\\[").replace("]", "\\]").replace("(", "\\(").replace(")", "\\)")


def _is_safe_pdf_url(url: str) -> bool:
    """Reject URLs that resolve to private/loopback/link-local/reserved IPs.

    Prevents SSRF via a malicious pdf_url returned by a third-party search
    API (e.g. a cloud metadata endpoint or an internal service address).
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        for info in socket.getaddrinfo(parsed.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except Exception:
        return False


def login_page():
    st.title("Login")
    entered = st.text_input("Passwort", type="password")
    if st.button("Anmelden"):
        if auth.check_password(entered, st.secrets.get("APP_PASSWORD", "")):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Falsches Passwort.")


def sidebar_nav() -> str:
    with st.sidebar:
        st.metric("Paper in Bibliothek", len(library_state.list_papers(st.session_state.library)))
        st.session_state.mode = st.radio(
            "Verarbeitungsmodus", ["A", "B"],
            index=0 if st.session_state.mode == "A" else 1, horizontal=True,
        )
        page = st.radio("Bereich", ["Suche", "Upload", "Bibliothek", "Analyse", "Q&A", "Aufgaben", "Export"])
        if st.button("Logout"):
            st.session_state.library = library_state.Library()
            st.session_state.pop("search_results", None)
            st.session_state.pop("library_view", None)
            st.session_state.pop("aufgaben_raw_text", None)
            st.session_state.pop("aufgaben_result", None)
            st.session_state.mode = "A"
            st.session_state.authenticated = False
            st.rerun()
    return page


def search_page():
    st.header("Suche")
    query = st.text_input("Suchbegriff")
    labels = [("semanticscholar", "Semantic Scholar"), ("core", "CORE"), ("pubmed", "PubMed"), ("europepmc", "Europe PMC")]
    cols = st.columns(4)
    sources = []
    for col, (key, label) in zip(cols, labels):
        if col.checkbox(label, value=(key == "semanticscholar")):
            sources.append(key)
    if st.button("Suchen"):
        if not query or not sources:
            st.warning("Bitte Suchbegriff eingeben und mindestens eine Quelle auswaehlen.")
        else:
            api_keys = {"core": st.secrets.get("CORE_API_KEY", "")}
            st.session_state.search_results = search_aggregator.aggregate(query, sources, api_keys)
    if "search_results" in st.session_state and not st.session_state.search_results:
        st.info("Keine Treffer.")
    for item in st.session_state.get("search_results", []):
        if not item.get("id"):
            continue
        with st.expander(f"{_escape_md(item['title'])} ({item.get('year', '?')})"):
            st.text(item.get("abstract", ""))
            if st.button("In Bibliothek uebernehmen", key=f"add_{item['source']}_{item['id']}"):
                paper = library_state.Paper(
                    id=item["id"], title=item["title"], authors=item["authors"],
                    year=item.get("year"), source=item["source"], abstract=item.get("abstract", ""),
                    pdf_url=item.get("pdf_url"),
                )
                library_state.add_paper(st.session_state.library, paper)
                if paper.pdf_url and _is_safe_pdf_url(paper.pdf_url):
                    try:
                        resp = requests.get(paper.pdf_url, timeout=30, allow_redirects=False)
                        if resp.is_redirect:
                            # A validated URL could still redirect to an internal
                            # address; never follow it, just treat as failed.
                            text, status = "", "failed"
                        else:
                            resp.raise_for_status()
                            text, status = pdf_extract.extract_text(resp.content)
                    except Exception:
                        text, status = "", "failed"
                    library_state.set_full_text(st.session_state.library, paper.id, text, status)
                st.success("Hinzugefuegt.")


def upload_page():
    st.header("Upload")
    uploaded = st.file_uploader("PDF hochladen", type=["pdf"], accept_multiple_files=True)
    for file in uploaded or []:
        if library_state.get_paper(st.session_state.library, file.name) is not None:
            continue
        full_text, status = pdf_extract.extract_text(file.getvalue())
        paper = library_state.Paper(
            id=file.name, title=file.name, source="upload",
            full_text=full_text, extract_status=status,
        )
        library_state.add_paper(st.session_state.library, paper)
        st.success(f"{file.name}: {status}")


def library_page():
    st.header("Bibliothek")
    st.session_state.library_view = st.radio("Ansicht", ["Einzel-Paper", "Mehrere/Vergleich"])
    for paper in library_state.list_papers(st.session_state.library):
        st.write(f"**{_escape_md(paper.title)}** — {paper.source} — Status: {paper.extract_status}")


def _get_selected_paper():
    papers = library_state.list_papers(st.session_state.library)
    if not papers:
        st.info("Bibliothek ist leer.")
        return None
    titles = {p.title: p.id for p in papers}
    choice = st.selectbox("Paper auswaehlen", list(titles.keys()))
    return library_state.get_paper(st.session_state.library, titles[choice])


def analysis_page():
    st.header("Analyse")
    paper = _get_selected_paper()
    if paper is None:
        return
    if not paper.full_text:
        st.warning("Kein Volltext verfuegbar (PDF nicht extrahierbar).")
        return
    if st.button("Analysieren"):
        use_mode_b = st.session_state.mode == "B" or qa_engine.is_too_long_for_direct(paper.full_text)
        if st.session_state.mode == "A" and use_mode_b:
            st.warning("Paper zu lang fuer Direkt-Modus, nutze RAG-Modus.")
        try:
            client = get_client(st.secrets["CLAUDE_API_KEY"])
            report = analysis_ragpipeline.analyze(paper.full_text, client) if use_mode_b else analysis_direct.analyze(paper.full_text, client)
            library_state.set_report(st.session_state.library, paper.id, report, "B" if use_mode_b else "A")
            st.success("Analyse abgeschlossen.")
        except KeyError:
            st.error("CLAUDE_API_KEY ist nicht konfiguriert.")
        except anthropic.RateLimitError:
            st.error("Claude-API-Limit erreicht. Bitte in einigen Minuten erneut versuchen.")
        except anthropic.APIError as exc:
            st.error(f"Claude-API-Fehler: {type(exc).__name__}. Bitte erneut versuchen.")
    if paper.report:
        st.json(paper.report)


def qa_page():
    st.header("Q&A")
    paper = _get_selected_paper()
    if paper is None or not paper.full_text:
        return
    question = st.text_input("Frage zum Paper")
    if st.button("Fragen") and question:
        effective_mode = "B" if (st.session_state.mode == "B" or qa_engine.is_too_long_for_direct(paper.full_text)) else "A"
        if st.session_state.mode == "A" and effective_mode == "B":
            st.warning("Paper zu lang fuer Direkt-Modus, nutze RAG-Modus.")
        try:
            client = get_client(st.secrets["CLAUDE_API_KEY"])
            answer = qa_engine.answer_question(paper.full_text, question, effective_mode, client)
            st.write(answer)
        except KeyError:
            st.error("CLAUDE_API_KEY ist nicht konfiguriert.")
        except anthropic.RateLimitError:
            st.error("Claude-API-Limit erreicht. Bitte in einigen Minuten erneut versuchen.")
        except anthropic.APIError as exc:
            st.error(f"Claude-API-Fehler: {type(exc).__name__}. Bitte erneut versuchen.")


def aufgaben_page():
    st.header("Aufgaben")
    paper = _get_selected_paper()
    if paper is None:
        return
    if not paper.full_text:
        st.warning("Kein Volltext verfuegbar (PDF nicht extrahierbar).")
        return

    source = st.radio(
        "Fragen-Quelle",
        ["Vorlage: Diversitaet & Intersektionalitaet", "Eigenes Fragen-Dokument hochladen"],
    )
    questions = None
    if source.startswith("Vorlage"):
        questions = custom_report.PRESET_TRANSKULTURALITAET
    else:
        question_file = st.file_uploader("Fragen-Dokument (.docx oder .pdf)", type=["docx", "pdf"])
        if question_file is not None:
            if question_file.name.lower().endswith(".docx"):
                raw_text, status = docx_extract.extract_text(question_file.getvalue())
            else:
                raw_text, status = pdf_extract.extract_text(question_file.getvalue())
            if status == "ok":
                st.session_state.aufgaben_raw_text = raw_text
            else:
                st.warning("Fragen-Dokument konnte nicht gelesen werden.")

    language = st.selectbox(
        "Sprache", ["de", "en", "tr"],
        format_func=lambda code: custom_report.LANGUAGE_NAMES[code],
    )
    personal_text = st.text_area("Eigene Ergaenzung (z.B. persoenliche Perspektive)")

    if st.button("Bericht erstellen"):
        try:
            client = get_client(st.secrets["CLAUDE_API_KEY"])
            active_questions = questions
            if active_questions is None:
                raw_text = st.session_state.get("aufgaben_raw_text", "")
                if not raw_text:
                    st.warning("Bitte zuerst ein Fragen-Dokument hochladen.")
                    return
                active_questions = custom_report.extract_questions_from_text(raw_text, client)
            answer = custom_report.answer_questions(active_questions, paper.full_text, language, client)
            final_text = answer
            if personal_text.strip():
                final_text = f"{answer}\n\n{personal_text.strip()}"
            st.session_state.aufgaben_result = final_text
        except KeyError:
            st.error("CLAUDE_API_KEY ist nicht konfiguriert.")
        except anthropic.RateLimitError:
            st.error("Claude-API-Limit erreicht. Bitte in einigen Minuten erneut versuchen.")
        except anthropic.APIError as exc:
            st.error(f"Claude-API-Fehler: {type(exc).__name__}. Bitte erneut versuchen.")

    if st.session_state.get("aufgaben_result"):
        st.text_area("Ergebnis", st.session_state.aufgaben_result, height=300)
        pdf_bytes = export_pdf.build_text_report_pdf(
            "Aufgabe: Diversitaet und Intersektionalitaet", st.session_state.aufgaben_result,
        )
        st.download_button("PDF herunterladen", pdf_bytes, file_name="aufgabe_bericht.pdf")


def export_page():
    st.header("Export")
    papers = library_state.list_papers(st.session_state.library)
    if not papers:
        st.info("Bibliothek ist leer.")
        return
    st.subheader("Einzelbericht (PDF)")
    paper = _get_selected_paper()
    if paper is not None and paper.report:
        safe_title = re.sub(r"[^\w\-. ]", "_", paper.title)[:80]
        pdf_bytes = export_pdf.build_report_pdf(paper.title, paper.report)
        st.download_button("PDF herunterladen", pdf_bytes, file_name=f"{safe_title}.pdf")
    st.subheader("Vergleichstabelle (Excel)")
    rows = [
        {
            "title": p.title, "authors": p.authors, "year": p.year, "source": p.source,
            "mode_used": p.mode_used, "report": p.report,
        }
        for p in papers
    ]
    xlsx_bytes = export_excel.build_workbook(rows)
    st.download_button("Excel herunterladen", xlsx_bytes, file_name="bericht.xlsx")


def main():
    _init_state()
    if not st.session_state.authenticated:
        login_page()
        return
    page = sidebar_nav()
    pages = {
        "Suche": search_page, "Upload": upload_page, "Bibliothek": library_page,
        "Analyse": analysis_page, "Q&A": qa_page, "Aufgaben": aufgaben_page, "Export": export_page,
    }
    pages[page]()


main()
