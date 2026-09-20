import os
import hashlib
import pandas as pd
import numpy as np
from faker import Faker

fake = Faker('en_IN')
Faker.seed(42)
np.random.seed(42)

ZONES = [
    {"zone_id": "ZONE_BLR_01", "city": "Bangalore", "tier": "Metro"},
    {"zone_id": "ZONE_DEL_01", "city": "Delhi_NCR", "tier": "Metro"},
    {"zone_id": "ZONE_BOM_01", "city": "Mumbai", "tier": "Metro"},
    {"zone_id": "ZONE_MAA_01", "city": "Chennai", "tier": "Metro"},
    {"zone_id": "ZONE_HYD_01", "city": "Hyderabad", "tier": "Metro"}
]

VEHICLE_TYPES = ["Bike", "Scooter", "Bicycle"]
WORK_PATTERNS = ["Full-Time", "Part-Time"]
PERSONA_CATEGORIES = ["Food_Delivery", "Q_Commerce", "E_Commerce"]

def hash_worker_id(raw_id: str) -> str:
    return hashlib.sha256(raw_id.encode('utf-8')).hexdigest()[:16]

def generate_worker_stream(num_workers=250):
    """Generates Stream 2: Worker & Persona Data matching IDinsight DERII & Zomato analytics benchmarks."""
    print("Collecting Stream 2: Worker & Persona Data...")
    
    workers = []
    
    for i in range(num_workers):
        raw_identity = f"SWIGGY_RIDER_{i+1000}_{fake.uuid4()}"
        worker_id = f"W_{hash_worker_id(raw_identity)}"
        
        zone = np.random.choice(ZONES)
        zone_id = zone["zone_id"]
        zone_tier = zone["tier"]
        
        # Persona category (DEVTrails 2026 sub-categories: Food 60%, Q-Commerce 25%, E-Commerce 15%)
        persona_category = np.random.choice(PERSONA_CATEGORIES, p=[0.60, 0.25, 0.15])
        
        # Vehicle selection: 60% Scooter, 30% Bike, 10% Bicycle
        vehicle = np.random.choice(VEHICLE_TYPES, p=[0.30, 0.60, 0.10])
        
        # Vehicle Disruption Vulnerability Score (Bicycle riders lose income much faster during rain/heat)
        vulnerability_score = 1.8 if vehicle == "Bicycle" else (1.2 if vehicle == "Bike" else 1.0)
        
        work_pattern = np.random.choice(WORK_PATTERNS, p=[0.75, 0.25])
        
        # IDinsight DERII Benchmarks:
        # Full-time: 48-60 hrs/week; Part-time: 20-30 hrs/week
        # Baseline wage: ~102 INR / hr (Metro) vs ~82 INR / hr (Tier-2)
        if work_pattern == "Full-Time":
            avg_hours = float(np.random.normal(52, 6))
            avg_days = int(np.random.normal(26, 2))
        else:
            avg_hours = float(np.random.normal(25, 4))
            avg_days = int(np.random.normal(16, 3))
            
        avg_hours = max(15.0, min(70.0, round(avg_hours, 1)))
        avg_days = max(10, min(30, avg_days))
        
        # Baseline hourly rate calculation
        hourly_rate = 102.0 if zone_tier == "Metro" else 82.0
        # Vehicle modifier (Bicycle slightly lower range, Scooter efficient)
        vehicle_mod = 1.05 if vehicle == "Scooter" else (0.90 if vehicle == "Bicycle" else 1.0)
        
        weekly_baseline_income = round(avg_hours * hourly_rate * vehicle_mod * np.random.uniform(0.92, 1.08), 2)
        
        tenure = int(np.random.exponential(180)) + 15
        rating = round(np.random.normal(4.65, 0.25), 2)
        rating = max(3.5, min(5.0, rating))
        
        workers.append({
            "worker_id": worker_id,
            "zone_id": zone_id,
            "city": zone["city"],
            "zone_tier": zone_tier,
            "persona_category": persona_category,
            "vehicle_type": vehicle,
            "vulnerability_score": vulnerability_score,
            "tenure_days": tenure,
            "work_pattern_type": work_pattern,
            "avg_active_hours_per_week": avg_hours,
            "avg_active_days_per_month": avg_days,
            "historical_weekly_income": weekly_baseline_income,
            "rating": rating
        })
        
    df_workers = pd.DataFrame(workers)
    
    out_dir = os.path.join("data", "raw", "worker")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "worker_population.csv")
    df_workers.to_csv(out_path, index=False)
    print(f"Saved Stream 2 to {out_path} ({len(df_workers)} workers)")
    return df_workers

if __name__ == "__main__":
    generate_worker_stream()
