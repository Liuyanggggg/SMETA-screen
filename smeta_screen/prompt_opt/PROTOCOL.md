# SMETA prompt protocol

Locked before any new TEST is scored. This is the methods object. A single-review point estimate is not.

## Why this shape

| Choice | Source | What we do not copy |
| --- | --- | --- |
| Discrete catalogue on a development slice, then freeze | Sanghera et al., *JAMIA* 2025 ocaf050 (S1 ladder; n=800 then n=119 695) | Balanced accuracy as the selection metric |
| Develop, then evaluate on held-out records | Homiar et al., *BMJ Ment Health* 2025 | Their depression-specific TRUE/FALSE items |
| Do not select on F1 | Adam et al., *Res Synth Methods* 2026 (515 prompts: selection criteria ≈ +8.1 F1 / −4.7 recall) | F1, accuracy, or balanced accuracy for winner pick |
| Structured ScreenPrompt vs poor zeroshot | Cao et al., *Ann Intern Med* 2025 (weighted sensitivity 97.7% vs 49.0%) | Their YYY/XXX string; we emit JSON |
| Textual gradient + beam, accept off the train slice | Pryzant et al., *EMNLP* 2023 ProTeGi | Unconstrained rewrite of PICOS into the rules |
| Sensitivity = studies **ultimately included**, not title/abstract votes | Homiar 2025 | Treating original-meta excludes as title/abstract gold |
| Lock the test set before prompt work | Reporting practice for LLM-SR methods | Peeking at TEST while editing |

Han et al. (arXiv:2510.16091): zero-shot maximises recall; self-reflection is unstable. Self-reflection is **not** in the catalogue.

APE/OPRO/GEPA/DSPy/TextGrad: map of automatic prompt optimisation. We use the screening analogue of APE (pick from a frozen discrete set) plus a constrained ProTeGi child, not a free meta-prompt that maximises F1.

## Analysis (pre-specified)

Positive class: gold include (final includes of the source meta-analysis).

Predicted positive: `include` or `uncertain` (first-pass list). Binary Sanghera/Cao-zeroshot prompts have no `uncertain`.

Primary: recall, Wilson 95% CI.

Secondary: n_flagged, workload_cut = 1 − n_flagged/n, precision.

Never used for selection: F1.

### Splits (written to `locked_split.json` before the first catalogue call)

Seed 42. TEST is locked first.

**Primary hold-out (paper):** a Sanghera-style **800-record 1:1 balanced set** (400 gold include + 400 exclude), pooled across the 45 metas. A single review cannot fill 400 includes.

Pool = all 45 metas, including PMID 33309569. The human 300-set is a separate kappa experiment and may overlap.

VAL and DEV are also 1:1, drawn from gold includes that remain after TEST is locked (VAL 40/40, DEV the rest 1:1).

The PMID 40640844 run (`test_pos=5`, 400 excludes) is a frozen demonstration and is not re-split.

### Catalogue selection (DEV only)

Let R0 = recall of `smeta_recall_first`.

Eligible = selectable prompts with recall_DEV ≥ R0.

Winner = eligible with highest (recall, workload_cut, precision).

`rsm_f1_methods` is contrast (`selectable=False`).

### Iteration (optional; DEV errors; accept on VAL)

Only if the winner is `iterable` (ternary SMETA-shaped templates). Sanghera binary rungs are not rewritten into ternary rules.

Beam of 3 ProTeGi edits. Drop any rule whose content tokens appear in CRITERIA except a generic screening vocabulary (`leakage.py`).

Accept a child iff recall_VAL ≥ catalogue-winner recall_VAL, then higher (workload_cut, precision). Otherwise keep the catalogue winner.

### TEST

Scored once after freeze. Production baseline is scored on the same TEST. No further edits.

A frozen run directory is not re-opened. New reviews get a new `--out`.

## Catalogue

13 templates in `catalogue.py`. Dump: `smeta-screen opt catalogue --out <dir>`.

PICOS lives only in `{criteria}`. `rsm_persona` and `sanghera_title` do not receive criteria (Adam / S1 control).

Parser adaptation: JSON instead of Include/Exclude or YYY/XXX. Decision space follows the source paper.

## What this can and cannot carry

This protocol is a methods subsection of the SMETA paper (or a methods paper after multi-review replication).

One review with 15 gold includes cannot carry a standalone top-journal methods claim: TEST recall CI is wide by construction. The 45-meta full-corpus analysis remains the primary SMETA result and uses the production prompt until this module is replicated across reviews.
