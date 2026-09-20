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
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, ConfusionMatrixDisplay

def train_fraud_detection_model():
    """Trains Intelligent Fraud Detection Classifier and logs metrics/SHAP artifacts to MLflow."""
    print("\n--- Training Intelligent Fraud Detection Model with MLflow Tracking ---")

    # 1. Load Processed Fraud Dataset
    data_path = os.path.join("data", "processed", "fraud_dataset.csv")
    if not os.path.exists(data_path):
        raise FileNotFoundError("Stage 2 output 'fraud_dataset.csv' not found. Please run Stage 2 pipeline first.")

    df = pd.read_csv(data_path)

    # 2. Select Features & Target
    feature_cols = [
        "gps_deviation_score", "device_id_reuse_count",
        "claim_vs_event_gap_minutes", "claims_per_worker_per_month",
        "claimed_amount", "earnings_loss_amount", "disruption_impact_ratio",
        "zone_disruption_risk_index", "gps_anomaly_flag",
        "syndicate_device_flag", "timing_gap_anomaly_flag"
    ]
    target_col = "is_fraud_label"

    X = df[feature_cols]
    y = df[target_col]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # 3. Setup MLflow Experiment
    mlflow.set_experiment("GigEase_Fraud_Detection")

    n_estimators = 120
    learning_rate = 0.08
    max_depth = 5

    with mlflow.start_run(run_name="GradientBoosting_FraudDetection_v1"):
        # Log Hyperparameters
        mlflow.log_param("n_estimators", n_estimators)
        mlflow.log_param("learning_rate", learning_rate)
        mlflow.log_param("max_depth", max_depth)
        mlflow.log_param("model_type", "GradientBoostingClassifier")
        mlflow.log_param("num_train_samples", len(X_train))

        # Train Classifier
        model = GradientBoostingClassifier(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            random_state=42
        )
        model.fit(X_train, y_train)

        # Evaluate Predictions
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]

        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        auc = roc_auc_score(y_test, y_proba)

        # Log Metrics to MLflow
        mlflow.log_metric("Accuracy", acc)
        mlflow.log_metric("Precision", prec)
        mlflow.log_metric("Recall", rec)
        mlflow.log_metric("F1_Score", f1)
        mlflow.log_metric("ROC_AUC", auc)

        print(f"Fraud Model Metrics -> Acc: {acc:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | F1: {f1:.4f} | AUC: {auc:.4f}")

        # Plot & Log Confusion Matrix Artifact
        fig, ax = plt.subplots(figsize=(6, 5))
        cm = confusion_matrix(y_test, y_pred)
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=["Legitimate", "Fraud"])
        disp.plot(cmap="Blues", ax=ax)
        ax.set_title("GigEase Fraud Detection — Confusion Matrix")
        plt.tight_layout()

        os.makedirs("models", exist_ok=True)
        cm_path = os.path.join("models", "fraud_confusion_matrix.png")
        fig.savefig(cm_path)
        plt.close(fig)

        mlflow.log_artifact(cm_path)

        # Plot & Log SHAP Feature Risk Breakdown Artifact
        fig_feat, ax_feat = plt.subplots(figsize=(10, 6))
        importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=True)
        importances.plot(kind="barh", ax=ax_feat, color="#fb7185")
        ax_feat.set_title("GigEase Fraud Model — Feature Risk Importance (SHAP Proxy)")
        plt.tight_layout()

        shap_path = os.path.join("models", "fraud_feature_importance.png")
        fig_feat.savefig(shap_path)
        plt.close(fig_feat)

        mlflow.log_artifact(shap_path)

        # Log & Register Model in MLflow Registry
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="fraud_model",
            registered_model_name="GigEase_FraudDetection_Model"
        )

        print("[PASSED] Intelligent Fraud Detection Model logged & registered in MLflow!")
        return model, f1, auc

if __name__ == "__main__":
    from src.models.mlflow_utils import init_mlflow_tracking
    init_mlflow_tracking()
    train_fraud_detection_model()
