from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from smeta_screen.llm import LLMClient
from smeta_screen.prompt_opt.spec import PromptSpec

ScreenFn = Callable[[PromptSpec, dict[str, str]], tuple[str, str]]


def screen_labeled(
    spec: PromptSpec,
    records: list[dict[str, str]],
    *,
    criteria: str,
    client: LLMClient | None = None,
    cache_dir: Path | None = None,
    workers: int = 8,
    screen_fn: ScreenFn | None = None,
    model_name: str = "mock",
) -> list[dict[str, Any]]:
    """Run one spec on labeled records. Cache by fingerprint + record_id + model."""

    def one(rec: dict[str, str]) -> dict[str, Any]:
        cached = _cache_get(cache_dir, spec, rec, model_name)
        if cached:
            return {**rec, **cached}
        if screen_fn is not None:
            decision, reason = screen_fn(spec, rec)
        else:
            if client is None:
                raise RuntimeError("需要 LLMClient 或 screen_fn")
            prompt = spec.render(criteria, rec["title"], rec["abstract"])
            decision, reason, _raw = client.complete(prompt)
        row = {"decision": decision, "reason": reason}
        _cache_put(cache_dir, spec, rec, model_name, row)
        return {**rec, **row}

    out: list[dict[str, Any]] = []
    if workers <= 1 or len(records) <= 1:
        return [one(r) for r in records]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, rec) for rec in records]
        for fut in as_completed(futs):
            out.append(fut.result())
    order = {r["record_id"]: i for i, r in enumerate(records)}
    out.sort(key=lambda r: order.get(str(r.get("record_id")), 10**9))
    return out


def screen_rendered(
    records: list[dict[str, str]],
    render_fn: Callable[[dict[str, str]], str],
    *,
    client: LLMClient,
    cache_dir: Path | None = None,
    workers: int = 8,
    model_name: str = "model",
    cache_prefix: str = "",
) -> list[dict[str, Any]]:
    def one(rec: dict[str, str]) -> dict[str, Any]:
        prompt = render_fn(rec)
        key = hashlib.sha256((cache_prefix + prompt + str(rec.get("record_id"))).encode()).hexdigest()[:20]
        if cache_dir is not None:
            p = cache_dir / f"{model_name}_{key}.json"
            if p.exists():
                try:
                    row = json.loads(p.read_text(encoding="utf-8"))
                    return {**rec, **row}
                except Exception:
                    pass
        decision, reason, _raw = client.complete(prompt)
        row = {"decision": decision, "reason": reason}
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / f"{model_name}_{key}.json").write_text(json.dumps(row), encoding="utf-8")
        return {**rec, **row}

    if workers <= 1 or len(records) <= 1:
        return [one(r) for r in records]
    out = []
    order = {r["record_id"]: i for i, r in enumerate(records)}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, rec) for rec in records]
        for fut in as_completed(futs):
            out.append(fut.result())
    out.sort(key=lambda r: order.get(str(r.get("record_id")), 10**9))
    return out


def _key(spec: PromptSpec, rec: dict[str, str], model_name: str) -> str:
    rid = str(rec.get("record_id") or rec.get("title") or "")
    return f"{spec.fingerprint()}_{model_name}_{_safe(rid)}"


def _safe(s: str) -> str:
    keep = "".join(ch if ch.isalnum() else "_" for ch in s)[:40]
    return keep or "row"


def _cache_get(cache_dir: Path | None, spec: PromptSpec, rec: dict[str, str], model: str) -> dict | None:
    if cache_dir is None:
        return None
    p = cache_dir / f"{_key(spec, rec, model)}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cache_put(
    cache_dir: Path | None,
    spec: PromptSpec,
    rec: dict[str, str],
    model: str,
    row: dict[str, str],
) -> None:
    if cache_dir is None:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_dir / f"{_key(spec, rec, model)}.json"
    p.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
