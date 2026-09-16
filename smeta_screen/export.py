from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def export_outputs(df: pd.DataFrame, out_dir: Path, list_flags: dict[str, pd.Series]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    drop = [c for c in ("_uid",) if c in df.columns]
    if drop:
        df = df.drop(columns=drop)
    xlsx = out_dir / "screening_lists.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="all", index=False)
        for name, mask in list_flags.items():
            sub = df.loc[mask].copy()
            sheet = name[:31]
            sub.to_excel(w, sheet_name=sheet, index=False)
            sub.to_excel(out_dir / f"{name}.xlsx", index=False)
    (out_dir / "all_rows.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in df.to_dict(orient="records")),
        encoding="utf-8",
    )
    summary = {
        "n_records": int(len(df)),
        "lists": {k: int(v.sum()) for k, v in list_flags.items()},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return xlsx
