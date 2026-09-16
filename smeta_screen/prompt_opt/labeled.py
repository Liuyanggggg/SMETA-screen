from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from smeta_screen.records import load_records


def _gold_of(raw: dict[str, Any]) -> str | None:
    for k in ("gold", "label", "y", "include"):
        if k in raw and raw[k] not in (None, ""):
            s = str(raw[k]).strip().lower()
            if s in {"1", "true", "yes", "include", "positive", "pos"}:
                return "include"
            if s in {"0", "false", "no", "exclude", "negative", "neg"}:
                return "exclude"
            if s in {"include", "exclude", "uncertain"}:
                return "include" if s != "exclude" else "exclude"
    return None


def load_labeled(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    recs = load_records(p)
    gold_by_id: dict[str, str] = {}
    gold_by_title: dict[str, str] = {}
    if p.suffix.lower() in {".json", ".jsonl"}:
        if p.suffix.lower() == ".jsonl":
            items = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("records") or data.get("data") or data.get("items") or [data]
            items = data
        for item in items:
            if not isinstance(item, dict):
                continue
            g = _gold_of(item)
            if not g:
                continue
            rid = str(item.get("record_id") or item.get("pmid") or item.get("PMID") or "")
            title = str(item.get("title") or item.get("Title") or "")
            if rid:
                gold_by_id[rid] = g
            if title:
                gold_by_title[title.strip()] = g
    out = []
    for r in recs:
        g = gold_by_id.get(r["record_id"]) or gold_by_title.get((r["title"] or "").strip())
        if not g:
            continue
        out.append({**r, "gold": g})
    if not out:
        raise ValueError(f"没有读到带 gold 的题录: {p}")
    return out


def split_hold(
    rows: list[dict[str, str]],
    hold_ratio: float,
    seed: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if hold_ratio <= 0 or len(rows) < 8:
        return list(rows), []
    rng = random.Random(seed)
    idx = list(range(len(rows)))
    rng.shuffle(idx)
    n_hold = max(1, int(round(len(rows) * hold_ratio)))
    n_hold = min(n_hold, len(rows) // 3 if len(rows) >= 9 else n_hold)
    hold_i = set(idx[:n_hold])
    dev = [rows[i] for i in range(len(rows)) if i not in hold_i]
    hold = [rows[i] for i in range(len(rows)) if i in hold_i]
    return dev, hold
