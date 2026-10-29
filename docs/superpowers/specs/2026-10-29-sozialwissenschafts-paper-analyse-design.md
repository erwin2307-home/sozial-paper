# Sozialwissenschafts-Paper-Analyse-App — Design

Status: Entwurf, zur Review
Datum: 2026-10-29
Vorlage: Erwin2307-py/Paper (GitHub) — main_app.py + modules/, als strukturelle Inspiration, nicht als Code-Basis für paper-qa2.

## 1. Ziel

Streamlit-App für Sozialwissenschaftler*innen: Paper suchen, hochladen, mit Claude analysieren (festes Schema), Fragen dazu stellen, exakten Bericht als Excel/PDF exportieren. Deployment: GitHub-Repo → Streamlit Community Cloud.

## 2. Architektur-Überblick

- Login-Gate (geteiltes Passwort) vor allem anderen.
- Sidebar-Navigation (kein Tab-Leisten-Layout wie im Original): Suche, Upload, Bibliothek, Analyse, Q&A, Export. Sidebar zeigt immer Anzahl Paper in Bibliothek + aktuellen Verarbeitungsmodus (A/B) + Logout.
- Verarbeitungsmodus pro Analyse/Q&A wählbar:
  - **Modus A (Direkt-Stuffing, Standard):** Volltext + Schema-Prompt direkt an Claude API. Kein Chunking, keine Vektor-DB.
  - **Modus B (RAG-Pipeline):** paper-qa2-artige Chunking/Retrieval-Schicht, Generierung über Claude statt OpenAI. Für sehr lange Paper oder spätere Cross-Paper-Suche.
- Bibliotheks-Modus wählbar: Einzel-Paper-Fokus oder Mehrere-Paper/Vergleich.
- Keine Datenbank — alles Streamlit Session-State. Persistenz nur über Export (Excel/PDF-Download).
- Claude-API-Key ausschließlich über `st.secrets`, nie im Code/Repo.

## 3. Komponenten & Dateien

```
app.py                      # Login-Gate + Sidebar-Navigation + Routing
modules/
  auth.py                   # Passwort-Check gegen st.secrets, session_state.authenticated
  search_semanticscholar.py # Semantic Scholar API-Call + Parsing
  search_core.py            # CORE API-Call + Parsing
  search_pubmed.py          # PubMed API-Call + Parsing
  search_europepmc.py       # Europe PMC API-Call + Parsing
  search_aggregator.py      # kombiniert gewählte Quellen (Checkboxen), Dedup/Merge
  pdf_extract.py            # PDF -> Volltext (pypdf/pdfplumber), einmalig beim Hinzufügen gecacht
  analysis_direct.py        # Modus A: Volltext + Schema-Prompt -> Claude
  analysis_ragpipeline.py   # Modus B: Chunking/Retrieval -> Claude
  report_schema.py          # feste Schema-Felder + Prompt-Template + Antwort-Parsing
  qa_engine.py               # Frage -> Modus A oder B -> Claude-Antwort
  export_excel.py           # Bibliothek/Berichte -> .xlsx (Vergleichstabelle)
  export_pdf.py             # einzelner Bericht -> .pdf (Leseformat)
  library_state.py          # zentrale Session-State-Verwaltung (Paper-Liste, Modus-Flags, Cache)
.streamlit/
  config.toml
requirements.txt
packages.txt                # System-Deps (z.B. poppler für pdfplumber falls nötig)
DEPLOYMENT.md
README.md
tests/
  test_pdf_extract.py
  test_search_aggregator.py
  test_report_schema.py
  test_qa_engine.py
  test_export.py
  test_auth.py
```

Alle Tabs/Seiten greifen auf Bibliothek ausschließlich über `library_state.py` zu — kein Modul kennt Interna eines anderen Moduls direkt.

## 4. Berichts-Schema (fest)

Pro Paper, erzeugt via Claude (Modus A oder B), folgende Felder:

- Forschungsfrage
- Theoretischer Rahmen
- Methodik (quantitativ / qualitativ / mixed-methods)
- Stichprobe (Größe, Zusammensetzung, Auswahlverfahren)
- Datenerhebung (Instrument, Zeitraum, Ort)
- Ergebnisse (Kernbefunde)
- Limitationen
- Implikationen / Schlussfolgerungen

Export-Tabelle (Excel) hat diese Felder als Spalten, eine Zeile pro Paper. PDF-Export rendert dieselben Felder als Fließtext-Bericht für ein Paper.

## 5. Daten-Fluss

1. **Login**: Passwort-Eingabe → Abgleich `st.secrets["APP_PASSWORD"]` → bei Erfolg `authenticated = True`, sonst Fehlermeldung, kein weiterer Zugriff.
2. **Suche**: Checkboxen (Semantic Scholar / CORE / PubMed / Europe PMC) + Suchbegriff → `search_aggregator.py` ruft gewählte Quellen auf → vereinte, deduplizierte Trefferliste → "In Bibliothek übernehmen" lädt PDF falls Link vorhanden.
3. **Upload**: direkter PDF-Upload → gleiche Bibliothek, Status "lokal hochgeladen".
4. **Extraktion**: beim Hinzufügen läuft `pdf_extract.py` einmal, Volltext wird in `library_state.py` gecacht.
5. **Analyse**: Paper + Modus (A/B) wählen → `analysis_direct.py` oder `analysis_ragpipeline.py` → `report_schema.py`-Prompt → Claude-Antwort → strukturiert an Paper im Session-State angehängt.
6. **Q&A**: Paper wählen, Frage stellen → `qa_engine.py` nutzt gewählten Modus + gecachten Volltext/Index → Antwort.
7. **Export**: Mehrere-Paper-Modus → `export_excel.py` sammelt alle Berichte; Einzel-Modus → `export_pdf.py` für aktuelles Paper.

## 6. Fehlerbehandlung

- Einzelne Such-API down/Rate-Limit → leere Liste + Warnung für diese Quelle, andere laufen weiter.
- PDF nicht extrahierbar (Scan ohne Text, defekt) → Paper-Status "Text nicht extrahierbar", Analyse/Q&A für dieses Paper gesperrt mit Hinweis.
- Claude-API-Fehler (Key fehlt, Rate-Limit, Timeout) → klare UI-Fehlermeldung, kein App-Crash, Retry möglich.
- Paper zu lang für Modus A → Hinweis "zu lang für Direkt-Modus, nutze RAG-Modus" statt stillem Abbruch/Kontextfenster-Fehler.
- Login: falsches Passwort → Fehlermeldung, kein Stacktrace.
- Session-Verlust bei Reload → Bibliothek geht verloren (bekannte Grenze von Session-State), Hinweis "vor Schließen exportieren".

## 7. Testing

- Unit-Tests (pytest) je Modul, externe API/Claude-Calls gemockt:
  - `pdf_extract.py` gegen bekanntes Test-PDF.
  - `search_aggregator.py` Dedup/Merge mit gemockten Antworten aller 4 Quellen.
  - `report_schema.py` Prompt-Befüllung + Antwort-Parsing inkl. leicht abweichendem Format.
  - `qa_engine.py` Modus-Umschaltung + Erkennung "zu lang für Modus A".
  - `export_excel.py` / `export_pdf.py` Struktur/Spalten-Check.
  - `auth.py` richtiges/falsches Passwort steuert `authenticated` korrekt.
- Kein automatisierter Test gegen echte Claude-API in CI (Kosten/Flakiness).
- Manueller Smoke-Test vor jedem Deploy: Login → Suche (1 Quelle) → Paper übernehmen → Analyse Modus A → Q&A → Export Excel+PDF.

## 8. Deployment

- Neues GitHub-Repo (unter Erwin2307-py oder vom Nutzer gewählt).
- Streamlit Community Cloud verbindet sich auf dieses Repo, Branch `main`, Entry-Point `app.py`.
- Secrets (`APP_PASSWORD`, Claude-API-Key, ggf. CORE-API-Key) über Streamlit Cloud "Secrets"-Einstellung, nicht im Repo.
- `DEPLOYMENT.md` dokumentiert Setup-Schritte (Repo erstellen, Secrets setzen, Cloud verbinden), analog zum Original-Repo-Pattern.

## 9. Offene Punkte

Keine offenen Fragen — alle Design-Entscheidungen in der Brainstorming-Session bestätigt.
