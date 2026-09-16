"""Constrained ProTeGi-style edit (Pryzant et al. EMNLP 2023).

1. Textual gradient from DEV errors.
2. Edit rules in the opposite direction.
3. Drop any rule that copies review-specific tokens from CRITERIA.
4. Accept only on VAL (never on TEST).
"""
from __future__ import annotations

import json
import re

import yaml

from smeta_screen.llm import LLMClient
from smeta_screen.prompt_opt.leakage import filter_rules, forbidden_from_criteria
from smeta_screen.prompt_opt.spec import OUTPUT_CONTRACT, PromptSpec

GRADIENT_PROMPT = """You write a short CRITIQUE of a first-pass screening prompt.
Use only the error list. Do not mention disease names, drug names, or trial acronyms.
List at most 5 generic failure modes (e.g. secondary analyses, wrong study design, reviews).

Current rules:
{rules}

False negatives (must remain include/uncertain):
{fn}

False positives (may be excluded only if a hard generic rule is met):
{fp}

Return a bullet list of generic failure modes, nothing else.
"""

EDIT_PROMPT = """Revise screening RULES to reduce false positives without creating false negatives.
Keep recall-first. Do not name a specific cancer, drug, biomarker, country, or trial.
Do not copy wording from any single review's PICOS. Rules must transfer to other reviews.

Current rules:
{rules}

Critique:
{grad}

Return YAML only:
rules:
  - ...
notes:
  - ...
"""


def propose_children(
    parent: PromptSpec,
    errors: list[dict],
    criteria: str,
    client: LLMClient,
    n_beam: int = 3,
) -> list[PromptSpec]:
    forbidden = forbidden_from_criteria(criteria)
    fn = [e for e in errors if e.get("kind") == "fn"][:8]
    fp = [e for e in errors if e.get("kind") == "fp"][:10]
    # strip titles to reduce leakage into the gradient
    slim = lambda xs: [{"kind": x["kind"], "decision": x.get("decision"), "reason": x.get("reason")} for x in xs]
    grad = client.complete_raw(
        GRADIENT_PROMPT.format(
            rules=yaml.safe_dump(parent.rules, allow_unicode=True),
            fn=json.dumps(slim(fn), ensure_ascii=False, indent=2),
            fp=json.dumps(slim(fp), ensure_ascii=False, indent=2),
        ),
        temperature=0.3,
    )
    children = []
    for i in range(n_beam):
        raw = client.complete_raw(
            EDIT_PROMPT.format(
                rules=yaml.safe_dump(parent.rules, allow_unicode=True),
                grad=grad,
            ),
            temperature=0.4 + 0.1 * i,
        )
        data = _parse_yaml(raw)
        rules = list(data.get("rules") or parent.rules)
        notes = list(data.get("notes") or [])
        kept, dropped = filter_rules(rules, forbidden)
        if len(kept) < 2:
            kept = list(parent.rules)
        if dropped:
            notes.append("dropped leaky rules: " + "; ".join(dropped[:3]))
        notes.append("ProTeGi constrained edit; leakage filter applied.")
        child = parent.child(
            f"{parent.id}_ptg{i}",
            role=parent.role,
            rules=kept,
            notes=notes,
            priority="recall_first",
        )
        child.output = OUTPUT_CONTRACT
        children.append(child)
    return children


def _parse_yaml(raw: str) -> dict:
    text = (raw or "").strip()
    m = re.search(r"```(?:yaml|yml)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    try:
        data = yaml.safe_load(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}
