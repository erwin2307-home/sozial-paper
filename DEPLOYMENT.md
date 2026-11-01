# Deployment

## Deployment auf Streamlit Community Cloud

1. Repo auf GitHub erstellen/pushen (Branch `main`).
2. Auf https://share.streamlit.io neue App anlegen, Repo + Branch `main` + Entry-Point `app.py` auswaehlen.
3. Unter "Secrets" folgende Werte eintragen:
   ```
   APP_PASSWORD = "dein-passwort"
   CLAUDE_API_KEY = "sk-ant-..."
   CORE_API_KEY = "dein-core-key"
   GOOGLE_TRANSLATE_API_KEY = "optional, offizielle Google-Uebersetzung"
   MYMEMORY_EMAIL = "optional, hoeheres kostenloses Tageslimit"
   ```
4. Deploy ausloesen. Bei Aenderungen an `main` deployed Streamlit Cloud automatisch neu.
5. Vor jedem Deploy: manuellen Smoke-Test durchfuehren (Login → Suche → Paper uebernehmen → Analyse Modus A → Q&A → Export Excel+PDF).

Da reines Streamlit kein Rate-Limiting fuer Login-Versuche ermoeglicht, ist ein langes, hochentropisches `APP_PASSWORD` (z. B. eine zufaellige Passphrase mit mindestens 20 Zeichen) die eigentliche Schutzmassnahme gegen Brute-Force-Versuche.
