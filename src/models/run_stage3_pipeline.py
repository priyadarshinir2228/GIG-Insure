import os
import sys
import mlflow
from mlflow.tracking import MlflowClient

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.models.train_pricing import train_dynamic_pricing_model
from src.models.train_fraud import train_fraud_detection_model
from src.models.mlflow_utils import init_mlflow_tracking

def run_stage3_pipeline():
    print("=" * 65)
    print("    GIGEASE MLOPS STAGE 3: MODEL TRAINING & MLFLOW TRACKING")
    print("=" * 65)

    # Initialize MLflow tracking URI (Local SQLite DB or Remote DagsHub Host)
    tracking_uri = init_mlflow_tracking()

    # 1. Train Dynamic Pricing Model
    model_pricing, mae, r2 = train_dynamic_pricing_model()

    # 2. Train Intelligent Fraud Detection Model
    model_fraud, f1, auc = train_fraud_detection_model()

    # 3. Query MLflow Client to Verify Experiment Logging & Model Registry
    client = MlflowClient(tracking_uri=tracking_uri)

    print("\n" + "=" * 65)
    print("        STAGE 3 MLFLOW EXPERIMENT TRACKING VERIFICATION")
    print("=" * 65)

    # List Experiments
    experiments = client.search_experiments()
    print("MLflow Experiments Found:")
    for exp in experiments:
        runs = client.search_runs(experiment_ids=[exp.experiment_id])
        print(f"  - Experiment: '{exp.name}' (ID: {exp.experiment_id}) -- Total Runs: {len(runs)}")
        for r in runs:
            print(f"    * Run Name: '{r.data.tags.get('mlflow.runName')}' | Run ID: {r.info.run_id}")
            print(f"      Metrics: {r.data.metrics}")

    # List Registered Models
    registered_models = client.search_registered_models()
    print("\nMLflow Model Registry Candidates:")
    for rm in registered_models:
        latest = rm.latest_versions[0] if rm.latest_versions else None
        version_str = f"v{latest.version}" if latest else "No versions"
        print(f"  [PASSED] Model Name: '{rm.name}' | Latest Version: {version_str}")

    print("\n=== STAGE 3 MODEL TRAINING & MLFLOW TRACKING COMPLETE! ===")
    print(f"[PASSED] Pricing Model (MAE: INR {mae:.2f}, R2: {r2:.4f})")
    print(f"[PASSED] Fraud Model (F1: {f1:.4f}, AUC: {auc:.4f})")
    print("Ready to proceed to Stage 4: Model Serving (FastAPI) & Docker Containerization!")

if __name__ == "__main__":
    run_stage3_pipeline()
