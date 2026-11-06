"""
Simulated carriers for negotiation evals.

Each scenario gets a carrier with a hidden floor (the lowest rate they'll take)
and a personality that decides how they bargain. The point is to make strategies
that look fine on one kind of carrier fall apart on another.
"""
import random
from dataclasses import dataclass, field

PERSONALITIES = ("flexible", "firm", "flaky", "proud")


@dataclass
class Scenario:
    id: str
    lane: str
    miles: int
    market: float
    ask: float          # what the carrier opens with
    floor: float        # hidden: lowest they'll accept
    ceiling: float      # ours: highest we can pay and keep our margin
    personality: str

    @property
    def deal_possible(self) -> bool:
        return self.floor <= self.ceiling


LANES = [
    ("Oakland, CA to Los Angeles, CA", 440), ("Dallas, TX to Atlanta, GA", 925),
    ("Chicago, IL to Newark, NJ", 940), ("Seattle, WA to Denver, CO", 1530),
    ("Houston, TX to Miami, FL", 1395), ("Scottsdale, AZ to Nashville, TN", 1760),
    ("Knoxville, TN to Charlotte, NC", 240), ("Los Angeles, CA to Chicago, IL", 2245),
]


def make_scenarios(n: int = 80, seed: int = 0) -> list[Scenario]:
    rng = random.Random(seed)
    out = []
    for i in range(n):
        lane, miles = rng.choice(LANES)
        per_mile = 1.55 if miles < 500 else 1.05 if miles < 1500 else 0.82
        market = round(max(375, miles * per_mile) * rng.uniform(0.92, 1.1), 0)
        ask = round(market * rng.uniform(1.0, 1.3), 0)
        floor = round(ask * rng.uniform(0.80, 0.95), 0)
        # Our ceiling comes from what we quoted the customer, so it sometimes
        # lands below the carrier's floor. Walking away is the right call then.
        ceiling = round(market * rng.uniform(0.95, 1.15), 0)
        out.append(Scenario(f"n{i:03d}", lane, miles, market, ask, floor, ceiling,
                            PERSONALITIES[i % len(PERSONALITIES)]))
    return out


@dataclass
class Carrier:
    scenario: Scenario
    max_rounds: int = 6
    hung_up: bool = field(default=False, init=False)

    def respond(self, offer: float, round_no: int, last_counter: float | None) -> dict:
        s = self.scenario
        if self.hung_up:
            return {"reply": "hung_up"}

        if s.personality == "proud" and round_no == 1 and offer < s.ask * 0.78:
            self.hung_up = True
            return {"reply": "hung_up", "why": "insulted by the opening offer"}

        if offer >= s.floor:
            return {"reply": "accept", "rate": offer}

        patience = 3 if s.personality == "flaky" else self.max_rounds
        if round_no >= patience:
            self.hung_up = True
            return {"reply": "hung_up", "why": "ran out of patience"}

        concession = {"flexible": 0.45, "firm": 0.18, "flaky": 0.4, "proud": 0.3}[s.personality]
        start = last_counter if last_counter is not None else s.ask
        counter = start - (start - s.floor) * concession
        # Never counter below their own floor, and never below what we just offered.
        counter = round(max(s.floor, offer, counter), 0)
        return {"reply": "counter", "rate": counter}
