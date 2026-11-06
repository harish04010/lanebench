import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from .carriers import PERSONALITIES, Carrier, Scenario
from .negotiators import Negotiator
from .parsers import Parser

DATA = Path(__file__).resolve().parent.parent / "data"
EVENTS = ("picked_up", "moving", "delayed", "delivered", "issue", "none")


# --------------------------------------------------------------------------
# Negotiation
# --------------------------------------------------------------------------

def run_negotiation(neg: Negotiator, sc: Scenario, max_rounds: int = 6) -> dict:
    carrier = Carrier(sc, max_rounds=max_rounds)
    history: list[dict] = []
    violations: list[str] = []
    last_counter = None
    outcome, price, why = "stalled", None, None

    for round_no in range(1, max_rounds + 1):
        mv = neg.move(sc.ask, sc.ceiling, history)
        if mv.action == "walk":
            outcome = "walked"
            break
        amount = history[-1]["counter"] if (mv.action == "accept" and history) else mv.amount
        if amount > sc.ceiling + 0.5:
            violations.append("over_ceiling")
        if mv.action == "offer" and history and amount < history[-1]["offer"]:
            violations.append("went_backwards")

        reply = carrier.respond(amount, round_no, last_counter)
        if reply["reply"] == "accept":
            outcome, price = "deal", reply["rate"]
            break
        if reply["reply"] == "hung_up":
            outcome, why = "hung_up", reply.get("why")
            break
        history.append({"offer": amount, "counter": reply["rate"]})
        last_counter = reply["rate"]

    return {
        "scenario": sc.id, "personality": sc.personality, "winnable": sc.deal_possible,
        "outcome": outcome, "price": price, "rounds": len(history) + (1 if outcome == "deal" else 0),
        "ask": sc.ask, "floor": sc.floor, "ceiling": sc.ceiling,
        "violations": violations, "why": why, "history": history,
    }


def summarize_negotiation(runs: list[dict]) -> dict:
    def stats(rs):
        winnable = [r for r in rs if r["winnable"]]
        hopeless = [r for r in rs if not r["winnable"]]
        deals = [r for r in rs if r["outcome"] == "deal"]
        clean_deals = [r for r in deals if not r["violations"]]
        return {
            "scenarios": len(rs),
            # A deal that broke our own rules doesn't count as a win.
            "close_rate": round(sum(r["outcome"] == "deal" and not r["violations"] for r in winnable) / len(winnable), 3) if winnable else None,
            "walked_when_hopeless": round(sum(r["outcome"] != "deal" for r in hopeless) / len(hopeless), 3) if hopeless else None,
            # How much above the carrier's real floor we paid. Lower is better.
            "overpay_vs_floor": round(sum((r["price"] - r["floor"]) / r["floor"] for r in clean_deals) / len(clean_deals), 4) if clean_deals else None,
            "savings_vs_ask": round(sum((r["ask"] - r["price"]) / r["ask"] for r in clean_deals) / len(clean_deals), 4) if clean_deals else None,
            # Dollars kept under our ceiling across every deal. The number a broker actually cares about.
            "margin_kept": round(sum(r["ceiling"] - r["price"] for r in clean_deals), 0),
            "loads_lost": sum(r["outcome"] != "deal" for r in winnable),
            "rule_breaking_deals": len(deals) - len(clean_deals),
            "hung_up_on": sum(r["outcome"] == "hung_up" for r in rs),
            "avg_rounds": round(sum(r["rounds"] for r in rs) / len(rs), 2) if rs else None,
            "violations": sum(len(r["violations"]) for r in rs),
        }

    out = {"overall": stats(runs), "by_personality": {}}
    for p in PERSONALITIES:
        out["by_personality"][p] = stats([r for r in runs if r["personality"] == p])
    return out


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

def load_messages(name: str) -> list[dict]:
    with open(DATA / name) as f:
        return [json.loads(line) for line in f if line.strip()]


def run_parsing(parser: Parser, rows: list[dict]) -> list[dict]:
    results = []
    for row in rows:
        try:
            p = parser.parse(row["text"])
            pred = asdict(p)
        except Exception as e:  # an eval should record crashes, not die on them
            pred = {"event": "error", "eta_hours": None, "needs_human": False, "error": str(e)}
        results.append({**row, "pred": pred})
    return results


def summarize_parsing(results: list[dict]) -> dict:
    n = len(results)
    correct = sum(r["pred"]["event"] == r["event"] for r in results)

    per_class = {}
    f1s = []
    for ev in EVENTS:
        tp = sum(r["pred"]["event"] == ev and r["event"] == ev for r in results)
        fp = sum(r["pred"]["event"] == ev and r["event"] != ev for r in results)
        fn = sum(r["pred"]["event"] != ev and r["event"] == ev for r in results)
        if tp + fn == 0:
            continue
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn)
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        f1s.append(f1)
        per_class[ev] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3), "support": tp + fn}

    with_eta = [r for r in results if r["eta_hours"] is not None]
    eta_ok = sum(r["pred"]["eta_hours"] is not None and abs(r["pred"]["eta_hours"] - r["eta_hours"]) <= 1 for r in with_eta)

    # Missing a message that needed a person is the expensive mistake.
    human = [r for r in results if r["needs_human"]]
    human_caught = sum(r["pred"]["needs_human"] for r in human)
    false_alarms = sum(r["pred"]["needs_human"] and not r["needs_human"] for r in results)

    confusion: dict = defaultdict(Counter)
    for r in results:
        confusion[r["event"]][r["pred"]["event"]] += 1

    return {
        "messages": n,
        "accuracy": round(correct / n, 3),
        "macro_f1": round(sum(f1s) / len(f1s), 3),
        "eta_within_1h": round(eta_ok / len(with_eta), 3) if with_eta else None,
        "needs_human_recall": round(human_caught / len(human), 3) if human else None,
        "false_alarms": false_alarms,
        "per_class": per_class,
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "misses": [{"id": r["id"], "text": r["text"], "expected": r["event"], "got": r["pred"]["event"]}
                   for r in results if r["pred"]["event"] != r["event"]],
    }
