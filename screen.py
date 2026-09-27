#!/usr/bin/env python3
"""Screen one JSONL of records with the frozen recall-first prompt.

Each line: {"id", "title", "abstract"}.
Writes JSONL: id, decision, reason.
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROMPT = (ROOT / "smeta_recall_first.txt").read_text()
VALID = ("include", "exclude", "uncertain")


def decide(text: str) -> tuple[str, str]:
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw).strip()
    try:
        data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        dec = str(data.get("decision", "")).lower()
        if dec in VALID:
            return dec, str(data.get("reason", ""))
    except json.JSONDecodeError:
        pass
    low = raw.lower()
    for k in VALID:
        if re.search(rf"\b{k}\b", low):
            return k, raw[:300]
    return "uncertain", raw[:200]


def call(criteria: str, title: str, abstract: str) -> tuple[str, str]:
    body = {
        "model": os.environ.get("SMETA_MODEL", "deepseek-chat"),
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": PROMPT.format(
                    criteria=criteria, title=title, abstract=abstract or ""
                ),
            }
        ],
    }
    req = urllib.request.Request(
        os.environ.get("SMETA_BASE", "https://api.deepseek.com/v1").rstrip("/")
        + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": "Bearer " + os.environ["SMETA_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        msg = json.load(resp)["choices"][0]["message"]["content"]
    return decide(msg)


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit("usage: screen.py criteria.txt records.jsonl out.jsonl")
    criteria = Path(sys.argv[1]).read_text()
    out = Path(sys.argv[3]).open("w")
    with Path(sys.argv[2]).open() as fh, out:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            dec, reason = call(criteria, row.get("title", ""), row.get("abstract", ""))
            out.write(json.dumps({"id": row.get("id"), "decision": dec, "reason": reason}) + "\n")


def _selfcheck() -> None:
    assert decide('{"decision":"include","reason":"rct"}')[0] == "include"
    assert decide("probably exclude this")[0] == "exclude"
    assert decide("???")[0] == "uncertain"


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        _selfcheck()
    else:
        main()
