from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol

import yaml

from smeta_screen.llm import LLMClient
from smeta_screen.prompt_opt.metrics import Metrics
from smeta_screen.prompt_opt.spec import OUTPUT_CONTRACT, PromptSpec

PLACEHOLDER_MARK = "PLACEHOLDER_OPTIMIZER_PROMPT"


class Optimizer(Protocol):
    def propose(self, spec: PromptSpec, metrics: Metrics, errors: list[dict]) -> PromptSpec | None:
        """Return a child spec, or None to stop and wait."""


class NoOpOptimizer:
    def propose(self, spec: PromptSpec, metrics: Metrics, errors: list[dict]) -> PromptSpec | None:
        return None


class ManualOptimizer:
    """Human edits NEXT_SPEC.yaml. Unchanged file → None (wait)."""

    def __init__(self, path: Path):
        self.path = path

    def propose(self, spec: PromptSpec, metrics: Metrics, errors: list[dict]) -> PromptSpec | None:
        if not self.path.exists():
            spec.dump(self.path)
            return None
        cand = PromptSpec.load(self.path)
        if cand.fingerprint() == spec.fingerprint():
            return None
        return spec.child("pending", role=cand.role, rules=cand.rules, notes=cand.notes, priority=cand.priority)


class ScriptedOptimizer:
    """Yields a fixed sequence of child specs. Used in tests."""

    def __init__(self, children: list[PromptSpec]):
        self.children = list(children)

    def propose(self, spec: PromptSpec, metrics: Metrics, errors: list[dict]) -> PromptSpec | None:
        if not self.children:
            return None
        nxt = self.children.pop(0)
        return spec.child(
            "pending",
            role=nxt.role,
            rules=nxt.rules,
            notes=nxt.notes,
            priority=nxt.priority,
        )


class LLMOptimizer:
    """Calls a model to rewrite slots. Optimizer prompt is loaded from disk — write it later."""

    def __init__(self, client: LLMClient, prompt_path: Path, allow_placeholder: bool = False):
        self.client = client
        self.prompt_path = prompt_path
        self.allow_placeholder = allow_placeholder

    def propose(self, spec: PromptSpec, metrics: Metrics, errors: list[dict]) -> PromptSpec | None:
        text = self.prompt_path.read_text(encoding="utf-8") if self.prompt_path.exists() else ""
        if PLACEHOLDER_MARK in text and not self.allow_placeholder:
            raise RuntimeError(
                f"优化器 prompt 仍是占位（{self.prompt_path}）。先写这段 prompt，或加 --allow-placeholder 做通路测试。"
            )
        digest = _error_digest(errors)
        filled = (
            text.replace("{{spec_yaml}}", yaml.safe_dump(spec.to_dict(), allow_unicode=True, sort_keys=False))
            .replace("{{metrics_json}}", json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2))
            .replace("{{errors_json}}", json.dumps(digest, ensure_ascii=False, indent=2))
        )
        raw = self.client.complete_raw(filled)
        data = _parse_spec_yaml(raw)
        if not data:
            raise RuntimeError("优化器没有返回可解析的 spec YAML")
        return spec.child(
            "pending",
            role=str(data.get("role") or spec.role),
            rules=list(data.get("rules") or spec.rules),
            notes=list(data.get("notes") or []),
            priority=str(data.get("priority") or spec.priority),
        )


def _error_digest(errors: list[dict], cap: int = 12) -> dict:
    fn = [e for e in errors if e.get("kind") == "fn"][:cap]
    fp = [e for e in errors if e.get("kind") == "fp"][:cap]
    return {"fn": fn, "fp": fp, "n_fn": sum(1 for e in errors if e.get("kind") == "fn"), "n_fp": sum(1 for e in errors if e.get("kind") == "fp")}


def _parse_spec_yaml(raw: str) -> dict | None:
    text = (raw or "").strip()
    m = re.search(r"```(?:yaml|yml)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    try:
        data = yaml.safe_load(text)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if "rules" not in data and "role" not in data:
        return None
    data["output"] = OUTPUT_CONTRACT
    return data
