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
