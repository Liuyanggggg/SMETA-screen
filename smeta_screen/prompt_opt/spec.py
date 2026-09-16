from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PRIORITIES = ("recall_first", "balanced", "strict")

OUTPUT_CONTRACT = """Follow the CRITERIA exactly.
Use ONLY the title and abstract. Do not invent facts.
Return STRICT JSON only, no markdown:
{"decision":"include|exclude|uncertain","reason":"<one short sentence>"}""".strip()

_POLICY_ROLE = "You are an expert biomedical evidence screener doing FIRST-PASS title/abstract screening."

_POLICY_RULES: dict[str, list[str]] = {
    "recall_first": [
        "Priority: MAXIMIZE RECALL. Missing an eligible study is worse than extra false positives.",
        'If information is missing or ambiguous, you MUST choose "uncertain" (not exclude).',
        "Only exclude when you are certain the record fails a hard exclusion rule.",
    ],
    "balanced": [
        "Balance recall and precision. Follow the CRITERIA.",
        "Choose \"uncertain\" when a key eligibility item is missing or ambiguous.",
    ],
    "strict": [
        "Priority: PRECISION. Only include when the title/abstract clearly meets inclusion rules.",
        "If a key item is missing, choose \"exclude\" rather than stretching to include.",
        "Use \"uncertain\" only when the record is close but not decidable.",
    ],
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class PromptSpec:
    """Versioned screening prompt. Only role / rules / notes are meant to iterate."""

    id: str
    priority: str = "recall_first"
    role: str = _POLICY_ROLE
    rules: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    output: str = OUTPUT_CONTRACT
    parent: str | None = None
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if self.priority not in PRIORITIES:
            raise ValueError(f"未知 priority {self.priority}，可选 {PRIORITIES}")
        self.role = (self.role or "").strip() or _POLICY_ROLE
        self.rules = [str(x).strip() for x in self.rules if str(x).strip()]
        self.notes = [str(x).strip() for x in self.notes if str(x).strip()]
        self.output = (self.output or "").strip() or OUTPUT_CONTRACT

    def fingerprint(self) -> str:
        payload = {
            "priority": self.priority,
            "role": self.role,
            "rules": self.rules,
            "notes": self.notes,
            "output": self.output,
        }
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def child(self, new_id: str, **changes: Any) -> "PromptSpec":
        data = {
            "id": new_id,
            "priority": self.priority,
            "role": self.role,
            "rules": list(self.rules),
            "notes": list(self.notes),
            "output": OUTPUT_CONTRACT,
            "parent": self.id,
            "created_at": _now(),
        }
        data.update(changes)
        data["output"] = OUTPUT_CONTRACT
        data["parent"] = self.id
        data["id"] = new_id
        return PromptSpec(**data)

    def render(self, criteria: str, title: str, abstract: str) -> str:
        lines = [self.role, ""]
        for i, rule in enumerate(self.rules, 1):
            lines.append(f"{i}. {rule}")
        if self.notes:
            lines.append("")
            lines.append("Additional notes:")
            for n in self.notes:
                lines.append(f"- {n}")
        lines.extend(
            [
                "",
                self.output or OUTPUT_CONTRACT,
                "",
                "=== CRITERIA ===",
                (criteria or "").strip(),
                "",
                "=== INPUT ===",
                f"Title: {(title or '').strip()}",
                "",
                "Abstract:",
                (abstract or "").strip() or "[No abstract]",
            ]
        )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent": self.parent,
            "created_at": self.created_at,
            "priority": self.priority,
            "fingerprint": self.fingerprint(),
            "role": self.role,
            "rules": list(self.rules),
            "notes": list(self.notes),
            "output": self.output,
        }

    def dump(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "PromptSpec":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"spec 不是字典: {path}")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptSpec":
        return cls(
            id=str(data.get("id") or "anon"),
            priority=str(data.get("priority") or "recall_first"),
            role=str(data.get("role") or _POLICY_ROLE),
            rules=list(data.get("rules") or []),
            notes=list(data.get("notes") or []),
            output=str(data.get("output") or OUTPUT_CONTRACT),
            parent=data.get("parent"),
            created_at=str(data.get("created_at") or _now()),
        )


def spec_from_policy(policy: str, spec_id: str = "v000") -> PromptSpec:
    if policy not in _POLICY_RULES:
        raise ValueError(f"未知策略 {policy}，可选 {list(_POLICY_RULES)}")
    return PromptSpec(
        id=spec_id,
        priority=policy,
        role=_POLICY_ROLE,
        rules=list(_POLICY_RULES[policy]),
        notes=[],
        output=OUTPUT_CONTRACT,
        parent=None,
    )
