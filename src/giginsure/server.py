"""GigInsure API + dashboards.

    python -m giginsure.server  (from src/)   or   python scripts/serve.py

Admin dashboard : http://127.0.0.1:8000/admin
Worker app      : http://127.0.0.1:8000/worker
"""
import argparse, functools, hmac, logging, os, subprocess, sys, threading

from flask import Flask, jsonify, request, send_from_directory, redirect

from . import ROOT, OUTPUTS
from .platform import Platform
from .validators import ValidationError, verify_token
from .console import banner, info

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def create_app(platform: Platform, admin_token=None):
    """`admin_token` (or GIGINSURE_ADMIN_TOKEN) locks every admin *action*; dashboards stay readable."""
    app = Flask(__name__, static_folder=None)
    P = platform
    admin_token = admin_token if admin_token is not None else os.environ.get("GIGINSURE_ADMIN_TOKEN", "")

    def admin_action(fn):
        @functools.wraps(fn)
        def wrapped(*a, **kw):
            sent = request.headers.get("X-Admin-Token", "")
            if admin_token and not hmac.compare_digest(sent.encode(), admin_token.encode()):
                return jsonify(error="admin token required"), 401
            return fn(*a, **kw)
        return wrapped

    @app.errorhandler(ValidationError)
    def _bad(e):
        return jsonify(error=str(e)), 400

    @app.get("/api/health")
    def health():
        m = P.models
        return jsonify(status="ok", pricing_version=m.get("pricing_version"), fraud_version=m.get("fraud_version"),
                       results_generated_at=m.get("results", {}).get("generated_at"), sim_hour=P.clock["sim_hour"],
                       admin_locked=bool(admin_token))

    @app.get("/")
    def root():
        return redirect("/admin")

    @app.get("/admin")
    def admin():
        return send_from_directory(WEB, "admin.html")

    @app.get("/worker")
    def worker():
        return send_from_directory(WEB, "worker.html")

    @app.get("/static/<path:p>")
    def static_files(p):
        return send_from_directory(WEB, p)

    # ---------------- shared
    @app.get("/api/zones")
    def zones():
        return jsonify([dict(id=z["id"], name=z["name"], flood_score=z["flood_score"]) for z in P.zones.values()])

    @app.get("/api/quote")
    def quote():
        with P.lock:
            return jsonify(P.quote(request.args.get("persona", "food"), int(request.args.get("zone_id", 0))))

    # ---------------- worker
    @app.post("/api/workers")
    def onboard():
        b = request.get_json(force=True)
        return jsonify(P.onboard(b.get("name"), b.get("persona"), b.get("zone_id"), b.get("upi"))), 201

    @app.get("/api/workers/<worker_id>")
    def worker_view(worker_id):
        v = P.worker_view(worker_id)
        return (jsonify(v), 200) if v else (jsonify(error="worker not found"), 404)

    @app.get("/api/me")
    def me():
        wid = verify_token(request.headers.get("Authorization", "").removeprefix("Bearer "))
        if not wid:
            return jsonify(error="invalid or expired token"), 401
        return jsonify(P.worker_view(wid))

    # ---------------- admin
    @app.get("/api/admin/summary")
    def summary():
        return jsonify(P.summary())

    @app.get("/api/admin/forecast")
    def forecast():
        with P.lock:
            return jsonify(P.forecast())

    @app.get("/api/admin/ml")
    def ml():
        return jsonify(P.ml_report())

    @app.post("/api/admin/simulate")
    @admin_action
    def simulate():
        b = request.get_json(force=True)
        zs = b.get("zone_ids") or [b.get("zone_id")]
        P.inject(zs, b.get("scenario", "rainstorm"), b.get("hours", 4), fraud_rate=0.35 if b.get("fraud_ring") else None)
        return jsonify(ok=True)

    @app.post("/api/admin/fast_forward")
    @admin_action
    def fast_forward():
        n = max(1, min(168, int(request.get_json(force=True).get("hours", 6))))
        for _ in range(n):
            P.tick()
        return jsonify(ok=True, hours=n)

    @app.post("/api/admin/speed")
    @admin_action
    def speed():
        P.tick_seconds = max(0.2, min(30.0, float(request.get_json(force=True).get("tick_seconds", 3))))
        P.log("ENGINE", f"simulation speed: 1 hour every {P.tick_seconds:g}s", "green")
        return jsonify(ok=True, tick_seconds=P.tick_seconds)

    @app.post("/api/admin/replay/<event_id>")
    @admin_action
    def replay(event_id):
        return jsonify(P.replay_event(event_id))

    @app.post("/api/admin/review/<int:claim_id>")
    @admin_action
    def review(claim_id):
        P.review(claim_id, bool(request.get_json(force=True).get("approve")))
        return jsonify(ok=True)

    @app.post("/api/admin/retrain")
    @admin_action
    def retrain():
        started = P.start_retrain(fast=bool(request.get_json(force=True).get("fast", True)))
        return jsonify(started=started, running=P.pipeline_running)

    return app


def main(argv=None):
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
    except ImportError:
        pass
    ap = argparse.ArgumentParser(description="GigInsure live platform + dashboards")
    ap.add_argument("--host", default=os.environ.get("GIGINSURE_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT") or os.environ.get("GIGINSURE_PORT", 8000)))
    ap.add_argument("--tick", type=float, default=float(os.environ.get("GIGINSURE_TICK_SECONDS", 3)), help="real seconds per simulated hour")
    ap.add_argument("--weather", choices=["mock", "openmeteo"], default=os.environ.get("GIGINSURE_WEATHER", "mock"))
    ap.add_argument("--workers", type=int, default=60, help="synthetic partners seeded into a fresh database")
    ap.add_argument("--reset", action="store_true", help="delete the live database and start fresh")
    ap.add_argument("--prod", action="store_true", default=os.environ.get("GIGINSURE_PROD") == "1",
                    help="serve with waitress (production WSGI server) instead of Flask's dev server")
    a = ap.parse_args(argv)
    if not os.path.exists(os.path.join(OUTPUTS, "results.json")):
        banner("No trained models found - running the pipeline once (fast mode) before starting the platform")
        subprocess.check_call([sys.executable, os.path.join(ROOT, "scripts", "run_pipeline.py"), "--fast"], cwd=ROOT)
    banner("GigInsure live platform")
    P = Platform(tick_seconds=a.tick, weather_source=a.weather, n_seed_workers=a.workers, reset=a.reset)
    info(f"admin dashboard : http://{a.host}:{a.port}/admin")
    info(f"worker app      : http://{a.host}:{a.port}/worker")
    info("live event log below  (TRIGGER / CLAIM / FRAUD / PAYOUT / POLICY / DRIFT / MODEL)\n")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # keep the terminal for platform events, not polling requests
    app = create_app(P)
    if not os.environ.get("GIGINSURE_ADMIN_TOKEN"):
        info("admin actions are UNLOCKED - set GIGINSURE_ADMIN_TOKEN before exposing this server publicly")
    threading.Thread(target=P.run_forever, daemon=True).start()
    if a.prod:
        # one process on purpose: the trigger monitor and the live state live in this process; threads serve requests
        from waitress import serve
        info(f"production server (waitress) on {a.host}:{a.port}")
        serve(app, host=a.host, port=a.port, threads=8, ident="giginsure")
    else:
        app.run(host=a.host, port=a.port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
