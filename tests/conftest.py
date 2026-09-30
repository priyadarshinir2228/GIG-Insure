import os, sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("GIGINSURE_DISABLE_MLFLOW", "1")


@pytest.fixture(scope="session")
def weekly():
    from giginsure import data as D
    return D.generate_weekly(n_weeks=60, n_zones=12)


@pytest.fixture(scope="session")
def claims():
    from giginsure import data as D
    return D.generate_claims(n=12000)
