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
