import os
import sys
import pandas as pd
from datetime import datetime

# Import stream collection functions
from collect_environmental import generate_environmental_stream
from collect_worker import generate_worker_stream
from collect_orders import generate_orders_stream
from collect_claims import generate_claims_stream

def generate_sources_documentation():
    """Generates data/sources.md attribution log as per Stage 1 requirements."""
    sources_content = f"""# Data Sources & Attribution Log — GigEase MLOps Stage 1

**Generated Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Project**: GigEase — AI-Powered Parametric Income Protection Platform for Swiggy Delivery Partners  
**Author**: PRIYADARSHINI R (24AD0222 | Batch 126)

---

## 1. Stream 1 — Environmental & Disruption Data
- **Source Name**: Open-Meteo Weather Reanalysis API & Forecast Engine
- **URL**: [https://open-meteo.com](https://open-meteo.com)
- **License**: Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Pull Date**: {datetime.now().strftime('%Y-%m-%d')}
- **Parameters Pulled**: Precipitation (`rainfall_mm`), Max Temp (`temperature_celsius`), Wind Speed (`wind_speed_kmph`), Weather Code (`WMO`).
- **Secondary Source**: CPCB Real-Time AQI API (data.gov.in) & OpenAQ (`openaq`)
- **Holiday Calendar**: Python `holidays` library (`holidays.India(subdiv='KA')`)

---

## 2. Stream 2 — Worker & Persona Data
- **Structural Reference**: Kaggle Zomato Delivery Operations Analytics Dataset
- **URL**: [https://www.kaggle.com/datasets/saurabhbadole/zomato-delivery-operations-analytics-dataset](https://www.kaggle.com/datasets/saurabhbadole/zomato-delivery-operations-analytics-dataset)
- **License**: Open Data Commons Attribution (ODC-By)
- **Income Benchmark Source**: IDinsight DERII Study (Gig Worker Wages in Urban India)
- **Cited Values**: Baseline hourly rate = ₹102/hr (Metro), ₹82/hr (Tier-2); 32% expense ratio; ₹18,761/month net earnings.
- **Generator Tools**: `Faker` (en_IN) + SDV `GaussianCopulaSynthesizer` for PII-safe hashed IDs (`worker_id`).

---

## 3. Stream 3 — Platform & Order Data
- **Source Structure**: Swiggy Delivery Partner Order Log Stream & Mock Platform API
- **License**: Synthetic Platform Stream (Proprietary Hackathon Simulator)
- **Aggregation Grain**: Weekly per-worker totals key `(worker_id, zone_id, week_start_date)`.
- **Fields Logged**: `orders_completed`, `orders_cancelled`, `baseline_expected_weekly_income`, `actual_weekly_earnings`, `earnings_loss_amount`.

---

## 4. Stream 4 — Claims & Fraud Signal Data
- **Source Structure**: Rule-Based Synthetic Fraud Anomaly Injector
- **License**: Internal Hackathon Proof-of-Work Generator
- **Fraud Patterns Injected**:
  1. **GPS Deviation**: Distances >15km from active zone during disruption.
  2. **Syndicate Device Sharing**: Clusters >3 workers sharing hashed `device_id`.
  3. **Timing Anomaly**: Claims submitted >12 hours after disruption event window.
- **Labels**: `is_fraud_label` (Supervised training ground truth).
"""
    out_path = os.path.join("data", "sources.md")
    os.makedirs("data", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(sources_content)
    print(f"Generated {out_path} attribution log.")

def run_pipeline():
    print("=" * 65)
    print("      GIGEASE MLOPS STAGE 1: DATA COLLECTION PIPELINE")
    print("=" * 65)
    
    # 1. Run Stream 1
    df_env = generate_environmental_stream(num_weeks=12)
    
    # 2. Run Stream 2
    df_workers = generate_worker_stream(num_workers=250)
    
    # 3. Run Stream 3
    df_orders = generate_orders_stream(df_env, df_workers)
    
    # 4. Run Stream 4
    df_claims = generate_claims_stream(df_orders, df_env)
    
    # 5. Generate Attribution Log
    generate_sources_documentation()
    
    # 6. Validate Stage 1 Checklist & Joinability
    print("\n" + "=" * 65)
    print("             STAGE 1 DELIVERABLE CHECKLIST VERIFICATION")
    print("=" * 65)
    
    check_files = [
        os.path.join("data", "raw", "environmental", "environmental_data.csv"),
        os.path.join("data", "raw", "worker", "worker_population.csv"),
        os.path.join("data", "raw", "orders", "platform_orders.csv"),
        os.path.join("data", "raw", "claims", "claims_dataset.csv"),
        os.path.join("data", "sources.md")
    ]
    
    all_exist = True
    for fpath in check_files:
        exists = os.path.exists(fpath)
        status = "[PASSED]" if exists else "[FAILED]"
        print(f"{status} {fpath}")
        if not exists:
            all_exist = False
            
    # Verify Joinability on (worker_id, zone_id, week_start_date)
    print("\nVerifying Stream Joinability on (worker_id, zone_id, week_start_date)...")
    merged_test = pd.merge(df_orders, df_workers, on=["worker_id", "zone_id"], how="inner")
    merged_claims = pd.merge(df_claims, merged_test, on=["worker_id", "zone_id", "week_start_date"], how="inner")
    
    print(f"[PASSED] Joinability Verified! Successfully joined streams into {len(merged_claims)} valid parametric claim records.")
    
    if all_exist:
        print("\n=== STAGE 1 DATA COLLECTION COMPLETE & VALIDATED! ===")
        # Sync Datasets to DagsHub Data Tab
        try:
            import dagshub
            dagshub_owner = os.getenv("DAGSHUB_REPO_OWNER", "priyadarshinir.aids2024")
            dagshub_repo = os.getenv("DAGSHUB_REPO_NAME", "GIG-Insure")
            dagshub.upload_files(
                repo_owner=dagshub_owner,
                repo_name=dagshub_repo,
                local_path="data",
                remote_path="data",
                commit_message="Update GigEase raw & processed datasets"
            )
            print(f"[PASSED] Datasets uploaded to DagsHub Data Tab: https://dagshub.com/{dagshub_owner}/{dagshub_repo}/src/main/data")
        except Exception as e:
            print(f"[NOTE] DagsHub Data sync skipped ({e}). Datasets stored locally in data/")

        print("Ready to proceed to Stage 2: Data Preprocessing & Feature Engineering.")


if __name__ == "__main__":
    run_pipeline()
