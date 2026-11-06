from lanebench.carriers import Carrier, make_scenarios
from lanebench.evaluate import load_messages, run_negotiation, run_parsing, summarize_negotiation, summarize_parsing
from lanebench.negotiators import BUILTIN as NEGOTIATORS, Move, Negotiator
from lanebench.parsers import RuleParser, extract_eta_hours


def test_scenarios_are_reproducible_and_mixed():
    a, b = make_scenarios(50, seed=3), make_scenarios(50, seed=3)
    assert [s.floor for s in a] == [s.floor for s in b]
    assert any(s.deal_possible for s in a) and any(not s.deal_possible for s in a)


def test_carrier_never_counters_below_its_floor():
    for sc in make_scenarios(100, seed=1):
        c = Carrier(sc)
        reply = c.respond(sc.floor * 0.5, 2, None)
        if reply["reply"] == "counter":
            assert reply["rate"] >= sc.floor


def test_proud_carrier_hangs_up_on_a_lowball():
    sc = next(s for s in make_scenarios(20) if s.personality == "proud")
    assert Carrier(sc).respond(sc.ask * 0.5, 1, None)["reply"] == "hung_up"


def test_no_strategy_closes_an_impossible_deal_within_the_rules():
    scenarios = [s for s in make_scenarios(120, seed=5) if not s.deal_possible]
    for cls in NEGOTIATORS.values():
        for sc in scenarios:
            r = run_negotiation(cls(), sc)
            assert not (r["outcome"] == "deal" and not r["violations"]), (cls.name, sc.id)


def test_harness_catches_a_strategy_that_breaks_the_ceiling():
    class Reckless(Negotiator):
        name = "reckless"
        def move(self, ask, ceiling, history):
            return Move("offer", ask * 2)

    runs = [run_negotiation(Reckless(), sc) for sc in make_scenarios(20)]
    assert summarize_negotiation(runs)["overall"]["violations"] == 20


def test_eta_extraction():
    assert extract_eta_hours("eta 45 min") == 1
    assert extract_eta_hours("running about 3 hrs behind") == 3
    assert extract_eta_hours("shop says couple hours") == 2
    assert extract_eta_hours("about a day and a half out") == 36
    assert extract_eta_hours("on schedule") is None


def test_parsing_metrics_shape():
    rows = load_messages("tracking_messages.jsonl")
    s = summarize_parsing(run_parsing(RuleParser(), rows))
    assert 0 <= s["accuracy"] <= 1 and s["messages"] == len(rows)
    assert set(s["per_class"]) <= {"picked_up", "moving", "delayed", "delivered", "issue", "none"}


def test_labels_are_valid():
    valid = {"picked_up", "moving", "delayed", "delivered", "issue", "none"}
    for name in ("tracking_messages.jsonl", "tracking_heldout.jsonl"):
        ids = set()
        for row in load_messages(name):
            assert row["event"] in valid
            assert row["id"] not in ids
            ids.add(row["id"])
