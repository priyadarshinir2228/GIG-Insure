from pydantic import BaseModel, Field, field_validator
from typing import Optional
import pandas as pd

class EnvironmentalSchema(BaseModel):
    date: str
    week_start_date: str
    zone_id: str
    city: str
    rainfall_mm: float = Field(ge=0.0)
    peak_hour_rain_mm: Optional[float] = Field(default=0.0, ge=0.0)
    temperature_celsius: float = Field(ge=-10.0, le=60.0)
    wind_speed_kmph: float = Field(ge=0.0)
    aqi_index: int = Field(ge=0, le=1000)
    curfew_flag: bool
    strike_flag: bool
    platform_outage_hours: Optional[float] = Field(default=0.0, ge=0.0)
    festival_flag: bool
    is_monsoon_period: bool

class WorkerSchema(BaseModel):
    worker_id: str
    zone_id: str
    zone_tier: str
    persona_category: Optional[str] = "Food_Delivery"
    vehicle_type: str
    vulnerability_score: Optional[float] = Field(default=1.0, ge=0.5, le=3.0)
    tenure_days: int = Field(ge=0)
    work_pattern_type: str
    avg_active_hours_per_week: float = Field(ge=0.0, le=100.0)
    historical_weekly_income: float = Field(ge=0.0)
    rating: float = Field(ge=1.0, le=5.0)

class OrderSchema(BaseModel):
    order_batch_id: str
    worker_id: str
    zone_id: str
    week_start_date: str
    orders_completed: int = Field(ge=0)
    orders_cancelled: int = Field(ge=0)
    baseline_expected_weekly_income: float = Field(ge=0.0)
    actual_weekly_earnings: float = Field(ge=0.0)
    earnings_loss_amount: float = Field(ge=0.0)

class ClaimSchema(BaseModel):
    claim_id: str
    worker_id: str
    zone_id: str
    week_start_date: str
    gps_deviation_score: float = Field(ge=0.0)
    device_id: str
    device_id_reuse_count: int = Field(ge=1)
    syndicate_cluster_flag: Optional[bool] = False
    weather_verification_discrepancy: Optional[float] = Field(default=0.0, ge=0.0, le=1.0)
    claim_vs_event_gap_minutes: int = Field(ge=0)
    claimed_amount: float = Field(ge=0.0)
    is_fraud_label: int = Field(ge=0, le=1)

def validate_dataframe(df: pd.DataFrame, schema_class, name: str) -> bool:
    """Validates each row of a DataFrame against Pydantic schema."""
    errors = 0
    records = df.to_dict(orient="records")
    for idx, record in enumerate(records):
        try:
            schema_class(**record)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"Validation error in {name} at row {idx}: {e}")
                
    if errors == 0:
        print(f"[PASSED] Data validation for {name} ({len(df)} records validated, 0 schema errors).")
        return True
    else:
        print(f"[FAILED] Data validation for {name} ({errors} schema errors detected).")
        return False

if __name__ == "__main__":
    import os
    env_df = pd.read_csv(os.path.join("data", "raw", "environmental", "environmental_data.csv"))
    validate_dataframe(env_df, EnvironmentalSchema, "Environmental Data")

    worker_df = pd.read_csv(os.path.join("data", "raw", "worker", "worker_population.csv"))
    validate_dataframe(worker_df, WorkerSchema, "Worker Population")

    order_df = pd.read_csv(os.path.join("data", "raw", "orders", "platform_orders.csv"))
    validate_dataframe(order_df, OrderSchema, "Platform Orders")

    claim_df = pd.read_csv(os.path.join("data", "raw", "claims", "claims_dataset.csv"))
    validate_dataframe(claim_df, ClaimSchema, "Claims Dataset")
