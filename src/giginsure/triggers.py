"""Parametric trigger engine, payout calculation and the zero-touch claim pipeline (mock gateway)."""
import uuid
import pandas as pd

THRESHOLDS = {"heavy_rain": ("rain", 50.0, ">"), "severe_aqi": ("aqi", 400.0, ">"), "extreme_heat": ("temp", 42.0, ">")}
PAYOUT_RATIO = 0.7
MAX_WEEKLY_PAYOUT = 4000.0


def breached(value, threshold, op=">"):
    return value > threshold if op == ">" else value < threshold


def evaluate_triggers(df: pd.DataFrame, use="obs"):
    """Vectorised evaluation over an hourly frame; returns boolean columns per trigger."""
    out = pd.DataFrame(index=df.index)
    for name, (col, thr, op) in THRESHOLDS.items():
        out[name] = df[f"{col}_{use}"] > thr
    out["any"] = out[list(THRESHOLDS)].any(axis=1)
    return out


def evaluate_reading(reading: dict, curfew=False):
    """Single live reading {rain, aqi, temp} -> list of fired trigger names (curfew is an official flag)."""
    fired = [name for name, (col, thr, op) in THRESHOLDS.items() if breached(reading[col], thr, op)]
    if curfew:
        fired.append("curfew")
    return fired


def severity(reading: dict, fired):
    """Disruption severity coefficient in [1, 1.5]: how far past its threshold the worst trigger is."""
    s = 1.0
    for name in fired:
        if name == "curfew":
            s = max(s, 1.2); continue
        col, thr, _ = THRESHOLDS[name]
        s = max(s, min(1.5, 1.0 + (reading[col] - thr) / thr))
    return round(s, 3)


def payout_amount(lost_hours, hourly_rate, already_paid_this_week=0.0):
    raw = max(lost_hours, 0.0) * hourly_rate * PAYOUT_RATIO
    return float(max(0.0, min(raw, MAX_WEEKLY_PAYOUT - already_paid_this_week)))


class MockGateway:
    """Stand-in for Razorpay test mode / UPI sandbox. Idempotent on the key."""
    def __init__(self): self.ledger = {}

    def pay(self, idempotency_key, worker_id, amount):
        if idempotency_key in self.ledger:
            return self.ledger[idempotency_key]
        r = dict(txn_id=uuid.uuid4().hex[:12], worker_id=worker_id, amount=amount, status="SUCCESS")
        self.ledger[idempotency_key] = r; return r


def process_claim(claim, fraud_score, thr, guard, gateway, lost_hours, hourly_rate, paid_so_far=0.0):
    """trigger -> duplicate check -> fraud gate -> payout. Returns (decision, txn|None)."""
    if not guard.register(claim["worker_id"], claim["zone_id"], claim["event_id"]):
        return "REJECT_DUPLICATE", None
    if fraud_score >= thr:
        return "HOLD_REVIEW", None
    amt = payout_amount(lost_hours, hourly_rate, paid_so_far)
    if amt <= 0:
        return "REJECT_ZERO", None
    key = f'{claim["worker_id"]}:{claim["zone_id"]}:{claim["event_id"]}'
    return "PAID", gateway.pay(key, claim["worker_id"], amt)
