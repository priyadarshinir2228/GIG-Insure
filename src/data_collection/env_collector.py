"""Environmental feeds for the parametric trigger engine.

Two sources:
  * ``mock``      (default) seasonal simulator with sensor noise, same process as ``generate_hourly_weather``.
  * ``openmeteo`` live readings from the free Open-Meteo weather + air-quality APIs (no key needed). Falls back
                  to the mock reading for a zone if the request fails.
Admin-injected scenarios (fake rainstorm, AQI spike, heatwave, curfew) are applied on top of either source.
"""
import time
import numpy as np
import requests

from giginsure.data import seasonal_components

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


class MockWeather:
    def __init__(self, seed=5):
        self.rng = np.random.RandomState(seed)

    def reading(self, zone, week_of_year, hour_of_day):
        _, mon, heat, smog = seasonal_components(week_of_year)
        r = self.rng
        rain = r.gamma(3.0, 9.0) if r.rand() < 0.01 + 0.05 * mon else r.gamma(0.5, 0.6)
        rain *= 0.8 + 0.4 * zone["flood_score"]
        aqi = float(np.clip(r.normal(150 + 200 * smog, 35), 30, 500))
        temp = r.normal(31 + 8 * heat + 3 * np.sin((hour_of_day - 9) * np.pi / 12), 0.9)
        return dict(rain=round(max(0.0, float(rain) + r.normal(0, 0.5)), 2), aqi=round(aqi, 1), temp=round(float(temp), 2), source="mock")


class OpenMeteoWeather:
    """Caches one live reading per zone for ``ttl_s`` seconds (Table 3.2: 15-minute refresh)."""
    def __init__(self, ttl_s=900, fallback=None):
        self.ttl, self.cache, self.fallback = ttl_s, {}, fallback or MockWeather()

    def _fetch(self, zone):
        w = requests.get(WEATHER_URL, params=dict(latitude=zone["lat"], longitude=zone["lon"],
                                                  current="precipitation,temperature_2m"), timeout=6).json()["current"]
        a = requests.get(AQ_URL, params=dict(latitude=zone["lat"], longitude=zone["lon"], current="us_aqi"), timeout=6).json()["current"]
        return dict(rain=float(w["precipitation"]), temp=float(w["temperature_2m"]), aqi=float(a["us_aqi"]), source="open-meteo")

    def reading(self, zone, week_of_year, hour_of_day):
        hit = self.cache.get(zone["id"])
        if hit and time.time() - hit[0] < self.ttl:
            return dict(hit[1])
        try:
            r = self._fetch(zone)
        except Exception:
            r = self.fallback.reading(zone, week_of_year, hour_of_day)
        self.cache[zone["id"]] = (time.time(), r)
        return dict(r)


SCENARIOS = {
    "rainstorm": dict(label="Heavy rainstorm", apply=lambda r, k, rng: r.update(rain=round(58 + 30 * k + rng.normal(0, 4), 1))),
    "aqi": dict(label="Severe AQI episode", apply=lambda r, k, rng: r.update(aqi=round(min(500, 415 + 60 * k + rng.normal(0, 8)), 1))),
    "heatwave": dict(label="Extreme heatwave", apply=lambda r, k, rng: r.update(temp=round(42.8 + 2.5 * k + rng.normal(0, 0.3), 2))),
    "curfew": dict(label="Curfew / zone closure", apply=lambda r, k, rng: r.update(curfew=True)),
}


def make_source(name):
    return OpenMeteoWeather() if name == "openmeteo" else MockWeather()
