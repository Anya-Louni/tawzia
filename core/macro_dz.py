"""
core/macro_dz.py
----------------
Algerian macroeconomic context, pulled live from the World Bank Open Data API.

Two jobs:

1. **Index the cost model to reality.** Algerian inflation ran above 9% in
   2022 and 2023. A staffing plan costed at last year's wage rates is wrong
   by a wide margin, and a savings figure that ignores it is worse than
   useless. We pull actual CPI and use it to age our labour costs.

2. **Ground the market sizing.** TAM slides invented on a whiteboard are the
   fastest way to lose a room. Population, labour force and GDP come from the
   World Bank, cited, and the arithmetic on top of them is shown.

Everything caches to disk after first fetch so the app runs offline.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import pandas as pd

CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache"
)

WB_BASE = "https://api.worldbank.org/v2/country/DZA/indicator"

INDICATORS = {
    "inflation":        ("FP.CPI.TOTL.ZG", "Inflation, consumer prices (annual %)"),
    "population":       ("SP.POP.TOTL",    "Population, total"),
    "labour_force":     ("SL.TLF.TOTL.IN", "Labour force, total"),
    "gdp_usd":          ("NY.GDP.MKTP.CD", "GDP (current US$)"),
    "gdp_per_capita":   ("NY.GDP.PCAP.CD", "GDP per capita (current US$)"),
    "unemployment":     ("SL.UEM.TOTL.ZS", "Unemployment, total (% of labour force)"),
    "urban_pop_pct":    ("SP.URB.TOTL.IN.ZS", "Urban population (% of total)"),
    "internet_pct":     ("IT.NET.USER.ZS", "Individuals using the Internet (% of population)"),
}

# Used only if the API is unreachable AND nothing is cached. Every value here
# was read back from the World Bank API on 2026-07-24 and verified against the
# raw JSON before being written down. Labelled as a fallback wherever it
# surfaces, never as a live reading.
_FALLBACK = {
    "inflation":      {"2022": 9.27, "2023": 9.32, "2024": 4.05, "2025": 1.4},
    "population":     {"2023": 46_164_219, "2024": 46_814_308, "2025": 47_435_312},
    "labour_force":   {"2023": 13_290_460, "2024": 13_425_069, "2025": 13_556_625},
    "unemployment":   {"2025": 11.6},
    "gdp_per_capita": {"2025": 6_051.0},
    "internet_pct":   {"2024": 77.4},
    "urban_pop_pct":  {"2025": 75.8},
}


def _cache_path(name: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)


def fetch_indicator(
    key: str,
    start_year: int = 2015,
    end_year: int = 2025,
    timeout: int = 20,
    allow_network: bool = True,
) -> pd.DataFrame:
    """
    Fetch one World Bank indicator for Algeria as a tidy DataFrame.

    Columns: year (int), value (float). Sorted ascending. Missing years are
    dropped rather than interpolated - a gap in the source is information.
    """
    if key not in INDICATORS:
        raise KeyError(f"Unknown indicator '{key}'. Known: {sorted(INDICATORS)}")

    code, label = INDICATORS[key]
    cache_name = f"wb_{key}_{start_year}_{end_year}.csv"
    path = _cache_path(cache_name)

    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if not df.empty:
                df.attrs["provenance"] = "cache (World Bank)"
                df.attrs["label"] = label
                return df
        except Exception:
            pass

    if allow_network:
        try:
            import requests

            resp = requests.get(
                f"{WB_BASE}/{code}",
                params={
                    "format": "json",
                    "per_page": 200,
                    "date": f"{start_year}:{end_year}",
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            payload = resp.json()

            if len(payload) < 2 or payload[1] is None:
                raise ValueError("World Bank returned no observations")

            rows = [
                {"year": int(r["date"]), "value": r["value"]}
                for r in payload[1]
                if r.get("value") is not None
            ]
            df = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
            df.to_csv(path, index=False)
            df.attrs["provenance"] = "World Bank Open Data (live)"
            df.attrs["label"] = label
            return df

        except Exception:
            pass

    fb = _FALLBACK.get(key, {})
    df = pd.DataFrame(
        [{"year": int(y), "value": v} for y, v in fb.items()]
    ).sort_values("year").reset_index(drop=True)
    df.attrs["provenance"] = "offline fallback (last observed 2026-07-24)"
    df.attrs["label"] = label
    return df


def latest(key: str, allow_network: bool = True) -> Optional[dict]:
    """Most recent observation for an indicator, with its year and provenance."""
    df = fetch_indicator(key, allow_network=allow_network)
    if df.empty:
        return None
    row = df.iloc[-1]
    return {
        "key": key,
        "label": df.attrs.get("label", key),
        "year": int(row["year"]),
        "value": float(row["value"]),
        "provenance": df.attrs.get("provenance", "unknown"),
    }


def cumulative_inflation(from_year: int, to_year: int, allow_network: bool = True) -> float:
    """
    Compound Algerian CPI inflation between two years, as a multiplier.

    Used to age wage and cost assumptions forward so a plan priced today is
    not quietly using 2022 money.
    """
    df = fetch_indicator("inflation", allow_network=allow_network)
    if df.empty:
        return 1.0
    window = df[(df["year"] > from_year) & (df["year"] <= to_year)]
    mult = 1.0
    for v in window["value"]:
        mult *= 1.0 + (v / 100.0)
    return mult


def snapshot(allow_network: bool = True) -> pd.DataFrame:
    """A small table of Algeria's headline indicators, for the UI."""
    rows = []
    for key in ("population", "gdp_per_capita", "inflation", "unemployment",
                "internet_pct", "urban_pop_pct"):
        got = latest(key, allow_network=allow_network)
        if got is None:
            continue
        rows.append({
            "Indicator": got["label"],
            "Value": got["value"],
            "Year": got["year"],
            "Source": got["provenance"],
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("World Bank / Algeria - self check\n")
    snap = snapshot()
    for _, r in snap.iterrows():
        print(f"  {r['Indicator'][:48]:<50} {r['Value']:>16,.1f}  ({r['Year']})")
    print(f"\n  provenance: {snap['Source'].iloc[0] if not snap.empty else 'n/a'}")

    mult = cumulative_inflation(2021, 2024)
    print(f"\n  Cumulative CPI inflation 2022-2024: x{mult:.3f} "
          f"({(mult - 1) * 100:.1f}% compounded)")
    print("  -> a cost baseline set in 2021 money understates today by that much.")
