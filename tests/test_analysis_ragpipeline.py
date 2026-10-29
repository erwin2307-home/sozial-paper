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
