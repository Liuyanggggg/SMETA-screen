from __future__ import annotations

from dataclasses import dataclass

from smeta_screen.prompt_opt.metrics import Metrics


@dataclass
class GateResult:
    accept: bool
    reason: str


def gate(
    parent: Metrics,
    child: Metrics,
    *,
    min_recall: float | None = None,
    objective: str = "recall",
) -> GateResult:
    """Accept child if it meets the recall floor and improves the objective tuple.

    objective=recall  → (recall, workload_cut, precision)
    objective=workload → (workload_cut, recall, precision)
    """
    floor = parent.recall if min_recall is None else float(min_recall)
    if child.recall + 1e-12 < floor:
        return GateResult(False, f"召回下降 {parent.recall:.4f} → {child.recall:.4f}（下限 {floor:.4f}）")
    if child.parse_fail > parent.parse_fail:
        return GateResult(False, f"解析失败增加 {parent.parse_fail} → {child.parse_fail}")

    pt = _obj(parent, objective)
    ct = _obj(child, objective)
    if ct > pt:
        return GateResult(True, f"目标提升 {pt} → {ct}")
    return GateResult(False, f"目标无提升 {pt} → {ct}")


def _obj(m: Metrics, objective: str) -> tuple[float, float, float]:
    if objective == "workload":
        return (round(m.workload_cut, 6), round(m.recall, 6), round(m.precision, 6))
    return (round(m.recall, 6), round(m.workload_cut, 6), round(m.precision, 6))
