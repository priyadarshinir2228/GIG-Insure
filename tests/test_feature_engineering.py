import os
import pytest
import pandas as pd
from src.features.preprocess import clean_and_preprocess_data
from src.features.build_features import build_feature_pipeline

def test_feature_datasets_exist_and_valid():
    master_path = os.path.join("data", "processed", "master_features.csv")
    pricing_path = os.path.join("data", "processed", "pricing_dataset.csv")
    fraud_path = os.path.join("data", "processed", "fraud_dataset.csv")

    assert os.path.exists(master_path), "Master features CSV missing"
    assert os.path.exists(pricing_path), "Pricing dataset CSV missing"
    assert os.path.exists(fraud_path), "Fraud dataset CSV missing"

    df_pricing = pd.read_csv(pricing_path)
    df_fraud = pd.read_csv(fraud_path)

    assert len(df_pricing) > 0
    assert len(df_fraud) > 0
    assert "target_dynamic_weekly_premium" in df_pricing.columns
    assert "is_fraud_label" in df_fraud.columns
