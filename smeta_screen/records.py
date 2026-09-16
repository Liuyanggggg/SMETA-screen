from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

TITLE_KEYS = ["title", "Title", "TI", "ArticleTitle"]
ABSTRACT_KEYS = ["abstract", "Abstract", "AB", "AbstractText"]
ID_KEYS = [
    "record_id",
    "pmid",
    "PMID",
    "Accession_Number",
    "Accession Number",
    "accession",
    "id",
    "ID",
    "doi",
    "DOI",
]


def _pick(d: dict, keys: list[str]) -> str:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return str(d[k]).strip()
    lower = {str(k).lower(): v for k, v in d.items()}
    for k in keys:
        v = lower.get(k.lower())
        if v not in (None, ""):
            return str(v).strip()
    return ""


def _norm_row(raw: dict[str, Any], fallback_id: str) -> dict[str, str] | None:
    title = _pick(raw, TITLE_KEYS)
    abstract = _pick(raw, ABSTRACT_KEYS)
    rid = _pick(raw, ID_KEYS) or fallback_id
    if not title:
        return None
    return {
        "record_id": rid,
        "title": title,
        "abstract": abstract,
    }


def _load_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in ("records", "data", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]
    rows = []
    for i, item in enumerate(data, 1):
        if not isinstance(item, dict):
            continue
        rec = _norm_row(item, f"row-{i}")
        if rec:
            rows.append(rec)
    return rows


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            continue
        rec = _norm_row(item, f"row-{i}")
        if rec:
            rows.append(rec)
    return rows


def _load_table(path: Path) -> list[dict]:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    df = df.fillna("")
    rows = []
    for i, item in enumerate(df.to_dict(orient="records"), 1):
        rec = _norm_row(item, f"row-{i}")
        if rec:
            rows.append(rec)
    return rows


def _parse_ris(text: str) -> list[dict]:
    records: list[dict] = []
    cur: dict[str, list[str]] = {}

    def flush():
        if not cur:
            return
        title = " ".join(cur.get("TI", cur.get("T1", []))).strip()
        abstract = " ".join(cur.get("AB", cur.get("N2", []))).strip()
        rid = ""
        for key in ("AN", "UR", "DO", "ID"):
            if cur.get(key):
                rid = cur[key][0].strip()
                break
        pmids = [x for x in cur.get("AN", []) + cur.get("ID", []) if re.fullmatch(r"\d{4,9}", x.strip())]
        if pmids:
            rid = pmids[0]
        if title:
            records.append({"record_id": rid or f"ris-{len(records)+1}", "title": title, "abstract": abstract})

    for raw in text.splitlines():
        if re.match(r"^ER\s+-", raw) or raw.strip() == "ER  -":
            flush()
            cur = {}
            continue
        m = re.match(r"^([A-Z0-9]{2})\s+-\s+(.*)$", raw)
        if m:
            tag, val = m.group(1), m.group(2)
            cur.setdefault(tag, []).append(val.strip())
        elif cur:
            last = list(cur.keys())[-1]
            cur[last][-1] = cur[last][-1] + " " + raw.strip()
    flush()
    return records


def load_records(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到题录文件: {p}")
    suf = p.suffix.lower()
    if suf == ".json":
        rows = _load_json(p)
    elif suf == ".jsonl":
        rows = _load_jsonl(p)
    elif suf in {".xlsx", ".xls", ".csv"}:
        rows = _load_table(p)
    elif suf in {".ris", ".txt"}:
        rows = _parse_ris(p.read_text(encoding="utf-8", errors="ignore"))
    else:
        raise ValueError(f"不支持的题录格式: {suf}（支持 json/jsonl/xlsx/csv/ris）")
    if not rows:
        raise ValueError(f"没有读到有效题录（需要 title 列）: {p}")
    seen = set()
    uniq = []
    for r in rows:
        key = (r["record_id"], r["title"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq
