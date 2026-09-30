import numpy as np
from giginsure import data as D


def test_weekly_shape(weekly):
    assert len(weekly) == 60 * 12 * 3
    assert set(D.FEATURES + [D.TARGET]).issubset(weekly.columns)


def test_premium_within_weekly_band(weekly):
    assert weekly[D.TARGET].between(15, 40).all()


def test_temporal_split_has_no_overlap():
    df = D.generate_weekly(n_weeks=D.N_WEEKS, n_zones=2)
    parts = D.split_temporal(df)
    weeks = [set(p.week) for p in parts]
    for i in range(len(weeks)):
        for j in range(i + 1, len(weeks)):
            assert not weeks[i] & weeks[j]
    assert max(weeks[0]) < min(weeks[1]) < min(weeks[2]) < min(weeks[3])
    assert sum(map(len, parts)) == len(df)


def test_generation_is_reproducible():
    a = D.generate_weekly(n_weeks=5, n_zones=3, seed=1)
    b = D.generate_weekly(n_weeks=5, n_zones=3, seed=1)
    assert a.equals(b)


def test_lagged_history_has_no_current_week_leakage(weekly):
    g = weekly[(weekly.zone_id == 0) & (weekly.persona == "food")].sort_values("week")
    # the first week has no history; week 1 history equals week 0's realised hours exactly
    assert g.hist_disrupt_hrs_12w.iloc[0] == 0.0
    assert np.isclose(g.hist_disrupt_hrs_12w.iloc[1], g.true_hours.iloc[0])


def test_no_health_accident_or_vehicle_features():
    banned = ("health", "medical", "accident", "injury", "vehicle", "repair", "hospital", "life")
    assert not [f for f in D.FEATURES if any(b in f.lower() for b in banned)]
