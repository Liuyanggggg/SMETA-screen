from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Iterable

import requests

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _chunks(xs: list[str], n: int) -> Iterable[list[str]]:
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def search_pubmed(
    query: str,
    email: str,
    api_key: str | None = None,
    retmax: int = 10000,
    pause: float = 0.35,
) -> list[dict[str, str]]:
    if not email:
        raise ValueError("PubMed 要求提供 email（NCBI 使用规范）。")
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(retmax),
        "retmode": "json",
        "tool": "smeta-screen",
        "email": email,
    }
    if api_key:
        params["api_key"] = api_key
    r = requests.get(f"{EUTILS}/esearch.fcgi", params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    ids = data.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    records: list[dict[str, str]] = []
    for batch in _chunks(ids, 200):
        fparams = {
            "db": "pubmed",
            "id": ",".join(batch),
            "retmode": "xml",
            "rettype": "abstract",
            "tool": "smeta-screen",
            "email": email,
        }
        if api_key:
            fparams["api_key"] = api_key
        fr = requests.get(f"{EUTILS}/efetch.fcgi", params=fparams, timeout=120)
        fr.raise_for_status()
        root = ET.fromstring(fr.text)
        for art in root.findall(".//PubmedArticle"):
            pmid_el = art.findtext(".//PMID")
            pmid = (pmid_el or "").strip()
            title = "".join(art.find(".//ArticleTitle").itertext()).strip() if art.find(".//ArticleTitle") is not None else ""
            abs_parts = []
            for ab in art.findall(".//Abstract/AbstractText"):
                abs_parts.append("".join(ab.itertext()).strip())
            abstract = "\n".join(p for p in abs_parts if p)
            if title:
                records.append({"record_id": pmid, "title": title, "abstract": abstract})
        time.sleep(pause)
    return records
