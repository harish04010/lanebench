"""
Negotiation strategies under test.

Each one sees only what a real agent would: the carrier's ask, our ceiling,
and the offers and counters so far. None of them can see the carrier's floor.
"""
import json
import os
from dataclasses import dataclass


@dataclass
class Move:
    action: str   # "offer", "accept", or "walk"
    amount: float = 0.0


class Negotiator:
    name = "base"
    description = ""

    def move(self, ask: float, ceiling: float, history: list[dict]) -> Move:
        raise NotImplementedError


class SplitTheDifference(Negotiator):
    name = "split"
    description = "Opens at 80% of ask, meets halfway, takes anything under the ceiling."

    def move(self, ask, ceiling, history):
        if not history:
            return Move("offer", round(ask * 0.8))
        counter, ours = history[-1]["counter"], history[-1]["offer"]
        if counter <= ceiling:
            return Move("accept", counter)
        nxt = (ours + counter) / 2
        if ours >= ceiling:
            return Move("walk")
        return Move("offer", round(min(nxt, ceiling)))


class Anchored(Negotiator):
    name = "anchored"
    description = "Waybill's policy: credible opening, shrinking steps, accepts once the gap is small."

    def move(self, ask, ceiling, history):
        if not history:
            return Move("offer", round(min(ask * 0.86, ceiling * 0.9)))
        counter, ours = history[-1]["counter"], history[-1]["offer"]
        if counter <= ceiling and (counter - ours <= 40 or len(history) >= 2):
            return Move("accept", counter)
        if ours >= ceiling - 1:
            return Move("walk")
        return Move("offer", round(min(ours + (counter - ours) * 0.55, ceiling)))


class Patient(Negotiator):
    name = "patient"
    description = "Opens low, concedes slowly, holds out for a small gap before accepting."

    def move(self, ask, ceiling, history):
        if not history:
            return Move("offer", round(min(ask * 0.8, ceiling * 0.85)))
        counter, ours = history[-1]["counter"], history[-1]["offer"]
        gap = counter - ours
        if counter <= ceiling and (gap <= counter * 0.03 or len(history) >= 4):
            return Move("accept", counter)
        if ours >= ceiling - 1:
            return Move("walk")
        return Move("offer", round(min(ours + gap * 0.35, ceiling)))


class LLMNegotiator(Negotiator):
    """Asks Claude for each move. Only runs when ANTHROPIC_API_KEY is set."""
    name = "llm"
    description = "Claude decides each move from the same information the others get."

    SYSTEM = (
        "You negotiate a rate with a car-hauling carrier on behalf of a freight broker. "
        "Never offer above the ceiling. Accept a counter only if it's at or under the ceiling. "
        "Walk away if a deal under the ceiling looks impossible. "
        'Reply with JSON only: {"action": "offer"|"accept"|"walk", "amount": number}'
    )

    def __init__(self, model: str | None = None):
        import httpx  # only needed for this strategy
        self.http = httpx.Client(timeout=30)
        self.key = os.environ["ANTHROPIC_API_KEY"]
        self.model = model or os.getenv("LANEBENCH_MODEL", "claude-sonnet-5-5")

    def move(self, ask, ceiling, history):
        prompt = f"Carrier asks ${ask:,.0f}. Your ceiling is ${ceiling:,.0f}. History: {json.dumps(history)}"
        r = self.http.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"},
            json={"model": self.model, "max_tokens": 200, "system": self.SYSTEM,
                  "messages": [{"role": "user", "content": prompt}]},
        )
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json()["content"])
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        return Move(data["action"], float(data.get("amount") or 0))


BUILTIN = {cls.name: cls for cls in (SplitTheDifference, Anchored, Patient)}
