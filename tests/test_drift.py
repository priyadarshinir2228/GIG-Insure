import numpy as np
import pandas as pd
from giginsure import drift as DR


def test_psi_near_zero_for_same_distribution():
    r = np.random.RandomState(0)
    assert DR.psi(r.normal(0, 1, 5000), r.normal(0, 1, 5000)) < 0.1


def test_psi_detects_mean_shift():
    r = np.random.RandomState(0)
    assert DR.psi(r.normal(0, 1, 5000), r.normal(1, 1, 5000)) > 0.2


def test_drift_report_flags_only_shifted_feature():
    r = np.random.RandomState(1)
    ref = pd.DataFrame(dict(a=r.normal(0, 1, 3000), b=r.normal(0, 1, 3000)))
    cur = pd.DataFrame(dict(a=r.normal(0, 1, 3000), b=r.normal(1.5, 1, 3000)))
    rep = DR.data_drift_report(ref, cur, ["a", "b"]).set_index("feature")
    assert not rep.loc["a", "drifted"] and rep.loc["b", "drifted"]


def test_concept_monitor_needs_consecutive_breaches():
    m = DR.ConceptDriftMonitor(1.0, 1.5, 3)
    for w, e in enumerate([2, 2, 1, 2, 2]):  # error dips between breaches
        assert not m.update(w, e)
    assert m.update(5, 2) and m.alarm_week == 5


def test_challenger_gate():
    assert DR.promote_challenger(2.82, 2.15)
    assert not DR.promote_challenger(2.0, 1.95)
