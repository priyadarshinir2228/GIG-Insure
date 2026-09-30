import pandas as pd
import pytest
from giginsure import triggers as T, fraud as F


@pytest.mark.parametrize("rain,fired", [(49.9, False), (50.0, False), (50.1, True)])
def test_rain_threshold_boundary(rain, fired):
    assert ("heavy_rain" in T.evaluate_reading(dict(rain=rain, aqi=100, temp=30))) is fired


@pytest.mark.parametrize("aqi,fired", [(399, False), (400, False), (401, True)])
def test_aqi_threshold_boundary(aqi, fired):
    assert ("severe_aqi" in T.evaluate_reading(dict(rain=0, aqi=aqi, temp=30))) is fired


@pytest.mark.parametrize("temp,fired", [(41.9, False), (42.1, True)])
def test_heat_threshold_boundary(temp, fired):
    assert ("extreme_heat" in T.evaluate_reading(dict(rain=0, aqi=100, temp=temp))) is fired


def test_vectorised_evaluation():
    df = pd.DataFrame(dict(rain_obs=[10, 60, 0], aqi_obs=[100, 100, 450], temp_obs=[30, 30, 43]))
    out = T.evaluate_triggers(df)
    assert out["heavy_rain"].tolist() == [False, True, False]
    assert out["any"].tolist() == [False, True, True]
    assert out.loc[2, "severe_aqi"] and out.loc[2, "extreme_heat"]


def test_payout_is_70_percent_of_lost_wages():
    assert T.payout_amount(4, 100) == 280.0


def test_payout_respects_weekly_cap():
    assert T.payout_amount(10, 100, already_paid_this_week=3900) == 100.0
    assert T.payout_amount(10, 100, already_paid_this_week=4000) == 0.0


def _claim():
    return dict(worker_id="w1", zone_id=2, event_id="E9")


def test_zero_touch_claim_paid_and_idempotent():
    g, gw = F.DuplicateGuard(), T.MockGateway()
    d, txn = T.process_claim(_claim(), 0.3, 0.5, g, gw, 3, 95)
    assert d == "PAID" and txn["amount"] == pytest.approx(199.5) and len(gw.ledger) == 1
    assert gw.pay("w1:2:E9", "w1", 199.5)["txn_id"] == txn["txn_id"] and len(gw.ledger) == 1


def test_duplicate_claim_rejected():
    g, gw = F.DuplicateGuard(), T.MockGateway()
    T.process_claim(_claim(), 0.3, 0.5, g, gw, 3, 95)
    d, txn = T.process_claim(_claim(), 0.3, 0.5, g, gw, 3, 95)
    assert d == "REJECT_DUPLICATE" and txn is None and len(gw.ledger) == 1


def test_suspicious_claim_held_for_review_not_paid():
    g, gw = F.DuplicateGuard(), T.MockGateway()
    d, txn = T.process_claim(_claim(), 0.7, 0.5, g, gw, 3, 95)
    assert d == "HOLD_REVIEW" and txn is None and not gw.ledger


def test_severity_grows_with_intensity():
    mild = T.severity(dict(rain=52, aqi=0, temp=0), ["heavy_rain"])
    heavy = T.severity(dict(rain=90, aqi=0, temp=0), ["heavy_rain"])
    assert 1.0 <= mild < heavy <= 1.5
