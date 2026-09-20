import pytest
from src.models.train_pricing import train_dynamic_pricing_model
from src.models.train_fraud import train_fraud_detection_model

def test_pricing_model_training():
    model, mae, r2 = train_dynamic_pricing_model()
    assert model is not None
    assert mae >= 0.0
    assert r2 > 0.80

def test_fraud_model_training():
    model, f1, auc = train_fraud_detection_model()
    assert model is not None
    assert f1 >= 0.80
    assert auc >= 0.80
