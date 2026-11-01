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


def test_europepmc_requests_core_result_type_for_abstracts():
    with patch("modules.search_europepmc.requests.get", return_value=_mock_response({})) as mock_get:
        search_europepmc.search("x")
    assert mock_get.call_args.kwargs["params"]["resultType"] == "core"


def test_europepmc_uses_open_access_pdf_link():
    payload = {"resultList": {"result": [{
        "id": "1", "title": "T", "fullTextUrlList": {"fullTextUrl": [
            {"documentStyle": "html", "availabilityCode": "OA", "url": "http://example.org/a.html"},
            {"documentStyle": "pdf", "availabilityCode": "S", "url": "http://example.org/paid.pdf"},
            {"documentStyle": "pdf", "availabilityCode": "OA", "url": "http://example.org/a.pdf"},
        ]},
    }]}}
    with patch("modules.search_europepmc.requests.get", return_value=_mock_response(payload)):
        assert search_europepmc.search("x")[0]["pdf_url"] == "http://example.org/a.pdf"


def test_europepmc_prefers_official_full_text_api_for_open_access_pmcid():
    payload = {"resultList": {"result": [{
        "id": "1", "title": "T", "pmcid": "PMC7", "isOpenAccess": "Y",
        "fullTextUrlList": {"fullTextUrl": [
            {"documentStyle": "pdf", "availabilityCode": "OA", "url": "https://europepmc.org/articles/PMC7?pdf=render"},
        ]},
    }]}}
    with patch("modules.search_europepmc.requests.get", return_value=_mock_response(payload)):
        assert search_europepmc.search("x")[0]["pdf_url"] == (
            "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7/fullTextXML"
        )


def test_pubmed_fetches_abstract_and_pmc_pdf_link():
    esearch = {"esearchresult": {"idlist": ["111"]}}
    esummary = {"result": {"111": {
        "title": "T", "articleids": [{"idtype": "pmc", "value": "PMC9"}],
    }}}
    efetch = Mock()
    efetch.content = (
        b'<?xml version="1.0"?><PubmedArticleSet><PubmedArticle><MedlineCitation>'
        b'<PMID>111</PMID><Article><Abstract><AbstractText Label="A">Erster <i>Teil</i>.</AbstractText>'
        b'<AbstractText>Zweiter Teil.</AbstractText></Abstract></Article>'
        b'</MedlineCitation></PubmedArticle></PubmedArticleSet>'
    )
    with patch("modules.search_pubmed.requests.get",
               side_effect=[_mock_response(esearch), _mock_response(esummary), efetch]):
        result = search_pubmed.search("x")[0]
    assert result["abstract"] == "Erster Teil. Zweiter Teil."
    assert result["pdf_url"] == "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9/fullTextXML"
