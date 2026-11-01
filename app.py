import re

import anthropic
import requests
import streamlit as st

from modules import auth, jats_extract, library_state, paper_download, pdf_extract, search_aggregator
from modules import analysis_direct, analysis_ragpipeline, qa_engine
from modules import export_excel, export_pdf, export_word
from modules import custom_report, docx_extract, essay
from modules.claude_client import EmptyResponseError, get_client

st.set_page_config(page_title="Sozialwissenschafts-Paper-Analyse", layout="wide")

TEXT_KIND_LABELS = {"full": "Volltext", "abstract": "nur Abstract", "none": "kein Text"}


def _init_state():
    if "library" not in st.session_state:
        st.session_state.library = library_state.Library()
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "mode" not in st.session_state:
        st.session_state.mode = "A"


def _escape_md(text) -> str:
    return str(text).replace("[", "\\[").replace("]", "\\]").replace("(", "\\(").replace(")", "\\)")


def _safe_filename(title: str) -> str:
    return re.sub(r"[^\w\-. ]", "_", title)[:80]


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
        page = st.radio("Bereich", ["Suche", "Upload", "Bibliothek", "Analyse", "Q&A", "Aufgaben", "Aufsatz", "Export"])
        if st.button("Logout"):
            st.session_state.library = library_state.Library()
            st.session_state.pop("search_results", None)
            st.session_state.pop("library_view", None)
            st.session_state.pop("aufgaben_raw_text", None)
            st.session_state.pop("aufgaben_result", None)
            st.session_state.pop("essay_result", None)
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
                if paper.pdf_url and paper_download.is_safe_url(paper.pdf_url):
                    content = paper_download.fetch_pdf(paper.pdf_url)
                    is_xml = jats_extract.is_jats_xml(content)
                    if not content:
                        text, status = "", "failed"
                    elif is_xml:
                        text, status = jats_extract.extract_text(content)
                    else:
                        text, status = pdf_extract.extract_text(content)
                    library_state.set_full_text(
                        st.session_state.library, paper.id, text, status,
                        pdf_bytes=content if status == "ok" and not is_xml else None,
                    )
                _, kind = library_state.usable_text(paper)
                if kind == "full":
                    st.success("Hinzugefuegt: Volltext geladen.")
                elif kind == "abstract":
                    st.info("Hinzugefuegt: PDF nicht verfuegbar, nur Abstract nutzbar.")
                else:
                    st.warning("Hinzugefuegt, aber weder PDF noch Abstract verfuegbar.")


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
        _, kind = library_state.usable_text(paper)
        st.write(f"**{_escape_md(paper.title)}** — {paper.source} — Status: {paper.extract_status} — Text: {TEXT_KIND_LABELS[kind]}")
        selected = st.checkbox(
            "Fuer Aufsatz verwenden", value=paper.selected, key=f"select_{paper.id}", disabled=kind == "none",
        )
        library_state.set_selected(st.session_state.library, paper.id, selected)
        if paper.pdf_bytes:
            st.download_button(
                "PDF speichern", paper.pdf_bytes, file_name=f"{_safe_filename(paper.title)}.pdf",
                mime="application/pdf", key=f"pdf_{paper.id}",
            )


def _paper_text_or_warn(paper) -> str:
    text, kind = library_state.usable_text(paper)
    if kind == "none":
        st.warning("Weder Volltext noch Abstract verfuegbar.")
    elif kind == "abstract":
        st.info("Kein Volltext verfuegbar, es wird nur der Abstract verwendet.")
    return text


def _question_input():
    """Render the question source widgets; returns the preset, or None for an uploaded document."""
    source = st.radio(
        "Fragen-Quelle",
        ["Vorlage: Diversitaet & Intersektionalitaet", "Eigenes Fragen-Dokument hochladen"],
    )
    if source.startswith("Vorlage"):
        return custom_report.PRESET_TRANSKULTURALITAET
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
    return None


def _resolve_questions(questions, client):
    if questions is not None:
        return questions
    raw_text = st.session_state.get("aufgaben_raw_text", "")
    if not raw_text:
        st.warning("Bitte zuerst ein Fragen-Dokument hochladen.")
        return None
    extracted = custom_report.extract_questions_from_text(raw_text, client)
    if not extracted:
        st.warning("Im Fragen-Dokument wurden keine Fragen gefunden.")
        return None
    return extracted


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
    text = _paper_text_or_warn(paper)
    if not text:
        return
    if st.button("Analysieren"):
        use_mode_b = st.session_state.mode == "B" or qa_engine.is_too_long_for_direct(text)
        if st.session_state.mode == "A" and use_mode_b:
            st.warning("Paper zu lang fuer Direkt-Modus, nutze RAG-Modus.")
        try:
            client = get_client(st.secrets["CLAUDE_API_KEY"])
            report = analysis_ragpipeline.analyze(text, client) if use_mode_b else analysis_direct.analyze(text, client)
            library_state.set_report(st.session_state.library, paper.id, report, "B" if use_mode_b else "A")
            st.success("Analyse abgeschlossen.")
        except KeyError:
            st.error("CLAUDE_API_KEY ist nicht konfiguriert.")
        except EmptyResponseError as exc:
            st.error(str(exc))
        except anthropic.RateLimitError:
            st.error("Claude-API-Limit erreicht. Bitte in einigen Minuten erneut versuchen.")
        except anthropic.APIError as exc:
            st.error(f"Claude-API-Fehler: {type(exc).__name__}. Bitte erneut versuchen.")
    if paper.report:
        st.json(paper.report)


def qa_page():
    st.header("Q&A")
    paper = _get_selected_paper()
    if paper is None:
        return
    text = _paper_text_or_warn(paper)
    if not text:
        return
    question = st.text_input("Frage zum Paper")
    if st.button("Fragen") and question:
        effective_mode = "B" if (st.session_state.mode == "B" or qa_engine.is_too_long_for_direct(text)) else "A"
        if st.session_state.mode == "A" and effective_mode == "B":
            st.warning("Paper zu lang fuer Direkt-Modus, nutze RAG-Modus.")
        try:
            client = get_client(st.secrets["CLAUDE_API_KEY"])
            answer = qa_engine.answer_question(text, question, effective_mode, client)
            st.write(answer)
        except KeyError:
            st.error("CLAUDE_API_KEY ist nicht konfiguriert.")
        except EmptyResponseError as exc:
            st.error(str(exc))
        except anthropic.RateLimitError:
            st.error("Claude-API-Limit erreicht. Bitte in einigen Minuten erneut versuchen.")
        except anthropic.APIError as exc:
            st.error(f"Claude-API-Fehler: {type(exc).__name__}. Bitte erneut versuchen.")


def aufgaben_page():
    st.header("Aufgaben")
    paper = _get_selected_paper()
    if paper is None:
        return
    text = _paper_text_or_warn(paper)
    if not text:
        return

    questions = _question_input()

    language = st.selectbox(
        "Sprache", ["de", "en", "tr"],
        format_func=lambda code: custom_report.LANGUAGE_NAMES[code],
    )
    personal_text = st.text_area("Eigene Ergaenzung (z.B. persoenliche Perspektive)")

    if st.button("Bericht erstellen"):
        try:
            client = get_client(st.secrets["CLAUDE_API_KEY"])
            active_questions = _resolve_questions(questions, client)
            if active_questions is None:
                return
            answer = custom_report.answer_questions(active_questions, text, language, client)
            final_text = answer
            if personal_text.strip():
                final_text = f"{answer}\n\n{personal_text.strip()}"
            st.session_state.aufgaben_result = final_text
        except KeyError:
            st.error("CLAUDE_API_KEY ist nicht konfiguriert.")
        except EmptyResponseError as exc:
            st.error(str(exc))
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


def aufsatz_page():
    st.header("Aufsatz")
    papers = [p for p in library_state.list_papers(st.session_state.library) if p.selected]
    if not papers:
        st.info("Bitte in der Bibliothek mindestens ein Paper fuer den Aufsatz anhaken.")
        return

    st.subheader("Quellen")
    for paper in papers:
        _, kind = library_state.usable_text(paper)
        st.write(f"- {_escape_md(paper.title)} ({TEXT_KIND_LABELS[kind]})")

    title = st.text_input("Titel", value="Aufsatz")
    questions = _question_input()
    language = st.selectbox(
        "Sprache des Hauptteils", ["de", "en", "tr"],
        format_func=lambda code: custom_report.LANGUAGE_NAMES[code],
    )
    personal_text = st.text_area("Eigene Ergaenzung (z.B. persoenliche Perspektive)")

    if st.button("Aufsatz erstellen"):
        try:
            client = get_client(st.secrets["CLAUDE_API_KEY"])
            active_questions = _resolve_questions(questions, client)
            if active_questions is None:
                return
            body = essay.generate_body(active_questions, papers, language, client)
            st.session_state.essay_result = {
                "title": title, "language": language,
                "sections": essay.build_sections(body, papers, personal_text),
            }
        except KeyError:
            st.error("CLAUDE_API_KEY ist nicht konfiguriert.")
        except EmptyResponseError as exc:
            st.error(str(exc))
        except anthropic.RateLimitError:
            st.error("Claude-API-Limit erreicht. Bitte in einigen Minuten erneut versuchen.")
        except anthropic.APIError as exc:
            st.error(f"Claude-API-Fehler: {type(exc).__name__}. Bitte erneut versuchen.")

    result = st.session_state.get("essay_result")
    if result:
        preview = "\n\n".join(f"{heading}\n\n{body}" for heading, body in result["sections"])
        st.text_area("Aufsatz", preview, height=400)
        if result["language"] == "tr":
            st.warning("Das PDF kann tuerkische Sonderzeichen nicht darstellen. Bitte die Word-Datei verwenden.")
        filename = _safe_filename(result["title"]) or "aufsatz"
        st.download_button(
            "Als PDF herunterladen", export_pdf.build_sections_pdf(result["title"], result["sections"]),
            file_name=f"{filename}.pdf", mime="application/pdf",
        )
        st.download_button(
            "Als Word herunterladen", export_word.build_docx(result["title"], result["sections"]),
            file_name=f"{filename}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )


def export_page():
    st.header("Export")
    papers = library_state.list_papers(st.session_state.library)
    if not papers:
        st.info("Bibliothek ist leer.")
        return
    st.subheader("Einzelbericht (PDF)")
    paper = _get_selected_paper()
    if paper is not None and paper.report:
        safe_title = _safe_filename(paper.title)
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
        "Analyse": analysis_page, "Q&A": qa_page, "Aufgaben": aufgaben_page, "Aufsatz": aufsatz_page, "Export": export_page,
    }
    pages[page]()


main()
