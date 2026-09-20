import os
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def train_dynamic_pricing_model():
    """Trains Dynamic Weekly Pricing Model and logs metrics/artifacts to MLflow."""
    print("\n--- Training Dynamic Weekly Premium Model with MLflow Tracking ---")
    
    # 1. Load Processed Pricing Dataset
    data_path = os.path.join("data", "processed", "pricing_dataset.csv")
    if not os.path.exists(data_path):
        raise FileNotFoundError("Stage 2 output 'pricing_dataset.csv' not found. Please run Stage 2 pipeline first.")
        
    df = pd.read_csv(data_path)

    # 2. Select Features & Target
    feature_cols = [
        "zone_tier_code", "tenure_days", "vehicle_risk_factor", "is_full_time",
        "avg_active_hours_per_week", "historical_weekly_income",
        "weekly_total_rainfall_mm", "weekly_max_temp_celsius",
        "weekly_avg_aqi", "zone_closure_days_count", "is_monsoon",
        "zone_disruption_risk_index", "monsoon_loading"
    ]
    target_col = "target_dynamic_weekly_premium"

    X = df[feature_cols]
    y = df[target_col]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 3. Setup MLflow Experiment
    mlflow.set_experiment("GigEase_Dynamic_Pricing")

    n_estimators = 100
    max_depth = 8
    random_state = 42

    with mlflow.start_run(run_name="RandomForest_DynamicPricing_v1"):
        # Log Hyperparameters
        mlflow.log_param("n_estimators", n_estimators)
        mlflow.log_param("max_depth", max_depth)
        mlflow.log_param("model_type", "RandomForestRegressor")
        mlflow.log_param("num_train_samples", len(X_train))

        # Train Model
        model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state
        )
        model.fit(X_train, y_train)

        # Evaluate Predictions
        y_pred = model.predict(X_test)

        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)

        # Log Metrics
        mlflow.log_metric("MAE", mae)
        mlflow.log_metric("RMSE", rmse)
        mlflow.log_metric("R2_Score", r2)

        print(f"Pricing Model Metrics -> MAE: INR {mae:.2f} | RMSE: INR {rmse:.2f} | R2: {r2:.4f}")

        # Plot & Log Feature Importance Artifact
        fig, ax = plt.subplots(figsize=(10, 6))
        importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=True)
        importances.plot(kind="barh", ax=ax, color="#38bdf8")
        ax.set_title("GigEase Dynamic Premium Model — Feature Importances")
        plt.tight_layout()

        os.makedirs("models", exist_ok=True)
        fig_path = os.path.join("models", "pricing_feature_importance.png")
        fig.savefig(fig_path)
        plt.close(fig)

        try:
            mlflow.log_artifact(fig_path)
            mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path="pricing_model",
                registered_model_name="GigEase_DynamicPricing_Model"
            )
            print("[PASSED] Dynamic Pricing Model logged & registered in MLflow!")
        except Exception as e:
            print(f"[WARNING] MLflow artifact logging skipped ({e}). Metrics logged successfully.")
        return model, mae, r2


if __name__ == "__main__":
    from src.models.mlflow_utils import init_mlflow_tracking
    init_mlflow_tracking()
    train_dynamic_pricing_model()
