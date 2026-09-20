import os
import hashlib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from faker import Faker

fake = Faker('en_IN')
fake.seed_instance(42)
np.random.seed(42)

def generate_device_id(seed_str: str) -> str:
    return "DEV_" + hashlib.md5(seed_str.encode('utf-8')).hexdigest()[:12]

def generate_claims_stream(df_orders=None, df_env=None):
    """Generates Stream 4: Claims & Fraud Signal Data (Legitimate Claims + Rule-based Injected Fraud)."""
    print("Collecting Stream 4: Claims & Fraud Signal Data...")
    
    if df_orders is None:
        orders_path = os.path.join("data", "raw", "orders", "platform_orders.csv")
        if os.path.exists(orders_path):
            df_orders = pd.read_csv(orders_path)
        else:
            raise FileNotFoundError("Stream 3 platform orders data must be generated first.")
            
    if df_env is None:
        env_path = os.path.join("data", "raw", "environmental", "environmental_data.csv")
        if os.path.exists(env_path):
            df_env = pd.read_csv(env_path)
        else:
            raise FileNotFoundError("Stream 1 environmental data must be generated first.")

    # Assign persistent device IDs to workers (some shared for syndicate fraud simulation)
    unique_workers = df_orders["worker_id"].unique()
    device_pool = [generate_device_id(f"DEVICE_{i}") for i in range(len(unique_workers) - 15)]
    
    worker_device_map = {}
    for idx, w_id in enumerate(unique_workers):
        if idx < len(device_pool):
            worker_device_map[w_id] = device_pool[idx]
        else:
            # Shared device pool for syndicate fraud cluster (~15 workers sharing 3 devices)
            worker_device_map[w_id] = device_pool[idx % 3]

    # Device reuse count lookup
    device_counts = pd.Series(worker_device_map.values()).value_counts().to_dict()

    claim_records = []
    claim_id_counter = 80000

    for _, row in df_orders.iterrows():
        worker_id = row["worker_id"]
        zone_id = row["zone_id"]
        week_start = row["week_start_date"]
        loss_amount = row["earnings_loss_amount"]
        disruption_ratio = row["disruption_impact_ratio"]
        
        device_id = worker_device_map[worker_id]
        reuse_count = device_counts[device_id]
        
        # Trigger claim if loss > 20% of baseline (Legitimate Parametric Trigger)
        if disruption_ratio >= 0.15 and loss_amount > 200.0:
            claim_id = f"CLM_{claim_id_counter}"
            claim_id_counter += 1
            
            event_id = f"EVT_{zone_id}_{week_start.replace('-', '')}"
            
            # Legitimate claim defaults
            gps_dev = round(np.random.gamma(1.5, 0.8), 2) # Typical minor GPS noise < 3 km
            gap_mins = int(np.random.exponential(45)) + 5 # Fast auto-trigger within 45 mins
            claims_per_mo = int(np.random.poisson(1.2)) + 1
            weather_discrepancy = round(np.random.uniform(0.0, 0.1), 2) # Normal API match
            syndicate_flag = bool(reuse_count > 3)
            is_fraud = 0
            
            # Inject Fraud Anomalies (~8-10% of claims)
            fraud_type = np.random.rand()
            if fraud_type < 0.03:
                # GPS Spoofing Fraud
                gps_dev = round(np.random.uniform(18.0, 45.0), 2)
                is_fraud = 1
            elif fraud_type < 0.05 and reuse_count > 3:
                # Device Sharing / Syndicate Fraud
                is_fraud = 1
            elif fraud_type < 0.07:
                # Timing Anomaly (Claimed days after event)
                gap_mins = int(np.random.uniform(720, 2880))
                is_fraud = 1
            elif fraud_type < 0.09:
                # Fake Weather / API Discrepancy Fraud (Worker claims severe flood when API shows 0mm rain)
                weather_discrepancy = round(np.random.uniform(0.65, 0.98), 2)
                is_fraud = 1
                
            claimed = round(loss_amount * 0.70, 2) # 70% loss coverage
            approved = 0.0 if is_fraud else claimed
            
            # Submission timestamp
            base_dt = datetime.strptime(week_start, "%Y-%m-%d") + timedelta(days=np.random.randint(1, 6))
            claim_ts = (base_dt + timedelta(minutes=gap_mins)).strftime("%Y-%m-%d %H:%M:%S")
            
            claim_records.append({
                "claim_id": claim_id,
                "worker_id": worker_id,
                "zone_id": zone_id,
                "week_start_date": week_start,
                "claim_timestamp": claim_ts,
                "disruption_event_id": event_id,
                "gps_deviation_score": gps_dev,
                "device_id": device_id,
                "device_id_reuse_count": reuse_count,
                "syndicate_cluster_flag": syndicate_flag,
                "weather_verification_discrepancy": weather_discrepancy,
                "claim_vs_event_gap_minutes": gap_mins,
                "claims_per_worker_per_month": claims_per_mo,
                "claimed_amount": claimed,
                "approved_amount": approved,
                "is_fraud_label": is_fraud
            })
            
    df_claims = pd.DataFrame(claim_records)
    
    out_dir = os.path.join("data", "raw", "claims")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "claims_dataset.csv")
    df_claims.to_csv(out_path, index=False)
    
    fraud_pct = (df_claims["is_fraud_label"].sum() / len(df_claims)) * 100 if len(df_claims) > 0 else 0
    print(f"Saved Stream 4 to {out_path} ({len(df_claims)} claims generated, {fraud_pct:.2f}% fraud rate)")
    return df_claims

if __name__ == "__main__":
    generate_claims_stream()
