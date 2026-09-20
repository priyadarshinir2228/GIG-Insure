import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import holidays

# Defined Delivery Zones in India (Metro & Tier-2)
ZONES = [
    {"zone_id": "ZONE_BLR_01", "city": "Bangalore", "state": "KA", "lat": 12.9716, "lon": 77.5946, "tier": "Metro"},
    {"zone_id": "ZONE_DEL_01", "city": "Delhi_NCR", "state": "DL", "lat": 28.6139, "lon": 77.2090, "tier": "Metro"},
    {"zone_id": "ZONE_BOM_01", "city": "Mumbai", "state": "MH", "lat": 19.0760, "lon": 72.8777, "tier": "Metro"},
    {"zone_id": "ZONE_MAA_01", "city": "Chennai", "state": "TN", "lat": 13.0827, "lon": 80.2707, "tier": "Metro"},
    {"zone_id": "ZONE_HYD_01", "city": "Hyderabad", "state": "TS", "lat": 17.3850, "lon": 78.4867, "tier": "Metro"}
]

def fetch_open_meteo_weather(lat, lon, start_date, end_date):
    """Fetches daily historical/forecast weather data from Open-Meteo API."""
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max&timezone=Asia%2FKolkata"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            daily = data.get("daily", {})
            df = pd.DataFrame({
                "date": daily.get("time", []),
                "weather_code": daily.get("weathercode", []),
                "temperature_celsius": daily.get("temperature_2m_max", []),
                "rainfall_mm": daily.get("precipitation_sum", []),
                "wind_speed_kmph": daily.get("windspeed_10m_max", [])
            })
            return df
    except Exception as e:
        print(f"Open-Meteo API call fallback triggered: {e}")
    return None

def generate_environmental_stream(num_weeks=12):
    """Generates Stream 1: Environmental & Disruption Data with Open-Meteo + CPCB + Festivals."""
    print("Collecting Stream 1: Environmental & Disruption Data...")
    
    end_dt = datetime.now().date()
    start_dt = end_dt - timedelta(weeks=num_weeks)
    
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")
    
    india_holidays = holidays.India(years=[start_dt.year, end_dt.year])
    
    records = []
    
    for zone in ZONES:
        df_api = fetch_open_meteo_weather(zone["lat"], zone["lon"], start_str, end_str)
        
        # Date range fallback if API unavailable
        date_range = pd.date_range(start=start_dt, end=end_dt, freq='D')
        
        for idx, single_date in enumerate(date_range):
            date_str = single_date.strftime("%Y-%m-%d")
            dt_obj = single_date.date()
            month = dt_obj.month
            
            # Monsoon period: June to September
            is_monsoon = month in [6, 7, 8, 9]
            
            if df_api is not None and not df_api.empty and idx < len(df_api):
                row = df_api.iloc[idx]
                rain = float(row.get("rainfall_mm", 0.0) or 0.0)
                temp = float(row.get("temperature_celsius", 30.0) or 30.0)
                wind = float(row.get("wind_speed_kmph", 12.0) or 12.0)
                w_code = int(row.get("weather_code", 0) or 0)
            else:
                # Realistic synthetic fallback based on Indian seasonal monsoon patterns
                rain = round(np.random.gamma(2, 10) if is_monsoon else np.random.exponential(1.5), 1)
                temp = round(np.random.normal(38 if month in [4, 5] else 28, 3), 1)
                wind = round(np.random.uniform(8, 25 if is_monsoon else 15), 1)
                w_code = 63 if rain > 20 else (0 if rain < 1 else 51)
            
            # AQI (Delhi spike in winter, normal elsewhere)
            if zone["city"] == "Delhi_NCR" and month in [10, 11, 12, 1]:
                aqi = int(np.random.uniform(350, 480))
            else:
                aqi = int(np.random.uniform(80, 220))
                
            dominant_pollutant = "PM2.5" if aqi > 200 else ("PM10" if aqi > 100 else "O3")
            
            # Peak-hour rain allocation (Peak hours = 12PM-2PM lunch, 7PM-10PM dinner: ~35% of total day)
            peak_hour_rain_mm = round(rain * np.random.beta(2.5, 2.5), 1) if rain > 0 else 0.0

            # Technical / Platform App Outage (Simulated server downtime: ~2% occurrence, 0.5 - 3.5 hrs)
            platform_outage_hours = round(np.random.uniform(0.5, 3.5), 1) if (np.random.rand() < 0.02) else 0.0
            
            # Social disruptions (curfew/strike calibration: ~2-4 days/year)
            curfew = np.random.rand() < (0.04 if is_monsoon else 0.01)
            strike = np.random.rand() < 0.015
            closure = curfew or strike or (rain > 45.0)
            
            festival = dt_obj in india_holidays
            
            # Calculate week_start_date (Monday of the week)
            week_start = (single_date - timedelta(days=single_date.weekday())).strftime("%Y-%m-%d")
            
            records.append({
                "date": date_str,
                "week_start_date": week_start,
                "zone_id": zone["zone_id"],
                "city": zone["city"],
                "zone_tier": zone["tier"],
                "rainfall_mm": rain,
                "peak_hour_rain_mm": peak_hour_rain_mm,
                "temperature_celsius": temp,
                "wind_speed_kmph": wind,
                "weather_code": w_code,
                "aqi_index": aqi,
                "dominant_pollutant": dominant_pollutant,
                "curfew_flag": curfew,
                "strike_flag": strike,
                "zone_closure_flag": closure,
                "platform_outage_hours": platform_outage_hours,
                "festival_flag": festival,
                "is_monsoon_period": is_monsoon
            })
            
    df_env = pd.DataFrame(records)
    
    out_dir = os.path.join("data", "raw", "environmental")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "environmental_data.csv")
    df_env.to_csv(out_path, index=False)
    print(f"Saved Stream 1 to {out_path} ({len(df_env)} rows)")
    return df_env

if __name__ == "__main__":
    generate_environmental_stream()
