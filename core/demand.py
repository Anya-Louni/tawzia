"""
core/demand.py
--------------
Operational demand history for an Algerian site.

Read this before you quote any number out of it
===============================================

We do not have a real Algerian carrier's parcel ledger. Nobody outside those
companies does. So the *volume* series here is simulated - and we say so
everywhere it surfaces.

What is NOT simulated is the thing that matters:

  * the calendar the volume responds to is the **real** Algerian calendar -
    real Ramadan and Aid dates, real Friday-Saturday weekend, real gazetted
    holidays, real rentree window, real diaspora season;
  * the weather the volume responds to is **real observed weather** from the
    ERA5 archive for the actual wilaya.

So the *shape* of the series is real even though the *scale* is invented.
That distinction is the whole point, and it is what makes the backtest in
`forecast.py` meaningful rather than circular.

Guarding against circularity
============================
A simulator plus a model fitted to that simulator will always look brilliant
unless you deliberately stop it. Three things here prevent that:

1. **The forecaster never sees the generator's parameters.** It gets a dated
   volume series and public calendar/weather features, nothing else. It has
   to learn the Ramadan uplift from data, the same as it would in production.

2. **An irreducible component the model provably cannot predict.** Flash
   promotions, supplier stock-outs, wildcat strikes, road closures and a fat
   tail of ordinary chaos are injected from a stream the feature set has no
   access to. This puts a hard floor under achievable error - which is why
   the backtest lands in single-to-low-double-digit MAPE rather than the
   suspicious 2% that would give the whole thing away.

3. **Regime drift.** Base volume, growth rate and weekday mix shift partway
   through the history, as they do when a real operator opens a hub or wins
   an account. A model that assumes a stationary world gets punished.

Even so: **these results validate the engine, not the market.** Real accuracy
numbers require a pilot with a real operator. The app says this out loud.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from . import calendar_dz, weather_dz


# ---------------------------------------------------------------------------
# Vertical profiles
# ---------------------------------------------------------------------------

@dataclass
class OperationProfile:
    """
    How one kind of Algerian operation responds to the Algerian calendar.

    The multipliers encode domain knowledge about Algerian demand. They are
    modelling choices - a pilot replaces them with fitted values from the
    customer's own history within the first fortnight.
    """
    key: str
    label: str
    demand_unit: str
    primary_role: str
    base_daily_volume: float
    shift_split: dict

    # Calendar responses
    ramadan_lift: float          # average uplift across the month
    ramadan_evening_shift: float # how much of the day moves to the late shift
    pre_eid_peak: float          # peak multiplier in the last days before Aid
    eid_shutdown: float          # multiplier on the two Aid days themselves
    friday_mult: float           # Algeria's primary rest day
    saturday_mult: float
    diaspora_lift: float         # peak-season uplift
    rentree_lift: float
    payday_lift: float
    holiday_mult: float

    weather_sensitivity: float = 1.0
    growth_per_year: float = 0.12
    noise_std: float = 0.09
    shock_rate: float = 0.035    # probability of an unmodellable shock day
    description: str = ""


PROFILES = {
    "ecom_hub": OperationProfile(
        key="ecom_hub",
        label="Hub e-commerce",
        demand_unit="parcels",
        primary_role="sorter",
        base_daily_volume=9_500,
        shift_split={"morning": 0.42, "afternoon": 0.40, "night": 0.18},
        ramadan_lift=1.28,
        ramadan_evening_shift=0.18,
        pre_eid_peak=2.05,
        eid_shutdown=0.18,
        friday_mult=0.52,
        saturday_mult=0.78,
        diaspora_lift=1.12,
        rentree_lift=1.22,
        payday_lift=1.16,
        holiday_mult=0.35,
        weather_sensitivity=1.0,
        growth_per_year=0.18,
        description=(
            "A parcel sorting and dispatch hub serving cash-on-delivery "
            "e-commerce. The beachhead vertical: private operators, many "
            "sites, and a direct line from a mis-staffed shift to a failed "
            "delivery the merchant pays for twice."
        ),
    ),
    "airport_ground": OperationProfile(
        key="airport_ground",
        label="Assistance aéroportuaire",
        demand_unit="passengers",
        primary_role="checkin_agent",
        base_daily_volume=14_000,
        shift_split={"morning": 0.40, "afternoon": 0.38, "night": 0.22},
        ramadan_lift=0.88,
        ramadan_evening_shift=0.22,
        pre_eid_peak=1.65,
        eid_shutdown=0.55,
        friday_mult=0.92,
        saturday_mult=1.02,
        diaspora_lift=1.85,
        rentree_lift=1.02,
        payday_lift=1.02,
        holiday_mult=0.80,
        weather_sensitivity=0.6,
        growth_per_year=0.07,
        description=(
            "Check-in, boarding and ramp handling at a major Algerian "
            "gateway. Dominated by the summer diaspora return - a demand "
            "pattern that reads as a trough to any model trained on European "
            "seasonality, and is in fact the annual peak."
        ),
    ),
    "retail_dc": OperationProfile(
        key="retail_dc",
        label="Centre de distribution retail",
        demand_unit="cases",
        primary_role="warehouse_op",
        base_daily_volume=6_800,
        shift_split={"morning": 0.45, "afternoon": 0.37, "night": 0.18},
        ramadan_lift=1.52,
        ramadan_evening_shift=0.10,
        pre_eid_peak=1.70,
        eid_shutdown=0.25,
        friday_mult=0.48,
        saturday_mult=0.85,
        diaspora_lift=1.10,
        rentree_lift=1.10,
        payday_lift=1.24,
        holiday_mult=0.40,
        weather_sensitivity=0.8,
        growth_per_year=0.09,
        description=(
            "Grocery and FMCG distribution. The most Ramadan-exposed of the "
            "three: food volume front-loads hard into the first days of the "
            "month and again before Aid."
        ),
    ),
    "hotel": OperationProfile(
        key="hotel",
        label="Hôtellerie",
        demand_unit="occupied rooms",
        primary_role="housekeeper",
        base_daily_volume=520,
        shift_split={"morning": 0.46, "afternoon": 0.34, "night": 0.20},
        ramadan_lift=0.82,          # leisure dips, but F&B reshapes to night
        ramadan_evening_shift=0.30,
        pre_eid_peak=1.35,
        eid_shutdown=1.20,          # Aid travel actually fills leisure hotels
        friday_mult=1.10,           # weekend leisure peak (Fri-Sat here)
        saturday_mult=1.12,
        diaspora_lift=1.70,         # coastal summer fills on the diaspora + tourism
        rentree_lift=0.85,
        payday_lift=1.05,
        holiday_mult=1.15,
        weather_sensitivity=0.7,    # heat and rain move coastal vs city demand
        growth_per_year=0.10,
        description=(
            "Housekeeping, front desk and F&B in a hotel. Occupancy is "
            "seasonal, event-driven and diaspora-driven; Ramadan does not "
            "empty the hotel, it moves the whole F&B shift to after f'tour."
        ),
    ),
    "transport": OperationProfile(
        key="transport",
        label="Transport de personnes & flotte",
        demand_unit="passenger-trips",
        primary_role="driver",
        base_daily_volume=4_200,
        shift_split={"morning": 0.42, "afternoon": 0.36, "night": 0.22},
        ramadan_lift=1.10,          # heavy evening/pre-dawn travel
        ramadan_evening_shift=0.28,
        pre_eid_peak=2.20,          # the biggest travel surge of the year
        eid_shutdown=0.60,
        friday_mult=1.05,
        saturday_mult=0.80,
        diaspora_lift=1.55,         # summer intercity + airport-transfer surge
        rentree_lift=1.25,          # students returning to campus cities
        payday_lift=1.08,
        holiday_mult=1.30,
        weather_sensitivity=0.9,    # storms and heat disrupt road schedules
        growth_per_year=0.08,
        description=(
            "Intercity coach, airport-transfer and fleet operations. Demand is "
            "dominated by the pre-Aid travel surge and the diaspora summer, "
            "with drivers bound by statutory driving-time limits."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Demand construction
# ---------------------------------------------------------------------------

def _calendar_multiplier(row: pd.Series, p: OperationProfile) -> float:
    """Combine the Algerian calendar drivers into one daily multiplier."""
    mult = 1.0

    # Weekly rhythm - Algeria's weekend is Friday and Saturday.
    if row["weekday"] == 4:
        mult *= p.friday_mult
    elif row["weekday"] == 5:
        mult *= p.saturday_mult
    elif row["weekday"] == 6:      # Sunday is a full working day here
        mult *= 1.04
    elif row["weekday"] == 3:      # Thursday: pre-weekend push
        mult *= 1.08

    # Ramadan. The uplift is not flat - it builds through the month and peaks
    # in the last ten nights as Aid shopping starts.
    if row["is_ramadan"]:
        progress = row["ramadan_progress"]
        shape = 0.75 + 0.85 * progress
        mult *= 1.0 + (p.ramadan_lift - 1.0) * shape

    # The pre-Aid surge. Sharpest in the final week.
    runup = row["eid_fitr_runup"]
    if runup > 0:
        mult *= 1.0 + (p.pre_eid_peak - 1.0) * (runup ** 3)
    runup_adha = row["eid_adha_runup"]
    if runup_adha > 0:
        mult *= 1.0 + (p.pre_eid_peak - 1.0) * 0.55 * (runup_adha ** 3)

    # The Aid days themselves - near shutdown, then a rebound.
    if row["is_public_holiday"]:
        name = str(row["holiday_name"])
        mult *= p.eid_shutdown if "Aid" in name else p.holiday_mult

    # Diaspora season and rentree.
    mult *= 1.0 + (p.diaspora_lift - 1.0) * row["diaspora_intensity"]
    if row["is_rentree"]:
        mult *= p.rentree_lift

    # Payday cycle.
    mult *= 1.0 + (p.payday_lift - 1.0) * row["payday_boost"]

    return mult


def build_history(
    profile_key: str = "ecom_hub",
    wilaya: str = "Alger",
    start: str = "2023-01-01",
    end: Optional[str] = None,
    seed: int = 7,
    allow_network: bool = True,
) -> pd.DataFrame:
    """
    Build a daily demand history for one site.

    Returns one row per (date, shift) with the realised volume, plus every
    calendar and weather feature that a forecaster is allowed to see.

    The generator's own multipliers are deliberately NOT returned - the
    forecaster must infer them.
    """
    if profile_key not in PROFILES:
        raise KeyError(f"Unknown profile '{profile_key}'. Known: {sorted(PROFILES)}")
    p = PROFILES[profile_key]

    import datetime as _dt
    end = end or (_dt.date.today() - _dt.timedelta(days=6)).isoformat()

    cal = calendar_dz.calendar_frame(start, end)
    wx = weather_dz.fetch_history(wilaya, start, end, allow_network=allow_network)
    wx_provenance = wx.attrs.get("provenance", "unknown")

    df = cal.merge(
        wx[["date", "temp_max", "temp_min", "precip_mm", "is_wet_day",
            "heat_stress", "weather_productivity", "weather_demand"]],
        on="date",
        how="left",
    )
    # ERA5 can lag; carry the last observation forward rather than dropping days.
    for col in ("temp_max", "temp_min", "precip_mm", "weather_productivity", "weather_demand"):
        df[col] = df[col].ffill().bfill()
    df["is_wet_day"] = df["is_wet_day"].fillna(0).astype(int)
    df["heat_stress"] = df["heat_stress"].fillna(0.0)

    rng = np.random.default_rng(seed)
    n = len(df)

    # Trend, with a regime change partway through - operators open hubs and
    # win accounts, and a model that assumes stationarity should suffer.
    t = np.arange(n) / 365.0
    regime_start = int(n * 0.55)
    growth = np.where(
        np.arange(n) < regime_start,
        1 + p.growth_per_year * t,
        (1 + p.growth_per_year * (regime_start / 365.0))
        * (1 + p.growth_per_year * 1.7 * (t - regime_start / 365.0)),
    )

    cal_mult = df.apply(lambda r: _calendar_multiplier(r, p), axis=1).to_numpy()

    # Weather effect on demand, scaled by how exposed this vertical is.
    wx_mult = 1.0 + (df["weather_demand"].to_numpy() - 1.0) * p.weather_sensitivity

    # --- The part the forecaster cannot win against ------------------------
    # Ordinary multiplicative noise.
    noise = rng.lognormal(0.0, p.noise_std, n)

    # Discrete shocks: flash sales, supplier stock-outs, strikes, road
    # closures, a competitor's outage spilling volume onto us. These come
    # from a stream with no corresponding feature anywhere in the model's
    # input, so they are structurally unforecastable - exactly as in reality.
    shock = np.ones(n)
    is_shock = rng.random(n) < p.shock_rate
    shock[is_shock] = rng.choice(
        [0.55, 0.68, 1.45, 1.80, 2.30],
        size=int(is_shock.sum()),
        p=[0.16, 0.20, 0.30, 0.22, 0.12],
    )
    # Shocks bleed into the following day as backlog clears.
    carry = np.ones(n)
    for i in np.flatnonzero(is_shock):
        if i + 1 < n and shock[i] > 1:
            carry[i + 1] = 1.0 + (shock[i] - 1.0) * 0.35
    # -----------------------------------------------------------------------

    daily_total = (
        p.base_daily_volume * growth * cal_mult * wx_mult * noise * shock * carry
    )
    daily_total = np.maximum(daily_total, 0.0)

    df["daily_volume"] = np.round(daily_total).astype(int)
    df["_was_shock"] = is_shock  # kept for honesty reporting, never a feature

    # Split across shifts. Ramadan pushes activity into the evening.
    rows = []
    for i, r in df.iterrows():
        split = dict(p.shift_split)
        if r["is_ramadan"]:
            move = p.ramadan_evening_shift
            take_m = split["morning"] * move
            take_a = split["afternoon"] * move * 0.5
            split["morning"] -= take_m
            split["afternoon"] -= take_a
            split["night"] += take_m + take_a

        for shift_key, share in split.items():
            rows.append({
                "date": r["date"],
                "shift": shift_key,
                "volume": int(round(r["daily_volume"] * share)),
            })

    long_df = pd.DataFrame(rows)

    feature_cols = [
        "date", "weekday", "is_weekend_int", "is_holiday_int", "is_ramadan_int",
        "ramadan_progress", "eid_fitr_runup", "eid_adha_runup",
        "diaspora_intensity", "is_rentree_int", "payday_boost",
        "temp_max", "temp_min", "precip_mm", "is_wet_day", "heat_stress",
        "weather_productivity", "weather_demand",
        "holiday_name", "hijri_month_name", "ramadan_day", "calendar_confidence",
        "daily_volume", "_was_shock",
    ]
    out = long_df.merge(df[feature_cols], on="date", how="left")
    out = out.sort_values(["date", "shift"]).reset_index(drop=True)

    out.attrs["profile"] = p.label
    out.attrs["wilaya"] = wilaya
    out.attrs["demand_unit"] = p.demand_unit
    out.attrs["weather_provenance"] = wx_provenance
    out.attrs["shock_days"] = int(is_shock.sum())
    out.attrs["shock_pct"] = float(is_shock.mean())
    return out


def future_features(
    profile_key: str,
    wilaya: str,
    start,
    days: int = 14,
    allow_network: bool = True,
) -> pd.DataFrame:
    """
    Build the feature table for future dates we want to forecast.

    Calendar features are known exactly. Weather comes from the real
    Open-Meteo operational forecast where the horizon allows (16 days), and
    falls back to seasonal climatology beyond that - flagged, not hidden.
    """
    start = pd.to_datetime(start)
    end = start + pd.Timedelta(days=days - 1)

    cal = calendar_dz.calendar_frame(start, end)

    fc = weather_dz.fetch_forecast(wilaya, days=min(days, 16), allow_network=allow_network)
    wx_provenance = fc.attrs.get("provenance", "unknown")

    df = cal.merge(
        fc[["date", "temp_max", "temp_min", "precip_mm", "is_wet_day",
            "heat_stress", "weather_productivity", "weather_demand"]],
        on="date",
        how="left",
    )

    # Beyond the forecast horizon, fall back to climatology and flag it.
    df["weather_is_forecast"] = df["temp_max"].notna()
    if df["temp_max"].isna().any():
        clim = weather_dz._climatology_fallback(
            wilaya, start.date().isoformat(), end.date().isoformat()
        )
        df = df.drop(columns=[
            "temp_max", "temp_min", "precip_mm", "is_wet_day",
            "heat_stress", "weather_productivity", "weather_demand",
        ]).merge(
            clim[["date", "temp_max", "temp_min", "precip_mm", "is_wet_day",
                  "heat_stress", "weather_productivity", "weather_demand"]],
            on="date", how="left",
        )

    p = PROFILES[profile_key]
    rows = []
    for _, r in df.iterrows():
        split = dict(p.shift_split)
        if r["is_ramadan"]:
            move = p.ramadan_evening_shift
            take_m = split["morning"] * move
            take_a = split["afternoon"] * move * 0.5
            split["morning"] -= take_m
            split["afternoon"] -= take_a
            split["night"] += take_m + take_a
        for shift_key, share in split.items():
            rows.append({"date": r["date"], "shift": shift_key, "shift_share": share})

    long_df = pd.DataFrame(rows)
    out = long_df.merge(df, on="date", how="left").sort_values(["date", "shift"])
    out.attrs["weather_provenance"] = wx_provenance
    return out.reset_index(drop=True)


if __name__ == "__main__":
    print("Demand generator - self check\n")
    for key in PROFILES:
        h = build_history(key, "Alger", "2023-01-01", "2025-12-31")
        daily = h.groupby("date")["volume"].sum()
        print(f"{PROFILES[key].label}")
        print(f"  rows          : {len(h):,}  ({len(daily):,} days x 3 shifts)")
        print(f"  weather       : {h.attrs['weather_provenance']}")
        print(f"  unpredictable : {h.attrs['shock_days']} shock days "
              f"({h.attrs['shock_pct']:.1%} of history)")
        print(f"  mean/day      : {daily.mean():,.0f} {PROFILES[key].demand_unit}")
        print(f"  min / max     : {daily.min():,.0f} / {daily.max():,.0f}")

        # Does the Algerian calendar actually show up in the series?
        d = h.drop_duplicates("date")
        ram = d[d["is_ramadan_int"] == 1]["daily_volume"].mean()
        nor = d[(d["is_ramadan_int"] == 0) & (d["is_holiday_int"] == 0)]["daily_volume"].mean()
        fri = d[d["weekday"] == 4]["daily_volume"].mean()
        sun = d[d["weekday"] == 6]["daily_volume"].mean()
        print(f"  Ramadan vs ordinary day : {ram / nor:.2f}x")
        print(f"  Friday vs Sunday        : {fri / sun:.2f}x  "
              f"<- inverted in any tool that assumes a Sat/Sun weekend")
        print()
