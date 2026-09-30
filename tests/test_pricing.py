import numpy as np
from giginsure import data as D, pricing as P


def test_metrics_on_perfect_prediction():
    y = np.array([20.0, 25.0, 30.0])
    m = P.metrics(y, y)
    assert m["mae"] == 0 and m["rmse"] == 0 and m["r2"] == 1 and m["within_2rs"] == 100


def _split(weekly):
    tr, te = weekly[weekly.week < 45], weekly[weekly.week >= 45]
    return tr[D.FEATURES], tr[D.TARGET], te[D.FEATURES], te[D.TARGET]


def test_gbdt_beats_linear_baseline_on_holdout(weekly):
    X, y, Xt, yt = _split(weekly)
    lin = P.baselines()["ridge_linear"].fit(X, y)
    gb = P.make_gbdt(learning_rate=0.1, max_depth=3, n_estimators=150, subsample=0.8).fit(X, y)
    mae_lin = P.metrics(yt, P.clip_premium(lin.predict(Xt)))["mae"]
    mae_gb = P.metrics(yt, P.clip_premium(gb.predict(Xt)))["mae"]
    assert mae_gb < 0.6 * mae_lin


def test_clipped_predictions_stay_in_band(weekly):
    X, y, Xt, _ = _split(weekly)
    p = P.clip_premium(P.baselines()["ridge_linear"].fit(X, y).predict(Xt * 3))
    assert (p >= 15).all() and (p <= 40).all()


def test_flood_prone_zone_pays_more_than_safe_zone(weekly):
    X, y, _, _ = _split(weekly)
    gb = P.make_gbdt(learning_rate=0.1, max_depth=3, n_estimators=150, subsample=0.8).fit(X, y)
    safe = D.forecast_features(0.02, "food", 31, hist_hours=2.0)
    flood = D.forecast_features(0.95, "food", 31, hist_hours=2.0)
    assert gb.predict(safe)[0] < gb.predict(flood)[0]


def test_cross_validation_returns_scores(weekly):
    X, y, _, _ = _split(weekly)
    cv = P.cv_scores(lambda: P.baselines()["ridge_linear"], X, y, n_splits=3)
    assert set(cv) == {"cv_mae_mean", "cv_mae_std", "cv_rmse_mean"} and cv["cv_mae_mean"] > 0
