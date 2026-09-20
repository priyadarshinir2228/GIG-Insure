import pytest
import pandas as pd
from src.data.validate import (
    EnvironmentalSchema, WorkerSchema, OrderSchema, ClaimSchema, validate_dataframe
)

def test_environmental_schema_valid():
    data = {
        "date": "2026-09-01",
        "week_start_date": "2026-08-31",
        "zone_id": "ZONE_BLR_01",
        "city": "Bengaluru",
        "rainfall_mm": 45.2,
        "temperature_celsius": 28.5,
        "wind_speed_kmph": 18.0,
        "aqi_index": 120,
        "curfew_flag": False,
        "strike_flag": False,
        "festival_flag": False,
        "is_monsoon_period": True
    }
    obj = EnvironmentalSchema(**data)
    assert obj.city == "Bengaluru"
    assert obj.rainfall_mm == 45.2

def test_worker_schema_valid():
    data = {
        "worker_id": "W_123456",
        "zone_id": "ZONE_BLR_01",
        "zone_tier": "Metro",
        "vehicle_type": "Scooter",
        "tenure_days": 180,
        "work_pattern_type": "Full-Time",
        "avg_active_hours_per_week": 48.0,
        "historical_weekly_income": 5200.0,
        "rating": 4.8
    }
    obj = WorkerSchema(**data)
    assert obj.worker_id == "W_123456"
    assert obj.rating == 4.8

def test_validate_dataframe_passed():
    df = pd.DataFrame([{
        "date": "2026-09-01",
        "week_start_date": "2026-08-31",
        "zone_id": "ZONE_BLR_01",
        "city": "Bengaluru",
        "rainfall_mm": 10.0,
        "temperature_celsius": 30.0,
        "wind_speed_kmph": 12.0,
        "aqi_index": 90,
        "curfew_flag": False,
        "strike_flag": False,
        "festival_flag": False,
        "is_monsoon_period": False
    }])
    result = validate_dataframe(df, EnvironmentalSchema, "Test Env Data")
    assert result is True
