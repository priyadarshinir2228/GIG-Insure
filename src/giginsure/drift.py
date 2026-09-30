"""Data drift (PSI, KS) and concept drift (rolling error) monitoring."""
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp


def psi(ref, cur, bins=10, eps=1e-6):
    ref, cur = np.asarray(ref, float), np.asarray(cur, float)
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    r = np.histogram(ref, edges)[0] / len(ref) + eps
    c = np.histogram(cur, edges)[0] / len(cur) + eps
    return float(np.sum((c - r) * np.log(c / r)))


def psi_status(v):
    return "stable" if v < 0.1 else ("moderate" if v < 0.2 else "significant")


def data_drift_report(ref: pd.DataFrame, cur: pd.DataFrame, features, alpha=0.01):
    rows = []
    for f in features:
        v = psi(ref[f], cur[f]); ks = ks_2samp(ref[f], cur[f])
        rows.append(dict(feature=f, psi=v, psi_status=psi_status(v), ks_stat=float(ks.statistic), ks_pvalue=float(ks.pvalue),
                         drifted=bool(v >= 0.2 or ks.pvalue < alpha and ks.statistic > 0.1)))
    return pd.DataFrame(rows)


class ConceptDriftMonitor:
    """Alarm when weekly MAE exceeds `factor` x baseline MAE for `patience` consecutive weeks."""
    def __init__(self, baseline_mae, factor=1.5, patience=3):
        self.base, self.factor, self.patience = baseline_mae, factor, patience
        self.streak, self.alarm_week, self.history = 0, None, []

    def update(self, week, mae):
        self.history.append((week, mae))
        self.streak = self.streak + 1 if mae > self.factor * self.base else 0
        if self.streak >= self.patience and self.alarm_week is None:
            self.alarm_week = week
        return self.alarm_week is not None


def promote_challenger(champion_mae, challenger_mae, min_gain=0.05):
    """Champion/challenger gate: challenger must improve MAE by at least `min_gain` (relative)."""
    return challenger_mae <= champion_mae * (1 - min_gain)
