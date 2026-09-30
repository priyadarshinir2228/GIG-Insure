"""API contract between the dashboards and the backend: every route the frontend calls answers, admin actions are locked."""
import os, re
import pytest

from conftest import ROOT

pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "outputs", "results.json")), reason="run the pipeline first")


@pytest.fixture()
def client(tmp_path, capsys):
    from giginsure.platform import Platform
    from giginsure.server import create_app
    app = create_app(Platform(db_path=str(tmp_path / "t.db"), n_seed_workers=10), admin_token="s3cret")
    return app.test_client()


def test_health_reports_models(client):
    h = client.get("/api/health").get_json()
    assert h["status"] == "ok" and h["pricing_version"] >= 1 and h["admin_locked"] is True


def test_every_frontend_route_exists(client):
    web = os.path.join(ROOT, "src", "giginsure", "web")
    used = set()
    for f in os.listdir(web):
        used |= set(re.findall(r"/api/[a-z_/]+", open(os.path.join(web, f), encoding="utf-8").read()))
    rules = {r.rule for r in client.application.url_map.iter_rules()}
    for u in used:
        assert any(rule == u.rstrip("/") or rule.startswith(u) for rule in rules), u


def test_read_only_dashboard_is_public(client):
    assert client.get("/api/admin/summary").status_code == 200
    assert client.get("/admin").status_code == 200 and client.get("/worker").status_code == 200


def test_admin_actions_need_token(client):
    body = {"zone_ids": [0], "scenario": "rainstorm", "hours": 2}
    assert client.post("/api/admin/simulate", json=body).status_code == 401
    assert client.post("/api/admin/simulate", json=body, headers={"X-Admin-Token": "wrong"}).status_code == 401
    assert client.post("/api/admin/simulate", json=body, headers={"X-Admin-Token": "s3cret"}).status_code == 200


def test_worker_onboarding_stays_open(client):
    r = client.post("/api/workers", json={"name": "Asha Kumar", "persona": "food", "zone_id": 1, "upi": "asha.k@okaxis"})
    assert r.status_code == 201 and 15 <= r.get_json()["quote"]["premium"] <= 40
