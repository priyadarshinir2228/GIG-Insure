"""Integration tests of the live platform: onboarding -> ML policy -> simulated rainstorm -> zero-touch claims -> payout.

Requires trained models (outputs/), produced by scripts/run_pipeline.py; skipped otherwise.
"""
import os
import pytest

from conftest import ROOT

pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "outputs", "results.json")), reason="run the pipeline first")


@pytest.fixture()
def platform(tmp_path, capsys):
    from giginsure.platform import Platform
    return Platform(db_path=str(tmp_path / "t.db"), n_seed_workers=20)


def test_onboarding_issues_ml_priced_weekly_policy(platform):
    r = platform.onboard("Asha Kumar", "qcom", 0, "asha.k@okaxis")
    assert 15 <= r["quote"]["premium"] <= 40 and r["quote"]["model_version"] >= 1
    v = platform.worker_view(r["worker"]["worker_id"])
    assert v["active_policy"]["premium"] == r["quote"]["premium"]


def test_simulated_rainstorm_pays_workers_automatically(platform):
    platform.fraud_rate = 0.0
    platform.inject([0], "rainstorm", hours=3)
    for _ in range(5):
        platform.tick()
    s = platform.summary()
    ev = [e for e in s["events"] if e["zone_id"] == 0]
    assert ev and ev[0]["status"] == "CLOSED" and "heavy_rain" in ev[0]["triggers"]
    workers_in_zone = next(z["workers"] for z in s["zones"] if z["id"] == 0)
    assert s["kpis"]["decisions"].get("PAID", 0) + s["kpis"]["decisions"].get("HOLD_REVIEW", 0) == workers_in_zone
    if workers_in_zone:
        assert s["kpis"]["payouts"] > 0
    # replaying the event must not move money
    before = s["kpis"]["payouts"]
    r = platform.replay_event(ev[0]["event_id"])
    assert set(r["decisions"]) <= {"REJECT_DUPLICATE"} and platform.summary()["kpis"]["payouts"] == before


def test_forecast_covers_every_zone(platform):
    f = platform.forecast()
    assert len(f["zones"]) == len(platform.zones) and f["total_expected_premium"] > 0
