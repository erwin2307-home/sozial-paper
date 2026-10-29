# Sozialwissenschafts-Paper-Analyse-App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Streamlit-App, mit der Sozialwissenschaftler*innen Paper suchen (Semantic Scholar/CORE/PubMed/Europe PMC), hochladen, per Claude analysieren (festes Schema) und befragen (Q&A) können, und einen exakten Bericht als Excel/PDF exportieren können.

**Architecture:** Alle Geschäftslogik liegt in reinen Python-Modulen unter `modules/` (keine `st.*`-Aufrufe, dadurch ohne Streamlit-Runtime testbar). `app.py` ist die dünne Streamlit-Schicht: Login-Gate, Sidebar-Navigation, verdrahtet `st.session_state` mit den Modulen. Zwei Analyse-Modi: Direkt-Stuffing (A, Standard) und BM25-Chunk-Retrieval (B, für sehr lange Paper), beide münden in denselben Claude-Call.

**Tech Stack:** Python, Streamlit, Anthropic SDK (`anthropic`), `pypdf`, `requests`, `rank-bm25`, `openpyxl`, `fpdf2`, `pytest` + `pytest-mock`.

**Spec:** `docs/superpowers/specs/2026-10-29-sozialwissenschafts-paper-analyse-design.md`

## Global Constraints

- Geschäftslogik in `modules/` ist reines Python ohne `st.*`-Aufrufe — nur `app.py` darf Streamlit-Widgets nutzen. Grund: Unit-Testbarkeit ohne Streamlit-Runtime (Spec Abschnitt 7).
- Claude-API-Key ausschließlich über `st.secrets["CLAUDE_API_KEY"]`, nie hartcodiert, nie im Repo (Spec Abschnitt 2, 8).
- Keine Datenbank — Persistenz nur über `st.session_state` + Export (Spec Abschnitt 2, 6).
- Kein Unit-/Integrationstest ruft echte externe APIs oder die echte Claude-API auf — alles gemockt (Spec Abschnitt 7).
- Berichts-Schema-Felder exakt: `forschungsfrage, theoretischer_rahmen, methodik, stichprobe, datenerhebung, ergebnisse, limitationen, implikationen` (Spec Abschnitt 4).
- UI-Sprache und Bericht-Inhalte: Deutsch.
- `packages.txt` wird nicht angelegt — alle gewählten Libraries (`pypdf`, `fpdf2`) sind pure-Python ohne System-Abhängigkeiten, Abweichung von der spekulativen Erwähnung in Spec Abschnitt 3 ("falls nötig").

---

## File Structure

```
app.py
modules/
  __init__.py
  auth.py
  library_state.py
  claude_client.py
  pdf_extract.py
  report_schema.py
  analysis_direct.py
  analysis_ragpipeline.py
  qa_engine.py
  search_semanticscholar.py
  search_core.py
  search_pubmed.py
  search_europepmc.py
  search_aggregator.py
  export_excel.py
  export_pdf.py
tests/
  __init__.py
  test_auth.py
  test_library_state.py
  test_claude_client.py
  test_pdf_extract.py
  test_report_schema.py
  test_analysis_direct.py
  test_analysis_ragpipeline.py
  test_qa_engine.py
  test_search_providers.py
  test_search_aggregator.py
  test_export_excel.py
  test_export_pdf.py
  test_app.py
.streamlit/
  config.toml
requirements.txt
DEPLOYMENT.md
README.md
```

---

### Task 1: `library_state.py` — zentrale Bibliotheks-Datenstruktur

**Files:**
- Create: `modules/__init__.py` (leer)
- Create: `modules/library_state.py`
- Test: `tests/__init__.py` (leer)
- Test: `tests/test_library_state.py`

**Interfaces:**
- Consumes: nichts
- Produces: `Paper` (dataclass: `id, title, authors, year, source, abstract, pdf_url, full_text, extract_status, report, mode_used`), `Library` (dataclass: `papers: dict[str, Paper]`), `add_paper(library, paper) -> Library`, `get_paper(library, paper_id) -> Paper | None`, `list_papers(library) -> list[Paper]`, `remove_paper(library, paper_id) -> Library`, `set_report(library, paper_id, report, mode_used) -> Library`, `set_full_text(library, paper_id, full_text, status) -> Library`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_library_state.py
from modules.library_state import Paper, Library, add_paper, get_paper, list_papers, remove_paper, set_report, set_full_text

def test_add_and_get_paper():
    lib = Library()
    paper = Paper(id="p1", title="Test Paper")
    add_paper(lib, paper)
    assert get_paper(lib, "p1") is paper

def test_get_missing_paper_returns_none():
    lib = Library()
    assert get_paper(lib, "missing") is None

def test_list_papers_returns_all():
    lib = Library()
    add_paper(lib, Paper(id="p1", title="A"))
    add_paper(lib, Paper(id="p2", title="B"))
    titles = {p.title for p in list_papers(lib)}
    assert titles == {"A", "B"}

def test_remove_paper():
    lib = Library()
    add_paper(lib, Paper(id="p1", title="A"))
    remove_paper(lib, "p1")
    assert get_paper(lib, "p1") is None

def test_set_report_attaches_report_and_mode():
    lib = Library()
    add_paper(lib, Paper(id="p1", title="A"))
    set_report(lib, "p1", {"forschungsfrage": "x"}, "A")
    paper = get_paper(lib, "p1")
    assert paper.report == {"forschungsfrage": "x"}
    assert paper.mode_used == "A"

def test_set_full_text_updates_status():
    lib = Library()
    add_paper(lib, Paper(id="p1", title="A"))
    set_full_text(lib, "p1", "some text", "ok")
    paper = get_paper(lib, "p1")
    assert paper.full_text == "some text"
    assert paper.extract_status == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_library_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules'` or `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/library_state.py
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Paper:
    id: str
    title: str = ""
    authors: str = ""
    year: Optional[int] = None
    source: str = "upload"
    abstract: str = ""
    pdf_url: Optional[str] = None
    full_text: Optional[str] = None
    extract_status: str = "pending"
    report: Optional[dict] = None
    mode_used: Optional[str] = None


@dataclass
class Library:
    papers: dict = field(default_factory=dict)


def add_paper(library: Library, paper: Paper) -> Library:
    library.papers[paper.id] = paper
    return library


def get_paper(library: Library, paper_id: str) -> Optional[Paper]:
    return library.papers.get(paper_id)


def list_papers(library: Library) -> list:
    return list(library.papers.values())


def remove_paper(library: Library, paper_id: str) -> Library:
    library.papers.pop(paper_id, None)
    return library


def set_report(library: Library, paper_id: str, report: dict, mode_used: str) -> Library:
    paper = library.papers.get(paper_id)
    if paper is not None:
        paper.report = report
        paper.mode_used = mode_used
    return library


def set_full_text(library: Library, paper_id: str, full_text: str, status: str) -> Library:
    paper = library.papers.get(paper_id)
    if paper is not None:
        paper.full_text = full_text
        paper.extract_status = status
    return library
```

Also create empty `modules/__init__.py` and `tests/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_library_state.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/__init__.py modules/library_state.py tests/__init__.py tests/test_library_state.py
git commit -m "feat: add library_state module for in-session paper storage"
```

---

### Task 2: `auth.py` — Passwort-Check

**Files:**
- Create: `modules/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: nichts
- Produces: `check_password(entered: str, secret: str) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_auth.py
from modules.auth import check_password

def test_correct_password_returns_true():
    assert check_password("geheim123", "geheim123") is True

def test_wrong_password_returns_false():
    assert check_password("falsch", "geheim123") is False

def test_empty_entered_returns_false():
    assert check_password("", "geheim123") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.auth'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/auth.py
def check_password(entered: str, secret: str) -> bool:
    return bool(entered) and entered == secret
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_auth.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/auth.py tests/test_auth.py
git commit -m "feat: add password-gate auth module"
```

---

### Task 3: `claude_client.py` — Claude-API-Wrapper

**Files:**
- Create: `modules/claude_client.py`
- Test: `tests/test_claude_client.py`
- Modify: `requirements.txt` (create if missing, append `anthropic>=0.40,<1`, `pytest>=8.0`, `pytest-mock>=3.14`)

**Interfaces:**
- Consumes: nichts
- Produces: `DEFAULT_MODEL = "claude-sonnet-5"`, `get_client(api_key: str)`, `call_claude(client, prompt: str, max_tokens: int = 4096) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_claude_client.py
from unittest.mock import Mock
from modules.claude_client import call_claude, get_client, DEFAULT_MODEL

def test_call_claude_returns_text_from_response():
    client = Mock()
    client.messages.create.return_value = Mock(content=[Mock(text="Antworttext")])
    result = call_claude(client, "Frage?")
    assert result == "Antworttext"

def test_call_claude_uses_default_model_and_prompt():
    client = Mock()
    client.messages.create.return_value = Mock(content=[Mock(text="ok")])
    call_claude(client, "Mein Prompt")
    _, kwargs = client.messages.create.call_args
    assert kwargs["model"] == DEFAULT_MODEL
    assert kwargs["messages"] == [{"role": "user", "content": "Mein Prompt"}]

def test_get_client_builds_anthropic_client(monkeypatch):
    created = {}

    class FakeAnthropic:
        def __init__(self, api_key):
            created["api_key"] = api_key

    monkeypatch.setattr("modules.claude_client.anthropic.Anthropic", FakeAnthropic)
    client = get_client("my-key")
    assert created["api_key"] == "my-key"
    assert isinstance(client, FakeAnthropic)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_claude_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.claude_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/claude_client.py
import anthropic

DEFAULT_MODEL = "claude-sonnet-5"


def get_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)


def call_claude(client, prompt: str, max_tokens: int = 4096) -> str:
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
```

Create `requirements.txt` with:

```
streamlit>=1.38
anthropic>=0.40,<1
pypdf>=4.0
requests>=2.31
rank-bm25>=0.2
openpyxl>=3.1
fpdf2>=2.7
pytest>=8.0
pytest-mock>=3.14
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -r requirements.txt && pytest tests/test_claude_client.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/claude_client.py tests/test_claude_client.py requirements.txt
git commit -m "feat: add Claude API client wrapper and project requirements"
```

---

### Task 4: `pdf_extract.py` — PDF-Volltext-Extraktion

**Files:**
- Create: `modules/pdf_extract.py`
- Test: `tests/test_pdf_extract.py`

**Interfaces:**
- Consumes: nichts
- Produces: `extract_text(pdf_bytes: bytes) -> tuple[str, str]` (Rückgabe `(full_text, status)`, `status` ist `"ok"` oder `"failed"`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pdf_extract.py
from pathlib import Path
from modules.pdf_extract import extract_text

FIXTURE_PDF = Path(__file__).resolve().parents[1] / "original" / "paper.pdf"

def test_extract_text_from_real_pdf_succeeds():
    pdf_bytes = FIXTURE_PDF.read_bytes()
    text, status = extract_text(pdf_bytes)
    assert status == "ok"
    assert len(text) > 100

def test_extract_text_from_garbage_bytes_fails():
    text, status = extract_text(b"this is not a pdf")
    assert status == "failed"
    assert text == ""

def test_extract_text_from_empty_bytes_fails():
    text, status = extract_text(b"")
    assert status == "failed"
    assert text == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pdf_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.pdf_extract'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/pdf_extract.py
from io import BytesIO
from pypdf import PdfReader


def extract_text(pdf_bytes: bytes) -> tuple:
    if not pdf_bytes:
        return "", "failed"
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        full_text = "\n".join(pages_text).strip()
    except Exception:
        return "", "failed"
    if not full_text:
        return "", "failed"
    return full_text, "ok"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pdf_extract.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/pdf_extract.py tests/test_pdf_extract.py
git commit -m "feat: add PDF full-text extraction module"
```

---

### Task 5: `report_schema.py` — Prompt-Template & Antwort-Parsing

**Files:**
- Create: `modules/report_schema.py`
- Test: `tests/test_report_schema.py`

**Interfaces:**
- Consumes: nichts
- Produces: `SCHEMA_FIELDS: list[str]`, `build_prompt(context_text: str) -> str`, `parse_response(raw_text: str) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report_schema.py
import json
from modules.report_schema import SCHEMA_FIELDS, build_prompt, parse_response

def test_build_prompt_contains_all_fields_and_context():
    prompt = build_prompt("MEIN PAPERTEXT")
    assert "MEIN PAPERTEXT" in prompt
    for field in SCHEMA_FIELDS:
        assert field in prompt

def test_parse_response_valid_json():
    payload = {f: f"wert-{f}" for f in SCHEMA_FIELDS}
    raw = json.dumps(payload)
    result = parse_response(raw)
    assert result == payload

def test_parse_response_json_embedded_in_extra_text():
    payload = {f: f"wert-{f}" for f in SCHEMA_FIELDS}
    raw = "Hier ist die Analyse:\n" + json.dumps(payload) + "\nEnde."
    result = parse_response(raw)
    assert result == payload

def test_parse_response_missing_fields_filled_with_default():
    raw = json.dumps({"forschungsfrage": "x"})
    result = parse_response(raw)
    assert result["forschungsfrage"] == "x"
    assert result["ergebnisse"] == "nicht angegeben"

def test_parse_response_garbage_returns_all_defaults():
    result = parse_response("kein json hier")
    assert all(v == "nicht angegeben" for v in result.values())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.report_schema'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/report_schema.py
import json
import re

SCHEMA_FIELDS = [
    "forschungsfrage",
    "theoretischer_rahmen",
    "methodik",
    "stichprobe",
    "datenerhebung",
    "ergebnisse",
    "limitationen",
    "implikationen",
]


def build_prompt(context_text: str) -> str:
    fields_list = "\n".join(f'- "{field}"' for field in SCHEMA_FIELDS)
    return (
        "Du bist Sozialwissenschaftlerin und analysierst ein wissenschaftliches Paper "
        "exakt anhand des folgenden Textauszugs.\n\n"
        f"TEXT:\n{context_text}\n\n"
        "Antworte ausschließlich mit einem JSON-Objekt mit genau diesen Schlüsseln:\n"
        f"{fields_list}\n"
        "Fülle jedes Feld mit einer präzisen, auf den Text gestützten Antwort auf Deutsch. "
        "Wenn eine Information im Text fehlt, schreibe \"nicht angegeben\"."
    )


def parse_response(raw_text: str) -> dict:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    json_str = match.group(0) if match else raw_text
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        data = {}
    return {field: data.get(field, "nicht angegeben") for field in SCHEMA_FIELDS}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_report_schema.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/report_schema.py tests/test_report_schema.py
git commit -m "feat: add fixed social-science report schema and parsing"
```

---

### Task 6: `analysis_direct.py` — Modus A (Direkt-Stuffing)

**Files:**
- Create: `modules/analysis_direct.py`
- Test: `tests/test_analysis_direct.py`

**Interfaces:**
- Consumes: `report_schema.build_prompt`, `report_schema.parse_response`, `claude_client.call_claude`
- Produces: `analyze(full_text: str, client) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_analysis_direct.py
from unittest.mock import patch
from modules.analysis_direct import analyze
from modules.report_schema import SCHEMA_FIELDS

def test_analyze_calls_claude_with_full_text_and_returns_parsed_report():
    fake_raw = "{" + ", ".join(f'"{f}": "x"' for f in SCHEMA_FIELDS) + "}"
    with patch("modules.analysis_direct.call_claude", return_value=fake_raw) as mock_call:
        result = analyze("VOLLTEXT DES PAPERS", client=object())
    assert result["forschungsfrage"] == "x"
    prompt_used = mock_call.call_args[0][1]
    assert "VOLLTEXT DES PAPERS" in prompt_used
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analysis_direct.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.analysis_direct'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/analysis_direct.py
from modules import report_schema
from modules.claude_client import call_claude


def analyze(full_text: str, client) -> dict:
    prompt = report_schema.build_prompt(full_text)
    raw = call_claude(client, prompt)
    return report_schema.parse_response(raw)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_analysis_direct.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add modules/analysis_direct.py tests/test_analysis_direct.py
git commit -m "feat: add direct-stuffing analysis mode (A)"
```

---

### Task 7: `analysis_ragpipeline.py` — Modus B (Chunking + BM25-Retrieval)

**Files:**
- Create: `modules/analysis_ragpipeline.py`
- Test: `tests/test_analysis_ragpipeline.py`

**Interfaces:**
- Consumes: `report_schema.build_prompt`, `report_schema.parse_response`, `claude_client.call_claude`
- Produces: `chunk_text(full_text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]`, `retrieve_relevant_chunks(chunks: list[str], query: str, top_k: int = 5) -> list[str]`, `analyze(full_text: str, client) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_analysis_ragpipeline.py
from unittest.mock import patch
from modules.analysis_ragpipeline import chunk_text, retrieve_relevant_chunks, analyze
from modules.report_schema import SCHEMA_FIELDS

def test_chunk_text_splits_long_text():
    text = "a" * 3500
    chunks = chunk_text(text, chunk_size=1500, overlap=200)
    assert len(chunks) == 3
    assert all(len(c) <= 1500 for c in chunks)

def test_chunk_text_empty_returns_empty_list():
    assert chunk_text("") == []

def test_retrieve_relevant_chunks_ranks_matching_chunk_first():
    chunks = [
        "Dieser Abschnitt behandelt Katzenfutter und Haustierpflege.",
        "Die Stichprobe umfasste 500 Befragte in einer quantitativen Online-Erhebung.",
        "Ein Rezept fuer Apfelkuchen mit Zimt und Zucker.",
    ]
    result = retrieve_relevant_chunks(chunks, "Stichprobe quantitative Erhebung", top_k=1)
    assert result == [chunks[1]]

def test_analyze_calls_claude_with_retrieved_context():
    fake_raw = "{" + ", ".join(f'"{f}": "x"' for f in SCHEMA_FIELDS) + "}"
    with patch("modules.analysis_ragpipeline.call_claude", return_value=fake_raw) as mock_call:
        result = analyze("Satz eins. " * 50, client=object())
    assert result["forschungsfrage"] == "x"
    assert mock_call.call_args is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analysis_ragpipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.analysis_ragpipeline'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/analysis_ragpipeline.py
from rank_bm25 import BM25Okapi

from modules import report_schema
from modules.claude_client import call_claude


def chunk_text(full_text: str, chunk_size: int = 1500, overlap: int = 200) -> list:
    if not full_text:
        return []
    chunks = []
    start = 0
    n = len(full_text)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(full_text[start:end])
        if end == n:
            break
        start = end - overlap
    return chunks


def retrieve_relevant_chunks(chunks: list, query: str, top_k: int = 5) -> list:
    if not chunks:
        return []
    tokenized_chunks = [c.lower().split() for c in chunks]
    bm25 = BM25Okapi(tokenized_chunks)
    scores = bm25.get_scores(query.lower().split())
    ranked_indices = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
    return [chunks[i] for i in ranked_indices[:top_k]]


def analyze(full_text: str, client) -> dict:
    chunks = chunk_text(full_text)
    query = " ".join(report_schema.SCHEMA_FIELDS)
    relevant = retrieve_relevant_chunks(chunks, query, top_k=8)
    prompt = report_schema.build_prompt("\n\n".join(relevant))
    raw = call_claude(client, prompt)
    return report_schema.parse_response(raw)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_analysis_ragpipeline.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/analysis_ragpipeline.py tests/test_analysis_ragpipeline.py
git commit -m "feat: add BM25 chunking/retrieval analysis mode (B)"
```

---

### Task 8: `qa_engine.py` — Fragen zu einem Paper

**Files:**
- Create: `modules/qa_engine.py`
- Test: `tests/test_qa_engine.py`

**Interfaces:**
- Consumes: `analysis_ragpipeline.chunk_text`, `analysis_ragpipeline.retrieve_relevant_chunks`, `claude_client.call_claude`
- Produces: `MAX_CHARS_MODE_A: int`, `is_too_long_for_direct(full_text: str) -> bool`, `answer_question(full_text: str, question: str, mode: str, client) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_qa_engine.py
from unittest.mock import patch
from modules.qa_engine import is_too_long_for_direct, answer_question, MAX_CHARS_MODE_A

def test_is_too_long_for_direct_false_under_limit():
    assert is_too_long_for_direct("x" * 100) is False

def test_is_too_long_for_direct_true_over_limit():
    assert is_too_long_for_direct("x" * (MAX_CHARS_MODE_A + 1)) is True

def test_answer_question_mode_a_uses_full_text_as_context():
    with patch("modules.qa_engine.call_claude", return_value="Antwort") as mock_call:
        result = answer_question("VOLLTEXT HIER", "Was ist die Methode?", "A", client=object())
    assert result == "Antwort"
    prompt_used = mock_call.call_args[0][1]
    assert "VOLLTEXT HIER" in prompt_used
    assert "Was ist die Methode?" in prompt_used

def test_answer_question_mode_b_uses_retrieved_chunks_not_full_text():
    long_text = "Satz eins. " * 500
    with patch("modules.qa_engine.call_claude", return_value="Antwort") as mock_call:
        result = answer_question(long_text, "Was ist die Stichprobe?", "B", client=object())
    assert result == "Antwort"
    prompt_used = mock_call.call_args[0][1]
    assert len(prompt_used) < len(long_text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_qa_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.qa_engine'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/qa_engine.py
from modules import analysis_ragpipeline
from modules.claude_client import call_claude

MAX_CHARS_MODE_A = 400_000


def is_too_long_for_direct(full_text: str) -> bool:
    return len(full_text or "") > MAX_CHARS_MODE_A


def answer_question(full_text: str, question: str, mode: str, client) -> str:
    if mode == "B":
        chunks = analysis_ragpipeline.chunk_text(full_text)
        relevant = analysis_ragpipeline.retrieve_relevant_chunks(chunks, question, top_k=5)
        context = "\n\n".join(relevant)
    else:
        context = full_text
    prompt = (
        "Beantworte die folgende Frage ausschließlich auf Basis des gegebenen Paper-Textauszugs. "
        "Wenn die Antwort nicht im Text steht, sage das explizit.\n\n"
        f"TEXT:\n{context}\n\nFRAGE: {question}"
    )
    return call_claude(client, prompt)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_qa_engine.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/qa_engine.py tests/test_qa_engine.py
git commit -m "feat: add Q&A engine with mode-aware context selection"
```

---

### Task 9: Such-Provider-Module (Semantic Scholar, CORE, PubMed, Europe PMC)

**Files:**
- Create: `modules/search_semanticscholar.py`
- Create: `modules/search_core.py`
- Create: `modules/search_pubmed.py`
- Create: `modules/search_europepmc.py`
- Test: `tests/test_search_providers.py`

**Interfaces:**
- Consumes: nichts
- Produces (jedes Modul): `search(query: str, api_key: str | None = None, limit: int = 10) -> list[dict]`, jedes Dict mit Schlüsseln `id, title, authors, year, abstract, pdf_url, source`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_search_providers.py
from unittest.mock import patch, Mock
from modules import search_semanticscholar, search_core, search_pubmed, search_europepmc


def _mock_response(json_data):
    response = Mock()
    response.json.return_value = json_data
    response.raise_for_status.return_value = None
    return response


def test_semanticscholar_search_normalizes_results():
    payload = {"data": [{
        "paperId": "abc", "title": "Titel A", "year": 2021,
        "authors": [{"name": "Max Muster"}], "abstract": "Zusammenfassung",
        "openAccessPdf": {"url": "http://example.org/a.pdf"},
    }]}
    with patch("modules.search_semanticscholar.requests.get", return_value=_mock_response(payload)):
        results = search_semanticscholar.search("sozialwissenschaft")
    assert results == [{
        "id": "abc", "title": "Titel A", "authors": "Max Muster", "year": 2021,
        "abstract": "Zusammenfassung", "pdf_url": "http://example.org/a.pdf",
        "source": "semanticscholar",
    }]


def test_core_search_normalizes_results():
    payload = {"results": [{
        "id": 42, "title": "Titel B", "yearPublished": 2020,
        "authors": [{"name": "Erika Muster"}], "abstract": "Abstract B",
        "downloadUrl": "http://example.org/b.pdf",
    }]}
    with patch("modules.search_core.requests.get", return_value=_mock_response(payload)):
        results = search_core.search("sozialwissenschaft", api_key="key")
    assert results == [{
        "id": "42", "title": "Titel B", "authors": "Erika Muster", "year": 2020,
        "abstract": "Abstract B", "pdf_url": "http://example.org/b.pdf",
        "source": "core",
    }]


def test_pubmed_search_two_step_lookup():
    esearch_payload = {"esearchresult": {"idlist": ["111"]}}
    esummary_payload = {"result": {"111": {
        "title": "Titel C", "authors": [{"name": "Anna Beispiel"}], "pubdate": "2019 Jan",
    }}}
    with patch(
        "modules.search_pubmed.requests.get",
        side_effect=[_mock_response(esearch_payload), _mock_response(esummary_payload)],
    ):
        results = search_pubmed.search("sozialwissenschaft")
    assert results == [{
        "id": "111", "title": "Titel C", "authors": "Anna Beispiel", "year": 2019,
        "abstract": "", "pdf_url": None, "source": "pubmed",
    }]


def test_pubmed_search_no_hits_returns_empty_list():
    esearch_payload = {"esearchresult": {"idlist": []}}
    with patch("modules.search_pubmed.requests.get", return_value=_mock_response(esearch_payload)):
        results = search_pubmed.search("xyz-unbekannt")
    assert results == []


def test_europepmc_search_normalizes_results():
    payload = {"resultList": {"result": [{
        "id": "789", "title": "Titel D", "authorString": "Tom Beispiel",
        "pubYear": "2022", "abstractText": "Abstract D",
    }]}}
    with patch("modules.search_europepmc.requests.get", return_value=_mock_response(payload)):
        results = search_europepmc.search("sozialwissenschaft")
    assert results == [{
        "id": "789", "title": "Titel D", "authors": "Tom Beispiel", "year": 2022,
        "abstract": "Abstract D", "pdf_url": None, "source": "europepmc",
    }]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search_providers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.search_semanticscholar'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/search_semanticscholar.py
import requests

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


def search(query: str, api_key: str = None, limit: int = 10) -> list:
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,abstract,openAccessPdf",
    }
    headers = {"x-api-key": api_key} if api_key else {}
    response = requests.get(API_URL, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("data", []):
        results.append({
            "id": item.get("paperId"),
            "title": item.get("title") or "",
            "authors": ", ".join(a.get("name", "") for a in item.get("authors", [])),
            "year": item.get("year"),
            "abstract": item.get("abstract") or "",
            "pdf_url": (item.get("openAccessPdf") or {}).get("url"),
            "source": "semanticscholar",
        })
    return results
```

```python
# modules/search_core.py
import requests

API_URL = "https://api.core.ac.uk/v3/search/works/"


def search(query: str, api_key: str = None, limit: int = 10) -> list:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    params = {"q": query, "limit": limit}
    response = requests.get(API_URL, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("results", []):
        authors = item.get("authors") or []
        results.append({
            "id": str(item.get("id")),
            "title": item.get("title") or "",
            "authors": ", ".join(a.get("name", "") for a in authors),
            "year": item.get("yearPublished"),
            "abstract": item.get("abstract") or "",
            "pdf_url": item.get("downloadUrl"),
            "source": "core",
        })
    return results
```

```python
# modules/search_pubmed.py
import requests

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


def search(query: str, api_key: str = None, limit: int = 10) -> list:
    search_params = {"db": "pubmed", "term": query, "retmax": limit, "retmode": "json"}
    if api_key:
        search_params["api_key"] = api_key
    search_resp = requests.get(ESEARCH_URL, params=search_params, timeout=15)
    search_resp.raise_for_status()
    ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    summary_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
    if api_key:
        summary_params["api_key"] = api_key
    summary_resp = requests.get(ESUMMARY_URL, params=summary_params, timeout=15)
    summary_resp.raise_for_status()
    summary_data = summary_resp.json().get("result", {})
    results = []
    for pmid in ids:
        item = summary_data.get(pmid)
        if not item:
            continue
        authors = ", ".join(a.get("name", "") for a in item.get("authors", []))
        results.append({
            "id": pmid,
            "title": item.get("title") or "",
            "authors": authors,
            "year": _extract_year(item.get("pubdate", "")),
            "abstract": "",
            "pdf_url": None,
            "source": "pubmed",
        })
    return results


def _extract_year(pubdate: str):
    digits = "".join(ch for ch in pubdate[:4] if ch.isdigit())
    return int(digits) if digits else None
```

```python
# modules/search_europepmc.py
import requests

API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def search(query: str, api_key: str = None, limit: int = 10) -> list:
    params = {"query": query, "format": "json", "pageSize": limit}
    response = requests.get(API_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("resultList", {}).get("result", []):
        results.append({
            "id": item.get("id"),
            "title": item.get("title") or "",
            "authors": item.get("authorString") or "",
            "year": int(item["pubYear"]) if item.get("pubYear") else None,
            "abstract": item.get("abstractText") or "",
            "pdf_url": None,
            "source": "europepmc",
        })
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_search_providers.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/search_semanticscholar.py modules/search_core.py modules/search_pubmed.py modules/search_europepmc.py tests/test_search_providers.py
git commit -m "feat: add Semantic Scholar, CORE, PubMed, Europe PMC search providers"
```

---

### Task 10: `search_aggregator.py` — Quellen-Checkbox-Kombination

**Files:**
- Create: `modules/search_aggregator.py`
- Test: `tests/test_search_aggregator.py`

**Interfaces:**
- Consumes: `search_semanticscholar.search`, `search_core.search`, `search_pubmed.search`, `search_europepmc.search`
- Produces: `PROVIDERS: dict[str, callable]`, `aggregate(query: str, sources: list[str], api_keys: dict | None = None) -> list[dict]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_search_aggregator.py
from unittest.mock import patch
from modules.search_aggregator import aggregate

def test_aggregate_merges_and_dedups_by_title():
    with patch("modules.search_aggregator.search_semanticscholar.search", return_value=[
        {"id": "1", "title": "Gleicher Titel", "authors": "", "year": 2020, "abstract": "", "pdf_url": None, "source": "semanticscholar"},
    ]), patch("modules.search_aggregator.search_core.search", return_value=[
        {"id": "2", "title": "gleicher titel", "authors": "", "year": 2020, "abstract": "", "pdf_url": None, "source": "core"},
        {"id": "3", "title": "Anderer Titel", "authors": "", "year": 2021, "abstract": "", "pdf_url": None, "source": "core"},
    ]):
        results = aggregate("query", ["semanticscholar", "core"])
    titles = [r["title"] for r in results]
    assert titles == ["Gleicher Titel", "Anderer Titel"]

def test_aggregate_skips_source_that_raises():
    with patch("modules.search_aggregator.search_semanticscholar.search", side_effect=RuntimeError("down")), \
         patch("modules.search_aggregator.search_core.search", return_value=[
             {"id": "1", "title": "Titel", "authors": "", "year": 2020, "abstract": "", "pdf_url": None, "source": "core"},
         ]):
        results = aggregate("query", ["semanticscholar", "core"])
    assert len(results) == 1
    assert results[0]["source"] == "core"

def test_aggregate_only_calls_selected_sources():
    with patch("modules.search_aggregator.search_pubmed.search", return_value=[]) as mock_pubmed, \
         patch("modules.search_aggregator.search_europepmc.search", return_value=[]) as mock_europepmc:
        aggregate("query", ["pubmed"])
    mock_pubmed.assert_called_once()
    mock_europepmc.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search_aggregator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.search_aggregator'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/search_aggregator.py
from modules import search_semanticscholar, search_core, search_pubmed, search_europepmc

PROVIDERS = {
    "semanticscholar": search_semanticscholar.search,
    "core": search_core.search,
    "pubmed": search_pubmed.search,
    "europepmc": search_europepmc.search,
}


def aggregate(query: str, sources: list, api_keys: dict = None) -> list:
    api_keys = api_keys or {}
    merged = []
    seen_titles = set()
    for source in sources:
        provider = PROVIDERS.get(source)
        if provider is None:
            continue
        try:
            results = provider(query, api_keys.get(source))
        except Exception:
            results = []
        for item in results:
            key = item["title"].strip().lower()
            if key and key not in seen_titles:
                seen_titles.add(key)
                merged.append(item)
    return merged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_search_aggregator.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/search_aggregator.py tests/test_search_aggregator.py
git commit -m "feat: add search aggregator combining checkbox-selected sources"
```

---

### Task 11: `export_excel.py` — Excel-Vergleichstabelle

**Files:**
- Create: `modules/export_excel.py`
- Test: `tests/test_export_excel.py`

**Interfaces:**
- Consumes: nichts (nimmt Liste von `dict` mit `title, authors, year, source, report`)
- Produces: `COLUMNS: list[str]`, `build_workbook(papers: list[dict]) -> bytes`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export_excel.py
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
    assert row_b[COLUMNS.index("forschungsfrage")] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export_excel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.export_excel'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/export_excel.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export_excel.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add modules/export_excel.py tests/test_export_excel.py
git commit -m "feat: add Excel comparison-table export"
```

---

### Task 12: `export_pdf.py` — PDF-Einzelbericht

**Files:**
- Create: `modules/export_pdf.py`
- Test: `tests/test_export_pdf.py`

**Interfaces:**
- Consumes: `report_schema.SCHEMA_FIELDS`
- Produces: `build_report_pdf(title: str, report: dict) -> bytes`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export_pdf.py
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
    report = {"forschungsfrage": "Er sagte „es funktioniert” — angeblich."}
    pdf_bytes = build_report_pdf("Test", report)
    assert pdf_bytes.startswith(b"%PDF")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export_pdf.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.export_pdf'`

- [ ] **Step 3: Write minimal implementation**

```python
# modules/export_pdf.py
from fpdf import FPDF

from modules.report_schema import SCHEMA_FIELDS

FIELD_LABELS = {
    "forschungsfrage": "Forschungsfrage",
    "theoretischer_rahmen": "Theoretischer Rahmen",
    "methodik": "Methodik",
    "stichprobe": "Stichprobe",
    "datenerhebung": "Datenerhebung",
    "ergebnisse": "Ergebnisse",
    "limitationen": "Limitationen",
    "implikationen": "Implikationen",
}

_REPLACEMENTS = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...",
}


def _sanitize(text: str) -> str:
    text = text or ""
    for src, dst in _REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def build_report_pdf(title: str, report: dict) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, _sanitize(title))
    for field in SCHEMA_FIELDS:
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 8, _sanitize(FIELD_LABELS.get(field, field)))
        pdf.set_font("Helvetica", "", 12)
        pdf.multi_cell(0, 8, _sanitize(report.get(field, "nicht angegeben")))
        pdf.ln(2)
    return bytes(pdf.output())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export_pdf.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add modules/export_pdf.py tests/test_export_pdf.py
git commit -m "feat: add single-paper PDF report export"
```

---

### Task 13: `app.py` — Login, Sidebar-Navigation, Deployment-Dateien

**Files:**
- Create: `app.py`
- Create: `.streamlit/config.toml`
- Create: `DEPLOYMENT.md`
- Create: `README.md`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: alle Module aus Task 1–12
- Produces: lauffähige Streamlit-App mit Login-Gate + Sidebar-Navigation

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app.py
from streamlit.testing.v1 import AppTest

def test_login_wrong_password_shows_error():
    at = AppTest.from_file("app.py")
    at.secrets["APP_PASSWORD"] = "geheim123"
    at.run()
    at.text_input[0].input("falsch").run()
    at.button[0].click().run()
    assert any("Falsches Passwort" in e.value for e in at.error)

def test_login_correct_password_reveals_sidebar_nav():
    at = AppTest.from_file("app.py")
    at.secrets["APP_PASSWORD"] = "geheim123"
    at.run()
    at.text_input[0].input("geheim123").run()
    at.button[0].click().run()
    assert len(at.sidebar.radio) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app.py -v`
Expected: FAIL with `FileNotFoundError` or `ModuleNotFoundError` (kein `app.py`)

- [ ] **Step 3: Write minimal implementation**

```python
# app.py
import streamlit as st

from modules import auth, library_state, pdf_extract, search_aggregator
from modules import analysis_direct, analysis_ragpipeline, qa_engine
from modules import export_excel, export_pdf
from modules.claude_client import get_client

st.set_page_config(page_title="Sozialwissenschafts-Paper-Analyse", layout="wide")


def _init_state():
    if "library" not in st.session_state:
        st.session_state.library = library_state.Library()
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "mode" not in st.session_state:
        st.session_state.mode = "A"


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
        page = st.radio("Bereich", ["Suche", "Upload", "Bibliothek", "Analyse", "Q&A", "Export"])
        if st.button("Logout"):
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
    if st.button("Suchen") and query and sources:
        api_keys = {"core": st.secrets.get("CORE_API_KEY", "")}
        st.session_state.search_results = search_aggregator.aggregate(query, sources, api_keys)
    for item in st.session_state.get("search_results", []):
        with st.expander(f"{item['title']} ({item.get('year', '?')})"):
            st.write(item.get("abstract", ""))
            if st.button("In Bibliothek uebernehmen", key=f"add_{item['id']}"):
                paper = library_state.Paper(
                    id=item["id"], title=item["title"], authors=item["authors"],
                    year=item.get("year"), source=item["source"], abstract=item.get("abstract", ""),
                    pdf_url=item.get("pdf_url"),
                )
                library_state.add_paper(st.session_state.library, paper)
                st.success("Hinzugefuegt.")


def upload_page():
    st.header("Upload")
    uploaded = st.file_uploader("PDF hochladen", type=["pdf"], accept_multiple_files=True)
    for file in uploaded or []:
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
        st.write(f"**{paper.title}** — {paper.source} — Status: {paper.extract_status}")


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
        client = get_client(st.secrets["CLAUDE_API_KEY"])
        use_mode_b = st.session_state.mode == "B" or qa_engine.is_too_long_for_direct(paper.full_text)
        if st.session_state.mode == "A" and use_mode_b:
            st.warning("Paper zu lang fuer Direkt-Modus, nutze RAG-Modus.")
        report = analysis_ragpipeline.analyze(paper.full_text, client) if use_mode_b else analysis_direct.analyze(paper.full_text, client)
        library_state.set_report(st.session_state.library, paper.id, report, "B" if use_mode_b else "A")
        st.success("Analyse abgeschlossen.")
    if paper.report:
        st.json(paper.report)


def qa_page():
    st.header("Q&A")
    paper = _get_selected_paper()
    if paper is None or not paper.full_text:
        return
    question = st.text_input("Frage zum Paper")
    if st.button("Fragen") and question:
        client = get_client(st.secrets["CLAUDE_API_KEY"])
        answer = qa_engine.answer_question(paper.full_text, question, st.session_state.mode, client)
        st.write(answer)


def export_page():
    st.header("Export")
    papers = library_state.list_papers(st.session_state.library)
    if not papers:
        st.info("Bibliothek ist leer.")
        return
    if st.session_state.get("library_view") == "Einzel-Paper":
        paper = papers[0]
        if paper.report:
            pdf_bytes = export_pdf.build_report_pdf(paper.title, paper.report)
            st.download_button("PDF herunterladen", pdf_bytes, file_name=f"{paper.title}.pdf")
    rows = [{"title": p.title, "authors": p.authors, "year": p.year, "source": p.source, "report": p.report} for p in papers]
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
        "Analyse": analysis_page, "Q&A": qa_page, "Export": export_page,
    }
    pages[page]()


main()
```

```toml
# .streamlit/config.toml
[theme]
base = "light"

[server]
maxUploadSize = 50
```

```markdown
# DEPLOYMENT.md

## Deployment auf Streamlit Community Cloud

1. Repo auf GitHub erstellen/pushen (Branch `main`).
2. Auf https://share.streamlit.io neue App anlegen, Repo + Branch `main` + Entry-Point `app.py` auswaehlen.
3. Unter "Secrets" folgende Werte eintragen:
   ```
   APP_PASSWORD = "dein-passwort"
   CLAUDE_API_KEY = "sk-ant-..."
   CORE_API_KEY = "dein-core-key"
   ```
4. Deploy ausloesen. Bei Aenderungen an `main` deployed Streamlit Cloud automatisch neu.
5. Vor jedem Deploy: manuellen Smoke-Test durchfuehren (Login → Suche → Paper uebernehmen → Analyse Modus A → Q&A → Export Excel+PDF).
```

```markdown
# README.md

Streamlit-App zur Suche, Analyse und Befragung sozialwissenschaftlicher Paper per Claude-API.

Siehe `DEPLOYMENT.md` fuer Setup und `docs/superpowers/specs/2026-10-29-sozialwissenschafts-paper-analyse-design.md` fuer das Design.

## Lokal starten

```bash
pip install -r requirements.txt
streamlit run app.py
```

Lokale Secrets in `.streamlit/secrets.toml` (nicht committen):

```
APP_PASSWORD = "dein-passwort"
CLAUDE_API_KEY = "sk-ant-..."
CORE_API_KEY = "dein-core-key"
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run full test suite**

Run: `pytest -v`
Expected: PASS (alle Tests aus Task 1–13)

- [ ] **Step 6: Commit**

```bash
git add app.py .streamlit/config.toml DEPLOYMENT.md README.md tests/test_app.py
git commit -m "feat: assemble Streamlit app with login gate and sidebar navigation"
```

---

## Self-Review Notes

- **Spec-Abdeckung:** Login (Task 13), Sidebar-Navigation (Task 13), Suche mit 4 Checkbox-Quellen (Task 9+10), Upload (Task 13), Bibliothek Einzel/Vergleich-Ansicht (Task 13), Modus A/B (Task 6+7+8+13), festes Bericht-Schema (Task 5), Q&A (Task 8), Excel+PDF-Export (Task 11+12), Claude-Secrets (Task 3+13), Fehlerbehandlung pro Spec Abschnitt 6 (Task 4/7/8/10/13 behandeln jeweils ihren Fall), Deployment (Task 13/DEPLOYMENT.md). Alle Spec-Abschnitte abgedeckt.
- **Platzhalter-Scan:** keine TBD/TODO, jeder Code-Schritt enthaelt lauffaehigen Code.
- **Typ-Konsistenz gepruft:** `Paper`/`Library`-Felder aus Task 1 stimmen mit Nutzung in Task 13 ueberein; `call_claude(client, prompt, max_tokens=4096)`-Signatur aus Task 3 identisch in Task 6/7/8 verwendet; `report_schema.SCHEMA_FIELDS` konsistent in Task 5/6/7/11/12 referenziert.
