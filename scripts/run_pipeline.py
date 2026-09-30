"""End-to-end MLOps pipeline: train -> track -> register -> monitor drift -> retrain -> benchmark.

Usage: python scripts/run_pipeline.py [--out outputs] [--fast]
Every number shown on the admin dashboard's "Model performance" panels is written to outputs/results.json
by this script. Trained models are saved to outputs/models/ and versioned in outputs/mlruns/registry.json.
"""
import argparse, json, os, pickle, shutil, sys, time
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from giginsure import data as D, pricing as P, fraud as F, drift as DR, triggers as T
from giginsure.tracking import Tracker, ModelRegistry
from giginsure.console import banner, stage, info, ok, warn, table, c
from sklearn.base import clone
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, roc_curve, precision_recall_curve
from sklearn.inspection import permutation_importance

N_STAGES = 8
MODEL_NAME = "giginsure-weekly-premium"


def _downsample_curve(x, y, n=120):
    idx = np.unique(np.linspace(0, len(x) - 1, min(n, len(x))).astype(int))
    return [float(v) for v in np.asarray(x)[idx]], [float(v) for v in np.asarray(y)[idx]]


def main(out, fast=False):
    shutil.rmtree(os.path.join(out, "mlruns"), ignore_errors=True)
    mdir = os.path.join(out, "models"); os.makedirs(mdir, exist_ok=True)
    R = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "fast_mode": bool(fast)}
    t0 = time.time()
    banner("GigInsure MLOps pipeline  |  data -> pricing -> fraud -> triggers -> drift -> registry")

    # ---- 1. data
    stage(1, N_STAGES, "Synthetic data generation & temporal split")
    df = D.generate_weekly()
    tr, va, te, mon = D.split_temporal(df)
    trva = pd.concat([tr, va]); X, y = trva[D.FEATURES], trva[D.TARGET]
    R["data"] = dict(rows=len(df), zones=int(df.zone_id.nunique()), weeks=int(df.week.max() + 1), train_rows=len(tr),
                     val_rows=len(va), test_rows=len(te), monitor_rows=len(mon),
                     premium_min=float(df[D.TARGET].min()), premium_max=float(df[D.TARGET].max()), premium_mean=float(df[D.TARGET].mean()))
    info(f"weekly pricing table: {len(df):,} rows = {R['data']['weeks']} weeks x {R['data']['zones']} zones x 3 personas")
    table([dict(part="model selection (train+val)", weeks=f"0-{D.VAL_END-1}", rows=len(trva)),
           dict(part="test (held out)", weeks=f"{D.VAL_END}-{D.TEST_END-1}", rows=len(te)),
           dict(part="monitoring stream (drift replay)", weeks=f"{D.TEST_END}-{D.N_WEEKS-1}", rows=len(mon))],
          ["part", "weeks", "rows"], ["partition", "weeks", "rows"])
    ok(f"premium band ₹{R['data']['premium_min']:.2f} - ₹{R['data']['premium_max']:.2f}  (mean ₹{R['data']['premium_mean']:.2f})")
    trk = Tracker("giginsure-pricing", root=os.path.join(out, "mlruns"), exp_id="1")
    reg = ModelRegistry(os.path.join(out, "mlruns", "registry.json"))
    R["tracking_backend"] = trk.backend
    info(f"experiment tracking backend: {c(trk.backend, 'bold')}  ->  {os.path.join(out, 'mlruns')}")

    # ---- 2. baselines
    stage(2, N_STAGES, "Weekly premium model: baselines (5-fold temporal CV)")
    results = {}
    for name, m in P.baselines().items():
        with trk.start_run(name, tags={"stage": "baseline", "model_family": name}):
            t = time.time(); cv = P.cv_scores(lambda m=m: clone(m), X, y)
            mm = clone(m).fit(X, y); fit_s = time.time() - t
            pt = P.clip_premium(mm.predict(te[D.FEATURES])); tm = P.metrics(te[D.TARGET], pt)
            trk.log_params({"model": name, "n_features": len(D.FEATURES), "cv": "TimeSeriesSplit(5)"})
            trk.log_metrics({**cv, **{f"test_{k}": v for k, v in tm.items()}, "fit_seconds": fit_s})
            results[name] = dict(cv=cv, test=tm, fit_seconds=fit_s)
            info(f"{name:<20} CV MAE ₹{cv['cv_mae_mean']:.3f} ± {cv['cv_mae_std']:.3f}   test MAE ₹{tm['mae']:.3f}   ({fit_s:.1f}s)")

    # ---- 3. tuning
    configs = P.grid_configs(fast)
    fams = [("gbdt", P.make_gbdt)] + ([("xgb", P.make_xgb)] if P.HAVE_XGB else [])
    stage(3, N_STAGES, f"Hyper-parameter search: {len(configs) * len(fams)} GBDT configurations (selection by CV only)")
    grid = []
    for fam, fn in fams:
        for cfg in configs:
            nm = f"{fam}_lr{cfg['learning_rate']}_d{cfg['max_depth']}_n{cfg['n_estimators']}"
            with trk.start_run(nm, tags={"stage": "tuning", "model_family": fam}):
                t = time.time(); cv = P.cv_scores(lambda cfg=cfg, fn=fn: fn(**cfg), X, y); dt = time.time() - t
                trk.log_params({"model": fam, **cfg, "cv": "TimeSeriesSplit(5)"}); trk.log_metrics({**cv, "cv_seconds": dt})
                grid.append(dict(run=nm, family=fam, **cfg, **cv))
                info(f"{nm:<26} CV MAE ₹{cv['cv_mae_mean']:.3f} ± {cv['cv_mae_std']:.3f}  ({dt:.1f}s)")
    grid_df = pd.DataFrame(grid).sort_values("cv_mae_mean").reset_index(drop=True)
    best = {k: (int(grid_df.loc[0, k]) if k in ("max_depth", "n_estimators") else float(grid_df.loc[0, k]))
            for k in ("learning_rate", "max_depth", "n_estimators", "subsample")}
    best_fn = dict(fams)[grid_df.loc[0, "family"]]
    R["tuning"] = grid_df.to_dict("records"); R["best_params"] = best; R["best_family"] = grid_df.loc[0, "family"]
    ok(f"best configuration: {grid_df.loc[0, 'run']}  (CV MAE ₹{grid_df.loc[0, 'cv_mae_mean']:.3f})")

    # ---- 4. champion + registry
    stage(4, N_STAGES, "Champion refit, test evaluation & model registry")
    with trk.start_run("gbdt_champion", tags={"stage": "champion", "model_family": R["best_family"]}):
        champ = best_fn(**best).fit(X, y)
        pt = P.clip_premium(champ.predict(te[D.FEATURES])); tm = P.metrics(te[D.TARGET], pt)
        cv = grid_df.loc[0, ["cv_mae_mean", "cv_mae_std", "cv_rmse_mean"]].to_dict()
        trk.log_params({"model": R["best_family"], **best, "train_weeks": f"0-{D.VAL_END-1}", "test_weeks": f"{D.VAL_END}-{D.TEST_END-1}"})
        trk.log_metrics({**cv, **{f"test_{k}": v for k, v in tm.items()}})
        v1_path = os.path.join(mdir, "pricing_v1.pkl")
        with open(v1_path, "wb") as f:
            pickle.dump(dict(model=champ, features=D.FEATURES, version=1), f)
        trk.log_artifact(v1_path, "model")
        run_id = trk._rec["run_id"]
        results["gbdt_champion"] = dict(cv=cv, test=tm)
    rng_nf = np.random.RandomState(1); R["noise_floor_mae"] = float(np.abs(rng_nf.normal(0, 1.2, 200000)).mean())
    R["pricing"] = results
    table([dict(model=k, cv=f"{v['cv']['cv_mae_mean']:.2f} ± {v['cv']['cv_mae_std']:.2f}", **v["test"]) for k, v in results.items()],
          ["model", "cv", "mae", "rmse", "r2", "mape", "within_2rs"],
          ["model", "CV MAE (₹)", "test MAE", "RMSE", "R²", "MAPE %", "±₹2 %"], nd=3,
          highlight=lambda r: "green" if r["model"] == "gbdt_champion" else None)
    lin = results["ridge_linear"]["test"]["mae"]
    info(f"MAE reduction vs linear baseline: {c(f'{(1 - tm['mae'] / lin) * 100:.1f}%', 'bold')}   (label-noise floor ₹{R['noise_floor_mae']:.2f})")
    v = reg.register(MODEL_NAME, run_id, tm, artifact=v1_path); reg.transition(MODEL_NAME, v, "Staging")
    gate_ok = tm["mae"] <= lin * 0.9
    if gate_ok: reg.transition(MODEL_NAME, v, "Production")
    R["registry_v1"] = dict(version=v, promoted=bool(gate_ok))
    (ok if gate_ok else warn)(f"registry: {MODEL_NAME} v{v} -> Staging -> {'Production' if gate_ok else 'held in Staging'} "
                              f"(gate: test MAE ≤ 90% of linear baseline)")
    pi = permutation_importance(champ, te[D.FEATURES], te[D.TARGET], n_repeats=5, random_state=0, scoring="neg_mean_absolute_error")
    R["importance"] = sorted([(f, float(m)) for f, m in zip(D.FEATURES, pi.importances_mean)], key=lambda x: -x[1])
    info("top drivers (permutation importance): " + ", ".join(f"{f} {m:.2f}" for f, m in R["importance"][:5]))
    sl = {}
    for p in ("food", "qcom", "ecom"):
        mk = (te.persona == p).values; sl[p] = P.metrics(te[D.TARGET][mk], pt[mk])
    R["persona_metrics"] = sl
    table([dict(persona=k, **m) for k, m in sl.items()], ["persona", "mae", "rmse", "r2", "within_2rs"],
          ["persona", "test MAE", "RMSE", "R²", "±₹2 %"])
    idx = np.random.RandomState(0).choice(len(te), min(600, len(te)), replace=False)
    R["test_pred"] = dict(y=te[D.TARGET].values[idx].tolist(), p=pt[idx].tolist())
    woy = te.week % 52; mk = ((woy >= 24) & (woy <= 40)).values
    R["monsoon_vs_dry"] = dict(monsoon=P.metrics(te[D.TARGET][mk], pt[mk]), other=P.metrics(te[D.TARGET][~mk], pt[~mk]),
                               n_monsoon=int(mk.sum()), n_other=int((~mk).sum()))

    # ---- 5. fraud
    stage(5, N_STAGES, "AI fraud detection: Isolation Forest vs LOF vs rule baseline")
    ftrk = Tracker("giginsure-fraud", root=os.path.join(out, "mlruns"), exp_id="2")
    cl = D.generate_claims()
    a, b = train_test_split(cl, test_size=0.4, random_state=0, stratify=cl.is_fraud)
    vl, ts = train_test_split(b, test_size=0.5, random_state=0, stratify=b.is_fraud)
    info(f"claims: {len(cl):,} ({cl.is_fraud.mean()*100:.1f}% fraud)  split train/val/test = {len(a):,}/{len(vl):,}/{len(ts):,}")
    fr = {}
    for ne in (100, 300):
        with ftrk.start_run(f"iforest_{ne}", tags={"stage": "tuning", "model_family": "isolation_forest"}):
            m = F.fit_iforest(a[F.FRAUD_FEATURES], n_estimators=ne)
            sv = F.anomaly_score(m, vl[F.FRAUD_FEATURES]); thr = F.threshold_at_fpr(sv[vl.is_fraud.values == 0], 0.02)
            ev = F.evaluate(vl.is_fraud, sv, thr)
            ftrk.log_params({"n_estimators": ne, "contamination": 0.06, "target_fpr": 0.02}); ftrk.log_metrics({f"val_{k}": v for k, v in ev.items()})
            fr[f"iforest_{ne}"] = dict(val=ev, thr=thr, model=m)
            info(f"iforest_{ne:<4} val PR-AUC {ev['pr_auc']:.3f}  recall {ev['recall']:.3f}  FPR {ev['fpr']:.3f}")
    bestk = max(("iforest_100", "iforest_300"), key=lambda k: fr[k]["val"]["pr_auc"])
    with ftrk.start_run("iforest_champion", tags={"stage": "champion", "model_family": "isolation_forest"}):
        m, thr = fr[bestk]["model"], fr[bestk]["thr"]
        m.set_params(n_jobs=1)  # single-claim scoring is faster without a thread pool
        st = F.anomaly_score(m, ts[F.FRAUD_FEATURES]); ev = F.evaluate(ts.is_fraud, st, thr)
        ftrk.log_params({"selected": bestk, "threshold": thr}); ftrk.log_metrics({f"test_{k}": v for k, v in ev.items()})
        fpath = os.path.join(mdir, "fraud_iforest.pkl")
        with open(fpath, "wb") as f:
            pickle.dump(dict(model=m, threshold=thr, features=F.FRAUD_FEATURES, selected=bestk), f)
        ftrk.log_artifact(fpath, "model"); frun = ftrk._rec["run_id"]
    fv = reg.register("giginsure-fraud-iforest", frun, ev, artifact=fpath)
    reg.transition("giginsure-fraud-iforest", fv, "Staging"); reg.transition("giginsure-fraud-iforest", fv, "Production")
    from sklearn.neighbors import LocalOutlierFactor
    lof = LocalOutlierFactor(n_neighbors=35, novelty=True, contamination=0.06).fit(a[F.FRAUD_FEATURES].values)
    sl_v = -lof.score_samples(vl[F.FRAUD_FEATURES].values); sl_t = -lof.score_samples(ts[F.FRAUD_FEATURES].values)
    with ftrk.start_run("lof_baseline", tags={"stage": "baseline", "model_family": "lof"}):
        thr_l = F.threshold_at_fpr(sl_v[vl.is_fraud.values == 0], 0.02); ev_l = F.evaluate(ts.is_fraud, sl_t, thr_l)
        ftrk.log_metrics({f"test_{k}": v for k, v in ev_l.items()})
    rs_t = F.rule_score(ts)
    with ftrk.start_run("rule_baseline", tags={"stage": "baseline", "model_family": "rules"}):
        ev_r = F.evaluate(ts.is_fraud, rs_t, 1.0); ftrk.log_metrics({f"test_{k}": v for k, v in ev_r.items()})
    table([dict(detector=f"Isolation Forest ({bestk})", **ev), dict(detector="Rule baseline (5 rules)", **ev_r),
           dict(detector="Local Outlier Factor", **ev_l)],
          ["detector", "precision", "recall", "f1", "roc_auc", "pr_auc", "fpr"],
          ["detector", "precision", "recall", "F1", "ROC-AUC", "PR-AUC", "FPR"],
          highlight=lambda r: "green" if r["detector"].startswith("Isolation") else None)
    info(f"confusion (test): TP {ev['tp']}  FP {ev['fp']}  FN {ev['fn']}  TN {ev['tn']}   alarm threshold {thr:.4f}")
    kinds = {}
    for k in ("spoof", "presence", "farming"):
        mk = (ts.kind == k).values; kinds[k] = dict(n=int(mk.sum()), recall=float((st[mk] >= thr).mean()))
    info("recall by fraud type: " + ", ".join(f"{k} {v['recall']*100:.1f}% (n={v['n']})" for k, v in kinds.items()))
    fpr_c, tpr_c, _ = roc_curve(ts.is_fraud, st); pr_p, pr_r, _ = precision_recall_curve(ts.is_fraud, st)
    R["fraud"] = dict(selected=bestk, threshold=float(thr), iforest=ev, lof=ev_l, rules=ev_r, by_kind=kinds, n_test=len(ts),
                      n_fraud_test=int(ts.is_fraud.sum()), roc=_downsample_curve(fpr_c, tpr_c), pr=_downsample_curve(pr_r[::-1], pr_p[::-1]),
                      val={k: v["val"] for k, v in fr.items()})

    # ---- 6. triggers
    stage(6, N_STAGES, "Parametric triggers vs ground truth (noisy sensor readings)")
    hw = D.generate_hourly_weather()
    obs = T.evaluate_triggers(hw, "obs"); tru = T.evaluate_triggers(hw, "true")
    trg = {}
    for name in list(T.THRESHOLDS) + ["any"]:
        yt, yp = tru[name].values.astype(int), obs[name].values.astype(int)
        trg[name] = dict(events=int(yt.sum()), precision=float(precision_score(yt, yp, zero_division=0)),
                         recall=float(recall_score(yt, yp, zero_division=0)), f1=float(f1_score(yt, yp, zero_division=0)))
    R["triggers"] = trg; R["hourly_rows"] = len(hw)
    info(f"{len(hw):,} zone-hours evaluated; thresholds: rain > 50 mm/hr, AQI > 400, temp > 42 °C")
    table([dict(trigger=k, **v) for k, v in trg.items()], ["trigger", "events", "precision", "recall", "f1"],
          ["trigger", "true hours", "precision", "recall", "F1"])

    # ---- 7. drift
    stage(7, N_STAGES, "Data drift (PSI/KS, seasonally matched) & concept drift with champion/challenger retraining")
    ref = df[df.week < D.VAL_END]

    def matched(w_lo, w_hi):
        cur = df[(df.week >= w_lo) & (df.week < w_hi)]
        return ref[(ref.week % 52).isin(set((cur.week % 52).unique()))], cur
    dd = {}
    feats = ["rain_fc_mm", "rain_days_fc", "aqi_fc", "temp_max_fc", "curfew_risk_30d", "hist_disrupt_hrs_12w", "hourly_rate", "flood_score"]
    for k, (lo, hi) in {"weeks 104-129 (stable)": (104, 130), "weeks 130-142 (covariate shift)": (130, 143),
                        "weeks 143-155 (covariate + concept)": (143, 156)}.items():
        rf, cur = matched(lo, hi)
        dd[k] = DR.data_drift_report(rf, cur, feats).to_dict("records")
    R["data_drift"] = dd
    rows = [dict(feature=f, **{k: f"{next(r for r in dd[k] if r['feature'] == f)['psi']:.3f}"
                               + (" DRIFT" if next(r for r in dd[k] if r['feature'] == f)["drifted"] else "") for k in dd}) for f in feats]
    table(rows, ["feature"] + list(dd), ["feature (PSI)"] + list(dd),
          highlight=lambda r: "yellow" if any("DRIFT" in str(v) for v in r.values()) else None)
    base_mae = results["gbdt_champion"]["test"]["mae"]
    mtrk = Tracker("giginsure-monitoring", root=os.path.join(out, "mlruns"), exp_id="3")
    N = int(df.week.max() + 1); static = champ; serving = champ; serving_ver = 1
    mon_c = DR.ConceptDriftMonitor(base_mae, 1.5, 3); weekly, events = [], []; cooldown = 0
    info(f"concept-drift monitor: alarm when weekly MAE > {1.5 * base_mae:.2f} (1.5 x ₹{base_mae:.2f}) for 3 consecutive weeks")
    for w in range(D.VAL_END, N):
        d = df[df.week == w]
        ms = float(np.abs(P.clip_premium(static.predict(d[D.FEATURES])) - d[D.TARGET]).mean())
        ma = float(np.abs(P.clip_premium(serving.predict(d[D.FEATURES])) - d[D.TARGET]).mean())
        weekly.append(dict(week=w, mae_static=ms, mae_adaptive=ma, serving_version=serving_ver))
        if cooldown > 0: cooldown -= 1; mon_c.streak = 0; continue
        mon_c.update(w, ma)
        if mon_c.streak >= mon_c.patience:  # ALARM: attempt retraining (challenger)
            hold = df[(df.week > w - 2) & (df.week <= w)]  # last 2 labelled weeks = holdout
            fit_df = df[(df.week <= w - 2) & (df.week > w - 2 - 78)]
            wts = np.where(fit_df.week > w - 2 - 4, 4.0, 1.0)
            chal_h = best_fn(**best).fit(fit_df[D.FEATURES], fit_df[D.TARGET], sample_weight=wts)
            m_old = P.metrics(hold[D.TARGET], P.clip_premium(serving.predict(hold[D.FEATURES])))
            m_new = P.metrics(hold[D.TARGET], P.clip_premium(chal_h.predict(hold[D.FEATURES])))
            gate = DR.promote_challenger(m_old["mae"], m_new["mae"], 0.05)
            warn(f"week {w}: CONCEPT-DRIFT ALARM (MAE {ma:.2f} for 3 weeks) -> challenger holdout MAE ₹{m_new['mae']:.2f} "
                 f"vs serving ₹{m_old['mae']:.2f}: gate {'PASS' if gate else 'FAIL'}")
            with mtrk.start_run(f"retrain_week{w}", tags={"stage": "challenger", "trigger": "concept_drift", "gate": "PASS" if gate else "FAIL"}):
                mtrk.log_params({"alarm_week": w, "train_window_weeks": 78, "recent_weight": 4.0, **best})
                mtrk.log_metrics({"holdout_mae_serving": m_old["mae"], "holdout_mae_challenger": m_new["mae"], "gate_passed": float(gate)})
                rid2 = mtrk._rec["run_id"]
            ev_d = dict(week=w, holdout_old=m_old["mae"], holdout_new=m_new["mae"], gate=bool(gate))
            if gate:
                full = df[(df.week <= w) & (df.week > w - 78)]
                serving = best_fn(**best).fit(full[D.FEATURES], full[D.TARGET], sample_weight=np.where(full.week > w - 4, 4.0, 1.0))
                p2 = os.path.join(mdir, f"pricing_v{len(reg.state[MODEL_NAME]) + 1}.pkl")
                v2 = reg.register(MODEL_NAME, rid2, m_new, artifact=p2)
                with open(p2, "wb") as f:
                    pickle.dump(dict(model=serving, features=D.FEATURES, version=v2), f)
                reg.transition(MODEL_NAME, v2, "Staging"); reg.transition(MODEL_NAME, v2, "Production")
                serving_ver = v2; ev_d["version"] = v2
                ok(f"registry: {MODEL_NAME} v{v2} promoted to Production; previous version archived")
            events.append(ev_d); cooldown = 3; mon_c.streak = 0
    wk = pd.DataFrame(weekly)
    R["concept"] = dict(baseline_mae=base_mae, threshold=1.5 * base_mae, weekly=weekly, events=events,
                        concept_start=D.CONCEPT_DRIFT_START, data_start=D.DATA_DRIFT_START,
                        static_mae_weeks_130_155=float(wk[wk.week >= 130].mae_static.mean()),
                        adaptive_mae_weeks_130_155=float(wk[wk.week >= 130].mae_adaptive.mean()),
                        static_peak=float(wk.mae_static.max()), adaptive_peak=float(wk.mae_adaptive.max()))
    info(f"mean MAE weeks 130-155: monitored ₹{R['concept']['adaptive_mae_weeks_130_155']:.2f} vs static ₹{R['concept']['static_mae_weeks_130_155']:.2f}")
    R["registry"] = reg.state
    table([dict(model=n, **{k: m[k] for k in ("version", "stage", "created")}) for n, vs in reg.state.items() for m in vs],
          ["model", "version", "stage", "created"], highlight=lambda r: "green" if r["stage"] == "Production" else "grey")

    # ---- 8. benchmarks
    stage(8, N_STAGES, "Performance benchmarks")
    one = te[D.FEATURES].iloc[[0]]
    lat = []
    for _ in range(2000):
        s = time.perf_counter(); champ.predict(one); lat.append((time.perf_counter() - s) * 1000)
    Xb = te[D.FEATURES]; s = time.perf_counter(); champ.predict(Xb); tb = time.perf_counter() - s
    Xf = ts[F.FRAUD_FEATURES]; s = time.perf_counter(); F.anomaly_score(m, Xf); tf = time.perf_counter() - s
    s = time.perf_counter(); T.evaluate_triggers(hw, "obs"); tt = time.perf_counter() - s
    guard, gw = F.DuplicateGuard(), T.MockGateway(); e2e = []
    for i in range(500):
        cl_ = dict(worker_id=f"w{i:05d}", zone_id=i % 40, event_id="E1"); s = time.perf_counter()
        sc = float(F.anomaly_score(m, ts[F.FRAUD_FEATURES].iloc[[i]])[0]); T.process_claim(cl_, sc, thr, guard, gw, 4.0, 95.0)
        e2e.append((time.perf_counter() - s) * 1000)
    R["performance"] = dict(price_latency_ms_p50=float(np.percentile(lat, 50)), price_latency_ms_p95=float(np.percentile(lat, 95)),
                            price_latency_ms_p99=float(np.percentile(lat, 99)), price_batch_rows_per_s=float(len(Xb) / tb),
                            fraud_score_rows_per_s=float(len(Xf) / tf), trigger_hours_per_s=float(len(hw) / tt),
                            e2e_claim_ms_p50=float(np.percentile(e2e, 50)), e2e_claim_ms_p95=float(np.percentile(e2e, 95)), n_e2e=len(e2e))
    pf = R["performance"]
    info(f"premium quote latency p50/p95/p99: {pf['price_latency_ms_p50']:.2f} / {pf['price_latency_ms_p95']:.2f} / {pf['price_latency_ms_p99']:.2f} ms")
    info(f"batch pricing {pf['price_batch_rows_per_s']:,.0f} rows/s | fraud scoring {pf['fraud_score_rows_per_s']:,.0f} claims/s | "
         f"triggers {pf['trigger_hours_per_s'] / 1e6:.1f} M zone-hours/s")
    info(f"claim decision path (trigger -> duplicate -> fraud -> payout) p50/p95: {pf['e2e_claim_ms_p50']:.2f} / {pf['e2e_claim_ms_p95']:.2f} ms")

    R["runs"] = [dict(exp=e.experiment, **{k: r[k] for k in ("run_name", "run_id", "params", "metrics", "tags")}) for e in (trk, ftrk, mtrk) for r in e.records]
    R["runtime_s"] = time.time() - t0
    with open(os.path.join(out, "results.json"), "w") as f:
        json.dump(R, f, indent=1, default=float)
    banner(f"Pipeline finished in {R['runtime_s']:.1f}s  |  {len(R['runs'])} tracked runs  |  results -> {os.path.join(out, 'results.json')}")
    return R


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs"))
    ap.add_argument("--fast", action="store_true", help="2-config grid instead of 12 (for quick demos / CI smoke runs)")
    a = ap.parse_args()
    main(os.path.abspath(a.out), a.fast)
