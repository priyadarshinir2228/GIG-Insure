---
title: GigInsure
emoji: 🌧️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
pinned: false
short_description: AI parametric income insurance for delivery partners
---

# GigInsure — AI-powered parametric income protection for delivery partners

Guidewire DEVTrails 2026. GigInsure is a weekly-priced, **loss-of-income-only** insurance platform for delivery
partners in food, quick-commerce and e-commerce. When a verified external disruption hits a partner's zone
(heavy rain, severe AQI, extreme heat or a curfew), claims open automatically. An AI fraud screen checks each one,
and the lost wages go to the partner's UPI straight away. Health, life, accident and vehicle cover are excluded.

## Quick start

```bash
python -m venv venv && venv\Scripts\activate        # Windows  (source venv/bin/activate on Linux/macOS)
pip install -r requirements.txt

python scripts/run_pipeline.py          # 1. train + evaluate + track + register models (~8 min; add --fast for ~1 min)
python scripts/check_gate.py            # 2. CI evaluation gate (8 checks, non-zero exit on regression)
pytest -q                               # 3. 56 automated tests
python scripts/serve.py                 # 4. live platform:  http://127.0.0.1:8000/admin  and  /worker
```

`serve.py` options: `--tick 2` (seconds per simulated hour), `--weather openmeteo` (live Open-Meteo feed instead of
the mock), `--reset` (fresh database), `--workers 60` (size of the seeded roster). If no trained models exist,
`serve.py` runs the pipeline in fast mode first.

## What you see in the terminal

**`run_pipeline.py`** prints each MLOps stage and its results:

| Stage | Terminal output |
|---|---|
| 1 Data | 18,720-row weekly table, temporal split (train+val weeks 0–103 / test 104–129 / monitoring 130–155), premium band |
| 2 Baselines | Ridge, random forest, histogram GBDT: 5-fold temporal CV MAE and test MAE |
| 3 Tuning | 12 GBDT configurations with CV MAE; best configuration |
| 4 Champion | Comparison table (MAE, RMSE, R², MAPE, ±₹2), MAE cut vs linear, registry promotion, feature importance, per-persona accuracy |
| 5 Fraud | Isolation Forest vs rules vs LOF (precision/recall/F1/ROC-AUC/PR-AUC/FPR), confusion matrix, recall per fraud type |
| 6 Triggers | Precision/recall/F1 per trigger against ground truth on 87,600 noisy zone-hours |
| 7 Drift | PSI table per feature and window (seasonally matched), concept-drift alarm, challenger gate, v2 promotion, registry |
| 8 Benchmarks | Quote latency p50/p95/p99, throughput, claim decision-path latency |

**`serve.py`** streams every platform event as it happens, colour-coded:
`ONBOARD` / `POLICY` / `RENEW` (ML pricing), `SIMULATE`, `TRIGGER`, `CLAIM` (zero-touch initiation), `EVENT`,
`FRAUD` (held, with anomaly score and reasons), `PAYOUT` (UPI txn, score, lost hours × rate × 70 %, latency),
`SETTLE`, `DUPLICATE`, `REVIEW`, `DRIFT` (live PSI warnings), `MODEL` / `MLOPS` (hot reload, retraining).
The same log appears at the bottom of the admin dashboard.

## Workflows (report flows F1–F9)

| # | Workflow | How it runs here | Code |
|---|---|---|---|
| F1 | Order cycle / activity | Mock platform API gives orders before an event; this feeds the fraud features | `data_collection/orders_collector.py` |
| F2 | Earnings baseline | Persona hourly rate (food ₹95, q-com ₹110, e-com ₹85) with per-worker variation | `giginsure/data.py`, `worker_synth.py` |
| F3 | KYC | Validated identity, name, persona, zone and UPI; mock DigiLocker marks the worker VERIFIED | `validators.py`, `Platform.onboard` |
| F4 | Premium calculation | Production GBDT prices the week from the zone flood score, forecast, 12-week live disruption history and persona. Clipped to ₹15–₹40. Shown against the city average (hyper-local adjustment) | `Platform.quote` |
| F5 | Insurance registration | Weekly policy issued; all policies re-priced and renewed every 168 simulated hours | `_issue_policy`, `_renew_week` |
| F6 | Situation event engine | Each zone is read every simulated hour; rain > 50 mm/hr, AQI > 400, temp > 42 °C or a curfew opens an event with a severity coefficient | `triggers.evaluate_reading`, `Platform.tick` |
| F7 | Claim flow | Zero-touch: a claim opens for every active policy in the zone. The validated window (≤ 10 h) × severity gives the lost hours | `_handle_zone`, `_close_event` |
| F8 | AI decision engine | `process_claim`: duplicate guard, then Isolation Forest score (threshold set for a 2 % false-positive budget), then HOLD_REVIEW or pay | `triggers.process_claim`, `fraud.py` |
| F9 | Fund transfer | Idempotent mock UPI gateway: lost hours × hourly rate × 70 %, capped at ₹4,000/week, one transaction per idempotency key | `DbGateway`, `payout_amount` |

MLOps loop: pipeline → MLflow-layout run store (`outputs/mlruns`) → model registry (None → Staging → Production →
Archived) → CI gate → the server loads the **Production** versions. When `results.json` changes (for example after
**Retrain now** on the dashboard), the server hot-reloads the models and the dashboard refreshes.

## Dashboards

**Admin (`/admin`) → Live operations**, polled every 2 s:
- **KPIs:** partners, active policies, premiums, UPI payouts, loss ratio, events, claim decisions, duplicates blocked, p95 decision latency.
- **Zone grid:** live rain/AQI/temp meters against thresholds, open events, zone loss ratio.
- **Disruption simulator:** rainstorm, AQI, heatwave or curfew in any zones, optional fraud ring. Fast-forward and speed controls.
- **Charts:** premiums vs payouts over time; sensor maxima vs thresholds.
- **Claims feed:** fraud-score bar against the threshold, signals, decision, amount, UPI txn.
- **Live fraud monitor:** live recall and FPR against the simulated ground truth; review queue with approve/reject.
- **Live data drift:** PSI of rain/AQI/temp against a seasonally matched reference.
- **Next-week predictive analytics:** ML premium per zone and persona, expected disrupted hours, expected claims vs expected premium, risk band.
- **Events table:** includes **Replay**, which resubmits every claim to prove the duplicate guard (ledger unchanged).

**Admin → Model performance (MLOps)**, loaded from `outputs/results.json`, reloads after each pipeline run:
- CI gate and model registry.
- Pricing model comparison, predicted-vs-actual scatter, tuning grid, feature importance, per-persona accuracy.
- Fraud ROC and PR curves, confusion matrix, recall per fraud type, detector comparison.
- Trigger precision/recall/F1.
- Concept-drift weekly MAE with retraining; data-drift PSI table.
- Performance benchmarks.

**Worker app (`/worker`):**
- Onboarding with a live AI-priced weekly quote and hyper-local adjustment.
- Earnings protected, active weekly cover, cover left this week.
- Live zone conditions, with an alert during a disruption ("you are covered, no claim needed").
- Payout and claim history; next week's price.

### 5-minute demo script
1. Open `/admin`, then pick Velachery and OMR in the simulator. Choose **Heavy rainstorm**, tick **inject fraud ring**, and click **Trigger disruption**.
2. Watch it in the terminal and dashboard: TRIGGER → zero-touch CLAIMs → EVENT closes → PAYOUT lines with UPI txn ids, and FRAUD holds for spoofers.
3. Approve or reject a held claim from the review queue. Click **Replay** on the event: every claim is REJECT_DUPLICATE and the ledger doesn't change.
4. Open `/worker` and enter a partner id from the claims feed: the payout is already there with no form filed. Onboard a new partner to see a live ML quote.
5. Click **+1 week**: policies are re-priced and renewed (RENEW in the terminal), and the loss ratio and forecast update.
6. Open the **Model performance** tab and click **Retrain now**: the pipeline streams into the terminal, the new models are hot-reloaded, and the panels update.

## Results (full pipeline run, seeded — reproduces the project report)

| Area | Result |
|---|---|
| Weekly premium (champion GBDT lr 0.1, depth 3, 300 trees) | Test MAE ₹0.901, RMSE ₹1.134, R² 0.967, 92.8 % within ±₹2; CV MAE ₹1.15 ± 0.32; −66.7 % MAE vs linear (₹2.705); noise floor ₹0.96 |
| Baselines (test MAE) | Random forest ₹0.908 · histogram GBDT ₹0.927 · Ridge ₹2.705 |
| Per persona (test MAE) | Food ₹0.893 · Q-commerce ₹0.887 · E-commerce ₹0.924 |
| Fraud (Isolation Forest, 300 trees) | Precision 0.764, recall 0.889, F1 0.822, ROC-AUC 0.991, PR-AUC 0.922, FPR 0.018; recall: spoofing 88.3 %, fake presence 82.9 %, claim farming 100 % |
| Fraud baselines | Rules: F1 0.764, FPR 0.032 · LOF: F1 0.392 |
| Triggers (F1) | Rain 0.935 · AQI 0.919 · heat 0.763 · any 0.898 |
| Data drift (PSI) | Stable window ≤ 0.026; drift flagged for rainfall 0.474, max temp 0.958, disruption history 0.310 (weeks 130–142) |
| Concept drift | Alarm at week 148. Challenger holdout MAE ₹2.15 vs ₹2.82, so the gate passed and v2 went to Production. Mean MAE weeks 130–155 ₹1.40 vs ₹1.48 static |
| CI gate | 8/8 checks pass |
| Tests | 56 passed (48 unit/integration/security/drift/tracking + 3 live-platform + 5 API-contract) |

Latency figures depend on the machine; see the benchmark stage output.

## Deployment (Docker · Hugging Face Spaces)

One container runs everything: the build trains the models (so the pickles always match the pinned
scikit-learn) and fails if the CI evaluation gate fails; the container serves the API and both dashboards with
`waitress` and runs the trigger monitor in the same process.

```bash
docker build -t giginsure .                                   # add --build-arg FAST=1 for a ~1 min build
docker run -p 8000:8000 -e GIGINSURE_ADMIN_TOKEN=choose-one giginsure
```

| Variable | Purpose |
|---|---|
| `GIGINSURE_ADMIN_TOKEN` | Locks admin actions (simulate, fast-forward, speed, replay, review, retrain). Dashboards stay readable; the admin page asks for the token once. Unset = unlocked (local use only). |
| `GIGINSURE_SECRET` | HMAC key for worker session tokens. |
| `PORT` | Port to listen on (default 8000). |
| `GIGINSURE_WEATHER` | `mock` (default) or `openmeteo` for live weather. |

`GET /api/health` reports the Production model versions and the simulation clock.

**Continuous deployment:** `.github/workflows/ci.yml` runs tests → model-validation gate → a Docker build
smoke test → deploy. With the repository secret `HF_TOKEN` (a Hugging Face write token) and the repository
variable `HF_SPACE` (e.g. `your-name/giginsure`) set, every push to `main` that passes the gate is pushed to that
Space, which rebuilds and serves it. Set `GIGINSURE_ADMIN_TOKEN` and `GIGINSURE_SECRET` as secrets in the Space
settings.

## Project layout

```
config/zones.yaml              locked zone taxonomy (Chennai zones, lat/lon, flood score)
src/giginsure/                 data, pricing, fraud, drift, triggers, tracking, validators, platform, server, web/
src/data_collection/           env feeds (mock / Open-Meteo), mock platform orders, worker + claim synthesis
scripts/run_pipeline.py        end-to-end MLOps pipeline      scripts/check_gate.py   CI evaluation gate
scripts/serve.py               live platform + dashboards      tests/                  pytest suite
.github/workflows/ci.yml       test → model-validation-gate → deploy-staging / deploy-production (manual approval)
outputs/                       results.json, models/, mlruns/ (MLflow layout + registry.json)  [generated]
data/giginsure.db              live platform SQLite store     [generated]
```

## Limitations
- All data is synthetic, so the numbers describe the simulator rather than the real world. Payments go through a mock gateway.
- Live claim telemetry is drawn from the same fraud archetypes as the training data, so live fraud recall is optimistic.
- Injected storms in a low-premium season push the loss ratio far above 100 %. That's expected: it is the stress scenario the next-week forecast and re-pricing respond to.
- MLflow is optional. Without it, the tracker writes MLflow's run-store layout directly (`mlflow ui --backend-store-uri outputs/mlruns`).
