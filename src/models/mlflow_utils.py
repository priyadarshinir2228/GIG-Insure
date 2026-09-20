import os
import mlflow

def init_mlflow_tracking():
    """Initializes MLflow tracking URI dynamically.
    Checks for DagsHub credentials / env vars, or custom MLFLOW_TRACKING_URI.
    Defaults to local SQLite 'sqlite:///mlflow.db'.
    """
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    dagshub_owner = os.getenv("DAGSHUB_REPO_OWNER")
    dagshub_repo = os.getenv("DAGSHUB_REPO_NAME")
    dagshub_token = os.getenv("DAGSHUB_TOKEN")

    if dagshub_owner and dagshub_repo:
        try:
            import dagshub
            if dagshub_token:
                os.environ["MLFLOW_TRACKING_USERNAME"] = dagshub_token
                os.environ["MLFLOW_TRACKING_PASSWORD"] = dagshub_token
            dagshub.init(repo_owner=dagshub_owner, repo_name=dagshub_repo, mlflow=True)
            print(f"[PASSED] DagsHub Hosted MLflow Tracking initialized for: https://dagshub.com/{dagshub_owner}/{dagshub_repo}.mlflow")
            return mlflow.get_tracking_uri()
        except Exception as e:
            print(f"[WARNING] DagsHub init note ({e}). Falling back to configured tracking URI.")

    if not tracking_uri:
        tracking_uri = "sqlite:///mlflow.db"

    mlflow.set_tracking_uri(tracking_uri)
    print(f"[PASSED] MLflow Tracking URI initialized: {tracking_uri}")
    return tracking_uri
