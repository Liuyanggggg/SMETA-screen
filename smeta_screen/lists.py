from __future__ import annotations

import pandas as pd


def attach_lists(df: pd.DataFrame, decision_col: str, prefix: str) -> pd.DataFrame:
    d = df[decision_col].fillna("").astype(str).str.lower()
    df[f"{prefix}__recall_first"] = d.isin(["include", "uncertain"])
    df[f"{prefix}__strict"] = d.eq("include")
    df[f"{prefix}__uncertain"] = d.eq("uncertain")
    return df


def conflict_mask(df: pd.DataFrame, decision_cols: list[str]) -> pd.Series:
    if len(decision_cols) < 2:
        return pd.Series(False, index=df.index)
    mat = df[decision_cols].fillna("").astype(str).apply(lambda s: s.str.lower())
    return mat.nunique(axis=1) > 1
