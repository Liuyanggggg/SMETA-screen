from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from smeta_screen.prompt_opt.spec import PromptSpec


class RunStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.versions = self.root / "versions"
        self.cache = self.root / "cache"
        self.versions.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)

    def next_id(self) -> str:
        n = 0
        while (self.versions / f"v{n:03d}").exists():
            n += 1
        return f"v{n:03d}"

    def dir_for(self, spec_id: str) -> Path:
        return self.versions / spec_id

    def save_version(
        self,
        spec: PromptSpec,
        metrics: dict[str, Any],
        predictions: list[dict[str, Any]],
        errors: list[dict[str, Any]],
        split: str = "dev",
    ) -> Path:
        d = self.dir_for(spec.id)
        d.mkdir(parents=True, exist_ok=True)
        spec.dump(d / "spec.yaml")
        (d / f"metrics_{split}.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _write_jsonl(d / f"predictions_{split}.jsonl", predictions)
        _write_jsonl(d / f"errors_{split}.jsonl", errors)
        return d

    def load_spec(self, spec_id: str) -> PromptSpec:
        return PromptSpec.load(self.dir_for(spec_id) / "spec.yaml")

    def best_id(self) -> str | None:
        p = self.root / "BEST"
        if p.exists():
            return p.read_text(encoding="utf-8").strip() or None
        return None

    def set_best(self, spec_id: str) -> None:
        (self.root / "BEST").write_text(spec_id + "\n", encoding="utf-8")

    def append_history(self, row: dict[str, Any]) -> None:
        p = self.root / "history.jsonl"
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def next_spec_path(self) -> Path:
        return self.root / "NEXT_SPEC.yaml"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
