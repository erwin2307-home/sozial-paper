import json
import re

from modules.claude_client import call_claude

LANGUAGE_NAMES = {"de": "Deutsch", "en": "English", "tr": "Turkce"}

PRESET_TRANSKULTURALITAET = [
    (
        "Beschreiben Sie in eigenen Worten, was Wolfgang Welsch unter Transkulturalitaet "
        "versteht. Gehen Sie darauf ein, was an diesem Ansatz besonders wichtig erscheint "
        "und worin sich Transkulturalitaet von Vorstellungen unterscheidet, die Kultur als "
        "klar voneinander getrennte Einheiten verstehen."
    ),
    (
        "Reflektieren Sie die Bedeutung des Konzepts der Transkulturalitaet fuer die Soziale "
        "Arbeit: welche Chancen eine transkulturelle Sichtweise fuer die Arbeit mit Menschen "
        "eroeffnet, welche Auswirkungen sie auf den Umgang mit Diversitaet, Zugehoerigkeit "
        "und Unterschiedlichkeit haben koennte, und welche Grenzen oder Herausforderungen "
        "dieser Ansatz hat."
    ),
    (
        "Formulieren Sie abschliessend eine Frage, einen Gedanken oder eine Aussage aus dem "
        "Text, die besonders beschaeftigt, ueberrascht oder irritiert hat."
    ),
]


def extract_questions_from_text(raw_text: str, client) -> list:
    prompt = (
        "Extrahiere wirklich alle Fragen und Aufgabenstellungen aus dem folgenden Text als Liste, "
        "auch jede Unterfrage, Teilaufgabe und jeden Eintrag aus einer Tabelle (Spalten sind durch | getrennt). "
        "Uebernimm den Wortlaut unveraendert und in der Reihenfolge des Textes und fasse nichts zusammen. "
        "Antworte ausschliesslich mit einem JSON-Array von Strings, ein Eintrag pro Frage/Aufgabe.\n\n"
        f"TEXT:\n{raw_text}"
    )
    raw = call_claude(client, prompt)
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    json_str = match.group(0) if match else raw
    try:
        questions = json.loads(json_str)
    except json.JSONDecodeError:
        questions = []
    return [str(q) for q in questions if str(q).strip()]
