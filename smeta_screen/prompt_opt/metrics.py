from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


POSITIVE = {"include", "uncertain"}


def _is_pos_gold(v: Any) -> bool:
    s = str(v or "").strip().lower()
    return s in {"1", "true", "yes", "include", "positive", "pos"}


def _is_pos_pred(decision: str, mode: str) -> bool:
    d = (decision or "").strip().lower()
    if mode == "strict":
        return d == "include"
    return d in POSITIVE


@dataclass
class Metrics:
    n: int = 0
    gold_pos: int = 0
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    n_flagged: int = 0
    parse_fail: int = 0
    recall: float = 0.0
    precision: float = 0.0
    specificity: float = 0.0
    workload_cut: float = 0.0
    by_decision: dict[str, int] = field(default_factory=dict)

    recall_lo: float = 0.0
    recall_hi: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    p = k / n
    z2 = z * z
    den = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / den
    half = z * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def score_rows(
    rows: Iterable[dict[str, Any]],
    *,
    mode: str = "recall_first",
) -> tuple[Metrics, list[dict[str, Any]]]:
    """Gold include = positive. Pred positive = include (+ uncertain unless strict)."""
    m = Metrics()
    errors: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for r in rows:
        gold_pos = _is_pos_gold(r.get("gold"))
        decision = str(r.get("decision") or "").strip().lower() or "uncertain"
        counts[decision] = counts.get(decision, 0) + 1
        pred_pos = _is_pos_pred(decision, mode)
        reason = str(r.get("reason") or "")
        if reason.startswith("unparsed:") or reason.startswith("error:"):
            m.parse_fail += 1
        m.n += 1
        if gold_pos:
            m.gold_pos += 1
        if pred_pos:
            m.n_flagged += 1
        if gold_pos and pred_pos:
            m.tp += 1
        elif (not gold_pos) and pred_pos:
            m.fp += 1
            errors.append(_err(r, "fp", gold_pos, decision))
        elif gold_pos and not pred_pos:
            m.fn += 1
            errors.append(_err(r, "fn", gold_pos, decision))
        else:
            m.tn += 1
    m.by_decision = counts
    m.recall = (m.tp / m.gold_pos) if m.gold_pos else 0.0
    m.recall_lo, m.recall_hi = wilson(m.tp, m.gold_pos) if m.gold_pos else (0.0, 0.0)
    m.precision = (m.tp / m.n_flagged) if m.n_flagged else 0.0
    neg = m.n - m.gold_pos
    m.specificity = (m.tn / neg) if neg else 0.0
    m.workload_cut = (1.0 - m.n_flagged / m.n) if m.n else 0.0
    return m, errors


def _err(r: dict[str, Any], kind: str, gold_pos: bool, decision: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "record_id": r.get("record_id"),
        "title": r.get("title"),
        "gold": "include" if gold_pos else "exclude",
        "decision": decision,
        "reason": r.get("reason") or "",
    }
