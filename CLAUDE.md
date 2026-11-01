# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Streamlit app for social scientists: search or upload papers, analyze them with Claude against a fixed schema, ask questions, and export reports as Excel/PDF. Deployed on Streamlit Community Cloud (branch `main`, entry point `app.py`; see `DEPLOYMENT.md`). The design is in `docs/superpowers/specs/`, the implementation plan in `docs/superpowers/plans/`.

## Commands

```bash
pip install -r requirements.txt -r requirements-dev.txt
streamlit run app.py

python -m pytest                                  # all tests
python -m pytest tests/test_auth.py               # one file
python -m pytest tests/test_app.py -k login       # by name
```

There is no linter or build step. Local secrets go in `.streamlit/secrets.toml` (gitignored): `APP_PASSWORD`, `CLAUDE_API_KEY`, `CORE_API_KEY`.

## Architecture

`app.py` holds the login gate, sidebar navigation, and one function per page (Suche, Upload, Bibliothek, Analyse, Q&A, Aufgaben, Export). `main()` runs at module level, so importing `app.py` executes the app.

**Constraints**

- Only `app.py` may call `st.*`, including `st.secrets`. `modules/` is plain Python, testable without a Streamlit runtime, and receives API keys and clients as arguments.
- There is no database. All state lives in `st.session_state` and is lost on reload; export is the only persistence. Logout must clear every user-data key by hand (see `sidebar_nav`), so add any new key there.
- Tests never call real external APIs or Claude. `tests/test_app.py` drives the real app through Streamlit's `AppTest`, with mocks.
- UI text and report content are German.

**Analysis flow**

- Mode A (`analysis_direct`) sends the full text to Claude. Mode B (`analysis_ragpipeline`) sends BM25-retrieved chunks; there are no embeddings or vector store.
- `app.py` falls back from A to B when `qa_engine.is_too_long_for_direct` is true (over 400,000 characters). The check is in the page functions, not the engines.
- All Claude calls go through `claude_client.call_claude`, which also sets the model (`DEFAULT_MODEL`). API errors are caught per page in `app.py`, and each page has its own copy of the `try/except`.

**Report schema**

`report_schema.SCHEMA_FIELDS` is the contract between the prompt, the parser, and both exports. `export_pdf.FIELD_LABELS` and `export_excel.COLUMNS` repeat the field names, so change all three together. `parse_response` fills missing fields with `"nicht angegeben"` rather than raising.

**Aufgaben page**

`custom_report` answers a preset or uploaded question set as free text and doesn't use the schema. It always sends the full text, without the mode A/B logic or the length check.

**Search**

Each `search_*` module exposes `search(query, api_key=None)` and returns dicts with the same keys: `id, title, authors, year, abstract, pdf_url, source`. To add a source, register it in `search_aggregator.PROVIDERS` and add its checkbox in `search_page`. The aggregator dedupes by normalized title and treats a failing provider as having no results.

**Security measures to preserve**

- `_is_safe_pdf_url` blocks SSRF through `pdf_url` values returned by search APIs, and redirects are deliberately not followed.
- `export_excel._sanitize_cell` prevents formula injection.
- `_escape_md` escapes third-party titles before they are rendered as Markdown.

## Gotchas

- PDF export uses a core Helvetica font, so `export_pdf._sanitize` forces text to Latin-1. Unsupported characters become `?`, including Turkish `ş`, `ğ`, and `ı` from the Aufgaben language option.
- `multi_cell` uses an explicit width of 190 because `0` fails on consecutive calls in fpdf2 2.8.9.
- `AppTest` resolves paths relative to the test file, and a cold import of `app.py` can exceed its default 3s timeout. Keep `APP_PATH` and `DEFAULT_TIMEOUT` in `tests/test_app.py` as they are.
- The tests address sidebar widgets by index (`at.sidebar.radio[1]` is the page selector), so adding or reordering sidebar radios breaks them.
