from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

from smeta_screen.criteria import load_criteria
from smeta_screen.export import export_outputs
from smeta_screen.lists import conflict_mask
from smeta_screen.llm import LLMClient, resolve_api_key
from smeta_screen.prompt_opt.spec import PromptSpec
from smeta_screen.prompts import render_prompt
from smeta_screen.pubmed import search_pubmed
from smeta_screen.records import load_records


def _screen_one(
    client: LLMClient,
    policy: str,
    criteria: str,
    rec: dict,
    spec: PromptSpec | None = None,
) -> dict:
    if spec is not None:
        prompt = spec.render(criteria, rec["title"], rec["abstract"])
    else:
        prompt = render_prompt(policy, criteria, rec["title"], rec["abstract"])
    decision, reason, raw = client.complete(prompt)
    return {
        "_uid": rec["_uid"],
        "record_id": rec["record_id"],
        "title": rec["title"],
        "abstract": rec["abstract"],
        "policy": policy,
        "decision": decision,
        "reason": reason,
        "raw": raw,
    }


def run_pipeline(cfg: dict[str, Any], mock: bool = False) -> Path:
    out_dir = Path(cfg.get("out_dir") or "output")
    criteria = load_criteria(cfg["criteria"])

    records: list[dict[str, str]]
    if cfg.get("pubmed_query"):
        records = search_pubmed(
            query=str(cfg["pubmed_query"]),
            email=str(cfg.get("email") or ""),
            api_key=__import__("os").environ.get(str(cfg.get("pubmed_api_key_env") or "NCBI_API_KEY")) or None,
            retmax=int(cfg.get("pubmed_retmax") or 10000),
        )
        if cfg.get("records"):
            extra = load_records(cfg["records"])
            seen = {(r["record_id"], r["title"]) for r in records}
            for r in extra:
                key = (r["record_id"], r["title"])
                if key not in seen:
                    records.append(r)
                    seen.add(key)
    else:
        records = load_records(cfg["records"])

    limit = cfg.get("limit")
    if limit:
        records = records[: int(limit)]
    if not records:
        raise RuntimeError("没有题录可筛。请提供 records 文件，或设置 pubmed_query。")

    mode = str(cfg.get("mode") or "slice")
    policies = list(cfg.get("policies") or ["recall_first"])
    if mode == "slice":
        policies = [policies[0]]

    models = cfg.get("models") or []
    if not models:
        raise RuntimeError("config 里至少要有一个 model。")

    workers = int(cfg.get("workers") or 8)
    spec: PromptSpec | None = None
    if cfg.get("prompt_spec"):
        spec = PromptSpec.load(cfg["prompt_spec"])
    for i, rec in enumerate(records):
        rec["_uid"] = f"u{i}"
    wide = pd.DataFrame(records)
    run_cols = []

    for model_cfg in models:
        label = str(model_cfg.get("label") or model_cfg.get("name") or "model")
        client = LLMClient(
            api_key="mock" if mock else resolve_api_key(model_cfg.get("api_key"), model_cfg.get("api_key_env")),
            base_url=model_cfg.get("base_url"),
            model=str(model_cfg.get("name")),
            max_retry=int(model_cfg.get("max_retry") or 5),
            mock=mock,
        )
        for policy in policies:
            jobs = []
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = {
                    ex.submit(_screen_one, client, policy, criteria, rec, spec): rec["record_id"]
                    for rec in records
                }
                for fut in tqdm(as_completed(futs), total=len(futs), desc=f"{label}/{policy}"):
                    jobs.append(fut.result())
            part = pd.DataFrame(jobs)
            col_d = f"{label}__{policy}__decision"
            col_r = f"{label}__{policy}__reason"
            part = part.rename(columns={"decision": col_d, "reason": col_r})
            wide = wide.merge(part[["_uid", col_d, col_r]], on="_uid", how="left")
            run_cols.append((label, policy, col_d))

    list_flags: dict[str, pd.Series] = {}
    primary_label, primary_policy, primary_col = run_cols[0]
    if mode == "slice":
        d = wide[primary_col].fillna("").astype(str).str.lower()
        list_flags["recall_first"] = d.isin(["include", "uncertain"])
        list_flags["strict"] = d.eq("include")
        list_flags["uncertain"] = d.eq("uncertain")
        list_flags["exclude"] = d.eq("exclude")
    else:
        for label, policy, col in run_cols:
            d = wide[col].fillna("").astype(str).str.lower()
            list_flags[f"{label}_{policy}_recall_first"] = d.isin(["include", "uncertain"])
            list_flags[f"{label}_{policy}_strict"] = d.eq("include")

    dec_cols = [c for _, _, c in run_cols]
    if len(dec_cols) >= 2:
        list_flags["conflict"] = conflict_mask(wide, dec_cols)

    xlsx = export_outputs(wide, out_dir, list_flags)
    return xlsx
