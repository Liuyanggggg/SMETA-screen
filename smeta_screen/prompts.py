from __future__ import annotations

POLICIES = ("recall_first", "balanced", "strict")

_SHARED_TAIL = """
Follow the CRITERIA exactly.
Use ONLY the title and abstract. Do not invent facts.
Return STRICT JSON only, no markdown:
{"decision":"include|exclude|uncertain","reason":"<one short sentence>"}

=== CRITERIA ===
<criteria>

=== INPUT ===
Title: <title>

Abstract:
<abstract>
""".strip()

TEMPLATES = {
    "recall_first": f"""
You are an expert biomedical evidence screener doing FIRST-PASS title/abstract screening.
Priority: MAXIMIZE RECALL. Missing an eligible study is worse than extra false positives.
If information is missing or ambiguous, you MUST choose "uncertain" (not exclude).
Only exclude when you are certain the record fails a hard exclusion rule.
{_SHARED_TAIL}
""".strip(),
    "balanced": f"""
You are an expert biomedical evidence screener doing FIRST-PASS title/abstract screening.
Balance recall and precision. Follow the CRITERIA.
Choose "uncertain" when a key eligibility item is missing or ambiguous.
{_SHARED_TAIL}
""".strip(),
    "strict": f"""
You are an expert biomedical evidence screener doing FIRST-PASS title/abstract screening.
Priority: PRECISION. Only include when the title/abstract clearly meets inclusion rules.
If a key item is missing, choose "exclude" rather than stretching to include.
Use "uncertain" only when the record is close but not decidable.
{_SHARED_TAIL}
""".strip(),
}


def render_prompt(policy: str, criteria: str, title: str, abstract: str) -> str:
    if policy not in TEMPLATES:
        raise ValueError(f"未知策略 {policy}，可选: {', '.join(POLICIES)}")
    return (
        TEMPLATES[policy]
        .replace("<criteria>", criteria.strip())
        .replace("<title>", (title or "").strip())
        .replace("<abstract>", (abstract or "").strip() or "[No abstract]")
    )
