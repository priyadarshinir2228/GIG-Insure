import os
import sys
import pandas as pd

# Ensure d:\GIG-Insure is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.data.validate import validate_dataframe, EnvironmentalSchema, WorkerSchema, OrderSchema, ClaimSchema
from src.features.preprocess import clean_and_preprocess_data
from src.features.build_features import build_feature_pipeline

def run_stage2_pipeline():
    print("=" * 65)
    print("  GIGEASE MLOPS STAGE 2: PREPROCESSING & FEATURE ENGINEERING")
    print("=" * 65)

    # 1. Step 1: Validate Raw Input Datasets
    print("\n--- Step 1: Executing Data Schema & Bound Validation ---")
    env_raw = pd.read_csv(os.path.join("data", "raw", "environmental", "environmental_data.csv"))
    worker_raw = pd.read_csv(os.path.join("data", "raw", "worker", "worker_population.csv"))
    orders_raw = pd.read_csv(os.path.join("data", "raw", "orders", "platform_orders.csv"))
    claims_raw = pd.read_csv(os.path.join("data", "raw", "claims", "claims_dataset.csv"))

    val_env = validate_dataframe(env_raw, EnvironmentalSchema, "Environmental Raw Stream")
    val_worker = validate_dataframe(worker_raw, WorkerSchema, "Worker Population Stream")
    val_orders = validate_dataframe(orders_raw, OrderSchema, "Platform Orders Stream")
    val_claims = validate_dataframe(claims_raw, ClaimSchema, "Claims Dataset Stream")

    if not (val_env and val_worker and val_orders and val_claims):
        print("❌ Data validation failed. Please inspect schema errors.")
        return False

    # 2. Step 2: Clean & Preprocess Data
    print("\n--- Step 2: Cleaning Data & Aggregating Weekly Features ---")
    clean_and_preprocess_data()

    # 3. Step 3: Feature Engineering Pipeline
    print("\n--- Step 3: Building Master & Training Feature Datasets ---")
    df_pricing, df_fraud = build_feature_pipeline()

    # 4. Verify Stage 2 Outputs & Summary
    print("\n" + "=" * 65)
    print("        STAGE 2 DELIVERABLE CHECKLIST VERIFICATION")
    print("=" * 65)

    check_files = [
        os.path.join("data", "processed", "processed_environmental.csv"),
        os.path.join("data", "processed", "processed_workers.csv"),
        os.path.join("data", "processed", "processed_orders.csv"),
        os.path.join("data", "processed", "processed_claims.csv"),
        os.path.join("data", "processed", "master_features.csv"),
        os.path.join("data", "processed", "pricing_dataset.csv"),
        os.path.join("data", "processed", "fraud_dataset.csv")
    ]

    all_exist = True
    for fpath in check_files:
        exists = os.path.exists(fpath)
        status = "[PASSED]" if exists else "[FAILED]"
        print(f"{status} {fpath}")
        if not exists:
            all_exist = False

    if all_exist:
        print("\n=== STAGE 2 PREPROCESSING & FEATURE ENGINEERING COMPLETE! ===")
        print(f"[PASSED] Dynamic Pricing Dataset: {len(df_pricing)} rows")
        print(f"[PASSED] Intelligent Fraud Dataset: {len(df_fraud)} rows")
        print("Ready to proceed to Stage 3: Model Development & MLflow Experiment Tracking!")
        return True

if __name__ == "__main__":
    run_stage2_pipeline()
