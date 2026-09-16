from __future__ import annotations

import json
import os
import random
import re
import time
from typing import Any

VALID = {"include", "exclude", "uncertain"}


def _parse_decision(text: str) -> tuple[str, str]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    data: dict[str, Any] | None = None
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = None
    if isinstance(data, dict):
        dec = str(data.get("decision") or "").strip().lower()
        reason = str(data.get("reason") or "").strip()
        if dec in VALID:
            return dec, reason
    low = raw.lower()
    for k in VALID:
        if re.search(rf"\b{k}\b", low):
            return k, raw[:300]
    return "uncertain", f"unparsed: {raw[:200]}"


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str | None,
        model: str,
        max_retry: int = 5,
        timeout: float = 60.0,
        mock: bool = False,
    ):
        self.model = model
        self.max_retry = max_retry
        self.mock = mock
        self._client = None
        if not mock:
            from openai import OpenAI

            # Clash 等工具会设置 all_proxy=socks5h://...；未装 socksio 时 httpx 会直接报错。
            # 有 HTTP 代理时改走 http(s)_proxy 即可。
            try:
                import socksio  # noqa: F401
            except Exception:
                for k in ("ALL_PROXY", "all_proxy"):
                    os.environ.pop(k, None)

            kwargs = {"api_key": api_key, "timeout": timeout}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = OpenAI(**kwargs)

    def complete(self, prompt: str) -> tuple[str, str, str]:
        if self.mock:
            title = ""
            m = re.search(r"Title:\s*(.*)", prompt)
            if m:
                title = m.group(1).lower()
            if "random" in title or "rct" in title or "trial" in title:
                return "include", "mock: looks like a trial", '{"decision":"include"}'
            if not title.strip():
                return "uncertain", "mock: empty", '{"decision":"uncertain"}'
            return "exclude", "mock: default exclude", '{"decision":"exclude"}'

        last_err = ""
        for attempt in range(self.max_retry):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    response_format={"type": "json_object"},
                )
                content = resp.choices[0].message.content or ""
                dec, reason = _parse_decision(content)
                return dec, reason, content
            except Exception as e:
                last_err = str(e)
                if "Insufficient Balance" in last_err or "Error code: 402" in last_err:
                    raise RuntimeError(f"DeepSeek 402 Insufficient Balance: {last_err}") from e
                delay = min(1.5 * (2**attempt), 30) + random.uniform(0, 0.3)
                time.sleep(delay)
        return "uncertain", f"error: {last_err}", ""

    def complete_raw(self, prompt: str, temperature: float = 0.2) -> str:
        """Free-text completion for the prompt optimizer (not a screening decision)."""
        if self.mock:
            return "role: mock\nrules:\n- mock rule\n"
        last_err = ""
        for attempt in range(self.max_retry):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                last_err = str(e)
                delay = min(1.5 * (2**attempt), 30) + random.uniform(0, 0.3)
                time.sleep(delay)
        raise RuntimeError(f"complete_raw 失败: {last_err}")


def resolve_api_key(value: str | None, env_name: str | None) -> str:
    if value:
        return value
    if env_name:
        got = os.environ.get(env_name, "")
        if got:
            return got
    raise RuntimeError(
        f"缺少 API key。请在 config 里写 api_key，或设置环境变量 {env_name or 'API_KEY'}。"
    )
