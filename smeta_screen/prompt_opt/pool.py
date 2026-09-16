"""Pool labeled title/abstract rows from the 45-meta SMETA table."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/liuyang/Desktop/SMETA")
SMETA_XLSX = ROOT / "0manuscript" / "SMETA_results.xlsx"
INCLUDES_XLSX = (
    ROOT / "0manuscript" / "public_data" / "derived" / "include_pubmed_abstracts_611rows_filled.xlsx"
)
SR_DIR = ROOT / "5result" / "7deepseek_result2"
HUMAN_300 = ROOT / "0manuscript" / "test_balanced_300.xlsx"
RESERVED_METAS: set[str] = set()  # all 45 metas in the 800 pool


def nt(s: str) -> str:
    s = str(s).lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def _load_screening(pmid: str) -> tuple[dict[str, dict], dict[str, dict]]:
    p = SR_DIR / f"{pmid}_output_with_abstract" / f"screening_results_{pmid}.json"
    if not p.exists():
        return {}, {}
    recs = json.loads(p.read_text(encoding="utf-8"))
    by_acc, by_title = {}, {}
    for x in recs:
        acc = str(x.get("Accession_Number") or "").strip()
        title = str(x.get("title") or "").strip()
        if acc:
            by_acc[acc] = x
        if title:
            by_title[nt(title)] = x
    return by_acc, by_title


def human_300_titles() -> set[str]:
    if not HUMAN_300.exists():
        return set()
    df = pd.read_excel(HUMAN_300, usecols=["title"])
    return {nt(t) for t in df["title"].astype(str) if nt(t)}


def _row(pmid: str, rid: str, title: str, abstract: str, gold: str) -> dict:
    return {
        "record_id": f"{pmid}::{rid}",
        "meta_id": pmid,
        "source_record_id": rid,
        "title": title,
        "abstract": abstract,
        "gold": gold,
    }


def build_pool(
    *,
    skip_metas: set[str] | None = None,
    skip_titles: set[str] | None = None,
    skip_keys: set[str] | None = None,
) -> list[dict]:
    skip_metas = {str(x) for x in (skip_metas or ())} | set(RESERVED_METAS)
    skip_titles = set(skip_titles or ())
    skip_keys = set(skip_keys or ())
    rows: list[dict] = []
    seen: set[str] = set()

    inc = pd.read_excel(INCLUDES_XLSX)
    for _, r in inc.iterrows():
        pmid = str(int(r.meta_id)) if pd.notna(r.meta_id) else ""
        if pmid in skip_metas:
            continue
        title = str(r.title or "").strip()
        abstract = str(r.abstract or "").strip()
        if not title or not abstract or title.lower() == "nan" or abstract.lower() == "nan":
            continue
        if nt(title) in skip_titles:
            continue
        rid = str(r.record_id).strip()
        key = f"{pmid}::{rid}"
        if key in seen or key in skip_keys:
            continue
        seen.add(key)
        rows.append(_row(pmid, rid, title, abstract, "include"))

    xl = pd.ExcelFile(SMETA_XLSX)
    for pmid in xl.sheet_names:
        if pmid in skip_metas:
            continue
        gold = pd.read_excel(SMETA_XLSX, sheet_name=pmid, usecols=["record_id", "gold_lable"])
        by_acc, by_title = _load_screening(pmid)
        for _, r in gold.iterrows():
            g = str(r.gold_lable).strip().lower()
            if g != "exclude":
                continue
            rid = str(r.record_id).strip()
            rec = by_acc.get(rid) or by_title.get(nt(rid))
            if rec is None:
                continue
            title = str(rec.get("title") or "").strip()
            abstract = str(rec.get("abstract") or "").strip()
            if not title or not abstract:
                continue
            if nt(title) in skip_titles:
                continue
            key = f"{pmid}::{rid}"
            if key in seen or key in skip_keys:
                continue
            seen.add(key)
            rows.append(_row(pmid, rid, title, abstract, "exclude"))
    return rows
