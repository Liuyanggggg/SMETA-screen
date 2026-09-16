from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from smeta_screen.llm import LLMClient
from smeta_screen.prompt_opt.gate import gate
from smeta_screen.prompt_opt.metrics import Metrics, score_rows
from smeta_screen.prompt_opt.propose import Optimizer
from smeta_screen.prompt_opt.screen import ScreenFn, screen_labeled
from smeta_screen.prompt_opt.spec import PromptSpec
from smeta_screen.prompt_opt.store import RunStore


@dataclass
class LoopResult:
    best_id: str
    rounds: int
    stopped: str


def evaluate_spec(
    spec: PromptSpec,
    records: list[dict[str, str]],
    *,
    criteria: str,
    store: RunStore,
    split: str,
    client: LLMClient | None = None,
    screen_fn: ScreenFn | None = None,
    workers: int = 8,
    model_name: str = "mock",
    mode: str = "recall_first",
) -> tuple[Metrics, list[dict[str, Any]]]:
    preds = screen_labeled(
        spec,
        records,
        criteria=criteria,
        client=client,
        cache_dir=store.cache,
        workers=workers,
        screen_fn=screen_fn,
        model_name=model_name,
    )
    metrics, errors = score_rows(preds, mode=mode)
    store.save_version(spec, metrics.to_dict(), preds, errors, split=split)
    return metrics, errors


def run_loop(
    *,
    store: RunStore,
    spec: PromptSpec,
    criteria: str,
    dev: list[dict[str, str]],
    hold: list[dict[str, str]] | None,
    optimizer: Optimizer,
    client: LLMClient | None = None,
    screen_fn: ScreenFn | None = None,
    workers: int = 8,
    model_name: str = "mock",
    max_rounds: int = 5,
    min_recall: float | None = None,
    objective: str = "recall",
    mode: str = "recall_first",
    log: Callable[[str], None] | None = None,
) -> LoopResult:
    say = log or (lambda s: print(s))
    hold = hold or []

    def eval_all(s: PromptSpec) -> tuple[Metrics, list[dict], Metrics | None]:
        dev_m, dev_e = evaluate_spec(
            s, dev, criteria=criteria, store=store, split="dev",
            client=client, screen_fn=screen_fn, workers=workers,
            model_name=model_name, mode=mode,
        )
        hold_m = None
        if hold:
            hold_m, _ = evaluate_spec(
                s, hold, criteria=criteria, store=store, split="hold",
                client=client, screen_fn=screen_fn, workers=workers,
                model_name=model_name, mode=mode,
            )
        return dev_m, dev_e, hold_m

    current = spec
    if not (store.dir_for(current.id) / "spec.yaml").exists():
        current.dump(store.dir_for(current.id) / "spec.yaml")
    store.set_best(current.id)

    dev_m, dev_e, hold_m = eval_all(current)
    say(_fmt("baseline", current, dev_m, hold_m))

    rounds = 0
    for _ in range(max_rounds):
        proposed = optimizer.propose(current, dev_m, dev_e)
        if proposed is None:
            nxt = store.next_spec_path()
            if not nxt.exists():
                current.dump(nxt)
            say(f"等待人工改 {nxt} 后再次运行 opt run。")
            return LoopResult(current.id, rounds, "wait_manual")

        if proposed.fingerprint() == current.fingerprint():
            say("候选与当前 fingerprint 相同，停止。")
            return LoopResult(current.id, rounds, "no_change")

        new_id = store.next_id()
        candidate = current.child(
            new_id,
            role=proposed.role,
            rules=proposed.rules,
            notes=proposed.notes,
            priority=proposed.priority,
        )
        c_dev, c_err, c_hold = eval_all(candidate)
        parent_for_gate = hold_m if (hold_m and c_hold) else dev_m
        child_for_gate = c_hold if (hold_m and c_hold) else c_dev
        decision = gate(parent_for_gate, child_for_gate, min_recall=min_recall, objective=objective)
        store.append_history(
            {
                "parent": current.id,
                "candidate": candidate.id,
                "accept": decision.accept,
                "reason": decision.reason,
                "parent_dev": dev_m.to_dict(),
                "child_dev": c_dev.to_dict(),
            }
        )
        rounds += 1
        say(_fmt("candidate " + candidate.id, candidate, c_dev, c_hold) + "  " + decision.reason)
        if decision.accept:
            current = candidate
            dev_m, dev_e, hold_m = c_dev, c_err, c_hold
            store.set_best(current.id)
            current.dump(store.next_spec_path())
        else:
            say(f"拒绝 {candidate.id}，保留 {current.id}。NEXT_SPEC.yaml 未覆盖，可继续改。")

    return LoopResult(current.id, rounds, "max_rounds")


def _fmt(tag: str, spec: PromptSpec, dev: Metrics, hold: Metrics | None) -> str:
    h = ""
    if hold is not None:
        h = f"  hold rec={hold.recall:.3f} prec={hold.precision:.3f} cut={hold.workload_cut:.3f}"
    return (
        f"[{tag} {spec.id}] dev rec={dev.recall:.3f} prec={dev.precision:.3f} "
        f"cut={dev.workload_cut:.3f} fn={dev.fn} fp={dev.fp}{h}"
    )
