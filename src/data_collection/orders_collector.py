"""Mock platform API: per-worker order activity (the real Zomato/Swiggy/Zepto partner APIs are not public)."""
import numpy as np

ORDERS_PER_HOUR = {"food": 1.8, "qcom": 2.6, "ecom": 1.2}


def orders_in_window(persona, hours, disrupted, rng: np.random.RandomState):
    """Orders a worker completes in a window; disruption suppresses order flow by ~85%."""
    lam = ORDERS_PER_HOUR[persona] * hours * (0.15 if disrupted else 1.0)
    return int(rng.poisson(lam))
