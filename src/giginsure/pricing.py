"""Weekly premium model: candidate models, temporal CV, tuning, evaluation."""
import itertools
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .data import PREMIUM_MIN, PREMIUM_MAX

try:  # optional drop-in, used automatically when installed
    from xgboost import XGBRegressor
    HAVE_XGB = True
except Exception:  # noqa
    HAVE_XGB = False

GRID = dict(learning_rate=[0.05, 0.1], max_depth=[3, 4, 5], n_estimators=[150, 300], subsample=[0.8])
FAST_GRID = dict(learning_rate=[0.1], max_depth=[3, 4], n_estimators=[150], subsample=[0.8])


def make_gbdt(**kw):
    """Gradient-boosted decision trees (same algorithm family as XGBoost/LightGBM)."""
    return GradientBoostingRegressor(random_state=0, **kw)


def make_xgb(**kw):
    return XGBRegressor(random_state=0, n_jobs=-1, **kw)


def baselines():
    return {"ridge_linear": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
            "random_forest": RandomForestRegressor(n_estimators=120, max_depth=12, n_jobs=-1, random_state=0),
            "hist_gbdt_default": HistGradientBoostingRegressor(random_state=0)}


def clip_premium(p):
    return np.clip(p, PREMIUM_MIN, PREMIUM_MAX)


def metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    return dict(mae=mean_absolute_error(y, p), rmse=mean_squared_error(y, p) ** 0.5, r2=r2_score(y, p),
                mape=float(np.mean(np.abs((y - p) / y)) * 100), within_2rs=float(np.mean(np.abs(y - p) <= 2.0) * 100))


def cv_scores(model_fn, X, y, n_splits=5):
    tss = TimeSeriesSplit(n_splits=n_splits); maes, rmses = [], []
    for tr, va in tss.split(X):
        m = model_fn(); m.fit(X.iloc[tr], y.iloc[tr]); p = clip_premium(m.predict(X.iloc[va]))
        maes.append(mean_absolute_error(y.iloc[va], p)); rmses.append(mean_squared_error(y.iloc[va], p) ** 0.5)
    return dict(cv_mae_mean=float(np.mean(maes)), cv_mae_std=float(np.std(maes)), cv_rmse_mean=float(np.mean(rmses)))


def grid_configs(fast=False):
    g = FAST_GRID if fast else GRID
    keys = list(g)
    return [dict(zip(keys, v)) for v in itertools.product(*g.values())]
