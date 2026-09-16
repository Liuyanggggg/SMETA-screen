"""Historical prompt family for experiments/run_prompt_select.py.

Paper protocol uses catalogue.py. The first 40640844 error_driven spec
leaked review PICOS; do not reuse it as a unified prompt.
"""

from __future__ import annotations

from smeta_screen.prompt_opt.spec import OUTPUT_CONTRACT, PromptSpec, spec_from_policy

_ROLE = "You are an expert biomedical evidence screener doing FIRST-PASS title/abstract screening."


def family() -> dict[str, PromptSpec]:
    out: dict[str, PromptSpec] = {}
    for name in ("recall_first", "balanced", "strict"):
        out[name] = spec_from_policy(name, name)

    out["sanghera_extreme"] = PromptSpec(
        id="sanghera_extreme",
        priority="recall_first",
        role=_ROLE,
        rules=[
            "Priority: MAXIMIZE RECALL. A missed eligible study is far worse than extra false positives.",
            "If there is ANY possibility the record is eligible, choose include.",
            "If a key eligibility item is missing from the abstract, choose include (not exclude).",
            "Choose uncertain only when the record is almost certainly ineligible but a hard exclusion rule is not fully met.",
            "Exclude only when the title/abstract clearly and unambiguously fails a hard exclusion rule in the CRITERIA.",
        ],
        notes=["Sanghera et al. JAMIA 2025 ocaf050: extreme inclusion bias; selected on a development set."],
        output=OUTPUT_CONTRACT,
    )

    out["cao_structured"] = PromptSpec(
        id="cao_structured",
        priority="recall_first",
        role=_ROLE,
        rules=[
            "Work through the record in this order: (1) population, (2) intervention/comparator, (3) setting/stage, (4) study design.",
            "Compare each item to the CRITERIA. Use only the title and abstract.",
            "If all items are compatible with inclusion, or only non-critical details are missing, choose include.",
            "If a hard exclusion rule in the CRITERIA is clearly met, choose exclude.",
            "If a critical inclusion item is genuinely undecidable and no hard exclusion applies, choose uncertain.",
            "Missing an eligible study is worse than extra false positives.",
        ],
        notes=["Cao et al. Ann Intern Med 2025: generic structured screening template adapted per review criteria."],
        output=OUTPUT_CONTRACT,
    )

    out["rsm_short"] = PromptSpec(
        id="rsm_short",
        priority="recall_first",
        role=_ROLE,
        rules=[
            "Screen this record for the systematic review described in CRITERIA.",
            "When unsure, choose include or uncertain rather than exclude.",
        ],
        notes=["Adam et al. Res Synth Methods 2026: shorter zeroshot prompts increased recall; detailed criteria increased F1 but reduced recall."],
        output=OUTPUT_CONTRACT,
    )
    return out
