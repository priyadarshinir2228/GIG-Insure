"""Claim telemetry synthesis: offline training table and per-claim live telemetry (same fraud archetypes)."""
import numpy as np

from giginsure.data import generate_claims, claim_telemetry

FRAUD_KINDS = {"spoof": 0.5, "presence": 0.3, "farming": 0.2}

__all__ = ["generate_claims", "claim_telemetry", "draw_live_claim"]


def draw_live_claim(rng: np.random.RandomState, fraud_rate=0.06):
    """Return (kind, telemetry) for one zero-touch claim in the live simulator."""
    kind = "genuine"
    if rng.rand() < fraud_rate:
        kind = str(rng.choice(list(FRAUD_KINDS), p=list(FRAUD_KINDS.values())))
    return kind, claim_telemetry(kind, rng)
