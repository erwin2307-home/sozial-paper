from defusedxml import ElementTree as ET
import requests

from modules.search_europepmc import PMC_FULLTEXT_URL

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


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
    abstracts = _fetch_abstracts(ids, api_key)
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
            "abstract": abstracts.get(pmid, ""),
            "pdf_url": _pmc_pdf_url(item),
            "source": "pubmed",
        })
    return results


def _pmc_pdf_url(item: dict):
    for article_id in item.get("articleids", []):
        if article_id.get("idtype") == "pmc" and article_id.get("value"):
            return PMC_FULLTEXT_URL.format(pmcid=article_id["value"])
    return None


def _fetch_abstracts(ids: list, api_key: str = None) -> dict:
    """Abstracts are optional extras: a failed lookup must not lose the search hits."""
    params = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}
    if api_key:
        params["api_key"] = api_key
    try:
        response = requests.get(EFETCH_URL, params=params, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception:
        return {}
    abstracts = {}
    for article in root.iter("PubmedArticle"):
        pmid = article.findtext("MedlineCitation/PMID")
        parts = ["".join(node.itertext()).strip() for node in article.iter("AbstractText")]
        if pmid and parts:
            abstracts[pmid] = " ".join(parts)
    return abstracts


def _extract_year(pubdate: str):
    digits = "".join(ch for ch in pubdate[:4] if ch.isdigit())
    return int(digits) if digits else None
