"""
Driver-text parsers under test.

Truck drivers text things like "dot inspection at the scale, gonna be late.
eta tmrw". A parser has to turn that into an event, an ETA if one was given,
and whether a person needs to look at it.
"""
import json
import os
import re
from dataclasses import dataclass


@dataclass
class Parsed:
    event: str            # picked_up | moving | delayed | delivered | issue | none
    eta_hours: int | None
    needs_human: bool


class Parser:
    name = "base"
    description = ""

    def parse(self, text: str) -> Parsed:
        raise NotImplementedError


class KeywordParser(Parser):
    """The obvious first attempt, and the one Waybill's mock started from."""
    name = "keyword"
    description = "First keyword that matches wins. No negation, no ETA parsing."

    RULES = [
        ("delivered", ("delivered", "dropped off", "signed")),
        ("picked_up", ("loaded", "picked up", "on the truck")),
        ("delayed", ("weather", "inspection", "tire", "late", "behind", "delay")),
    ]

    def parse(self, text):
        t = text.lower()
        for event, words in self.RULES:
            if any(w in t for w in words):
                return Parsed(event, None, False)
        return Parsed("moving" if len(t.strip()) > 3 else "none", None, False)


_NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "couple": 2, "few": 3, "three": 3, "several": 4}


def extract_eta_hours(t: str) -> int | None:
    t = t.lower()
    if "day and a half" in t:
        return 36
    if re.search(r"\b(lose|losing) a day\b", t):
        return 24
    m = re.search(r"(\d+(?:\.\d+)?)\s*(min|mins|minutes)\b", t)
    if m:
        return max(1, round(float(m.group(1)) / 60))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours)\b", t)
    if m:
        return round(float(m.group(1)))
    m = re.search(r"\b(a|an|one|two|couple|few|three|several)\s+(?:of\s+)?(hr|hrs|hour|hours)\b", t)
    if m and m.group(1) not in ("a", "few", "several"):
        return _NUM_WORDS[m.group(1)]
    m = re.search(r"take my (\d+)", t)  # "take my 10" = 10-hour rest break
    if m:
        return int(m.group(1))
    return None


class RuleParser(Parser):
    """
    What the keyword parser grew into after reading its failures:
    issues beat everything, negations are respected, future tense
    isn't a delivery, and ETAs are pulled out with regexes.
    """
    name = "rules"
    description = "Ordered rules with negation, tense and ETA handling."

    ISSUE = ("scratch", "chip", "dent", "scraped", "damage", "dead", "won't sign", "wont sign",
             "doesn't match", "doesnt match", "refusing", "nobody at", "no one at",
             "doesn't work", "doesnt work", "what do you want me to do")
    DELAY = ("weather", "snow", "inspection", "tire", "late", "behind", "delay", "broke down",
             "breakdown", "accident", "stuck", "hit my hours", "take my 10", "sitting tight",
             "waiting on", "lose a day", "can't pick up", "cant pick up", "not loaded yet")
    DELIVERED = ("delivered", "dropped off", "dropped it", "rolled it off", "on their lot",
                 "dealer has it", "left it with", "signed the bol", "signed +")
    PICKED_UP = ("loaded", "picked up", "on the truck", "got it on")
    HUMAN = ("call me",)

    NEGATED = re.compile(r"\b(no|not|n't|without)\s+(\w+\s+)?(delay|delays|delayed|damage|issues?)\b")

    def parse(self, text):
        t = text.lower().strip()
        eta = extract_eta_hours(t)
        if not t or len(t) <= 3:
            return Parsed("none", None, False)
        if any(w in t for w in self.HUMAN):
            return Parsed("none", None, True)

        cleaned = self.NEGATED.sub(" ", t)  # "no damage" shouldn't count as damage

        if any(w in cleaned for w in self.ISSUE):
            return Parsed("issue", eta, True)
        if any(w in cleaned for w in self.DELAY):
            serious = any(w in cleaned for w in ("broke down", "breakdown", "can't pick up", "cant pick up"))
            return Parsed("delayed", eta, serious)
        future = re.search(r"\b(will be|gonna be|should be)\b", cleaned) or "is next" in cleaned
        if not future and any(w in cleaned for w in self.DELIVERED):
            return Parsed("delivered", None, False)
        if any(w in cleaned for w in self.PICKED_UP):
            return Parsed("picked_up", None, False)
        return Parsed("moving", eta, False)


class LLMParser(Parser):
    name = "llm"
    description = "Claude classifies each message with a short schema."

    SYSTEM = (
        "You read texts from car-hauling truck drivers. Classify the message. "
        "event: picked_up (vehicle just loaded), moving (en route, including future delivery plans), "
        "delayed (behind schedule or waiting), delivered (handed over), issue (damage, dispute, "
        "access or paperwork problem), none (no information). "
        "eta_hours: integer hours if the driver gives a time estimate, else null. "
        "needs_human: true if someone at the brokerage should step in. "
        'Reply with JSON only: {"event": ..., "eta_hours": ..., "needs_human": ...}'
    )

    def __init__(self, model: str | None = None):
        import httpx
        self.http = httpx.Client(timeout=30)
        self.key = os.environ["ANTHROPIC_API_KEY"]
        self.model = model or os.getenv("LANEBENCH_MODEL", "claude-sonnet-5-5")

    def parse(self, text):
        r = self.http.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"},
            json={"model": self.model, "max_tokens": 120, "system": self.SYSTEM,
                  "messages": [{"role": "user", "content": f"Driver text: {text!r}"}]},
        )
        r.raise_for_status()
        out = "".join(b.get("text", "") for b in r.json()["content"])
        d = json.loads(out[out.find("{"): out.rfind("}") + 1])
        return Parsed(d["event"], d.get("eta_hours"), bool(d.get("needs_human")))


BUILTIN = {cls.name: cls for cls in (KeywordParser, RuleParser)}
