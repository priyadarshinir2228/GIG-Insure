import os
import pandas as pd
import numpy as np

def clean_and_preprocess_data():
    """Reads raw datasets, cleans missing values, standardizes types, and aggregates weekly features."""
    print("Executing Stage 2: Data Preprocessing & Cleaning...")
    
    # 1. Load Raw Datasets
    raw_env_path = os.path.join("data", "raw", "environmental", "environmental_data.csv")
    raw_worker_path = os.path.join("data", "raw", "worker", "worker_population.csv")
    raw_orders_path = os.path.join("data", "raw", "orders", "platform_orders.csv")
    raw_claims_path = os.path.join("data", "raw", "claims", "claims_dataset.csv")

    df_env = pd.read_csv(raw_env_path)
    df_workers = pd.read_csv(raw_worker_path)
    df_orders = pd.read_csv(raw_orders_path)
    df_claims = pd.read_csv(raw_claims_path)

    # 2. Preprocess Environmental Stream (Weekly Grain Aggregation)
    df_env["date"] = pd.to_datetime(df_env["date"])
    df_env["rainfall_mm"] = df_env["rainfall_mm"].fillna(0.0)
    df_env["aqi_index"] = df_env["aqi_index"].fillna(df_env["aqi_index"].median())

    df_env_weekly = df_env.groupby(["zone_id", "week_start_date"]).agg({
        "rainfall_mm": ["sum", "max"],
        "temperature_celsius": ["max", "mean"],
        "wind_speed_kmph": "max",
        "aqi_index": "mean",
        "curfew_flag": "sum",
        "strike_flag": "sum",
        "zone_closure_flag": "sum",
        "festival_flag": "max",
        "is_monsoon_period": "max"
    }).reset_index()

    # Flatten column MultiIndex
    df_env_weekly.columns = [
        "zone_id", "week_start_date",
        "weekly_total_rainfall_mm", "weekly_max_rainfall_mm",
        "weekly_max_temp_celsius", "weekly_avg_temp_celsius",
        "weekly_max_wind_kmph", "weekly_avg_aqi",
        "curfew_days_count", "strike_days_count",
        "zone_closure_days_count", "has_festival", "is_monsoon"
    ]

    # Convert booleans to int (0/1)
    df_env_weekly["has_festival"] = df_env_weekly["has_festival"].astype(int)
    df_env_weekly["is_monsoon"] = df_env_weekly["is_monsoon"].astype(int)

    # 3. Preprocess Worker Stream (Categorical Encoding & Scaling Prep)
    tier_map = {"Metro": 1, "Tier-2": 0}
    vehicle_map = {"Scooter": 1.0, "Bike": 1.05, "Bicycle": 1.20} # Risk sensitivity factor
    pattern_map = {"Full-Time": 1, "Part-Time": 0}

    df_workers["zone_tier_code"] = df_workers["zone_tier"].map(tier_map).fillna(1)
    df_workers["vehicle_risk_factor"] = df_workers["vehicle_type"].map(vehicle_map).fillna(1.0)
    df_workers["is_full_time"] = df_workers["work_pattern_type"].map(pattern_map).fillna(1)

    # 4. Save Cleaned Datasets to data/processed/
    proc_dir = os.path.join("data", "processed")
    os.makedirs(proc_dir, exist_ok=True)

    df_env_weekly.to_csv(os.path.join(proc_dir, "processed_environmental.csv"), index=False)
    df_workers.to_csv(os.path.join(proc_dir, "processed_workers.csv"), index=False)
    df_orders.to_csv(os.path.join(proc_dir, "processed_orders.csv"), index=False)
    df_claims.to_csv(os.path.join(proc_dir, "processed_claims.csv"), index=False)

    print(f"[PASSED] Data Preprocessing Complete! Saved clean files to {proc_dir}")
    return df_env_weekly, df_workers, df_orders, df_claims

if __name__ == "__main__":
    clean_and_preprocess_data()
