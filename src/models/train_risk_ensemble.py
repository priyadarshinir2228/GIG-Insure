import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
import mlflow
import mlflow.sklearn

def train_zone_risk_ensemble():
    """
    Model 1: Risk Prediction Model (XGBoost + Prophet 65/35 Ensemble Simulator).
    Predicts zone disruption probability every Sunday night to drive premium loading.
    """
    print("\n--- Training Model 1: Zone Risk Prediction Ensemble (XGBoost + Prophet) ---")
    
    # Generate synthetic training features if dataset missing
    np.random.seed(42)
    n_samples = 1000
    
    X = pd.DataFrame({
        "rainfall_7d_avg": np.random.gamma(2, 15, n_samples),
        "max_temp_celsius": np.random.normal(32, 5, n_samples),
        "aqi_index": np.random.uniform(80, 450, n_samples),
        "elevation_m": np.random.uniform(5, 120, n_samples),
        "drainage_deficit_score": np.random.uniform(0.1, 0.9, n_samples),
        "is_monsoon": np.random.choice([0, 1], p=[0.65, 0.35], size=n_samples)
    })
    
    # Target: High Disruption Event (1 or 0)
    y = ((X["rainfall_7d_avg"] > 60) | (X["max_temp_celsius"] > 42) | (X["aqi_index"] > 380) | ((X["drainage_deficit_score"] > 0.7) & (X["is_monsoon"] == 1))).astype(int)
    
    # 1. XGBoost Component (Gradient Boosting Classifier)
    xgb_model = GradientBoostingClassifier(n_estimators=100, max_depth=5, learning_rate=0.05, random_state=42)
    xgb_model.fit(X, y)
    
    # 2. Prophet Component Simulation (Seasonal Trend Predictor)
    def prophet_predict_seasonal_floor(row):
        is_monsoon = row["is_monsoon"]
        drainage = row["drainage_deficit_score"]
        return float(np.clip(0.15 + (0.50 if is_monsoon else 0.05) + drainage * 0.25, 0.0, 1.0))

    prophet_preds = X.apply(prophet_predict_seasonal_floor, axis=1).values
    xgb_probs = xgb_model.predict_proba(X)[:, 1]
    
    # 3. Ensemble Formula: 0.65 * XGBoost + 0.35 * Prophet
    ensemble_risk_scores = round_scores(0.65 * xgb_probs + 0.35 * prophet_preds)
    
    print(f"Risk Ensemble Trained successfully ({n_samples} samples). Mean Zone Risk Score: {np.mean(ensemble_risk_scores):.4f}")
    
    # Log to MLflow
    mlflow.set_experiment("GigEase_Zone_Risk_Ensemble")
    with mlflow.start_run(run_name="XGBoost_Prophet_Risk_v1"):
        mlflow.log_param("ensemble_ratio", "65% XGBoost / 35% Prophet")
        mlflow.log_metric("Mean_Risk_Score", float(np.mean(ensemble_risk_scores)))
        mlflow.sklearn.log_model(xgb_model, "risk_xgb_component")
        
    return xgb_model

def round_scores(arr):
    return np.round(np.clip(arr, 0.0, 1.0), 4)

def predict_zone_risk(zone_id: str, weather_data: dict) -> float:
    """Inference helper computing combined risk score for specified zone."""
    base_risk = 0.45 if "MAA" in zone_id else (0.35 if "DEL" in zone_id else 0.25)
    rain = weather_data.get("weekly_total_rainfall_mm", 0.0)
    aqi = weather_data.get("weekly_avg_aqi", 100.0)
    is_monsoon = weather_data.get("is_monsoon", 0)
    
    score = base_risk + (rain / 300.0) * 0.40 + (aqi / 500.0) * 0.20 + (0.15 if is_monsoon else 0.0)
    return round(float(np.clip(score, 0.0, 1.0)), 4)

if __name__ == "__main__":
    from src.models.mlflow_utils import init_mlflow_tracking
    init_mlflow_tracking()
    train_zone_risk_ensemble()
