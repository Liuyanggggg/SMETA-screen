"""Pre-specified catalogue winner. Do not select on F1."""
from __future__ import annotations

from smeta_screen.prompt_opt.catalogue import CatalogueEntry
from smeta_screen.prompt_opt.metrics import Metrics

BASELINE_ID = "smeta_recall_first"


def pick_catalogue_winner(
    entries: list[CatalogueEntry],
    metrics: dict[str, Metrics],
    *,
    baseline_id: str = BASELINE_ID,
) -> str:
    """Recall floor of the production baseline, then workload_cut, then precision.

    Contrast entries (selectable=False, e.g. rsm_f1_methods) cannot win.
    F1 is never used.
    """
    if baseline_id not in metrics:
        raise KeyError(f"baseline {baseline_id} was not scored on DEV")
    r0 = metrics[baseline_id].recall
    elig = [
        e.id
        for e in entries
        if e.selectable and e.id in metrics and metrics[e.id].recall + 1e-12 >= r0
    ]
    if not elig:
        return baseline_id
    return max(
        elig,
        key=lambda k: (metrics[k].recall, metrics[k].workload_cut, metrics[k].precision),
    )
