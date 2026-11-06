# Lanebench results (seed 0)

## Negotiation

| Strategy | Close rate (winnable, within rules) | Offers over our ceiling | Overpay vs floor | Margin kept | Loads lost | Hung up on | Avg rounds |
|---|---|---|---|---|---|---|---|
| split | 100.0% | 10 | 6.6% | $1,832 | 0 | 3 | 2.05 |
| anchored | 100.0% | 0 | 2.2% | $3,641 | 0 | 8 | 1.74 |
| patient | 71.4% | 0 | 1.4% | $3,340 | 12 | 32 | 2.35 |

### Close rate by carrier personality

| Strategy | flexible | firm | flaky | proud |
|---|---|---|---|---|
| split | 100.0% | 100.0% | 100.0% | 100.0% |
| anchored | 100.0% | 100.0% | 100.0% | 100.0% |
| patient | 92.3% | 100.0% | 41.7% | 50.0% |

## Driver-text parsing

| Parser | Dev accuracy | Held-out accuracy | Held-out macro F1 | ETA within 1h (held out) | Needs-human recall (held out) | False alarms (held out) |
|---|---|---|---|---|---|---|
| keyword | 52.1% | 30.0% | 0.23 | 0.0% | 0.0% | 0 |
| rules | 97.9% | 30.0% | 0.19 | 100.0% | 0.0% | 0 |

### keyword: held-out misses

- “vehicle secured on top rack, departing now”: expected `picked_up`, got `moving`
- “flat on the tractor, roadside service 90 min out”: expected `delayed`, got `moving`
- “construction backup on 75, crawling”: expected `delayed`, got `moving`
- “handed keys to the sales manager, all set”: expected `delivered`, got `moving`
- “dealer accepted the unit”: expected `delivered`, got `moving`
- “mirror cracked, not sure if it happened before pickup”: expected `issue`, got `moving`
- “the address you gave me is a house not a dealership”: expected `issue`, got `moving`
- “gonna be delivered in like 20 min”: expected `moving`, got `delivered`
- “had to reroute, adds about 3 hrs”: expected `delayed`, got `moving`
- “customer not answering phone, I'm at the gate”: expected `issue`, got `moving`
- “ok will do”: expected `none`, got `moving`
- “loading now”: expected `picked_up`, got `moving`
- “wreck ahead, we're stopped”: expected `delayed`, got `moving`
- “unloaded at the dealer, no damage”: expected `delivered`, got `picked_up`

### rules: held-out misses

- “vehicle secured on top rack, departing now”: expected `picked_up`, got `moving`
- “flat on the tractor, roadside service 90 min out”: expected `delayed`, got `moving`
- “construction backup on 75, crawling”: expected `delayed`, got `moving`
- “handed keys to the sales manager, all set”: expected `delivered`, got `moving`
- “dealer accepted the unit”: expected `delivered`, got `moving`
- “mirror cracked, not sure if it happened before pickup”: expected `issue`, got `moving`
- “the address you gave me is a house not a dealership”: expected `issue`, got `moving`
- “drop complete, BOL signed”: expected `delivered`, got `moving`
- “had to reroute, adds about 3 hrs”: expected `delayed`, got `moving`
- “customer not answering phone, I'm at the gate”: expected `issue`, got `moving`
- “ok will do”: expected `none`, got `moving`
- “loading now”: expected `picked_up`, got `moving`
- “wreck ahead, we're stopped”: expected `delayed`, got `moving`
- “unloaded at the dealer, no damage”: expected `delivered`, got `picked_up`
