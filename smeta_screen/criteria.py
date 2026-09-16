from __future__ import annotations

import json
from pathlib import Path


def load_criteria(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到纳排标准文件: {p}")
    text = p.read_text(encoding="utf-8").strip()
    if p.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            if data.get("criteria"):
                return str(data["criteria"]).strip()
            parts = []
            if data.get("background"):
                items = data["background"]
                if isinstance(items, list):
                    parts.append("BACKGROUND:\n" + "\n".join(f"- {x}" for x in items))
                else:
                    parts.append("BACKGROUND:\n" + str(items))
            if data.get("include"):
                items = data["include"]
                if isinstance(items, list):
                    parts.append("INCLUDE:\n" + "\n".join(f"- {x}" for x in items))
                else:
                    parts.append("INCLUDE:\n" + str(items))
            if data.get("exclude"):
                items = data["exclude"]
                if isinstance(items, list):
                    parts.append("EXCLUDE:\n" + "\n".join(f"- {x}" for x in items))
                else:
                    parts.append("EXCLUDE:\n" + str(items))
            joined = "\n\n".join(parts).strip()
            if joined:
                return joined
    if not text:
        raise ValueError(f"纳排标准文件是空的: {p}")
    return text
