import pytest
import numpy as np
from src.models.monitor_drift import calculate_psi

def test_calculate_psi_no_drift():
    base = np.random.normal(50, 10, 1000)
    curr = np.random.normal(50, 10, 1000)
    psi = calculate_psi(base, curr)
    assert psi < 0.10, f"Expected low PSI, got {psi}"

def test_calculate_psi_with_drift():
    base = np.random.normal(50, 10, 1000)
    curr = np.random.normal(100, 25, 1000)
    psi = calculate_psi(base, curr)
    assert psi > 0.25, f"Expected high PSI > 0.25, got {psi}"
