"""Seeded synthetic data generators (weekly pricing table, claims, hourly weather).

Real platform earnings are proprietary, so all data here is synthetic. Seeds make every
number in the project report reproducible.
"""
import numpy as np
import pandas as pd

PERSONAS = {"food": dict(rate=95.0, hours=42.0), "qcom": dict(rate=110.0, hours=48.0), "ecom": dict(rate=85.0, hours=40.0)}
FEATURES = ["flood_score", "rain_fc_mm", "rain_days_fc", "aqi_fc", "temp_max_fc", "curfew_risk_30d",
            "hist_disrupt_hrs_12w", "hourly_rate", "active_hours", "season_sin", "season_cos",
            "persona_food", "persona_qcom"]
TARGET = "premium_inr"
N_WEEKS = 156  # 3 years
TRAIN_END, VAL_END, TEST_END = 84, 104, 130  # temporal split; weeks >= 130 form the monitoring stream
DATA_DRIFT_START, CONCEPT_DRIFT_START = 130, 143
PREMIUM_MIN, PREMIUM_MAX = 15.0, 40.0
PREMIUM_BASE, PREMIUM_LOAD = 16.0, 0.085  # premium = base + expected_loss * load


def make_zones(n=40, seed=7):
    rng = np.random.RandomState(seed)
    return pd.DataFrame({"zone_id": np.arange(n), "flood_score": rng.beta(2, 3, n).round(3)})


def seasonal_components(week):
    woy = week % 52
    monsoon = np.exp(-((woy - 31) / 7.0) ** 2) + 0.7 * np.exp(-((woy - 45) / 3.5) ** 2)  # SW + NE monsoon
    heat = np.exp(-((woy - 18) / 4.0) ** 2)
    smog = np.exp(-((woy - 48) / 4.0) ** 2) + np.exp(-((woy - 1) / 3.0) ** 2)
    return woy, monsoon, heat, smog


def true_disruption_hours(df, concept_shift=False):
    rain = df.flood_score * np.clip(df.rain_fc_mm - 20, 0, None) * 0.11 + 0.05 * np.clip(df.rain_fc_mm - 50, 0, None) ** 1.3 * df.flood_score
    if concept_shift:  # drainage failure: flood-prone zones now lose far more hours per mm of rain
        rain = rain * np.where(df.flood_score > 0.4, 1.9, 1.2)
    aqi = np.clip(df.aqi_fc - 300, 0, None) / 100.0 * 2.4
    heat = np.clip(df.temp_max_fc - 40, 0, None) * 0.9
    curfew = df.curfew_risk_30d * 1.6
    return rain + aqi + heat + curfew


def premium_from_hours(df, hours, noise_sd=0.0, rng=None):
    exp_loss = hours * df.hourly_rate * 0.7  # 70 % wage replacement
    prem = PREMIUM_BASE + exp_loss * PREMIUM_LOAD
    if noise_sd and rng is not None:
        prem = prem + rng.normal(0, noise_sd, len(df))
    return np.clip(prem, PREMIUM_MIN, PREMIUM_MAX)


def expected_loss_from_premium(premium):
    """Invert the pricing rule: expected weekly payout (INR) implied by a premium."""
    return np.maximum(np.asarray(premium, float) - PREMIUM_BASE, 0.0) / PREMIUM_LOAD


def generate_weekly(seed=42, n_weeks=N_WEEKS, n_zones=40):
    rng = np.random.RandomState(seed)
    zones = make_zones(n_zones)
    rows = []
    for w in range(n_weeks):
        woy, mon, heat, smog = seasonal_components(w)
        data_shift = w >= DATA_DRIFT_START
        for _, z in zones.iterrows():
            for p, meta in PERSONAS.items():
                rain = max(0.0, rng.gamma(2.0, 5.0) + 42 * mon * (0.6 + 0.8 * rng.rand()) * (1.35 if data_shift else 1.0) - 6)
                rows.append(dict(week=w, zone_id=int(z.zone_id), persona=p, flood_score=z.flood_score,
                                 rain_fc_mm=rain, rain_days_fc=np.clip(rng.poisson(0.8 + 3.2 * mon), 0, 7),
                                 aqi_fc=np.clip(rng.normal(150 + 260 * smog, 45), 40, 500),
                                 temp_max_fc=rng.normal(32 + 9 * heat + (1.8 if data_shift else 0), 1.8),
                                 curfew_risk_30d=float(rng.poisson(0.12 + 0.05 * (z.flood_score > 0.6))),
                                 hourly_rate=meta["rate"] * rng.normal(1, 0.04), active_hours=meta["hours"] * rng.normal(1, 0.05),
                                 season_sin=np.sin(2 * np.pi * woy / 52), season_cos=np.cos(2 * np.pi * woy / 52)))
    df = pd.DataFrame(rows)
    df["persona_food"] = (df.persona == "food").astype(int)
    df["persona_qcom"] = (df.persona == "qcom").astype(int)
    hrs = np.where(df.week >= CONCEPT_DRIFT_START, true_disruption_hours(df, True), true_disruption_hours(df, False))
    df["true_hours"] = hrs
    df[TARGET] = premium_from_hours(df, pd.Series(hrs, index=df.index), noise_sd=1.2, rng=rng)
    # rolling 12-week realised disruption hours per (zone, persona): a legitimate lagged feature (shifted by 1 week)
    df = df.sort_values(["zone_id", "persona", "week"]).reset_index(drop=True)
    df["hist_disrupt_hrs_12w"] = (df.groupby(["zone_id", "persona"])["true_hours"]
                                  .transform(lambda s: s.shift(1).rolling(12, min_periods=1).mean())).fillna(0.0)
    return df.sort_values(["week", "zone_id", "persona"]).reset_index(drop=True)


def split_temporal(df):
    return (df[df.week < TRAIN_END], df[(df.week >= TRAIN_END) & (df.week < VAL_END)],
            df[(df.week >= VAL_END) & (df.week < TEST_END)], df[df.week >= TEST_END])


def forecast_features(flood_score, persona, week_of_year, hist_hours=None, rng=None, rain_boost=1.0):
    """Feature row for pricing one worker for an upcoming week (mock weather forecast).

    Uses the seasonal expectation of each forecast variable, so the quote is deterministic for a
    given zone, persona and week unless ``rng`` is passed.
    """
    woy, mon, heat, smog = seasonal_components(week_of_year)
    meta = PERSONAS[persona]
    jitter = (lambda sd: rng.normal(0, sd)) if rng is not None else (lambda sd: 0.0)
    rain = max(0.0, (10.0 + 42 * mon * 1.0 - 6) * rain_boost + jitter(4))
    row = dict(flood_score=float(flood_score), rain_fc_mm=rain, rain_days_fc=float(np.clip(0.8 + 3.2 * mon, 0, 7)),
               aqi_fc=float(np.clip(150 + 260 * smog + jitter(20), 40, 500)), temp_max_fc=float(32 + 9 * heat + jitter(0.8)),
               curfew_risk_30d=0.12 + 0.05 * (flood_score > 0.6), hourly_rate=meta["rate"], active_hours=meta["hours"],
               season_sin=float(np.sin(2 * np.pi * woy / 52)), season_cos=float(np.cos(2 * np.pi * woy / 52)),
               persona_food=int(persona == "food"), persona_qcom=int(persona == "qcom"))
    if hist_hours is None:
        hist_hours = float(true_disruption_hours(pd.DataFrame([row])).iloc[0])
    row["hist_disrupt_hrs_12w"] = float(hist_hours)
    return pd.DataFrame([row])[FEATURES]


def generate_claims(n=30000, seed=11, fraud_rate=0.06):
    """Claims with telemetry features. Three fraud archetypes: GPS spoofing, fake presence, claim farming."""
    rng = np.random.RandomState(seed)
    y = (rng.rand(n) < fraud_rate).astype(int)
    kind = np.where(y == 1, rng.choice(["spoof", "presence", "farming"], n, p=[0.5, 0.3, 0.2]), "genuine")
    d = pd.DataFrame({
        "gps_cell_dist_km": rng.gamma(2.0, 0.35, n),
        "max_speed_kmph": np.clip(rng.normal(29, 8, n), 0, None),
        "max_ping_gap_min": rng.gamma(2.0, 2.2, n),
        "claims_last_7d": rng.poisson(0.35, n),
        "zone_match_ratio": np.clip(rng.beta(18, 2, n), 0, 1),
        "orders_before_event": rng.poisson(3.2, n),
        "device_count_24h": 1 + rng.binomial(1, 0.03, n)})
    s = kind == "spoof"; p = kind == "presence"; f = kind == "farming"
    d.loc[s, "gps_cell_dist_km"] = rng.gamma(6.0, 1.0, s.sum()); d.loc[s, "max_speed_kmph"] = rng.normal(85, 30, s.sum()).clip(20, 250)
    d.loc[p, "zone_match_ratio"] = rng.beta(3, 5, p.sum()); d.loc[p, "orders_before_event"] = rng.poisson(0.4, p.sum())
    d.loc[p, "gps_cell_dist_km"] = rng.gamma(3.0, 0.8, p.sum())
    d.loc[f, "claims_last_7d"] = rng.poisson(4.0, f.sum()) + 2; d.loc[f, "device_count_24h"] = 2 + rng.binomial(2, 0.5, f.sum())
    d.loc[f, "max_ping_gap_min"] = rng.gamma(5.0, 3.0, f.sum())
    d["is_fraud"] = y; d["kind"] = kind
    return d


def claim_telemetry(kind, rng):
    """One claim's telemetry for the live simulator, drawn from the same archetypes as ``generate_claims``."""
    t = dict(gps_cell_dist_km=rng.gamma(2.0, 0.35), max_speed_kmph=max(0.0, rng.normal(29, 8)),
             max_ping_gap_min=rng.gamma(2.0, 2.2), claims_last_7d=int(rng.poisson(0.35)),
             zone_match_ratio=float(np.clip(rng.beta(18, 2), 0, 1)), orders_before_event=int(rng.poisson(3.2)),
             device_count_24h=1 + int(rng.binomial(1, 0.03)))
    if kind == "spoof":
        t.update(gps_cell_dist_km=rng.gamma(6.0, 1.0), max_speed_kmph=float(np.clip(rng.normal(85, 30), 20, 250)))
    elif kind == "presence":
        t.update(zone_match_ratio=rng.beta(3, 5), orders_before_event=int(rng.poisson(0.4)), gps_cell_dist_km=rng.gamma(3.0, 0.8))
    elif kind == "farming":
        t.update(claims_last_7d=int(rng.poisson(4.0)) + 2, device_count_24h=2 + int(rng.binomial(2, 0.5)), max_ping_gap_min=rng.gamma(5.0, 3.0))
    return {k: float(v) for k, v in t.items()}


def generate_hourly_weather(days=365, n_zones=10, seed=5):
    """Hourly ground-truth and noisy sensor readings used to evaluate the parametric triggers."""
    rng = np.random.RandomState(seed)
    h = days * 24
    rows = []
    for z in range(n_zones):
        t = np.arange(h); woy = (t // 24 // 7) % 52
        mon = np.exp(-((woy - 31) / 7.0) ** 2) + 0.7 * np.exp(-((woy - 45) / 3.5) ** 2)
        rain = np.where(rng.rand(h) < 0.02 + 0.10 * mon, rng.gamma(3.0, 9.0, h), rng.gamma(0.5, 0.6, h))
        aqi = np.clip(rng.normal(170 + 240 * (np.exp(-((woy - 48) / 4.0) ** 2)), 55), 30, 500)
        hod = t % 24
        temp = rng.normal(31 + 8 * np.exp(-((woy - 18) / 4.0) ** 2) + 3 * np.sin((hod - 9) * np.pi / 12), 1.4)
        rows.append(pd.DataFrame(dict(zone=z, hour=t, rain_true=rain, aqi_true=aqi, temp_true=temp,
                                      rain_obs=rain + rng.normal(0, 2.0, h), aqi_obs=aqi + rng.normal(0, 12, h),
                                      temp_obs=temp + rng.normal(0, 0.6, h))))
    return pd.concat(rows, ignore_index=True)
