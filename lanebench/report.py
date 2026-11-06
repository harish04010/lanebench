from pathlib import Path


def _pct(x):
    return "–" if x is None else f"{x:.1%}"


def write_markdown(result: dict, path: Path) -> None:
    lines = [f"# Lanebench results (seed {result['seed']})", ""]

    lines += ["## Negotiation", "",
              "| Strategy | Close rate (winnable, within rules) | Offers over our ceiling | Overpay vs floor | Margin kept | Loads lost | Hung up on | Avg rounds |",
              "|---|---|---|---|---|---|---|---|"]
    for name, v in result["negotiation"].items():
        o = v["summary"]["overall"]
        lines.append(f"| {name} | {_pct(o['close_rate'])} | {o['violations']} | "
                     f"{_pct(o['overpay_vs_floor'])} | ${o['margin_kept']:,.0f} | {o['loads_lost']} | "
                     f"{o['hung_up_on']} | {o['avg_rounds']} |")

    lines += ["", "### Close rate by carrier personality", "",
              "| Strategy | " + " | ".join(next(iter(result["negotiation"].values()))["summary"]["by_personality"]) + " |",
              "|---|" + "---|" * 4]
    for name, v in result["negotiation"].items():
        bp = v["summary"]["by_personality"]
        lines.append(f"| {name} | " + " | ".join(_pct(s["close_rate"]) for s in bp.values()) + " |")

    lines += ["", "## Driver-text parsing", "",
              "| Parser | Dev accuracy | Held-out accuracy | Held-out macro F1 | ETA within 1h (held out) | Needs-human recall (held out) | False alarms (held out) |",
              "|---|---|---|---|---|---|---|"]
    for name, v in result["parsing"].items():
        d, h = v["dev"], v["heldout"]
        lines.append(f"| {name} | {_pct(d['accuracy'])} | {_pct(h['accuracy'])} | {h['macro_f1']:.2f} | "
                     f"{_pct(h['eta_within_1h'])} | {_pct(h['needs_human_recall'])} | {h['false_alarms']} |")

    for name, v in result["parsing"].items():
        misses = v["heldout"]["misses"]
        if misses:
            lines += ["", f"### {name}: held-out misses", ""]
            lines += [f"- “{m['text']}”: expected `{m['expected']}`, got `{m['got']}`" for m in misses]

    path.write_text("\n".join(lines) + "\n")
