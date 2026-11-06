"""
python -m lanebench              # run everything with the built-in agents
python -m lanebench --llm        # also run Claude (needs ANTHROPIC_API_KEY)
python -m lanebench --n 200      # more negotiation scenarios
"""
import argparse
import json
import os
import time
from pathlib import Path

from . import __version__
from .carriers import make_scenarios
from .evaluate import load_messages, run_negotiation, run_parsing, summarize_negotiation, summarize_parsing
from .negotiators import BUILTIN as NEGOTIATORS, LLMNegotiator
from .parsers import BUILTIN as PARSERS, LLMParser
from .report import write_markdown

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(prog="lanebench")
    ap.add_argument("--n", type=int, default=80, help="negotiation scenarios")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--llm", action="store_true", help="include Claude-backed agents")
    ap.add_argument("--out", default=str(ROOT / "results"))
    args = ap.parse_args()

    negotiators = {name: cls() for name, cls in NEGOTIATORS.items()}
    parsers = {name: cls() for name, cls in PARSERS.items()}
    if args.llm:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise SystemExit("--llm needs ANTHROPIC_API_KEY set")
        negotiators["llm"] = LLMNegotiator()
        parsers["llm"] = LLMParser()

    scenarios = make_scenarios(args.n, args.seed)
    print(f"Negotiation: {len(scenarios)} scenarios, "
          f"{sum(s.deal_possible for s in scenarios)} winnable")
    negotiation = {}
    for name, neg in negotiators.items():
        runs = [run_negotiation(neg, sc) for sc in scenarios]
        negotiation[name] = {"description": neg.description, "summary": summarize_negotiation(runs), "runs": runs}
        o = negotiation[name]["summary"]["overall"]
        print(f"  {name:9} close {o['close_rate']:.0%}  overpay {o['overpay_vs_floor']:.1%}  "
              f"kept ${o['margin_kept']:,.0f}  offers over ceiling {o['violations']}")

    dev, heldout = load_messages("tracking_messages.jsonl"), load_messages("tracking_heldout.jsonl")
    print(f"Parsing: {len(dev)} dev messages, {len(heldout)} held out")
    parsing = {}
    for name, p in parsers.items():
        parsing[name] = {
            "description": p.description,
            "dev": summarize_parsing(run_parsing(p, dev)),
            "heldout": summarize_parsing(run_parsing(p, heldout)),
        }
        d, h = parsing[name]["dev"], parsing[name]["heldout"]
        print(f"  {name:9} dev acc {d['accuracy']:.0%}  held-out acc {h['accuracy']:.0%}  "
              f"needs-human recall {h['needs_human_recall']:.0%}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    result = {
        "version": __version__, "generated_at": time.strftime("%Y-%m-%d"),
        "seed": args.seed, "negotiation": negotiation, "parsing": parsing,
    }
    (out / "results.json").write_text(json.dumps(result, indent=1))
    write_markdown(result, out / "summary.md")

    # Slim copy for the static report page (no per-run transcripts beyond a sample).
    site = json.loads(json.dumps(result))
    for v in site["negotiation"].values():
        runs = [r for r in v.pop("runs") if r["history"]]
        deals = [r for r in runs if r["outcome"] == "deal" and len(r["history"]) >= 2]
        v["sample"] = deals[:3] + [r for r in runs if r["outcome"] != "deal"][:3]
    (ROOT / "site" / "data.json").write_text(json.dumps(site, separators=(",", ":")))
    print(f"Wrote {out / 'results.json'}, {out / 'summary.md'} and site/data.json")


if __name__ == "__main__":
    main()
