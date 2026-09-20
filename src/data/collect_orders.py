import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

def generate_orders_stream(df_env=None, df_workers=None):
    """Generates Stream 3: Platform & Order Data (Weekly Aggregated Order & Earnings Stream)."""
    print("Collecting Stream 3: Platform & Order Data...")
    
    if df_env is None:
        env_path = os.path.join("data", "raw", "environmental", "environmental_data.csv")
        if os.path.exists(env_path):
            df_env = pd.read_csv(env_path)
        else:
            raise FileNotFoundError("Stream 1 environmental data must be generated first.")
            
    if df_workers is None:
        worker_path = os.path.join("data", "raw", "worker", "worker_population.csv")
        if os.path.exists(worker_path):
            df_workers = pd.read_csv(worker_path)
        else:
            raise FileNotFoundError("Stream 2 worker population data must be generated first.")

    # Group environmental data by zone and week_start_date
    env_weekly = df_env.groupby(["zone_id", "week_start_date"]).agg({
        "rainfall_mm": "sum",
        "peak_hour_rain_mm": "sum",
        "temperature_celsius": "max",
        "aqi_index": "mean",
        "curfew_flag": "sum",
        "strike_flag": "sum",
        "zone_closure_flag": "sum",
        "platform_outage_hours": "sum",
        "festival_flag": "sum"
    }).reset_index()

    order_records = []
    order_id_counter = 50000

    for _, worker in df_workers.iterrows():
        worker_id = worker["worker_id"]
        zone_id = worker["zone_id"]
        baseline_weekly = worker["historical_weekly_income"]
        vulnerability = float(worker.get("vulnerability_score", 1.0))
        
        # Get environmental weeks for worker's zone
        zone_env = env_weekly[env_weekly["zone_id"] == zone_id]
        
        for _, env_week in zone_env.iterrows():
            week_start = env_week["week_start_date"]
            total_rain = env_week["rainfall_mm"]
            peak_rain = env_week.get("peak_hour_rain_mm", total_rain * 0.4)
            max_temp = env_week["temperature_celsius"]
            avg_aqi = env_week["aqi_index"]
            closures = env_week["zone_closure_flag"]
            outage_hrs = env_week.get("platform_outage_hours", 0.0)
            festivals = env_week["festival_flag"]
            
            # Calculate disruption loss multiplier with peak-hour weighting & vehicle vulnerability
            disruption_drop = 0.0
            if peak_rain > 50.0 or total_rain > 120.0: # Heavy peak rain week
                disruption_drop += np.random.uniform(0.35, 0.55) * vulnerability
            elif total_rain > 60.0: # Moderate heavy rain week
                disruption_drop += np.random.uniform(0.15, 0.30) * vulnerability
                
            if max_temp > 42.0: # Extreme heatwave
                disruption_drop += np.random.uniform(0.10, 0.25) * vulnerability
                
            if avg_aqi > 380: # Severe pollution
                disruption_drop += np.random.uniform(0.15, 0.30)
                
            if closures > 0: # Curfews / Bandh days
                disruption_drop += closures * 0.15
                
            if outage_hrs > 0: # App outage / server crash (each outage hour = ~5% drop in weekly earnings)
                disruption_drop += outage_hrs * 0.05
                
            # Demand surge during festivals (+15% to +35%)
            if festivals > 0:
                disruption_drop -= 0.20
                
            # Cap drop between 0% and 85% loss
            disruption_drop = max(0.0, min(0.85, disruption_drop))
            
            actual_weekly_earnings = round(baseline_weekly * (1.0 - disruption_drop) * np.random.uniform(0.95, 1.05), 2)
            
            # Average earnings per delivery order: ~INR 65 - 85
            avg_payout_per_order = 75.0
            orders_completed = int(actual_weekly_earnings / avg_payout_per_order)
            orders_cancelled = int(orders_completed * (0.05 + disruption_drop * 0.3))
            
            total_distance_km = round(orders_completed * np.random.uniform(3.5, 6.2), 1)
            
            order_records.append({
                "order_batch_id": f"ORD_{order_id_counter}",
                "worker_id": worker_id,
                "zone_id": zone_id,
                "week_start_date": week_start,
                "orders_completed": orders_completed,
                "orders_cancelled": orders_cancelled,
                "baseline_expected_weekly_income": baseline_weekly,
                "actual_weekly_earnings": actual_weekly_earnings,
                "earnings_loss_amount": round(max(0.0, baseline_weekly - actual_weekly_earnings), 2),
                "total_distance_km": total_distance_km,
                "disruption_impact_ratio": round(disruption_drop, 3)
            })
            order_id_counter += 1

    df_orders = pd.DataFrame(order_records)
    
    out_dir = os.path.join("data", "raw", "orders")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "platform_orders.csv")
    df_orders.to_csv(out_path, index=False)
    print(f"Saved Stream 3 to {out_path} ({len(df_orders)} weekly order records)")
    return df_orders

if __name__ == "__main__":
    generate_orders_stream()
