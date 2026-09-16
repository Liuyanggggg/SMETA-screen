"""Lock TEST before any prompt is scored. Homiar/JCE: develop then evaluate once."""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path


def _ids(xs: list[dict]) -> list[str]:
    return [str(x["record_id"]) for x in xs]


def lock_balanced(
    rows: list[dict],
    *,
    seed: int = 42,
    target_n: int = 800,
    n_val_pos: int = 40,
    min_dev_pos: int = 80,
) -> dict:
    """Sanghera-style 1:1 set. TEST is locked first at target_n (400/400).

    Remaining gold includes (and an equal number of excludes) become VAL then DEV,
    also 1:1. Does not pad extra excludes to fake n=800.
    """
    rng = random.Random(seed)
    pos = [r for r in rows if r.get("gold") == "include"]
    neg = [r for r in rows if r.get("gold") != "include"]
    rng.shuffle(pos)
    rng.shuffle(neg)
    half = target_n // 2
    reserve = n_val_pos + min_dev_pos
    if len(pos) < reserve + 1:
        raise ValueError(
            f"gold includes={len(pos)} too few to lock a 1:1 TEST and keep "
            f"{reserve} includes for VAL+DEV"
        )
    if len(neg) < half + n_val_pos + min_dev_pos:
        raise ValueError(f"gold excludes={len(neg)} too few for 1:1 splits")
    test_pos_n = min(half, len(pos) - reserve)
    test_p, test_n = pos[:test_pos_n], neg[:test_pos_n]
    rest_p, rest_n = pos[test_pos_n:], neg[test_pos_n:]
    val_p, val_n = rest_p[:n_val_pos], rest_n[:n_val_pos]
    dev_p = rest_p[n_val_pos:]
    dev_n = rest_n[n_val_pos : n_val_pos + len(dev_p)]
    n_test = len(test_p) + len(test_n)
    return {
        "seed": seed,
        "mode": "balanced_1to1",
        "target_n": target_n,
        "n_total": len(rows),
        "n_pos": len(pos),
        "n_neg": len(neg),
        "dev_ids": _ids(dev_p + dev_n),
        "val_ids": _ids(val_p + val_n),
        "test_ids": _ids(test_p + test_n),
        "n_dev": len(dev_p) + len(dev_n),
        "n_val": len(val_p) + len(val_n),
        "n_test": n_test,
        "dev_pos": len(dev_p),
        "val_pos": len(val_p),
        "test_pos": len(test_p),
        "reached_target": n_test == target_n,
        "test_by_meta": dict(Counter(str(r.get("meta_id") or "") for r in test_p + test_n)),
        "note": (
            "TEST is a locked 1:1 balanced set (Sanghera n=800 analogue). "
            "IDs written before catalogue scoring. Do not resplit."
        ),
    }


def lock_splits(
    rows: list[dict],
    *,
    seed: int = 42,
    test_pos: int = 5,
    val_pos: int = 4,
    n_dev_neg: int = 100,
    n_val_neg: int = 80,
    n_test_neg: int = 400,
) -> dict:
    rng = random.Random(seed)
    pos = [r for r in rows if r.get("gold") == "include"]
    neg = [r for r in rows if r.get("gold") != "include"]
    rng.shuffle(pos)
    rng.shuffle(neg)
    if len(pos) < test_pos + val_pos + 1:
        test_pos = max(1, len(pos) // 3)
        val_pos = max(1, len(pos) // 3)
    test_p = pos[:test_pos]
    val_p = pos[test_pos : test_pos + val_pos]
    dev_p = pos[test_pos + val_pos :]
    test_n = neg[:n_test_neg]
    val_n = neg[n_test_neg : n_test_neg + n_val_neg]
    rest = neg[n_test_neg + n_val_neg :]
    dev_n = rest[:n_dev_neg]
    return {
        "seed": seed,
        "n_total": len(rows),
        "n_pos": len(pos),
        "dev_ids": _ids(dev_p + dev_n),
        "val_ids": _ids(val_p + val_n),
        "test_ids": _ids(test_p + test_n),
        "n_dev": len(dev_p) + len(dev_n),
        "n_val": len(val_p) + len(val_n),
        "n_test": len(test_p) + len(test_n),
        "dev_pos": len(dev_p),
        "val_pos": len(val_p),
        "test_pos": len(test_p),
        "note": "TEST ids are locked before catalogue scoring. Do not resplit.",
    }


def take(rows: list[dict], ids: list[str]) -> list[dict]:
    want = set(ids)
    return [r for r in rows if str(r["record_id"]) in want]


def save_splits(path: Path, spec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
