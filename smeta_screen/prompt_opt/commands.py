from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from smeta_screen.config import load_config
from smeta_screen.criteria import load_criteria
from smeta_screen.dotenv import load_dotenv
from smeta_screen.llm import LLMClient, resolve_api_key
from smeta_screen.prompt_opt.catalogue import dump_catalogue
from smeta_screen.prompt_opt.labeled import load_labeled, split_hold
from smeta_screen.prompt_opt.loop import run_loop
from smeta_screen.prompt_opt.propose import LLMOptimizer, ManualOptimizer, PLACEHOLDER_MARK
from smeta_screen.prompt_opt.spec import spec_from_policy
from smeta_screen.prompt_opt.store import RunStore

PKG = Path(__file__).resolve().parent.parent
TEMPLATES = PKG / "templates"


def cmd_opt_init(args: argparse.Namespace) -> int:
    dest = Path(args.out).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    mapping = {
        "opt.yaml": "opt.yaml",
        "optimizer_prompt.txt": "optimizer_prompt.txt",
        "opt_labeled.jsonl": "labeled.jsonl",
        "criteria.txt": "criteria.txt",
    }
    for src_name, dst_name in mapping.items():
        src = TEMPLATES / src_name
        target = dest / dst_name
        if target.exists() and not args.force:
            print(f"已存在，跳过: {target}")
            continue
        shutil.copy(src, target)
        print(f"已写入 {target}")
    spec = spec_from_policy(args.policy, "v000")
    store = RunStore(dest)
    spec.dump(store.dir_for("v000") / "spec.yaml")
    spec.dump(store.next_spec_path())
    store.set_best("v000")
    print(f"基线 spec: {store.dir_for('v000') / 'spec.yaml'}  （{args.policy}）")
    print("\n下一步：")
    print(f"  1. 把带 gold 的题录放进 {dest / 'labeled.jsonl'}（或改 opt.yaml）")
    print(f"  2. 编辑 {dest / 'criteria.txt'}")
    print("  3. smeta-screen opt run --config opt.yaml")
    print("  4. 看 versions/v000/errors_dev.jsonl，改 NEXT_SPEC.yaml，再跑一次")
    print("  优化器 prompt 先不用写。要用 LLM 改 prompt 时再填 optimizer_prompt.txt。")
    return 0


def cmd_opt_run(args: argparse.Namespace) -> int:
    load_dotenv(args.env)
    cfg_path = Path(args.config).resolve()
    cfg = load_config(cfg_path)
    cfg_dir = cfg_path.parent
    run_dir = Path(args.run_dir or cfg.get("run_dir") or cfg_dir).resolve()
    store = RunStore(run_dir)

    def rel(key: str, default: str | None = None) -> Path | None:
        val = cfg.get(key) or default
        if not val:
            return None
        p = Path(str(val))
        return p if p.is_absolute() else (cfg_dir / p)

    criteria_path = rel("criteria", "criteria.txt")
    labeled_path = Path(args.labeled) if args.labeled else rel("labeled", "labeled.jsonl")
    hold_path = Path(args.hold) if args.hold else rel("hold")
    if criteria_path is None or not criteria_path.exists():
        raise FileNotFoundError("找不到 criteria")
    if labeled_path is None or not labeled_path.exists():
        raise FileNotFoundError("找不到 labeled 题录（每条需要 gold）")

    criteria = load_criteria(criteria_path)
    labeled = load_labeled(labeled_path)
    if hold_path and hold_path.exists():
        hold = load_labeled(hold_path)
        dev = labeled
    else:
        ratio = float(args.hold_ratio if args.hold_ratio is not None else cfg.get("hold_ratio") or 0.0)
        dev, hold = split_hold(labeled, ratio, int(cfg.get("split_seed") or 42))

    policy = str(args.policy or cfg.get("policy") or "recall_first")
    best = store.best_id()
    if best and (store.dir_for(best) / "spec.yaml").exists():
        spec = store.load_spec(best)
    elif (store.dir_for("v000") / "spec.yaml").exists():
        spec = store.load_spec("v000")
    else:
        spec = spec_from_policy(policy, "v000")

    mock = bool(args.mock)
    screener_cfg = cfg.get("screener") or (cfg.get("models") or [{}])[0]
    client = LLMClient(
        api_key="mock" if mock else resolve_api_key(
            screener_cfg.get("api_key"), screener_cfg.get("api_key_env")
        ),
        base_url=screener_cfg.get("base_url"),
        model=str(screener_cfg.get("name") or "mock"),
        mock=mock,
    )
    model_name = "mock" if mock else str(screener_cfg.get("name") or "model")

    opt_kind = str(args.optimizer or cfg.get("optimizer") or "manual")
    prompt_path = rel("optimizer_prompt", "optimizer_prompt.txt") or (run_dir / "optimizer_prompt.txt")
    allow_ph = bool(args.allow_placeholder or cfg.get("allow_placeholder"))
    if opt_kind == "llm":
        raw_p = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
        if PLACEHOLDER_MARK in raw_p and not allow_ph:
            raise RuntimeError(
                f"优化器 prompt 仍是占位（{prompt_path}）。先写这段 prompt，或加 --allow-placeholder。"
            )
    if opt_kind == "llm":
        opt_cfg = cfg.get("optimizer_model") or screener_cfg
        opt_client = LLMClient(
            api_key="mock" if mock else resolve_api_key(opt_cfg.get("api_key"), opt_cfg.get("api_key_env")),
            base_url=opt_cfg.get("base_url"),
            model=str(opt_cfg.get("name") or "mock"),
            mock=mock,
        )
        optimizer = LLMOptimizer(opt_client, prompt_path, allow_placeholder=allow_ph)
    else:
        optimizer = ManualOptimizer(store.next_spec_path())

    workers = int(args.workers or cfg.get("workers") or 8)
    max_rounds = int(args.max_rounds or cfg.get("max_rounds") or 5)
    min_recall = cfg.get("min_recall")
    if args.min_recall is not None:
        min_recall = args.min_recall
    objective = str(cfg.get("objective") or "recall")
    mode = str(cfg.get("mode") or "recall_first")

    print(f"run_dir={run_dir}  spec={spec.id}  labeled={len(labeled)}  dev={len(dev)}  hold={len(hold)}")
    print(f"optimizer={opt_kind}  mock={mock}")
    result = run_loop(
        store=store,
        spec=spec,
        criteria=criteria,
        dev=dev,
        hold=hold,
        optimizer=optimizer,
        client=client,
        workers=workers,
        model_name=model_name,
        max_rounds=1 if opt_kind == "manual" else max_rounds,
        min_recall=float(min_recall) if min_recall is not None else None,
        objective=objective,
        mode=mode,
    )
    print(f"best={result.best_id}  rounds={result.rounds}  stopped={result.stopped}")
    print(f"筛查时用这一版: --prompt-spec {store.dir_for(result.best_id) / 'spec.yaml'}")
    return 0


def cmd_opt_status(args: argparse.Namespace) -> int:
    store = RunStore(Path(args.run_dir).resolve())
    best = store.best_id()
    print(f"BEST {best or '（无）'}")
    hist = store.root / "history.jsonl"
    if hist.exists():
        lines = [json.loads(x) for x in hist.read_text(encoding="utf-8").splitlines() if x.strip()]
        for row in lines[-12:]:
            mark = "ACCEPT" if row.get("accept") else "reject"
            print(f"  {row.get('parent')} → {row.get('candidate')}  {mark}  {row.get('reason')}")
    versions = sorted(p.name for p in store.versions.iterdir() if p.is_dir())
    print("versions:", ", ".join(versions) or "（无）")
    nxt = store.next_spec_path()
    if nxt.exists():
        print(f"NEXT_SPEC {nxt}")
    return 0


def cmd_opt_catalogue(args: argparse.Namespace) -> int:
    dest = Path(args.out).resolve() if args.out else None
    dump_catalogue(dest)
    if dest is not None:
        print(f"wrote {dest / 'PROMPT_LIST.txt'}")
        print(f"wrote {dest / 'prompts'}")
    return 0
