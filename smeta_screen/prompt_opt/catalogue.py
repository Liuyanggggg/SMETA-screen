"""Literature-derived screening prompt catalogue (frozen templates).

PICOS for a given review is injected only via {criteria} at render time.
Templates themselves must not name a disease, drug, or trial.

JSON instead of bare Include/Exclude or YYY/XXX is a pre-specified
parser adaptation; decision space (binary vs ternary) follows the source.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


PLACEHOLDERS = ("{sr_title}", "{criteria}", "{title}", "{abstract}")

_BINARY_JSON = (
    'Respond with JSON only, no markdown: '
    '{"decision":"include|exclude","reason":"<one short sentence>"}.'
)
_TERNARY_JSON = (
    "Return STRICT JSON only, no markdown:\n"
    '{"decision":"include|exclude|uncertain","reason":"<one short sentence>"}'
)
_INPUT = "=== INPUT ===\nTitle: {title}\n\nAbstract:\n{abstract}"


@dataclass(frozen=True)
class CatalogueEntry:
    id: str
    source: str
    citation: str
    family: str
    decision_space: str  # binary | ternary
    selectable: bool  # False = contrast only, never a catalogue winner
    iterable: bool  # ProTeGi rewrite allowed (ternary SMETA-shaped only)
    uses_criteria: bool
    template: str
    note: str = ""

    def render(self, *, sr_title: str, criteria: str, title: str, abstract: str) -> str:
        text = self.template
        text = text.replace("{sr_title}", sr_title or "")
        text = text.replace("{criteria}", (criteria or "").strip())
        text = text.replace("{title}", (title or "").strip())
        text = text.replace("{abstract}", (abstract or "").strip() or "[No abstract]")
        return text

    def to_meta(self) -> dict:
        d = asdict(self)
        d.pop("template", None)
        return d


def _sanghera(bias: str, extra: str, *, extreme: bool = False) -> str:
    """S1 wording, JSON in place of 'Respond only with Include or Exclude'."""
    title_bit = (
        f"You are screening articles for inclusion in the systematic review "
        f"titled '{{sr_title}}'{', with heavy preference towards inclusion' if extreme else ''}."
    )
    return f"""{title_bit} {extra} {_BINARY_JSON}

Systematic Review Title: {{sr_title}}
Inclusion and exclusion criteria:
{{criteria}}
Article Title: {{title}}
Article Abstract: {{abstract}}"""


def catalogue() -> list[CatalogueEntry]:
    return [
        CatalogueEntry(
            id="smeta_recall_first",
            source="SMETA production",
            citation="SMETA recall-first policy (uncertain retained as flagged).",
            family="smeta",
            decision_space="ternary",
            selectable=True,
            iterable=True,
            uses_criteria=True,
            note="Production baseline. Uncertain counts as a first-pass positive.",
            template="""You are an expert biomedical evidence screener doing FIRST-PASS title/abstract screening.
Priority: MAXIMIZE RECALL. Missing an eligible study is worse than extra false positives.
If information is missing or ambiguous, you MUST choose "uncertain" (not exclude).
Only exclude when you are certain the record fails a hard exclusion rule.
Follow the CRITERIA exactly. Use ONLY the title and abstract. Do not invent facts.

"""
            + _TERNARY_JSON
            + """

=== CRITERIA ===
{criteria}

"""
            + _INPUT,
        ),
        CatalogueEntry(
            id="sanghera_none",
            source="Sanghera S1 none",
            citation="Sanghera et al. JAMIA 2025;32:893-904, Supplementary S1, Bias Level: None.",
            family="sanghera",
            decision_space="binary",
            selectable=True,
            iterable=False,
            uses_criteria=True,
            note="S1 default: no inclusion bias. Binary; do not rewrite into ternary rules.",
            template=_sanghera(
                "none",
                "Using the inclusion criteria for the systematic review provided below, "
                "decide if the screened articles should be included based on their title and abstract.",
            ),
        ),
        CatalogueEntry(
            id="sanghera_mild",
            source="Sanghera S1 mild",
            citation="Sanghera et al. JAMIA 2025;32:893-904, Supplementary S1, Bias Level: Mild.",
            family="sanghera",
            decision_space="binary",
            selectable=True,
            iterable=False,
            uses_criteria=True,
            note="S1 mild inclusion bias. Winner of the PMID 40640844 locked-split demonstration.",
            template=_sanghera(
                "mild",
                "Using the inclusion criteria for the systematic review provided below, "
                "decide if the screened articles should be included based on their title and abstract. "
                "Where relevance to the systematic review title is apparent, and the article meets most "
                "inclusion criteria, favour inclusion unless clear exclusion criteria are met.",
            ),
        ),
        CatalogueEntry(
            id="sanghera_moderate",
            source="Sanghera S1 moderate",
            citation="Sanghera et al. JAMIA 2025;32:893-904, Supplementary S1, Bias Level: Moderate.",
            family="sanghera",
            decision_space="binary",
            selectable=True,
            iterable=False,
            uses_criteria=True,
            note="S1 moderate inclusion bias. Missing from the v1 11-item demo; in the frozen list.",
            template=_sanghera(
                "moderate",
                "Using the inclusion criteria for the systematic review provided below, "
                "decide if the screened articles should be included based on their title and abstract. "
                "If the article seems likely to be relevant to the systematic review's theme, and it does "
                "not explicitly meet any exclusion criteria, lean towards inclusion.",
            ),
        ),
        CatalogueEntry(
            id="sanghera_heavy",
            source="Sanghera S1 heavy",
            citation="Sanghera et al. JAMIA 2025;32:893-904, Supplementary S1, Bias Level: Heavy.",
            family="sanghera",
            decision_space="binary",
            selectable=True,
            iterable=False,
            uses_criteria=True,
            note="S1 heavy inclusion bias.",
            template=_sanghera(
                "heavy",
                "Using the inclusion criteria for the systematic review provided below, "
                "decide if the screened articles should be included based on their title and abstract. "
                "If there is any uncertainty if an article fulfils the inclusion criteria, but the abstract "
                "appears relevant to the title of the systematic review, lean towards including the article, "
                "as long as no exclusion criteria are met.",
            ),
        ),
        CatalogueEntry(
            id="sanghera_extreme",
            source="Sanghera S1 extreme",
            citation="Sanghera et al. JAMIA 2025;32:893-904, Supplementary S1, Bias Level: Extreme.",
            family="sanghera",
            decision_space="binary",
            selectable=True,
            iterable=False,
            uses_criteria=True,
            note="S1 extreme inclusion bias. GPT-4o used this rung in Sanghera.",
            template=_sanghera(
                "extreme",
                "Your primary goal is to include articles unless there are overwhelming reasons to exclude. "
                "Apply the inclusion criteria very loosely and the exclusion criteria extremely strictly. "
                "Assume relevance unless proven otherwise beyond any reasonable doubt. "
                "Prioritise maximum sensitivity. Exclude only if the article is unequivocally irrelevant "
                "or explicitly violates multiple exclusion criteria.",
                extreme=True,
            ),
        ),
        CatalogueEntry(
            id="sanghera_title",
            source="Sanghera S1 title",
            citation="Sanghera et al. JAMIA 2025;32:893-904, Supplementary S1, Bias Level: Title (control).",
            family="sanghera",
            decision_space="binary",
            selectable=True,
            iterable=False,
            uses_criteria=False,
            note="S1 control: SR title only, no PICOS. Adam: adding selection criteria raises F1 and cuts recall.",
            template=f"""You are screening articles for inclusion in the systematic review titled '{{sr_title}}'. Using the systematic review title, decide if the screened articles should be included based on the relevance of their title and abstract. If there is any uncertainty, lean towards including the article. {_BINARY_JSON}

Systematic Review Title: {{sr_title}}
Article Title: {{title}}
Article Abstract: {{abstract}}""",
        ),
        CatalogueEntry(
            id="cao_zeroshot",
            source="Cao Figure 3 zero-shot",
            citation="Cao et al. Ann Intern Med. 2025;178:389-401, Figure 3 zero-shot prompt.",
            family="cao",
            decision_space="binary",
            selectable=True,
            iterable=False,
            uses_criteria=True,
            note="Figure 3 asked YYY/XXX. Mapped to include/exclude. Weighted sensitivity ~49% in Cao.",
            template="""You are a researcher rigorously screening titles and abstracts of scientific papers for inclusion or exclusion in a review paper. Use the criteria below to inform your decision. If any exclusion criteria are met or not all inclusion criteria are met, exclude the article. If all inclusion criteria are met, include the article.

{criteria}

"""
            + _BINARY_JSON
            + "\n\n"
            + _INPUT,
        ),
        CatalogueEntry(
            id="cao_screenprompt",
            source="Cao Abstract ScreenPrompt",
            citation="Cao et al. Ann Intern Med. 2025;178:389-401, Figure 3 Abstract ScreenPrompt (Framework CoT).",
            family="cao",
            decision_space="ternary",
            selectable=True,
            iterable=True,
            uses_criteria=True,
            note="Cao YYY = inclusion advised OR uncertainty persists → include or uncertain. XXX → exclude. Weighted sensitivity ~97.7% in Cao.",
            template="""The following is an excerpt of 2 sets of criteria. A study is considered included if it meets all the inclusion criteria. If a study meets any of the exclusion criteria, it should be excluded. Here are the 2 sets of criteria:

{criteria}

Title: {title}

Abstract:
{abstract}

Study Objectives: first-pass title/abstract screening for the systematic review described above.

We now assess whether the paper should be included from the SR by evaluating it against each and every predefined inclusion and exclusion criterion. First, we will reflect on how we will decide whether a paper should be included or excluded. Then, we will think step by step for each criteria, giving reasons for why they are met or not met.
Studies that may not fully align with the primary focus of our inclusion criteria but provide data or insights potentially relevant to our review deserve thoughtful consideration. Given the nature of abstracts as concise summaries of comprehensive research, some degree of interpretation is necessary.
Our aim should be to inclusively screen abstracts, ensuring broad coverage of pertinent studies while filtering out those that are clearly irrelevant.
Conclude with STRICT JSON only on the last line:
{"decision":"include|exclude|uncertain","reason":"<one short sentence>"}
Choose include when inclusion is advised. Choose uncertain when uncertainty persists. Choose exclude only when the paper warrants exclusion.""",
        ),
        CatalogueEntry(
            id="homiar_pico_yn",
            source="Homiar yes/no PICO",
            citation="Homiar et al. BMJ Ment Health. 2025;28:e301762. Yes/no questions over PICO; 'Return TRUE if…'.",
            family="homiar",
            decision_space="ternary",
            selectable=True,
            iterable=True,
            uses_criteria=True,
            note="Homiar's questions were review-specific. We keep the transferable form: yes/no over PICO elements in {criteria}, not their depression items.",
            template="""You are doing first-pass title/abstract screening for '{sr_title}'.
Answer each question TRUE or FALSE using ONLY the title and abstract. Then output a final decision.

For every inclusion element in CRITERIA ask: "Does the study include this element?"
For every exclusion element in CRITERIA ask: "Does this abstract meet this exclusion?"

Decision rule:
- If any exclusion question is TRUE, decision=exclude.
- Else if all critical inclusion questions are TRUE, decision=include.
- Else if a key inclusion item is missing or ambiguous, decision=uncertain.
- Else decision=exclude.
Never invent facts. Prefer include or uncertain over exclude when unsure.

CRITERIA:
{criteria}

"""
            + _INPUT
            + "\n\n"
            + _TERNARY_JSON,
        ),
        CatalogueEntry(
            id="rsm_persona",
            source="Adam Table 3 top recall",
            citation="Adam et al. Res Synth Methods. 2026;17:939-956, Table 3 Top R/Sn: 'You are a world-class clinical researcher.'",
            family="rsm",
            decision_space="ternary",
            selectable=True,
            iterable=True,
            uses_criteria=False,
            note="Table 3 top recall is this sentence alone (R/Sn 98.8%, specificity 8.7%). Criteria are NOT injected: Adam found selection criteria +8.1 F1 / −4.7 recall.",
            template="""You are a world-class clinical researcher.

Screen the title and abstract below. When unsure, do not exclude.

"""
            + _TERNARY_JSON
            + "\n\n"
            + _INPUT,
        ),
        CatalogueEntry(
            id="rsm_f1_methods",
            source="Adam Table 3 top F1",
            citation="Adam et al. Res Synth Methods. 2026;17:939-956, Table 3 Top F1 (methods-focused; contrast, not selectable).",
            family="rsm",
            decision_space="ternary",
            selectable=False,
            iterable=False,
            uses_criteria=True,
            note="Contrast only. Shows the F1-maximising prompt. Must not be chosen as the screening policy.",
            template="""You are tasked with evaluating a collection of academic papers to determine its relevance to this meta-analysis. Include titles/abstracts only if they definitively match the inclusion criteria. Your evaluation should focus particularly on the methods of the meta-analysis, enabling it to serve as a meaningful and rigorous synthesis of the meta-analysis.

{criteria}

If a hard exclusion is certain, exclude. If inclusion is definitive, include. If a critical item is missing, uncertain.

"""
            + _TERNARY_JSON
            + "\n\n"
            + _INPUT,
        ),
        CatalogueEntry(
            id="li_assistant",
            source="Li assistant prompt",
            citation="Li, Sun, Tan. Syst Rev. 2024;13:219. Topic + eligibility + abstract; binary yes/no in the paper; we keep uncertain.",
            family="li",
            decision_space="ternary",
            selectable=True,
            iterable=True,
            uses_criteria=True,
            note="Li required yes/no. SMETA first-pass keeps uncertain when the abstract is insufficient.",
            template="""I would like you to help me with conducting a systematic review titled '{sr_title}'. I will provide the title and abstract for one journal article and would like you to screen the paper for inclusion. Here are the eligibility criteria:

{criteria}

Use ONLY the title and abstract. If the abstract is insufficient and no exclusion rule is clearly met, choose uncertain.

"""
            + _INPUT
            + "\n\n"
            + _TERNARY_JSON,
        ),
    ]


def by_id() -> dict[str, CatalogueEntry]:
    return {e.id: e for e in catalogue()}


def selectable_ids() -> list[str]:
    return [e.id for e in catalogue() if e.selectable]


def iterable_ids() -> set[str]:
    return {e.id for e in catalogue() if e.iterable}


def dump_catalogue(dest: Path | None = None) -> list[CatalogueEntry]:
    cat = catalogue()
    if dest is None:
        for e in cat:
            flag = "SEL" if e.selectable else "CTR"
            it = "IT" if e.iterable else "  "
            print(f"{e.id:22} {e.family:10} {e.decision_space:8} {flag} {it}  {e.citation}")
        return cat
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "prompts").mkdir(exist_ok=True)
    meta = []
    lines = [
        "冻结 prompt 目录（评分前写入）。正文不含某篇 PICOS；{criteria} 运行时注入。",
        "SEL=参与胜出；CTR=对照，禁止当选。IT=允许 ProTeGi 改写（仅三分类）。",
        "",
        f"{'id':22} {'family':10} {'space':8} {'sel':3} {'it':2}  citation",
    ]
    for e in cat:
        (dest / "prompts" / f"{e.id}.txt").write_text(e.template, encoding="utf-8")
        meta.append(e.to_meta())
        lines.append(
            f"{e.id:22} {e.family:10} {e.decision_space:8} "
            f"{'Y' if e.selectable else 'n':3} {'Y' if e.iterable else 'n':2}  {e.citation}"
        )
    (dest / "PROMPT_LIST.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (dest / "PROMPT_LIST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return cat
