# GigEase — Comprehensive High-Level Architecture (HLD) & MLOps Blueprint

> **Project**: GigEase — AI-Powered Parametric Income Protection Platform for Swiggy Delivery Partners  
> **Hackathon Track**: Guidewire DEVTrails 2026 University Hackathon  
> **Academic Standard**: MLOps PBL Course Specification (AD4V71 / R25 Regulation)

---

## 1. Problem Statement Analysis & SDE Mindset

### Core Challenge Synthesis
Platform-based delivery partners in India (specifically **Swiggy food delivery partners**) face a 20–30% loss of monthly earnings due to uncontrollable external disruptions. Standard insurance products fail gig workers because they carry long settlement cycles, rigid monthly/annual premiums, and cover irrelevant risks (health/vehicle repairs).

**GigEase** solves this by delivering an **AI-Enabled Parametric Income Protection Platform** operating strictly on a **Weekly Pricing Model** with **Zero-Touch Automated Payouts** for **Loss of Income ONLY**.

---

## 2. Problem-by-Problem Breakdown, SDE Solutions & Tech Choices

| # | Problem to Solve | SDE Mindset & Architectural Approach | Chosen Tech, Tools & Methods | Technical Rationale |
|---|---|---|---|---|
| **P1** | **Gig Worker Income Volatility & Weekly Financial Cadence** | Build a dynamic weekly micro-premium engine ($W_{avg}$ baseline + zone risk factor) that recalculates coverage & premiums every 7 days matching the worker's payout cycle. | **Python 3.10+, Scikit-Learn, LightGBM/XGBoost, Pandas** | LightGBM provides ultra-fast tabular regression to compute dynamic weekly premiums based on historical 12-week income and zone risk. |
| **P2** | **Real-Time Disruption Verification (Parametric Triggers)** | Implement an automated dual-source trigger engine evaluating STFI (weather/pollution) and RSMD (curfew/strikes) with geofence matching to confirm income drop before initiating claims. | **Open-Meteo REST API, CPCB / OpenAQ API, `geopy`, `holidays.India`** | Open-Meteo offers keyless historical reanalysis back to 1940 for backtesting monsoon risk; `geopy` classifies metro vs tier-2 zones without commercial API costs. |
| **P3** | **Delivery Fraud & Syndicate Exploitation** | Construct a multi-layered anomaly & fraud detection pipeline checking GPS deviation, device fingerprint reuse, timing gaps, and SHAP explainability. | **Isolation Forest + Supervised Classifier, SDV (Synthetic Data Vault), Faker, SHAP** | SDV generates statistically correlated synthetic fraud signals; SHAP provides local feature attributions for auditability. |
| **P4** | **Zero-Touch Instant Claim & Payout Settlement** | Eliminate manual claim forms. When a disruption is confirmed, open a claim shell automatically and dispatch instant UPI transfers via payment simulator. | **FastAPI, Async Pydantic, Razorpay Test Mode / UPI Simulator, SQLite / PostgreSQL** | Asynchronous REST endpoints handle high-concurrency event webhooks with sub-second automated claim generation. |
| **P5** | **Data Versioning & Reproducibility (MLOps Unit I & II)** | Enforce strict dataset versioning across all 4 raw data streams (Environmental, Worker Persona, Platform Orders, Claims/Fraud) ensuring 100% reproducible model runs. | **DVC (Data Version Control), Git** | DVC tracks large datasets and pipeline steps (`dvc.yaml`) without cluttering Git repositories, guaranteeing reproducible experiments. |
| **P6** | **Experiment Tracking & Model Governance (MLOps Unit II & III)** | Track hyperparameter tuning, model metrics (MAE, RMSE, F1-Score, ROC-AUC), and register production candidate models in a central registry. | **MLflow (Tracking & Model Registry)** | MLflow provides experiment comparison, metric tracking, and a production model stage registry for smooth deployment transitions. |
| **P7** | **Production Serving & CI/CT/CD Automation (MLOps Unit III & V)** | Containerize the inference service and establish automated CI/CD pipelines that run tests and trigger continuous retraining when new data arrives or drift occurs. | **Docker, Docker Compose, PyTest, GitHub Actions** | Docker ensures environmental parity; GitHub Actions automates linting, testing, image building, and automated retraining pipelines. |
| **P8** | **Model Drift & Operational Analytics (MLOps Unit III & IV)** | Monitor prediction latency, data drift, loss ratios, and display real-time metrics on dual dashboards (Worker Coverage vs Insurer Loss Ratios). | **Evidently AI / Custom Drift Scorer, Chart.js, HTML5/CSS3 Dashboard** | Monitors feature distribution shifts (e.g. unexpected weather anomalies) and gives executive visibility into underwriting profitability. |

---

## 3. Reconstructed High-Level Architecture (HLD)

The diagram below integrates the **Parametric Income Protection Business Flow** with the **End-to-End MLOps Lifecycle Pipeline**:

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#DBEAFE', 'primaryTextColor': '#1B3A6B', 'primaryBorderColor': '#2563EB', 'lineColor': '#2563EB', 'secondaryColor': '#CCFBF1', 'tertiaryColor': '#EDE9FE', 'background': '#FFFFFF', 'nodeBorder': '#2563EB', 'clusterBkg': '#F8FAFC', 'clusterBorder': '#64748B', 'edgeLabelBackground': '#FFFFFF', 'fontFamily': 'Inter, Arial, sans-serif'}}}%%

flowchart TD

    %% ─── ACTORS ─────────────────────────────────────────────────────────────
    WORKER(["🧑‍💼 Swiggy Delivery Partner"])
    ADMIN(["📊 Insurer / Risk Admin"])

    %% ─── LAYER 1: DATA INGESTION & VERSIONING (MLOps Unit I & II) ─────────
    subgraph L1["LAYER 1 — Ingestion & Data Pipeline (DVC Versioned)"]
        direction TB
        S1["Stream 1: Open-Meteo & CPCB APIs\n(Weather, Rain, AQI, Temp)"]
        S2["Stream 2: Persona & Worker Engine\n(SDV + Faker Synthetic Population)"]
        S3["Stream 3: Platform Order Stream\n(Kaggle Zomato Aligned Orders & Earnings)"]
        S4["Stream 4: Fraud Signal Injector\n(GPS Spoof, Device Sharing, Timing Gaps)"]
        DVC_PIPE[["📦 DVC Pipeline (dvc.yaml)\nIngest ➔ Preprocess ➔ Validate"]]
    end

    %% ─── LAYER 2: MLOPS CORE & MODEL REGISTRY (MLOps Unit II & III) ────────
    subgraph L2["LAYER 2 — MLOps Core & Experimentation (MLflow)"]
        direction TB
        PREPROC["Feature Engineering & Scaling\n(Zone Tier, Monsoon Weight, Tenure)"]
        TRAIN_PRICING["Dynamic Weekly Pricing Model\n(LightGBM / XGBoost Regressor)"]
        TRAIN_FRAUD["Intelligent Fraud Classifier\n(Isolation Forest + Supervised Classifier)"]
        MLFLOW[("🧪 MLflow Experiment Tracking\n& Production Model Registry")]
    end

    %% ─── LAYER 3: PARAMETRIC TRIGGER & RISK ENGINE (DevTrails Core) ───────
    subgraph L3["LAYER 3 — Parametric Trigger & Risk Engine"]
        direction TB
        LIVE_MONITOR["Real-Time Trigger Monitor\n(Rain >35mm/h, AQI >400, Heat >42°C, Curfews)"]
        CONFIRM{"Dual-Source Event\nConfirmation?"}
        GEO_MATCH["Geofencing Service\nZone Matching"]
        LOSS_CALC["Income Loss Engine\n(Expected Baseline - Actual Earnings)"]
    end

    %% ─── LAYER 4: AI DECISION & FRAUD DETECTION (DevTrails + MLOps Unit III)
    subgraph L4["LAYER 4 — AI Decision & Fraud Guard"]
        direction TB
        FRAUD_EVAL["Fraud Score Evaluator\n(GPS Deviation + Device Reuse)"]
        SHAP_EXPLAIN["SHAP Explainability Engine\n(Local Feature Risk Breakdown)"]
        DECISION_GATE{"Auto-Approve\n/ Flag / Reject"}
    end

    %% ─── LAYER 5: SERVING, PAYOUT & AUTOMATION (DevTrails + MLOps Unit IV/V)
    subgraph L5["LAYER 5 — FastAPI Microservice & Instant Settlement"]
        direction TB
        FASTAPI["⚡ FastAPI REST Server\n/quote · /subscribe · /trigger · /claim"]
        PAYOUT_SIM["Instant UPI / Razorpay Simulator\n(Automated UTR Generation)"]
        NOTIFY["Twilio / WhatsApp / Push\nNotification Dispatcher"]
    end

    %% ─── LAYER 6: CI/CT/CD & MONITORING (MLOps Unit IV & V) ────────────────
    subgraph L6["LAYER 6 — CI/CT/CD & Drift Monitoring"]
        direction TB
        DRIFT_MONITOR["Data & Model Drift Monitor\n(Evidently AI / PSI Score Tracking)"]
        GITHUB_ACTIONS[["⚙️ GitHub Actions CI/CT/CD\nAutomated Test ➔ Retrain ➔ Deploy"]]
        DASHBOARDS["📊 Dual Interactive Web Dashboard\nWorker Protection View vs Admin Loss Ratio View"]
    end

    %% ─── CONNECTIONS: DATA & TRAINING ──────────────────────────────────────
    S1 --> DVC_PIPE
    S2 --> DVC_PIPE
    S3 --> DVC_PIPE
    S4 --> DVC_PIPE

    DVC_PIPE --> PREPROC
    PREPROC --> TRAIN_PRICING
    PREPROC --> TRAIN_FRAUD

    TRAIN_PRICING --> MLFLOW
    TRAIN_FRAUD --> MLFLOW

    MLFLOW -->|"Deploys Model"| FASTAPI

    %% ─── CONNECTIONS: BUSINESS WORKFLOW ────────────────────────────────────
    WORKER -->|"Onboarding & Policy Quote"| FASTAPI
    FASTAPI -->|"Calculates Dynamic Weekly Premium"| TRAIN_PRICING

    S1 --> LIVE_MONITOR
    LIVE_MONITOR --> CONFIRM
    CONFIRM -->|"Verified ✓"| GEO_MATCH
    GEO_MATCH --> LOSS_CALC
    LOSS_CALC -->|"Calculates Loss"| FRAUD_EVAL

    FRAUD_EVAL --> SHAP_EXPLAIN
    SHAP_EXPLAIN --> DECISION_GATE

    DECISION_GATE -->|"Approved (95%+)"| PAYOUT_SIM
    PAYOUT_SIM -->|"Instant UPI Credit"| WORKER
    PAYOUT_SIM --> NOTIFY

    %% ─── CONNECTIONS: MONITORING & RETRAINING ──────────────────────────────
    FASTAPI -->|"Inference Logs"| DRIFT_MONITOR
    DRIFT_MONITOR -->|"Drift Threshold Exceeded"| GITHUB_ACTIONS
    GITHUB_ACTIONS -->|"Triggers Continuous Retraining"| DVC_PIPE

    FASTAPI --> DASHBOARDS
    DRIFT_MONITOR --> DASHBOARDS
    DASHBOARDS --> ADMIN

    %% ─── STYLES ─────────────────────────────────────────────────────────────
    classDef pipeline fill:#DBEAFE,stroke:#2563EB,stroke-width:2px,color:#1B3A6B,font-weight:bold
    classDef mlflow fill:#EDE9FE,stroke:#7C3AED,stroke-width:2px,color:#7C3AED
    classDef engine fill:#CCFBF1,stroke:#0D9488,stroke-width:2px,color:#0D9488
    classDef fraud fill:#FEF9C3,stroke:#CA8A04,stroke-width:2px,color:#92400E
    classDef api fill:#DCFCE7,stroke:#16A34A,stroke-width:2px,color:#15803D,font-weight:bold
    classDef cicd fill:#FFE4E6,stroke:#E11D48,stroke-width:2px,color:#9F1239
    classDef actor fill:#1B3A6B,stroke:#1B3A6B,color:#FFFFFF,font-weight:bold

    class S1,S2,S3,S4,DVC_PIPE pipeline
    class PREPROC,TRAIN_PRICING,TRAIN_FRAUD,MLFLOW mlflow
    class LIVE_MONITOR,CONFIRM,GEO_MATCH,LOSS_CALC engine
    class FRAUD_EVAL,SHAP_EXPLAIN,DECISION_GATE fraud
    class FASTAPI,PAYOUT_SIM,NOTIFY api
    class DRIFT_MONITOR,GITHUB_ACTIONS,DASHBOARDS cicd
    class WORKER,ADMIN actor
```

---

## 4. Summary of MLOps Lifecycle Compliance

1. **Unit I — Foundation & Problem Formulation**: Structured around Swiggy delivery worker income loss, defining MLOps actors (Data Engineer, ML Engineer, Risk Admin) and baseline SLAs.
2. **Unit II — Data Versioning & Experimentation**: Implements DVC versioning on raw data streams and MLflow tracking for dynamic pricing & fraud models.
3. **Unit III — Production Serving & Explainability**: REST inference APIs powered by FastAPI, with SHAP feature explainability for every processed claim.
4. **Unit IV — Architecture & Maturity Model**: Advanced Level 1/Level 2 MLOps architecture featuring automated feature engineering and model serving.
5. **Unit V — CI/CT/CD & Retraining Automation**: Docker containerized deployment orchestrated by GitHub Actions with drift-triggered retraining loops.
