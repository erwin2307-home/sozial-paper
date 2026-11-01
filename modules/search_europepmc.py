import requests

API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
# Europe PMC blocks scripted PDF downloads (403); this official endpoint serves the same article as JATS XML.
PMC_FULLTEXT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"


def search(query: str, api_key: str = None, limit: int = 10) -> list:
    params = {"query": query, "format": "json", "pageSize": limit, "resultType": "core"}
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
            "pdf_url": _find_pdf_url(item),
            "source": "europepmc",
        })
    return results


def _find_pdf_url(item: dict):
    if item.get("pmcid") and item.get("isOpenAccess") == "Y":
        return PMC_FULLTEXT_URL.format(pmcid=item["pmcid"])
    links = (item.get("fullTextUrlList") or {}).get("fullTextUrl") or []
    for link in links:
        if link.get("documentStyle") == "pdf" and link.get("availabilityCode") in ("OA", "F"):
            return link.get("url")
    return None
