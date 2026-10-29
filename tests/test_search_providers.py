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
