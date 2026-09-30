"""Live GigInsure platform: onboarding, ML weekly pricing, real-time trigger monitoring, zero-touch claims,
AI fraud screening, duplicate guard and instant (mock) UPI payouts.

The decision path for every claim is ``triggers.process_claim`` -- the same function the pipeline benchmarks --
backed here by a SQLite duplicate guard and an idempotent SQLite payout ledger.
"""
import collections, datetime, json, os, pickle, sqlite3, subprocess, sys, threading, time
import numpy as np
import pandas as pd
import yaml

from . import ROOT, OUTPUTS, CONFIG, DATA
from . import data as D, fraud as F, triggers as T, drift as DR, validators as V
from .console import c
from data_collection.env_collector import make_source, SCENARIOS
from data_collection.worker_synth import synth_workers
from data_collection.claims_synth import draw_live_claim
from data_collection.orders_collector import orders_in_window

PRICING_MODEL = "giginsure-weekly-premium"
FRAUD_MODEL = "giginsure-fraud-iforest"
MAX_EVENT_HOURS = 10          # one disruption window is capped at a 10-hour shift
HOURS_PER_WEEK = 168

SCHEMA = """
CREATE TABLE IF NOT EXISTS zones(id INTEGER PRIMARY KEY, name TEXT, lat REAL, lon REAL, flood_score REAL);
CREATE TABLE IF NOT EXISTS workers(worker_id TEXT PRIMARY KEY, name TEXT, persona TEXT, zone_id INTEGER, upi TEXT,
    hourly_rate REAL, kyc_status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS policies(policy_id INTEGER PRIMARY KEY AUTOINCREMENT, worker_id TEXT, week_no INTEGER,
    premium REAL, expected_loss REAL, max_weekly_payout REAL, model_version INTEGER, status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, zone_id INTEGER, triggers TEXT, source TEXT, start_hour INTEGER,
    hours INTEGER, peak_rain REAL, peak_aqi REAL, peak_temp REAL, severity REAL, status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS claims(claim_id INTEGER PRIMARY KEY AUTOINCREMENT, worker_id TEXT, zone_id INTEGER, event_id TEXT,
    week_no INTEGER, lost_hours REAL, amount REAL, fraud_score REAL, threshold REAL, reasons TEXT, telemetry TEXT,
    true_kind TEXT, decision TEXT, txn_id TEXT, decided_ms REAL, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS claim_keys(key TEXT PRIMARY KEY, created_at TEXT);
CREATE TABLE IF NOT EXISTS payouts(txn_id TEXT PRIMARY KEY, idem_key TEXT UNIQUE, worker_id TEXT, upi TEXT, amount REAL,
    week_no INTEGER, status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
"""


def now_s():
    return time.strftime("%Y-%m-%d %H:%M:%S")


class DbGuard:
    """Duplicate guard persisted in SQLite: one claim per (worker, zone, event), survives restarts."""
    def __init__(self, db): self.db = db

    def register(self, worker_id, zone_id, event_id):
        try:
            self.db.execute("INSERT INTO claim_keys VALUES (?,?)", (F.duplicate_key(worker_id, zone_id, event_id), now_s()))
            return True
        except sqlite3.IntegrityError:
            return False


class DbGateway:
    """Mock UPI / Razorpay-test-mode gateway with an idempotent ledger (same contract as triggers.MockGateway)."""
    def __init__(self, db, week_fn): self.db, self.week_fn = db, week_fn

    def pay(self, idempotency_key, worker_id, amount):
        row = self.db.execute("SELECT txn_id, worker_id, amount, status FROM payouts WHERE idem_key=?", (idempotency_key,)).fetchone()
        if row:
            return dict(zip(("txn_id", "worker_id", "amount", "status"), row))
        upi = self.db.execute("SELECT upi FROM workers WHERE worker_id=?", (worker_id,)).fetchone()[0]
        txn = "pay_" + os.urandom(6).hex()
        self.db.execute("INSERT INTO payouts VALUES (?,?,?,?,?,?,?,?)", (txn, idempotency_key, worker_id, upi, amount, self.week_fn(), "SUCCESS", now_s()))
        return dict(txn_id=txn, worker_id=worker_id, amount=amount, status="SUCCESS")


class Platform:
    def __init__(self, db_path=None, outputs=OUTPUTS, tick_seconds=3.0, weather_source="mock", n_seed_workers=60, reset=False):
        self.outputs, self.tick_seconds, self.weather_name = outputs, float(tick_seconds), weather_source
        self.db_path = db_path or os.path.join(DATA, "giginsure.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if reset and os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self.db.executescript(SCHEMA)
        self.rng = np.random.RandomState(int(time.time()) % 100000)
        self.weather = make_source(weather_source)
        self.guard, self.gateway = DbGuard(self.db), DbGateway(self.db, lambda: self.week_no)
        self.log_buf = collections.deque(maxlen=200)
        self.series = collections.deque(maxlen=24 * 14)
        self.recent_readings = collections.deque(maxlen=HOURS_PER_WEEK * 12)
        self.scenarios = {}           # zone_id -> dict(kind, hours_left, total, fraud_rate)
        self.current = {}             # zone_id -> latest reading
        self.live_drift, self.pipeline_proc, self.models = {}, None, {}
        self.fraud_rate = 0.06
        self._load_zones()
        self._restore_clock()
        self.load_models()
        self._drift_ref = self._build_drift_reference()
        if not self.db.execute("SELECT COUNT(*) FROM workers").fetchone()[0]:
            self._seed_workers(n_seed_workers)
        self._stop = threading.Event()

    # ------------------------------------------------------------------ logging
    def log(self, tag, msg, colour="cyan"):
        stamp = f"W{self.week_no:02d} {self.day_name} {self.hour_of_day:02d}:00"
        line = f"[{tag}] {msg}"
        self.log_buf.append(dict(t=now_s(), sim=stamp, tag=tag, msg=msg))
        print(c(f"{time.strftime('%H:%M:%S')} ", "grey") + c(f"{stamp:<14}", "dim") + c(f"[{tag:<7}] ", "bold", colour) + msg, flush=True)

    # ------------------------------------------------------------------ setup
    def _load_zones(self):
        with open(os.path.join(CONFIG, "zones.yaml")) as f:
            cfg = yaml.safe_load(f)
        self.city = cfg.get("city", "")
        self.zones = {z["id"]: z for z in cfg["zones"]}
        for z in self.zones.values():
            self.db.execute("INSERT OR REPLACE INTO zones VALUES (?,?,?,?,?)", (z["id"], z["name"], z["lat"], z["lon"], z["flood_score"]))

    def _restore_clock(self):
        row = self.db.execute("SELECT v FROM kv WHERE k='clock'").fetchone()
        if row:
            self.clock = json.loads(row[0])
        else:
            today = datetime.date.today()
            self.clock = dict(sim_hour=0, start_woy=int(today.isocalendar()[1]) - 1, start_hod=8, start_dow=today.weekday())

    def _save_clock(self):
        self.db.execute("INSERT OR REPLACE INTO kv VALUES ('clock', ?)", (json.dumps(self.clock),))

    @property
    def abs_hour(self): return self.clock["start_dow"] * 24 + self.clock["start_hod"] + self.clock["sim_hour"]

    @property
    def week_no(self): return self.abs_hour // HOURS_PER_WEEK

    @property
    def week_of_year(self): return (self.clock["start_woy"] + self.week_no) % 52

    @property
    def hour_of_day(self): return self.abs_hour % 24

    @property
    def day_name(self): return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][(self.abs_hour // 24) % 7]

    # ------------------------------------------------------------------ models
    def _results_path(self): return os.path.join(self.outputs, "results.json")

    def load_models(self):
        reg_path = os.path.join(self.outputs, "mlruns", "registry.json")
        if not (os.path.exists(reg_path) and os.path.exists(self._results_path())):
            raise FileNotFoundError("trained models not found - run `python scripts/run_pipeline.py` first")
        with open(reg_path) as f:
            reg = json.load(f)
        prod = lambda name: next(m for m in reg[name] if m["stage"] == "Production")
        pm, fm = prod(PRICING_MODEL), prod(FRAUD_MODEL)
        with open(pm["artifact"], "rb") as f:
            pricing = pickle.load(f)
        with open(fm["artifact"], "rb") as f:
            fraud = pickle.load(f)
        fraud["model"].set_params(n_jobs=1)  # one claim at a time: skip thread-pool start-up cost
        with open(self._results_path()) as f:
            results = json.load(f)
        self.models = dict(pricing=pricing["model"], pricing_version=pm["version"], pricing_metrics=pm["metrics"],
                           fraud=fraud["model"], fraud_threshold=float(fraud["threshold"]), fraud_version=fm["version"],
                           registry=reg, results=results, results_mtime=os.path.getmtime(self._results_path()), loaded_at=now_s())
        if hasattr(self, "log_buf"):
            self.log("MODEL", f"loaded pricing GBDT v{pm['version']} (Production, registry MAE ₹{pm['metrics']['mae']:.2f}) and fraud IsolationForest "
                              f"v{fm['version']} (threshold {self.models['fraud_threshold']:.4f}) from registry", "magenta")

    def maybe_reload(self):
        p = self._results_path()
        if os.path.exists(p) and os.path.getmtime(p) != self.models.get("results_mtime") and not self.pipeline_running:
            try:
                self.load_models()
                self.log("MODEL", "new pipeline results detected -> models hot-reloaded; dashboard metrics refreshed", "magenta")
            except Exception as e:  # half-written outputs; retry next tick
                self.log("MODEL", f"reload deferred: {e}", "yellow")

    @property
    def pipeline_running(self):
        return self.pipeline_proc is not None and self.pipeline_proc.poll() is None

    def start_retrain(self, fast=True):
        if self.pipeline_running:
            return False
        cmd = [sys.executable, os.path.join(ROOT, "scripts", "run_pipeline.py"), "--out", self.outputs] + (["--fast"] if fast else [])
        self.log("MLOPS", f"retraining pipeline started ({'fast' if fast else 'full'} grid) - output streams below", "magenta")
        self.pipeline_proc = subprocess.Popen(cmd, cwd=ROOT, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        return True

    # ------------------------------------------------------------------ pricing
    def _hist_hours(self, zone_id, weeks=12):
        """Realised disruption hours per week in the zone over the last 12 policy weeks (live lagged feature)."""
        lo = max(0, self.clock["sim_hour"] - weeks * HOURS_PER_WEEK)
        h = self.db.execute("SELECT COALESCE(SUM(hours),0) FROM events WHERE zone_id=? AND start_hour>=?", (zone_id, lo)).fetchone()[0]
        span = max(1.0, min(weeks, (self.clock["sim_hour"] - lo) / HOURS_PER_WEEK))
        return h / span if self.clock["sim_hour"] >= HOURS_PER_WEEK else None

    def quote(self, persona, zone_id, week_of_year=None, hourly_rate=None):
        V.validate_persona(persona)
        z = self.zones[zone_id]
        woy = self.week_of_year if week_of_year is None else week_of_year
        X = D.forecast_features(z["flood_score"], persona, woy, hist_hours=self._hist_hours(zone_id))
        if hourly_rate:
            X["hourly_rate"] = hourly_rate
        t = time.perf_counter()
        prem = float(np.clip(self.models["pricing"].predict(X)[0], D.PREMIUM_MIN, D.PREMIUM_MAX))
        ms = (time.perf_counter() - t) * 1000
        exp_loss = float(D.expected_loss_from_premium(prem))
        rate = float(X["hourly_rate"].iloc[0])
        # hyper-local comparison: same persona/week priced at the city's average flood exposure
        avg_flood = float(np.mean([q["flood_score"] for q in self.zones.values()]))
        Xa = X.copy(); Xa["flood_score"] = avg_flood
        city = float(np.clip(self.models["pricing"].predict(Xa)[0], D.PREMIUM_MIN, D.PREMIUM_MAX))
        return dict(premium=round(prem, 2), expected_loss=round(exp_loss, 2), expected_hours=round(exp_loss / (rate * T.PAYOUT_RATIO), 2),
                    city_avg_premium=round(city, 2), hyperlocal_adjustment=round(prem - city, 2),
                    max_weekly_payout=T.MAX_WEEKLY_PAYOUT, model_version=self.models["pricing_version"], latency_ms=round(ms, 2),
                    forecast=dict(rain_mm=round(float(X.rain_fc_mm.iloc[0]), 1), aqi=round(float(X.aqi_fc.iloc[0])),
                                  temp_max=round(float(X.temp_max_fc.iloc[0]), 1), hist_hours=round(float(X.hist_disrupt_hrs_12w.iloc[0]), 2)))

    def _issue_policy(self, w, quiet=False):
        q = self.quote(w["persona"], w["zone_id"], hourly_rate=w["hourly_rate"])
        self.db.execute("UPDATE policies SET status='EXPIRED' WHERE worker_id=? AND status='ACTIVE'", (w["worker_id"],))
        self.db.execute("INSERT INTO policies(worker_id,week_no,premium,expected_loss,max_weekly_payout,model_version,status,created_at) "
                        "VALUES (?,?,?,?,?,?,?,?)", (w["worker_id"], self.week_no, q["premium"], q["expected_loss"], q["max_weekly_payout"],
                                                     q["model_version"], "ACTIVE", now_s()))
        if not quiet:
            self.log("POLICY", f"{w['worker_id']} {w['name']} ({w['persona']}, {self.zones[w['zone_id']]['name']}): weekly premium "
                               f"₹{q['premium']:.2f} [ML v{q['model_version']}, hyper-local {q['hyperlocal_adjustment']:+.2f}] "
                               f"cover up to ₹{T.MAX_WEEKLY_PAYOUT:,.0f}/week", "blue")
        return q

    def _seed_workers(self, n):
        ws = synth_workers(list(self.zones), n)
        for w in ws:
            self.db.execute("INSERT INTO workers VALUES (?,?,?,?,?,?,?,?)", (w["worker_id"], w["name"], w["persona"], w["zone_id"], w["upi"],
                                                                            w["hourly_rate"], "VERIFIED", now_s()))
            self._issue_policy(w, quiet=True)
        prem = self.db.execute("SELECT SUM(premium), AVG(premium) FROM policies").fetchone()
        self.log("ONBOARD", f"seeded {n} synthetic delivery partners across {len(self.zones)} {self.city} zones; "
                            f"ML-priced weekly policies issued (₹{prem[0]:,.0f} premium, avg ₹{prem[1]:.2f})", "blue")

    def onboard(self, name, persona, zone_id, upi, worker_id=None):
        with self.lock:
            name, persona, upi = V.validate_name(name), V.validate_persona(persona), V.validate_upi(upi)
            zone_id = V.validate_zone(zone_id, set(self.zones))
            if worker_id:
                V.validate_worker_id(worker_id)
            else:
                n = self.db.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
                worker_id = f"GW{n + 1:04d}"
                while self.db.execute("SELECT 1 FROM workers WHERE worker_id=?", (worker_id,)).fetchone():
                    n += 1; worker_id = f"GW{n + 1:04d}"
            if self.db.execute("SELECT 1 FROM workers WHERE worker_id=?", (worker_id,)).fetchone():
                raise V.ValidationError("worker already registered")
            w = dict(worker_id=worker_id, name=name, persona=persona, zone_id=zone_id, upi=upi, hourly_rate=D.PERSONAS[persona]["rate"])
            self.db.execute("INSERT INTO workers VALUES (?,?,?,?,?,?,?,?)", (worker_id, name, persona, zone_id, upi, w["hourly_rate"], "VERIFIED", now_s()))
            self.log("ONBOARD", f"new partner {worker_id} {name} - {persona} in {self.zones[zone_id]['name']}, KYC verified (mock DigiLocker), UPI linked", "blue")
            q = self._issue_policy(w)
            return dict(worker=w, quote=q, token=V.sign_token(worker_id))

    # ------------------------------------------------------------------ admin controls
    def inject(self, zone_ids, kind, hours=4, fraud_rate=None):
        if kind not in SCENARIOS:
            raise V.ValidationError(f"scenario must be one of {list(SCENARIOS)}")
        hours = int(max(1, min(MAX_EVENT_HOURS, int(hours))))
        with self.lock:
            for z in zone_ids:
                z = V.validate_zone(z, set(self.zones))
                self.scenarios[z] = dict(kind=kind, hours_left=hours, total=hours, fraud_rate=fraud_rate)
                self.log("SIMULATE", f"{SCENARIOS[kind]['label']} injected into {self.zones[z]['name']} for {hours}h"
                                     + (f" with fraud ring (fraud rate {fraud_rate:.0%})" if fraud_rate else ""), "yellow")

    def replay_event(self, event_id):
        """Re-submit every claim of a settled event: the duplicate guard must reject all of them."""
        with self.lock:
            rows = self.db.execute("SELECT worker_id, zone_id, event_id, fraud_score, threshold, lost_hours FROM claims WHERE event_id=? "
                                   "AND decision NOT IN ('MONITORING')", (event_id,)).fetchall()
            before = self.db.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM payouts").fetchone()
            res = collections.Counter()
            for wid, zid, eid, sc, thr, lh in rows:
                rate = self.db.execute("SELECT hourly_rate FROM workers WHERE worker_id=?", (wid,)).fetchone()[0]
                d, _ = T.process_claim(dict(worker_id=wid, zone_id=zid, event_id=eid), sc, thr, self.guard, self.gateway, lh, rate)
                res[d] += 1
            after = self.db.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM payouts").fetchone()
            self.stats_dup = getattr(self, "stats_dup", 0) + res["REJECT_DUPLICATE"]
            self.log("DUPLICATE", f"replayed {len(rows)} claims of {event_id}: {dict(res)}; ledger unchanged "
                                  f"({before[0]} txns ₹{before[1]:,.0f} -> {after[0]} txns ₹{after[1]:,.0f})", "red")
            return dict(replayed=len(rows), decisions=dict(res), ledger_before=before, ledger_after=after)

    def review(self, claim_id, approve):
        with self.lock:
            r = self.db.execute("SELECT worker_id, zone_id, event_id, amount, decision FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
            if not r or r[4] != "HOLD_REVIEW":
                raise V.ValidationError("claim is not awaiting review")
            wid, zid, eid, amt, _ = r
            if approve:
                txn = self.gateway.pay(f"{wid}:{zid}:{eid}", wid, amt)
                self.db.execute("UPDATE claims SET decision='PAID_AFTER_REVIEW', txn_id=?, updated_at=? WHERE claim_id=?", (txn["txn_id"], now_s(), claim_id))
                self.log("REVIEW", f"claim #{claim_id} approved by insurer -> ₹{amt:,.2f} paid to {wid} ({txn['txn_id']})", "green")
            else:
                self.db.execute("UPDATE claims SET decision='REJECTED_FRAUD', updated_at=? WHERE claim_id=?", (now_s(), claim_id))
                self.log("REVIEW", f"claim #{claim_id} rejected as fraud by insurer ({wid})", "red")

    # ------------------------------------------------------------------ simulation loop
    def run_forever(self):
        self.log("ENGINE", f"parametric trigger monitor started: {len(self.zones)} zones, 1 simulated hour every {self.tick_seconds:g}s, "
                           f"weather source = {self.weather_name}", "green")
        while not self._stop.is_set():
            t = time.time()
            try:
                self.tick()
            except Exception as e:  # keep the monitor alive; surface the error
                self.log("ERROR", repr(e), "red")
            self._stop.wait(max(0.05, self.tick_seconds - (time.time() - t)))

    def stop(self): self._stop.set()

    def tick(self):
        with self.lock:
            self.maybe_reload()
            old_week = self.week_no
            self.clock["sim_hour"] += 1
            if self.week_no != old_week:
                self._renew_week()
            fired_any = []
            for zid, z in self.zones.items():
                r = self.weather.reading(z, self.week_of_year, self.hour_of_day)
                r["curfew"] = False
                sc = self.scenarios.get(zid)
                if sc:
                    k = 1 - abs((sc["total"] - sc["hours_left"]) - sc["total"] / 2) / max(1, sc["total"])  # storm peaks mid-window
                    SCENARIOS[sc["kind"]]["apply"](r, k, self.rng)
                    r["source"] = "simulated:" + sc["kind"]
                    sc["hours_left"] -= 1
                    if sc["hours_left"] <= 0:
                        del self.scenarios[zid]
                fired = T.evaluate_reading(r, r["curfew"])
                r["fired"] = fired
                self.current[zid] = r
                self.recent_readings.append(dict(rain=r["rain"], aqi=r["aqi"], temp=r["temp"]))
                self._handle_zone(zid, r, fired, sc)
                if fired: fired_any.append(zid)
            self._record_series()
            if self.clock["sim_hour"] % 12 == 0:
                self._update_live_drift()
            self._save_clock()

    def _open_event(self, zid):
        return self.db.execute("SELECT event_id, hours, severity, start_hour FROM events WHERE zone_id=? AND status='OPEN'", (zid,)).fetchone()

    def _handle_zone(self, zid, r, fired, sc):
        ev = self._open_event(zid)
        z = self.zones[zid]
        if fired and not ev:
            eid = f"EV{self.clock['sim_hour']:05d}Z{zid:02d}"
            sev = T.severity(r, fired)
            self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (eid, zid, ",".join(fired), r["source"], self.clock["sim_hour"], 1,
                                                                                   r["rain"], r["aqi"], r["temp"], sev, "OPEN", now_s()))
            workers = self.db.execute("SELECT w.worker_id FROM workers w JOIN policies p ON p.worker_id=w.worker_id AND p.status='ACTIVE' "
                                      "WHERE w.zone_id=?", (zid,)).fetchall()
            for (wid,) in workers:
                self.db.execute("INSERT INTO claims(worker_id,zone_id,event_id,week_no,decision,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                                (wid, zid, eid, self.week_no, "MONITORING", now_s(), now_s()))
            self.log("TRIGGER", f"{z['name']}: {', '.join(fired)} breached (rain {r['rain']:.1f} mm/hr, AQI {r['aqi']:.0f}, "
                                f"temp {r['temp']:.1f}°C{', curfew' if r['curfew'] else ''}) -> event {eid} opened, severity {sev}", "red")
            self.log("CLAIM", f"zero-touch: {len(workers)} claims auto-initiated for active policies in {z['name']} (no worker action needed)", "yellow")
            if sc and sc.get("fraud_rate"):
                self._event_fraud_rate = getattr(self, "_event_fraud_rate", {}); self._event_fraud_rate[eid] = sc["fraud_rate"]
        elif fired and ev:
            eid, hours, sev, _ = ev
            self.db.execute("UPDATE events SET hours=hours+1, severity=MAX(severity, ?), peak_rain=MAX(peak_rain, ?), peak_aqi=MAX(peak_aqi, ?), "
                            "peak_temp=MAX(peak_temp, ?), triggers=? WHERE event_id=?",
                            (T.severity(r, fired), r["rain"], r["aqi"], r["temp"], ",".join(sorted(set(fired) | set(self._ev_triggers(eid)))), eid))
            if hours + 1 >= MAX_EVENT_HOURS:
                self._close_event(eid)
        elif ev and not fired:
            self._close_event(ev[0])

    def _ev_triggers(self, eid):
        return [t for t in self.db.execute("SELECT triggers FROM events WHERE event_id=?", (eid,)).fetchone()[0].split(",") if t]

    def _close_event(self, eid):
        zid, hours, sev, trig = self.db.execute("SELECT zone_id, hours, severity, triggers FROM events WHERE event_id=?", (eid,)).fetchone()
        self.db.execute("UPDATE events SET status='CLOSED' WHERE event_id=?", (eid,))
        z = self.zones[zid]
        self.log("EVENT", f"{eid} in {z['name']} closed after {hours}h ({trig}); validated disruption window = {hours}h x severity {sev}", "cyan")
        claims = self.db.execute("SELECT c.claim_id, c.worker_id, w.name, w.persona, w.hourly_rate, w.upi FROM claims c "
                                 "JOIN workers w ON w.worker_id=c.worker_id WHERE c.event_id=? AND c.decision='MONITORING'", (eid,)).fetchall()
        frate = getattr(self, "_event_fraud_rate", {}).pop(eid, None) or self.fraud_rate
        thr = self.models["fraud_threshold"]
        tally = collections.Counter(); paid_total = 0.0
        for cid, wid, name, persona, rate, upi in claims:
            t0 = time.perf_counter()
            kind, tel = draw_live_claim(self.rng, frate)
            if kind == "genuine":  # activity validation from the (mock) platform API: orders before the event
                tel["orders_before_event"] = float(orders_in_window(persona, 2, False, self.rng))
            score = float(F.anomaly_score(self.models["fraud"], pd.DataFrame([tel])[F.FRAUD_FEATURES])[0])
            lost = float(min(hours, MAX_EVENT_HOURS) * sev)
            paid_week = self.db.execute("SELECT COALESCE(SUM(amount),0) FROM payouts WHERE worker_id=? AND week_no=?", (wid, self.week_no)).fetchone()[0]
            amount = T.payout_amount(lost, rate, paid_week)
            decision, txn = T.process_claim(dict(worker_id=wid, zone_id=zid, event_id=eid), score, thr, self.guard, self.gateway, lost, rate, paid_week)
            ms = (time.perf_counter() - t0) * 1000
            reasons = F.rule_reasons(tel)
            self.db.execute("UPDATE claims SET lost_hours=?, amount=?, fraud_score=?, threshold=?, reasons=?, telemetry=?, true_kind=?, decision=?, "
                            "txn_id=?, decided_ms=?, updated_at=? WHERE claim_id=?",
                            (lost, amount, score, thr, "; ".join(reasons), json.dumps(tel), kind, decision, txn["txn_id"] if txn else None, ms, now_s(), cid))
            tally[decision] += 1
            if decision == "PAID":
                paid_total += amount
                self.log("PAYOUT", f"{wid} {name}: ₹{amount:,.2f} -> {upi} via UPI ({txn['txn_id']}) | fraud score {score:.3f} < {thr:.3f} | "
                                   f"{lost:.1f} lost h x ₹{rate:.0f} x 70% | {ms:.1f} ms", "green")
            elif decision == "HOLD_REVIEW":
                self.log("FRAUD", f"{wid} {name}: HELD for review - anomaly score {score:.3f} ≥ {thr:.3f} "
                                  f"({', '.join(reasons) or 'multivariate anomaly'}) [simulated truth: {kind}]", "red")
            else:
                self.log("CLAIM", f"{wid}: {decision}", "yellow")
        self.log("SETTLE", f"{eid}: {len(claims)} claims -> {dict(tally)}; ₹{paid_total:,.2f} paid instantly", "green")

    def _renew_week(self):
        ws = self.db.execute("SELECT worker_id, name, persona, zone_id, upi, hourly_rate FROM workers").fetchall()
        for row in ws:
            self._issue_policy(dict(zip(("worker_id", "name", "persona", "zone_id", "upi", "hourly_rate"), row)), quiet=True)
        prem = self.db.execute("SELECT SUM(premium), AVG(premium) FROM policies WHERE week_no=?", (self.week_no,)).fetchone()
        self.log("RENEW", f"policy week {self.week_no} (week-of-year {self.week_of_year}): {len(ws)} policies re-priced by ML model "
                          f"v{self.models['pricing_version']} using live 12-week disruption history -> ₹{prem[0]:,.0f} premium (avg ₹{prem[1]:.2f})", "blue")

    def _record_series(self):
        prem, paid = self._totals()
        rs = list(self.current.values())
        self.series.append(dict(h=self.clock["sim_hour"], label=f"{self.day_name} {self.hour_of_day:02d}h", premiums=prem, payouts=paid,
                                max_rain=max(r["rain"] for r in rs), max_aqi=max(r["aqi"] for r in rs), max_temp=max(r["temp"] for r in rs),
                                zones_disrupted=sum(bool(r["fired"]) for r in rs)))

    def _totals(self):
        prem = self.db.execute("SELECT COALESCE(SUM(premium),0) FROM policies").fetchone()[0]
        paid = self.db.execute("SELECT COALESCE(SUM(amount),0) FROM payouts").fetchone()[0]
        return float(prem), float(paid)

    # ------------------------------------------------------------------ live drift
    def _build_drift_reference(self):
        """Seasonally matched reference: 14 full days of the undisturbed feed for the current week-of-year
        (comparing against another season, or a partial day, raises false alarms -- see report Table 5.5)."""
        from data_collection.env_collector import MockWeather
        ref_src, rows = MockWeather(seed=99), []
        for z in self.zones.values():
            for h in range(24 * 14):
                rows.append(ref_src.reading(z, self.week_of_year, h % 24))
        ref = pd.DataFrame(rows)
        return dict(rain=ref.rain.values, aqi=ref.aqi.values, temp=ref.temp.values)

    def _update_live_drift(self):
        if len(self.recent_readings) < 72 * len(self.zones):  # need 3 full diurnal cycles before judging
            return
        cur = pd.DataFrame(list(self.recent_readings))
        out = {}
        for f in ("rain", "aqi", "temp"):
            v = DR.psi(self._drift_ref[f], cur[f].values)
            out[f] = dict(psi=round(v, 3), status=DR.psi_status(v))
        prev = {k: v["status"] for k, v in self.live_drift.items()}
        self.live_drift = out
        for f, v in out.items():
            if v["status"] == "significant" and prev.get(f) != "significant":
                self.log("DRIFT", f"live {f} distribution drifted from the seasonal reference (PSI {v['psi']:.3f} ≥ 0.2) -> early warning; "
                                  f"review thresholds / schedule retraining", "yellow")

    # ------------------------------------------------------------------ read models for the dashboards
    def forecast(self):
        """Next-week predictive analytics: ML premium per zone/persona -> expected disruption hours & claim liability."""
        woy = (self.week_of_year + 1) % 52
        rows = []
        counts = dict(self.db.execute("SELECT zone_id, COUNT(*) FROM workers GROUP BY zone_id").fetchall())
        by_zp = self.db.execute("SELECT zone_id, persona, COUNT(*), AVG(hourly_rate) FROM workers GROUP BY zone_id, persona").fetchall()
        mix = collections.defaultdict(list)
        for zid, p, n, rate in by_zp:
            mix[zid].append((p, n, rate))
        for zid, z in self.zones.items():
            liab, hours, prem_sum, n_tot = 0.0, [], 0.0, 0
            per_persona = {}
            for p in D.PERSONAS:
                q = self.quote(p, zid, week_of_year=woy)
                per_persona[p] = q["premium"]
            for p, n, rate in mix.get(zid, []):
                q = self.quote(p, zid, week_of_year=woy, hourly_rate=rate)
                liab += q["expected_loss"] * n; prem_sum += q["premium"] * n; n_tot += n; hours.append(q["expected_hours"])
            eh = float(np.mean(hours)) if hours else self.quote("food", zid, week_of_year=woy)["expected_hours"]
            rows.append(dict(zone_id=zid, name=z["name"], flood_score=z["flood_score"], workers=counts.get(zid, 0), premiums=per_persona,
                             expected_hours=round(eh, 2), expected_claims_inr=round(liab, 0), expected_premium_inr=round(prem_sum, 0),
                             risk="high" if eh >= 4 else ("medium" if eh >= 1.5 else "low")))
        return dict(week_of_year=woy, zones=rows, total_expected_claims=round(sum(r["expected_claims_inr"] for r in rows), 0),
                    total_expected_premium=round(sum(r["expected_premium_inr"] for r in rows), 0))

    def summary(self):
        with self.lock:
            q1 = lambda sql, *a: self.db.execute(sql, a).fetchone()[0]
            prem, paid = self._totals()
            dec = dict(self.db.execute("SELECT decision, COUNT(*) FROM claims GROUP BY decision").fetchall())
            live = self.db.execute("SELECT true_kind, decision FROM claims WHERE true_kind IS NOT NULL").fetchall()
            inj = [d for k, d in live if k != "genuine"]
            gen = [d for k, d in live if k == "genuine"]
            flagged = lambda d: d in ("HOLD_REVIEW", "REJECTED_FRAUD", "PAID_AFTER_REVIEW")
            zones = []
            wcount = dict(self.db.execute("SELECT zone_id, COUNT(*) FROM workers GROUP BY zone_id").fetchall())
            zone_paid = dict(self.db.execute("SELECT c.zone_id, SUM(p.amount) FROM payouts p JOIN claims c ON c.txn_id=p.txn_id GROUP BY c.zone_id").fetchall())
            zone_prem = dict(self.db.execute("SELECT w.zone_id, SUM(p.premium) FROM policies p JOIN workers w ON w.worker_id=p.worker_id GROUP BY w.zone_id").fetchall())
            for zid, z in self.zones.items():
                r = self.current.get(zid, {})
                ev = self._open_event(zid)
                zones.append(dict(id=zid, name=z["name"], flood_score=z["flood_score"], rain=r.get("rain"), aqi=r.get("aqi"), temp=r.get("temp"),
                                  curfew=r.get("curfew"), fired=r.get("fired", []), source=r.get("source"), event_id=ev[0] if ev else None,
                                  event_hours=ev[1] if ev else 0, workers=wcount.get(zid, 0), scenario=self.scenarios.get(zid, {}).get("kind"),
                                  premiums=round(zone_prem.get(zid, 0) or 0, 2), payouts=round(zone_paid.get(zid, 0) or 0, 2),
                                  loss_ratio=round((zone_paid.get(zid, 0) or 0) / zone_prem[zid], 3) if zone_prem.get(zid) else 0))
            ev_cols = ("event_id", "zone_id", "triggers", "source", "start_hour", "hours", "peak_rain", "peak_aqi", "peak_temp", "severity", "status")
            events = [dict(zip(ev_cols, r)) for r in self.db.execute(f"SELECT {','.join(ev_cols)} FROM events ORDER BY start_hour DESC LIMIT 15")]
            for e in events:
                e["zone"] = self.zones[e["zone_id"]]["name"]
                e["claims"] = q1("SELECT COUNT(*) FROM claims WHERE event_id=?", e["event_id"])
                e["paid"] = q1("SELECT COALESCE(SUM(amount),0) FROM claims WHERE event_id=? AND decision IN ('PAID','PAID_AFTER_REVIEW')", e["event_id"])
            cl_cols = ("claim_id", "worker_id", "zone_id", "event_id", "lost_hours", "amount", "fraud_score", "threshold", "reasons", "true_kind",
                       "decision", "txn_id", "decided_ms", "updated_at")
            claims = [dict(zip(cl_cols, r)) for r in self.db.execute(
                f"SELECT {','.join(cl_cols)} FROM claims WHERE decision!='MONITORING' ORDER BY updated_at DESC, claim_id DESC LIMIT 60")]
            for cl in claims:
                cl["zone"] = self.zones[cl["zone_id"]]["name"]
            held = [cl for cl in claims if cl["decision"] == "HOLD_REVIEW"]
            dm = [r[0] for r in self.db.execute("SELECT decided_ms FROM claims WHERE decided_ms IS NOT NULL ORDER BY claim_id DESC LIMIT 500")]
            res = self.models["results"]
            return dict(
                clock=dict(sim_hour=self.clock["sim_hour"], week_no=self.week_no, week_of_year=self.week_of_year, day=self.day_name,
                           hour=self.hour_of_day, tick_seconds=self.tick_seconds, weather=self.weather_name, city=self.city),
                kpis=dict(workers=q1("SELECT COUNT(*) FROM workers"), active_policies=q1("SELECT COUNT(*) FROM policies WHERE status='ACTIVE'"),
                          premiums=round(prem, 2), payouts=round(paid, 2), loss_ratio=round(paid / prem, 4) if prem else 0.0,
                          avg_premium=round(q1("SELECT COALESCE(AVG(premium),0) FROM policies WHERE status='ACTIVE'"), 2),
                          week_premiums=round(q1("SELECT COALESCE(SUM(premium),0) FROM policies WHERE week_no=?", self.week_no), 2),
                          week_payouts=round(q1("SELECT COALESCE(SUM(amount),0) FROM payouts WHERE week_no=?", self.week_no), 2),
                          events_total=q1("SELECT COUNT(*) FROM events"), events_open=q1("SELECT COUNT(*) FROM events WHERE status='OPEN'"),
                          claims_total=sum(dec.values()), decisions=dec, duplicates_blocked=getattr(self, "stats_dup", 0),
                          decision_ms_p50=round(float(np.percentile(dm, 50)), 2) if dm else None,
                          decision_ms_p95=round(float(np.percentile(dm, 95)), 2) if dm else None),
                live_fraud=dict(scored=len(live), injected=len(inj), caught=sum(flagged(d) for d in inj),
                                genuine=len(gen), false_alarms=sum(flagged(d) for d in gen),
                                live_recall=round(sum(flagged(d) for d in inj) / len(inj), 3) if inj else None,
                                live_fpr=round(sum(flagged(d) for d in gen) / len(gen), 3) if gen else None,
                                threshold=self.models["fraud_threshold"]),
                zones=zones, events=events, claims=claims[:40], held=held, series=list(self.series), live_drift=self.live_drift,
                scenarios={k: v["kind"] for k, v in self.scenarios.items()},
                models=dict(pricing_version=self.models["pricing_version"], pricing_mae=self.models["pricing_metrics"]["mae"],
                            fraud_version=self.models["fraud_version"], loaded_at=self.models["loaded_at"],
                            results_generated_at=res.get("generated_at"), pipeline_running=self.pipeline_running, fast_mode=res.get("fast_mode")),
                log=list(self.log_buf)[-60:])

    def ml_report(self):
        R = self.models["results"]
        keep = ("generated_at", "fast_mode", "data", "tracking_backend", "pricing", "best_params", "best_family", "tuning", "importance",
                "persona_metrics", "test_pred", "monsoon_vs_dry", "noise_floor_mae", "fraud", "triggers", "hourly_rows", "data_drift",
                "concept", "registry", "performance", "runtime_s")
        out = {k: R.get(k) for k in keep}
        out["n_runs"] = len(R.get("runs", []))
        try:
            sys.path.insert(0, os.path.join(ROOT, "scripts"))
            import check_gate
            out["gate"] = check_gate.run(self._results_path())
        except Exception as e:
            out["gate"] = [dict(check="gate unavailable", threshold="", measured=0, result=str(e))]
        return out

    def worker_view(self, worker_id):
        with self.lock:
            w = self.db.execute("SELECT worker_id, name, persona, zone_id, upi, hourly_rate, kyc_status, created_at FROM workers WHERE worker_id=?",
                                (worker_id,)).fetchone()
            if not w:
                return None
            w = dict(zip(("worker_id", "name", "persona", "zone_id", "upi", "hourly_rate", "kyc_status", "created_at"), w))
            pol = self.db.execute("SELECT policy_id, week_no, premium, expected_loss, max_weekly_payout, model_version, status, created_at "
                                  "FROM policies WHERE worker_id=? ORDER BY policy_id DESC LIMIT 8", (worker_id,)).fetchall()
            pol = [dict(zip(("policy_id", "week_no", "premium", "expected_loss", "max_weekly_payout", "model_version", "status", "created_at"), p)) for p in pol]
            cls = self.db.execute("SELECT c.claim_id, c.event_id, e.triggers, c.lost_hours, c.amount, c.decision, c.txn_id, c.updated_at FROM claims c "
                                  "JOIN events e ON e.event_id=c.event_id WHERE c.worker_id=? ORDER BY c.claim_id DESC LIMIT 20", (worker_id,)).fetchall()
            cls = [dict(zip(("claim_id", "event_id", "triggers", "lost_hours", "amount", "decision", "txn_id", "updated_at"), r)) for r in cls]
            paid = self.db.execute("SELECT COALESCE(SUM(amount),0) FROM payouts WHERE worker_id=?", (worker_id,)).fetchone()[0]
            paid_week = self.db.execute("SELECT COALESCE(SUM(amount),0) FROM payouts WHERE worker_id=? AND week_no=?", (worker_id, self.week_no)).fetchone()[0]
            spent = self.db.execute("SELECT COALESCE(SUM(premium),0) FROM policies WHERE worker_id=?", (worker_id,)).fetchone()[0]
            z = self.zones[w["zone_id"]]
            r = self.current.get(w["zone_id"], {})
            return dict(worker=w, zone=dict(name=z["name"], flood_score=z["flood_score"], rain=r.get("rain"), aqi=r.get("aqi"), temp=r.get("temp"),
                                            fired=r.get("fired", []), event=(self._open_event(w["zone_id"]) or [None])[0]),
                        active_policy=next((p for p in pol if p["status"] == "ACTIVE"), None), policies=pol, claims=cls,
                        protected_total=round(paid, 2), paid_this_week=round(paid_week, 2),
                        remaining_cover=round(T.MAX_WEEKLY_PAYOUT - paid_week, 2), premiums_paid=round(spent, 2),
                        next_week_quote=self.quote(w["persona"], w["zone_id"], week_of_year=(self.week_of_year + 1) % 52, hourly_rate=w["hourly_rate"]),
                        clock=dict(week_no=self.week_no, day=self.day_name, hour=self.hour_of_day))
