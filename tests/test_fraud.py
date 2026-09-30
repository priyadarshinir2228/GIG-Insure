import numpy as np
import pytest
from sklearn.model_selection import train_test_split
from giginsure import fraud as F


@pytest.fixture(scope="module")
def fitted(claims):
    a, b = train_test_split(claims, test_size=0.5, random_state=0, stratify=claims.is_fraud)
    m = F.fit_iforest(a[F.FRAUD_FEATURES], n_estimators=150)
    s = F.anomaly_score(m, b[F.FRAUD_FEATURES])
    return b, s


def test_spoofed_claims_score_higher(fitted):
    b, s = fitted
    assert s[(b.kind == "spoof").values].mean() > s[(b.kind == "genuine").values].mean()


def test_roc_auc_high_and_fpr_low(fitted):
    b, s = fitted
    thr = F.threshold_at_fpr(s[b.is_fraud.values == 0], 0.02)
    ev = F.evaluate(b.is_fraud, s, thr)
    assert ev["roc_auc"] > 0.95 and ev["fpr"] <= 0.03


def test_threshold_controls_fpr(fitted):
    b, s = fitted
    g = s[b.is_fraud.values == 0]
    thr = F.threshold_at_fpr(g, 0.02)
    assert abs((g >= thr).mean() - 0.02) <= 0.005


def test_rule_baseline_flags_gps_spoofing(claims):
    spoof = claims[claims.kind == "spoof"]
    assert (F.rule_score(spoof) >= 1).mean() > 0.8


def test_duplicate_guard_blocks_second_registration():
    g = F.DuplicateGuard()
    assert g.register("w1", 3, "E1") is True
    assert g.register("w1", 3, "E1") is False
    assert g.register("w1", 3, "E2") is True
