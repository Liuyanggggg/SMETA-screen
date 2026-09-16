"""Block review-specific PICOS from entering optimized rules."""
from __future__ import annotations

import re

_STOP = {
    "about", "above", "after", "again", "against", "almost", "already", "also",
    "although", "always", "among", "another", "because", "before", "being",
    "below", "between", "both", "check", "clearly", "compare", "compares",
    "comparing", "comparison", "conducted", "context", "could", "does", "doing",
    "during", "each", "either", "every", "focus", "from", "have", "here",
    "into", "just", "later", "like", "made", "make", "mentions", "most",
    "must", "only", "other", "over", "same", "should", "since", "some",
    "such", "than", "that", "their", "them", "then", "there", "these", "this",
    "those", "through", "under", "until", "using", "very", "when", "where",
    "which", "while", "will", "with", "without", "would", "your",
}

_GENERIC = {
    "study", "studies", "trial", "trials", "randomized", "randomised", "rct",
    "review", "meta", "analysis", "abstract", "title", "inclusion", "exclusion",
    "include", "exclude", "uncertain", "criteria", "patient", "patients",
    "population", "intervention", "comparator", "outcome", "design", "phase",
    "control", "placebo", "versus", "compared", "treatment", "therapy",
    "primary", "secondary", "human", "animal", "editorial", "letter",
    "conference", "protocol", "cohort", "retrospective", "prospective",
    "systematic", "screening", "eligible", "ineligible", "missing",
    "ambiguous", "first-pass", "title", "abstract", "json", "decision",
    "reason", "advanced", "early", "stage", "cancer", "chemotherapy",
    "immunotherapy", "inhibitor", "combination", "alone", "plus",
}

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9\\-]{3,}")


def content_tokens(text: str) -> set[str]:
    blob = (text or "").replace("/", " ").replace("\\", " ")
    return {m.group(0).lower() for m in _TOKEN.finditer(blob)}


def forbidden_from_criteria(criteria: str) -> set[str]:
    toks = content_tokens(criteria)
    return {t for t in toks if t not in _GENERIC and t not in _STOP and not t.isdigit()}


def leakage_hits(rule: str, forbidden: set[str]) -> list[str]:
    toks = content_tokens(rule)
    return sorted(toks & forbidden)


def filter_rules(rules: list[str], forbidden: set[str]) -> tuple[list[str], list[str]]:
    kept, dropped = [], []
    for r in rules:
        hits = leakage_hits(r, forbidden)
        if hits:
            dropped.append(f"{r}  [leak:{','.join(hits[:8])}]")
        else:
            kept.append(r)
    return kept, dropped
