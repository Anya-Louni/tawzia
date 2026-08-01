"""
core/weather_dz.py
------------------
Real Algerian weather, wired to Open-Meteo.

Why weather belongs in a workforce model
========================================
Weather is not decoration here. In Algerian ground operations it moves three
things that all land on the roster:

  * **Delivery productivity.** Rain in Algiers or Oran slows last-mile drops
    and pushes the failed-attempt rate up. In a 95%-cash-on-delivery market a
    failed attempt is not a rescheduled visit - it is a return leg the
    merchant pays for.
  * **Volume.** Heat above roughly 38C suppresses same-day footfall and
    shifts orders to evening slots. The Sahara wilayas (Ouargla, Adrar,
    Tamanrasset) spend much of the summer there.
  * **Labour supply and safety.** Extreme heat drives absenteeism and legally
    mandated rest breaks, cutting effective hours per rostered worker.

Open-Meteo gives us the ERA5 reanalysis archive (real observed history, not a
model guess) plus an operational forecast, per coordinate, with no API key and
no rate limit worth worrying about. That means our history is genuinely real
even though the operational volumes are simulated.

Everything is cached to disk on first fetch, so a laptop that has been online
once will run the full demo on a competition floor with no wifi.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from typing import Optional

import numpy as np
import pandas as pd

CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache"
)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


# ---------------------------------------------------------------------------
# Algerian wilaya capitals
# ---------------------------------------------------------------------------
# Coordinates of the wilaya capitals that carry the bulk of Algeria's
# commercial and logistics activity. `weight` is a rough share of national
# parcel/retail volume, used only to build a sensible multi-site default -
# a real deployment reads actual site volumes from the customer.

WILAYAS = {
    "Alger":        {"lat": 36.7538, "lon": 3.0588,  "weight": 0.26, "climate": "coastal"},
    "Oran":         {"lat": 35.6971, "lon": -0.6308, "weight": 0.13, "climate": "coastal"},
    "Constantine":  {"lat": 36.3650, "lon": 6.6147,  "weight": 0.08, "climate": "highland"},
    "Blida":        {"lat": 36.4703, "lon": 2.8277,  "weight": 0.06, "climate": "coastal"},
    "Setif":        {"lat": 36.1898, "lon": 5.4108,  "weight": 0.06, "climate": "highland"},
    "Annaba":       {"lat": 36.9000, "lon": 7.7667,  "weight": 0.05, "climate": "coastal"},
    "Bejaia":       {"lat": 36.7500, "lon": 5.0667,  "weight": 0.05, "climate": "coastal"},
    "Batna":        {"lat": 35.5560, "lon": 6.1741,  "weight": 0.04, "climate": "highland"},
    "Tlemcen":      {"lat": 34.8828, "lon": -1.3167, "weight": 0.04, "climate": "highland"},
    "Skikda":       {"lat": 36.8761, "lon": 6.9092,  "weight": 0.03, "climate": "coastal"},
    "Tizi Ouzou":   {"lat": 36.7169, "lon": 4.0497,  "weight": 0.04, "climate": "highland"},
    "Biskra":       {"lat": 34.8500, "lon": 5.7333,  "weight": 0.03, "climate": "saharan"},
    "Djelfa":       {"lat": 34.6703, "lon": 3.2630,  "weight": 0.03, "climate": "steppe"},
    "Ouargla":      {"lat": 31.9492, "lon": 5.3256,  "weight": 0.03, "climate": "saharan"},
    "Ghardaia":     {"lat": 32.4900, "lon": 3.6700,  "weight": 0.02, "climate": "saharan"},
    "Mostaganem":   {"lat": 35.9315, "lon": 0.0892,  "weight": 0.02, "climate": "coastal"},
    "Bechar":       {"lat": 31.6167, "lon": -2.2167, "weight": 0.02, "climate": "saharan"},
    "Tamanrasset":  {"lat": 22.7850, "lon": 5.5228,  "weight": 0.01, "climate": "saharan"},
}

DEFAULT_WILAYA = "Alger"

# Thresholds that actually bite in Algerian operations.
HEAT_STRESS_C = 38.0     # above this, productivity and attendance degrade
SEVERE_HEAT_C = 44.0     # Saharan summer; mandated rest breaks
WET_DAY_MM = 1.0         # enough rain to slow last-mile delivery
HEAVY_RAIN_MM = 12.0     # route disruption


def _cache_path(name: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)


def _read_cache(name: str) -> Optional[pd.DataFrame]:
    path = _cache_path(name)
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, parse_dates=["date"])
            if not df.empty:
                return df
        except Exception:
            return None
    return None


def _write_cache(name: str, df: pd.DataFrame) -> None:
    try:
        df.to_csv(_cache_path(name), index=False)
    except Exception:
        pass  # caching is a nicety, never a hard dependency


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def fetch_history(
    wilaya: str = DEFAULT_WILAYA,
    start: str = "2023-01-01",
    end: Optional[str] = None,
    timeout: int = 30,
    allow_network: bool = True,
) -> pd.DataFrame:
    """
    Real observed daily weather for a wilaya capital, from the ERA5 archive.

    Returns a DataFrame indexed by date with temperature, precipitation, wind
    and the derived operational stress flags. Falls back to cache, then to a
    climatology-based synthetic series, so this function never blocks a demo.
    """
    if wilaya not in WILAYAS:
        raise KeyError(f"Unknown wilaya '{wilaya}'. Known: {sorted(WILAYAS)}")

    # The ERA5 archive lags real time by about 5 days.
    end = end or (_dt.date.today() - _dt.timedelta(days=6)).isoformat()
    cache_name = f"weather_{wilaya.replace(' ', '_')}_{start}_{end}.csv"

    cached = _read_cache(cache_name)
    if cached is not None:
        cached.attrs["provenance"] = "cache (Open-Meteo ERA5)"
        return cached

    if allow_network:
        try:
            import requests

            w = WILAYAS[wilaya]
            resp = requests.get(
                ARCHIVE_URL,
                params={
                    "latitude": w["lat"],
                    "longitude": w["lon"],
                    "start_date": start,
                    "end_date": end,
                    "daily": ",".join([
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_sum",
                        "windspeed_10m_max",
                    ]),
                    "timezone": "Africa/Algiers",
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            daily = resp.json()["daily"]

            df = pd.DataFrame({
                "date": pd.to_datetime(daily["time"]),
                "temp_max": daily["temperature_2m_max"],
                "temp_min": daily["temperature_2m_min"],
                "precip_mm": daily["precipitation_sum"],
                "wind_max": daily["windspeed_10m_max"],
            })
            df = _add_stress_features(df)
            _write_cache(cache_name, df)
            df.attrs["provenance"] = "Open-Meteo ERA5 reanalysis (live)"
            return df

        except Exception:
            pass  # fall through to climatology

    df = _climatology_fallback(wilaya, start, end)
    df.attrs["provenance"] = "offline climatology fallback (NOT observed data)"
    return df


def fetch_forecast(
    wilaya: str = DEFAULT_WILAYA,
    days: int = 16,
    timeout: int = 20,
    allow_network: bool = True,
) -> pd.DataFrame:
    """Operational weather forecast for the roster horizon (up to 16 days)."""
    if wilaya not in WILAYAS:
        raise KeyError(f"Unknown wilaya '{wilaya}'")

    days = int(np.clip(days, 1, 16))
    today = _dt.date.today().isoformat()
    cache_name = f"wxfc_{wilaya.replace(' ', '_')}_{today}_{days}.csv"

    cached = _read_cache(cache_name)
    if cached is not None:
        cached.attrs["provenance"] = "cache (Open-Meteo forecast)"
        return cached

    if allow_network:
        try:
            import requests

            w = WILAYAS[wilaya]
            resp = requests.get(
                FORECAST_URL,
                params={
                    "latitude": w["lat"],
                    "longitude": w["lon"],
                    "daily": ",".join([
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_sum",
                        "windspeed_10m_max",
                    ]),
                    "forecast_days": days,
                    "timezone": "Africa/Algiers",
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            daily = resp.json()["daily"]

            df = pd.DataFrame({
                "date": pd.to_datetime(daily["time"]),
                "temp_max": daily["temperature_2m_max"],
                "temp_min": daily["temperature_2m_min"],
                "precip_mm": daily["precipitation_sum"],
                "wind_max": daily["windspeed_10m_max"],
            })
            df = _add_stress_features(df)
            _write_cache(cache_name, df)
            df.attrs["provenance"] = "Open-Meteo operational forecast (live)"
            return df

        except Exception:
            pass

    start = _dt.date.today()
    df = _climatology_fallback(
        wilaya, start.isoformat(), (start + _dt.timedelta(days=days - 1)).isoformat()
    )
    df.attrs["provenance"] = "offline climatology fallback (NOT a real forecast)"
    return df


# ---------------------------------------------------------------------------
# Derived operational features
# ---------------------------------------------------------------------------

def _add_stress_features(df: pd.DataFrame) -> pd.DataFrame:
    """Turn raw weather into the operational signals the roster cares about."""
    df = df.copy()
    df["precip_mm"] = df["precip_mm"].fillna(0.0)
    df["temp_max"] = df["temp_max"].ffill().bfill()
    df["temp_min"] = df["temp_min"].ffill().bfill()
    df["wind_max"] = df["wind_max"].fillna(0.0)

    df["is_wet_day"] = (df["precip_mm"] >= WET_DAY_MM).astype(int)
    df["is_heavy_rain"] = (df["precip_mm"] >= HEAVY_RAIN_MM).astype(int)
    df["heat_stress"] = np.clip(
        (df["temp_max"] - HEAT_STRESS_C) / (SEVERE_HEAT_C - HEAT_STRESS_C), 0, 1.5
    )

    # Productivity multiplier: how much of a nominal shift actually converts
    # into completed work. Rain slows the road; heat cuts sustainable pace.
    rain_drag = 0.10 * df["is_wet_day"] + 0.10 * df["is_heavy_rain"]
    heat_drag = 0.12 * df["heat_stress"]
    df["weather_productivity"] = np.clip(1.0 - rain_drag - heat_drag, 0.60, 1.0)

    # Demand multiplier: bad weather suppresses footfall but lifts delivery.
    df["weather_demand"] = np.clip(
        1.0 + 0.05 * df["is_wet_day"] - 0.06 * df["heat_stress"], 0.85, 1.10
    )
    return df


def _climatology_fallback(wilaya: str, start: str, end: str) -> pd.DataFrame:
    """
    Offline stand-in built from each climate zone's seasonal profile.

    Clearly labelled as a fallback everywhere it surfaces. It exists so the
    app degrades gracefully with no network - it is never presented as
    observed data.
    """
    dates = pd.date_range(start, end, freq="D")
    climate = WILAYAS[wilaya]["climate"]

    profile = {
        "coastal":  {"t_mean": 19.0, "t_amp": 8.5,  "rain_win": 0.32, "rain_sum": 0.02},
        "highland": {"t_mean": 17.0, "t_amp": 11.0, "rain_win": 0.26, "rain_sum": 0.03},
        "steppe":   {"t_mean": 20.0, "t_amp": 12.5, "rain_win": 0.14, "rain_sum": 0.03},
        "saharan":  {"t_mean": 25.5, "t_amp": 13.5, "rain_win": 0.04, "rain_sum": 0.01},
    }[climate]

    doy = dates.dayofyear.to_numpy()
    seasonal = -np.cos(2 * np.pi * (doy - 15) / 365.25)
    rng = np.random.default_rng(abs(hash(wilaya)) % (2**32))

    temp_max = profile["t_mean"] + profile["t_amp"] * seasonal + 6.0 + rng.normal(0, 2.5, len(dates))
    temp_min = temp_max - (9.0 if climate != "saharan" else 14.0) + rng.normal(0, 1.5, len(dates))

    is_winter = (doy < 90) | (doy > 300)
    p_rain = np.where(is_winter, profile["rain_win"], profile["rain_sum"])
    wet = rng.random(len(dates)) < p_rain
    precip = np.where(wet, rng.exponential(5.0, len(dates)), 0.0)

    df = pd.DataFrame({
        "date": dates,
        "temp_max": temp_max,
        "temp_min": temp_min,
        "precip_mm": precip,
        "wind_max": rng.uniform(5, 30, len(dates)),
    })
    return _add_stress_features(df)


def national_weather(start: str, end: str, allow_network: bool = True) -> pd.DataFrame:
    """
    Volume-weighted national weather signal across the major wilayas.

    Used when a customer runs a national network rather than one site.
    """
    frames = []
    for name, meta in WILAYAS.items():
        if meta["weight"] < 0.03:
            continue  # keep the fetch light; the tail barely moves the average
        df = fetch_history(name, start, end, allow_network=allow_network)
        df = df[["date", "weather_productivity", "weather_demand", "temp_max", "precip_mm"]].copy()
        for col in ("weather_productivity", "weather_demand", "temp_max", "precip_mm"):
            df[col] = df[col] * meta["weight"]
        frames.append(df)

    total_weight = sum(m["weight"] for m in WILAYAS.values() if m["weight"] >= 0.03)
    combined = frames[0]
    for f in frames[1:]:
        combined = combined.merge(f, on="date", how="outer", suffixes=("", "_r"))
        for col in ("weather_productivity", "weather_demand", "temp_max", "precip_mm"):
            combined[col] = combined[col].fillna(0) + combined[f"{col}_r"].fillna(0)
            combined.drop(columns=[f"{col}_r"], inplace=True)

    for col in ("weather_productivity", "weather_demand", "temp_max", "precip_mm"):
        combined[col] = combined[col] / total_weight

    return combined.sort_values("date").reset_index(drop=True)


if __name__ == "__main__":
    print("Open-Meteo integration - self check\n")

    hist = fetch_history("Alger", "2024-06-01", "2024-08-31")
    print(f"Alger, summer 2024 - {len(hist)} days")
    print(f"  provenance : {hist.attrs.get('provenance')}")
    print(f"  temp max   : {hist['temp_max'].min():.1f}C to {hist['temp_max'].max():.1f}C")
    print(f"  wet days   : {int(hist['is_wet_day'].sum())}")
    print(f"  mean productivity multiplier : {hist['weather_productivity'].mean():.3f}")

    print()
    sah = fetch_history("Ouargla", "2024-06-01", "2024-08-31")
    print(f"Ouargla (Sahara), summer 2024 - provenance: {sah.attrs.get('provenance')}")
    print(f"  temp max   : {sah['temp_max'].min():.1f}C to {sah['temp_max'].max():.1f}C")
    print(f"  days over {HEAT_STRESS_C}C : {int((sah['temp_max'] > HEAT_STRESS_C).sum())}")
    print(f"  mean productivity multiplier : {sah['weather_productivity'].mean():.3f}")

    print()
    fc = fetch_forecast("Alger", days=14)
    print(f"Alger 14-day forecast - provenance: {fc.attrs.get('provenance')}")
    print(fc[["date", "temp_max", "precip_mm", "weather_productivity"]].head(7).to_string(index=False))
