"""Claim anomaly detection with Isolation Forest, plus a rule-based baseline."""
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (precision_score, recall_score, f1_score, roc_auc_score, average_precision_score,
                             confusion_matrix)

FRAUD_FEATURES = ["gps_cell_dist_km", "max_speed_kmph", "max_ping_gap_min", "claims_last_7d", "zone_match_ratio",
                  "orders_before_event", "device_count_24h"]


def rule_score(d):
    """Deterministic baseline: count of violated hard rules."""
    return ((d.gps_cell_dist_km > 3.0).astype(int) + (d.max_speed_kmph > 80).astype(int) + (d.zone_match_ratio < 0.5).astype(int)
            + (d.claims_last_7d >= 4).astype(int) + (d.device_count_24h >= 2).astype(int)).values.astype(float)


def rule_reasons(t):
    """Human-readable reasons for a single claim's telemetry dict (shown on the admin dashboard)."""
    r = []
    if t["gps_cell_dist_km"] > 3.0: r.append("GPS far from cell tower")
    if t["max_speed_kmph"] > 80: r.append("impossible speed jump")
    if t["zone_match_ratio"] < 0.5: r.append("not present in zone")
    if t["claims_last_7d"] >= 4: r.append("claim farming pattern")
    if t["device_count_24h"] >= 2: r.append("multiple devices")
    return r


def fit_iforest(X, n_estimators=300, seed=0, contamination=0.06):
    return IsolationForest(n_estimators=n_estimators, contamination=contamination, random_state=seed, n_jobs=-1).fit(X)


def anomaly_score(model, X):
    return -model.score_samples(X)  # higher = more anomalous


def threshold_at_fpr(scores_genuine, target_fpr=0.02):
    return float(np.quantile(scores_genuine, 1 - target_fpr))


def evaluate(y, score, thr):
    pred = (score >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return dict(precision=precision_score(y, pred, zero_division=0), recall=recall_score(y, pred), f1=f1_score(y, pred),
                roc_auc=roc_auc_score(y, score), pr_auc=average_precision_score(y, score), fpr=fp / (fp + tn),
                tp=int(tp), fp=int(fp), fn=int(fn), tn=int(tn))


def duplicate_key(worker_id, zone_id, event_id):
    return f"{worker_id}:{zone_id}:{event_id}"


class DuplicateGuard:
    """Idempotent claim registry: one payout per (worker, zone, disruption event)."""
    def __init__(self): self._seen = set()

    def register(self, worker_id, zone_id, event_id):
        k = duplicate_key(worker_id, zone_id, event_id)
        if k in self._seen: return False
        self._seen.add(k); return True
