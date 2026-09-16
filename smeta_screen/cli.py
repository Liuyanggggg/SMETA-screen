from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from smeta_screen import __version__
from smeta_screen.config import default_config, load_config, validate_policies
from smeta_screen.dotenv import load_dotenv
from smeta_screen.pipeline import run_pipeline
from smeta_screen.prompt_opt.commands import (
    cmd_opt_catalogue,
    cmd_opt_init,
    cmd_opt_run,
    cmd_opt_status,
)
from smeta_screen.pubmed import search_pubmed
from smeta_screen.records import load_records


PKG = Path(__file__).resolve().parent


def _cmd_init(args: argparse.Namespace) -> int:
    dest = Path(args.out).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    templates = PKG / "templates"
    mapping = {
        "config.yaml": "config.yaml",
        "criteria.txt": "criteria.txt",
        "records.json": "records.json",
        "env.example": ".env.example",
    }
    for src_name, dst_name in mapping.items():
        src = templates / src_name
        target = dest / dst_name
        if target.exists() and not args.force:
            print(f"已存在，跳过: {target}")
            continue
        shutil.copy(src, target)
        print(f"已写入 {target}")
    print("\n下一步：")
    print(f"  1. 编辑 {dest/'criteria.txt'}  （纳排标准）")
    print(f"  2. 把题录放进 {dest/'records.json'}，或改 config.yaml 里的 pubmed_query")
    print(f"  3. 复制 {dest/'.env.example'} 为 .env，填入 API key")
    print(f"  4. smeta-screen run --config {dest/'config.yaml'}")
    return 0


def _cmd_pubmed(args: argparse.Namespace) -> int:
    load_dotenv(args.env)
    recs = search_pubmed(
        query=args.query,
        email=args.email,
        api_key=__import__("os").environ.get("NCBI_API_KEY"),
        retmax=args.retmax,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PubMed 命中 {len(recs)} 条，已保存 {out}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    load_dotenv(args.env)
    if args.config:
        cfg = load_config(args.config)
        cfg_dir = Path(args.config).resolve().parent
    else:
        cfg = default_config()
        cfg_dir = Path.cwd()
        if args.records:
            cfg["records"] = args.records
        if args.criteria:
            cfg["criteria"] = args.criteria
        if args.out:
            cfg["out_dir"] = args.out

    if args.records:
        cfg["records"] = args.records
    if args.criteria:
        cfg["criteria"] = args.criteria
    if args.out:
        cfg["out_dir"] = args.out
    if args.pubmed_query:
        cfg["pubmed_query"] = args.pubmed_query
    if args.email:
        cfg["email"] = args.email
    if args.limit is not None:
        cfg["limit"] = args.limit
    if args.mode:
        cfg["mode"] = args.mode
    if args.policies:
        cfg["policies"] = [p.strip() for p in args.policies.split(",") if p.strip()]
    if args.workers:
        cfg["workers"] = args.workers
    if getattr(args, "prompt_spec", None):
        cfg["prompt_spec"] = args.prompt_spec

    cfg["policies"] = validate_policies(list(cfg.get("policies") or ["recall_first"]))

    for key in ("criteria", "records", "out_dir", "prompt_spec"):
        val = cfg.get(key)
        if val and not Path(val).is_absolute():
            cfg[key] = str((cfg_dir / val).resolve())

    if cfg.get("records") and not cfg.get("pubmed_query"):
        n = len(load_records(cfg["records"]))
        print(f"读到题录 {n} 条")

    xlsx = run_pipeline(cfg, mock=args.mock)
    print(f"完成。名单在: {xlsx}")
    print("  recall_first = 纳入 + 不确定（怕漏，人再看）")
    print("  strict       = 只留明确纳入（少看）")
    print("  uncertain    = 模型拿不准")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="smeta-screen",
        description="题录初筛：纳排标准 + 题录 + API key → 宽松/严格/争议名单",
    )
    p.add_argument("--version", action="version", version=f"smeta-screen {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="在一个文件夹里放下示例配置")
    s.add_argument("--out", default="./smeta_run", help="工作目录")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=_cmd_init)

    s = sub.add_parser("pubmed", help="用 PubMed 官方接口检索（不要爬 Embase 网页）")
    s.add_argument("--query", required=True)
    s.add_argument("--email", required=True, help="NCBI 要求的联系邮箱")
    s.add_argument("--out", default="records.json")
    s.add_argument("--retmax", type=int, default=10000)
    s.add_argument("--env", default=".env")
    s.set_defaults(func=_cmd_pubmed)

    s = sub.add_parser("run", help="筛查并导出名单")
    s.add_argument("--config", help="config.yaml")
    s.add_argument("--records", help="题录文件 json/jsonl/xlsx/csv/ris")
    s.add_argument("--criteria", help="纳排标准 txt 或 json")
    s.add_argument("--out", help="输出目录")
    s.add_argument("--pubmed-query", help="可选：同时用 PubMed 检索")
    s.add_argument("--email")
    s.add_argument("--mode", choices=["slice", "multi_prompt"], help="slice=只跑一次再切名单；multi_prompt=每种策略各跑一次")
    s.add_argument("--policies", help="逗号分隔: recall_first,balanced,strict")
    s.add_argument("--limit", type=int)
    s.add_argument("--workers", type=int)
    s.add_argument("--prompt-spec", help="用迭代得到的 spec.yaml 替代内置策略模板")
    s.add_argument("--mock", action="store_true", help="不调用真实 API，用假结果试流程")
    s.add_argument("--env", default=".env")
    s.set_defaults(func=_cmd_run)

    s = sub.add_parser("opt", help="prompt 自迭代（规则槽位可改；优化器文案后补）")
    opt_sub = s.add_subparsers(dest="opt_cmd", required=True)

    p_init = opt_sub.add_parser("init", help="建一个迭代工作目录")
    p_init.add_argument("--out", default="./prompt_opt_run")
    p_init.add_argument("--policy", default="recall_first", choices=["recall_first", "balanced", "strict"])
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_opt_init)

    p_run = opt_sub.add_parser("run", help="评估当前 spec；manual 模式下吃进 NEXT_SPEC.yaml")
    p_run.add_argument("--config", required=True, help="opt.yaml")
    p_run.add_argument("--run-dir")
    p_run.add_argument("--labeled")
    p_run.add_argument("--hold")
    p_run.add_argument("--hold-ratio", type=float)
    p_run.add_argument("--policy")
    p_run.add_argument("--optimizer", choices=["manual", "llm"])
    p_run.add_argument("--max-rounds", type=int)
    p_run.add_argument("--min-recall", type=float)
    p_run.add_argument("--workers", type=int)
    p_run.add_argument("--allow-placeholder", action="store_true")
    p_run.add_argument("--mock", action="store_true")
    p_run.add_argument("--env", default=".env")
    p_run.set_defaults(func=cmd_opt_run)

    p_st = opt_sub.add_parser("status", help="看 BEST / 历史")
    p_st.add_argument("--run-dir", default=".")
    p_st.set_defaults(func=cmd_opt_status)

    p_cat = opt_sub.add_parser("catalogue", help="导出冻结 prompt 目录（文献模板，不含某篇 PICOS）")
    p_cat.add_argument("--out", help="写入该目录：PROMPT_LIST.txt 和 prompts/*.txt；省略则打印")
    p_cat.set_defaults(func=cmd_opt_catalogue)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
