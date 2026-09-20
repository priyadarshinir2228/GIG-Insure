import os
import mlflow

def init_mlflow_tracking():
    """Initializes DagsHub Hosted MLflow Tracking & Automatic Logging dynamically.
    DagsHub Repository: priyadarshinir.aids2024 / GIG-Insure
    """
    os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"

    dagshub_owner = os.getenv("DAGSHUB_REPO_OWNER", "priyadarshinir.aids2024")
    dagshub_repo = os.getenv("DAGSHUB_REPO_NAME", "GIG-Insure")
    dagshub_token = os.getenv("DAGSHUB_TOKEN")

    # Step 1: Initialize DagsHub MLflow Connection
    try:
        import dagshub
        if dagshub_token:
            os.environ["MLFLOW_TRACKING_USERNAME"] = dagshub_token
            os.environ["MLFLOW_TRACKING_PASSWORD"] = dagshub_token
        
        dagshub.init(repo_owner=dagshub_owner, repo_name=dagshub_repo, mlflow=True)
        print(f"[PASSED] DagsHub Hosted MLflow Tracking connected: https://dagshub.com/{dagshub_owner}/{dagshub_repo}.mlflow")
    except Exception as e:
        print(f"[NOTE] DagsHub auto-init note: ({e}). Falling back to MLflow tracking configuration.")

    # Step 2: Enable MLflow Automatic Logging (mlflow.autolog)
    try:
        mlflow.autolog(log_models=True, disable=False, exclusive=False)
        print("[PASSED] MLflow autologging enabled for Scikit-Learn, LightGBM, & XGBoost models!")
    except Exception as e:
        print(f"[WARNING] MLflow autologging note: {e}")

    # Step 3: Fallback Tracking URI if DagsHub is unauthenticated/offline
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        current_uri = mlflow.get_tracking_uri()
        if current_uri and "dagshub.com" in current_uri:
            tracking_uri = current_uri
        elif os.getenv("GITHUB_ACTIONS") or os.getenv("CI"):
            mlruns_dir = os.path.abspath("mlruns")
            os.makedirs(mlruns_dir, exist_ok=True)
            tracking_uri = f"file://{mlruns_dir}"
        else:
            tracking_uri = "sqlite:///mlflow.db"

    mlflow.set_tracking_uri(tracking_uri)
    print(f"[PASSED] Final Active MLflow Tracking URI: {tracking_uri}")
    return tracking_uri
