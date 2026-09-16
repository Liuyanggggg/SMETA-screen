from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from smeta_screen.prompts import POLICIES


def load_config(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到配置文件: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml 必须是字典")
    return data


def default_config() -> dict[str, Any]:
    return {
        "criteria": "criteria.txt",
        "records": "records.json",
        "pubmed_query": None,
        "email": "your.name@example.com",
        "pubmed_api_key_env": "NCBI_API_KEY",
        "out_dir": "output",
        "workers": 8,
        "limit": None,
        "mode": "slice",
        "policies": ["recall_first"],
        "models": [
            {
                "name": "qwen-plus",
                "label": "qwen",
                "api_key_env": "QWEN_API_KEY",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            }
        ],
    }


def validate_policies(policies: list[str]) -> list[str]:
    out = []
    for p in policies:
        if p not in POLICIES:
            raise ValueError(f"未知策略 {p}，可选 {list(POLICIES)}")
        out.append(p)
    if not out:
        raise ValueError("至少需要一个 policy")
    return out
