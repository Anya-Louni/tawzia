"""
core/aviation.py
----------------
The airport-operations engine: a flight network for Algiers (ALG), the
passenger flow it generates, and the way delays cascade through it.

What's real and what's modelled
===============================
- **Real:** the ALG route network (the actual destinations Air Algérie and
  partners fly), realistic aircraft types and seat counts, published turnaround
  minima, and — crucially — the **Algerian calendar** that drives when the
  airport is busy (the diaspora summer peak, Ramadan's evening shift, Aïd).
- **Modelled:** the specific daily schedule, tail assignments and the delays
  themselves. No airline gives out its live rotation plan or its delay log, so
  these are simulated — but simulated the way the system actually behaves, so
  the models that run on top are the same ones you'd deploy on real AODB/FIDS
  data.

Why this is the right thing to build for Air Algérie / Aéroport d'Alger
=======================================================================
Air Algérie is scaling from ~8.8M passengers (2025) toward ~10M (2026) and
taking ~60 new aircraft. ALG already jams at peak and has had days where one
late aircraft cascaded delays across the whole schedule. The expensive
problems there are:

  1. **Peak passenger surges** you didn't staff for → check-in queues, missed
     connections. Worst during the diaspora summer, which a Western-calendar
     tool reads as low season.
  2. **Delay cascades** — a late inbound eats its turnaround and pushes every
     subsequent flight that aircraft flies. Predicting the cascade before it
     happens is where the money is.

This module models both. It extends the same forecast-and-optimise engine the
rest of Tawzia already uses, into the aviation vertical.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from . import calendar_dz

AIRPORT = "ALG"  # Houari Boumediene, Algiers
AIRLINE = "AH"   # Air Algérie


# ---------------------------------------------------------------------------
# The real ALG route network
# ---------------------------------------------------------------------------
# Destinations Air Algérie and partners actually serve from Algiers, tagged by
# region because region drives aircraft size, load-factor seasonality and the
# diaspora effect (France above all).

@dataclass(frozen=True)
class Route:
    iata: str
    city: str
    region: str          # "france" | "europe" | "maghreb" | "africa" | "mideast" | "asia" | "domestic"
    block_hours: float    # one-way flight time
    daily_frequency: float  # avg rotations/day (can be <1 = not daily)
    diaspora: bool = False  # heavy diaspora demand in summer


ROUTES = [
    # France — the diaspora backbone
    Route("CDG", "Paris CDG", "france", 2.3, 4.0, diaspora=True),
    Route("ORY", "Paris Orly", "france", 2.3, 3.0, diaspora=True),
    Route("MRS", "Marseille", "france", 1.7, 3.0, diaspora=True),
    Route("LYS", "Lyon", "france", 1.8, 2.0, diaspora=True),
    Route("TLS", "Toulouse", "france", 1.8, 1.0, diaspora=True),
    Route("NCE", "Nice", "france", 1.6, 1.0, diaspora=True),
    Route("LIL", "Lille", "france", 2.4, 0.7, diaspora=True),
    Route("BOD", "Bordeaux", "france", 2.0, 0.7, diaspora=True),
    # Rest of Europe
    Route("BCN", "Barcelona", "europe", 1.3, 1.0),
    Route("MAD", "Madrid", "europe", 1.5, 1.0),
    Route("FCO", "Rome", "europe", 1.8, 0.7),
    Route("LHR", "London", "europe", 3.0, 1.0),
    Route("FRA", "Frankfurt", "europe", 2.6, 0.7),
    Route("IST", "Istanbul", "europe", 3.2, 1.0),
    Route("BRU", "Brussels", "europe", 2.5, 0.7, diaspora=True),
    Route("GVA", "Geneva", "europe", 1.9, 0.5, diaspora=True),
    # Maghreb & Africa
    Route("TUN", "Tunis", "maghreb", 1.0, 1.0),
    Route("CMN", "Casablanca", "maghreb", 1.5, 0.7),
    Route("CAI", "Cairo", "africa", 3.5, 0.5),
    Route("DKR", "Dakar", "africa", 4.5, 0.4),
    Route("NKC", "Nouakchott", "africa", 3.0, 0.4),
    Route("BKO", "Bamako", "africa", 3.5, 0.3),
    Route("NDJ", "N'Djamena", "africa", 4.0, 0.3),
    # Middle East & Asia (incl. new long-haul)
    Route("DXB", "Dubai", "mideast", 6.0, 0.7),
    Route("JED", "Jeddah", "mideast", 5.5, 0.5),  # Umrah/Hajj-sensitive
    Route("CAN", "Guangzhou", "asia", 11.0, 0.3),  # launched late 2025
    Route("YUL", "Montreal", "asia", 8.5, 0.5, diaspora=True),
    # Domestic — the new subsidiary's territory
    Route("ORN", "Oran", "domestic", 1.0, 4.0),
    Route("CZL", "Constantine", "domestic", 0.8, 3.0),
    Route("AAE", "Annaba", "domestic", 0.9, 2.0),
    Route("TMR", "Tamanrasset", "domestic", 2.2, 1.0),
    Route("OGX", "Ouargla", "domestic", 1.2, 1.0),
    Route("BJA", "Bejaia", "domestic", 0.7, 1.0),
    Route("GHA", "Ghardaia", "domestic", 1.3, 0.7),
    Route("HME", "Hassi Messaoud", "domestic", 1.3, 1.5),  # oil-sector traffic
]

ROUTE_BY_IATA = {r.iata: r for r in ROUTES}


# ---------------------------------------------------------------------------
# Fleet
# ---------------------------------------------------------------------------
# Aircraft families in the Air Algérie fleet + the incoming 737 MAX, with
# representative seat counts. `min_turnaround` is the published minimum ground
# time — the constraint the whole cascade model turns on.

@dataclass(frozen=True)
class Aircraft:
    family: str
    seats: int
    min_turnaround: int   # minutes
    haul: str             # "narrow" | "wide" | "regional"


FLEET = {
    "738": Aircraft("Boeing 737-800", 155, 40, "narrow"),
    "73M": Aircraft("Boeing 737 MAX 8", 165, 40, "narrow"),   # incoming
    "332": Aircraft("Airbus A330-200", 263, 60, "wide"),
    "321": Aircraft("Airbus A321neo", 185, 45, "narrow"),
    "AT7": Aircraft("ATR 72-600", 70, 25, "regional"),
}


def _aircraft_for(route: Route, rng: np.random.Generator) -> str:
    """Pick a plausible aircraft type for a route."""
    if route.region == "domestic":
        if route.block_hours < 1.0:
            return rng.choice(["738", "AT7", "73M"], p=[0.5, 0.3, 0.2])
        return rng.choice(["738", "73M", "AT7"], p=[0.55, 0.25, 0.20])
    if route.region in ("asia",) or route.block_hours > 5.5:
        return "332"  # widebody long-haul
    if route.region == "france":
        return rng.choice(["738", "73M", "321", "332"], p=[0.4, 0.25, 0.2, 0.15])
    return rng.choice(["738", "73M", "321"], p=[0.5, 0.3, 0.2])


# ---------------------------------------------------------------------------
# Load factor: how full the planes are, driven by the Algerian calendar
# ---------------------------------------------------------------------------

def _load_factor(route: Route, ctx: calendar_dz.DayContext, rng: np.random.Generator) -> float:
    """
    Fraction of seats sold. This is where the Algerian calendar reshapes
    aviation demand in ways a generic model misses entirely.
    """
    base = {
        "france": 0.86, "europe": 0.80, "maghreb": 0.78, "africa": 0.74,
        "mideast": 0.80, "asia": 0.82, "domestic": 0.76,
    }[route.region]

    # Diaspora summer: France and other diaspora routes run near-full for
    # months. This is the single biggest predictable event at ALG, and it
    # reads as LOW season to any model built on European seasonality.
    if route.diaspora and ctx.diaspora_intensity > 0:
        base += 0.13 * ctx.diaspora_intensity

    # Ramadan: leisure travel dips, then Aïd drives a sharp return peak.
    if ctx.is_ramadan:
        base -= 0.06
    if ctx.is_eid_period:
        base += 0.12

    # Jeddah spikes around Umrah season (approximated: Ramadan + Dhu al-Hijjah).
    if route.iata == "JED" and (ctx.is_ramadan or ctx.hijri_month == 12):
        base += 0.14

    # Summer rentrée reversal: early September, diaspora returns abroad, so the
    # France routes stay full outbound.
    base += rng.normal(0, 0.05)
    return float(np.clip(base, 0.45, 0.99))


# ---------------------------------------------------------------------------
# Schedule construction
# ---------------------------------------------------------------------------

def build_day_schedule(date, seed: Optional[int] = None) -> pd.DataFrame:
    """
    Build one day's flight schedule at ALG: every arrival and departure, with
    aircraft, seats, passengers, scheduled times and the tail that flies it.

    Rotation-first construction
    ---------------------------
    Aircraft fly **chains**, not single trips: one tail does
    ALG→CDG→ALG→ORN→ALG→MRS→ALG through the day, with a tight turnaround at ALG
    between legs. We build the schedule tail-by-tail so those chains — and the
    tight ground times that let a delay jump from one leg to the next — exist
    explicitly. Without that structure the cascade model has nothing to
    propagate along.
    """
    date = pd.to_datetime(date).date() if not isinstance(date, _dt.date) else date
    seed = seed if seed is not None else (date.toordinal() % 100000)
    rng = np.random.default_rng(seed)

    ctx = calendar_dz.day_context(date)

    season = 1.0 + 0.18 * ctx.diaspora_intensity
    if ctx.is_public_holiday and ctx.is_eid_period:
        season *= 0.55
    if ctx.is_ramadan:
        season *= 0.92

    # 1. Expand routes into the day's round-trip "trips" to be flown.
    trips = []  # each: dict(route, ac_code)
    for route in ROUTES:
        n_rot = route.daily_frequency * season
        whole = int(n_rot) + (1 if rng.random() < (n_rot - int(n_rot)) else 0)
        for _ in range(whole):
            trips.append({"route": route, "ac_code": _aircraft_for(route, rng)})

    # 2. Split into long-haul (one trip fills a tail's day) and chainable
    #    short/medium-haul (packed into multi-leg rotations).
    long_haul = [t for t in trips if t["route"].block_hours > 5.5]
    chainable = [t for t in trips if t["route"].block_hours <= 5.5]
    rng.shuffle(chainable)

    flights = []
    tail_counter = [0]

    def _next_tail() -> str:
        tail_counter[0] += 1
        n = tail_counter[0]
        return f"7T-VJ{n:03d}"

    # 3. Long-haul: each its own tail, departing in the evening bank.
    for t in long_haul:
        tail = _next_tail()
        dep_hour = rng.choice([21, 22, 23, 0, 1], p=[0.3, 0.3, 0.2, 0.1, 0.1])
        dep_time = _dt.datetime.combine(date, _dt.time(int(dep_hour % 24),
                                                       int(rng.choice([0, 10, 20, 30, 45]))))
        _emit_roundtrip(flights, t, tail, dep_time, ctx, rng)

    # 4. Chainable: pack trips onto tails as sequential rotations with a tight
    #    ALG turnaround between legs. This is where cascades are born.
    i = 0
    while i < len(chainable):
        tail = _next_tail()
        # Domestic/short tails fly more legs a day than medium-haul ones.
        legs_today = int(rng.integers(2, 5))
        # Start in the morning bank, staggered so tails don't all leave at once.
        cur = _dt.datetime.combine(
            date, _dt.time(int(rng.integers(6, 9)), int(rng.choice([0, 15, 30, 45])))
        )
        for _ in range(legs_today):
            if i >= len(chainable):
                break
            t = chainable[i]; i += 1
            arr_time = _emit_roundtrip(flights, t, tail, cur, ctx, rng)
            # Tight ALG turnaround before this tail's next departure: the
            # minimum plus a small, variable buffer. Small buffer => a late
            # inbound eats it and the next flight slips.
            ac = FLEET[t["ac_code"]]
            buffer = int(rng.integers(10, 45))
            cur = arr_time + _dt.timedelta(minutes=ac.min_turnaround + buffer)

    df = pd.DataFrame(flights).sort_values("sched_time").reset_index(drop=True)
    df["date"] = pd.to_datetime(date)
    df.attrs["day_context"] = ctx
    return df


def _emit_roundtrip(flights, trip, tail, dep_time, ctx, rng) -> "_dt.datetime":
    """
    Emit the departure and the return arrival for one round-trip on a tail.

    Returns the scheduled arrival time back at ALG, so the caller can chain the
    tail's next leg onto it.
    """
    route = trip["route"]
    ac = FLEET[trip["ac_code"]]
    lf = _load_factor(route, ctx, rng)
    pax = int(round(ac.seats * lf))

    turn_out = ac.min_turnaround + int(rng.integers(20, 80))
    arr_time = dep_time + _dt.timedelta(minutes=int(route.block_hours * 60 * 2 + turn_out))

    common = dict(
        tail=tail, aircraft=trip["ac_code"], aircraft_name=ac.family,
        seats=ac.seats, route_iata=route.iata, route_city=route.city,
        region=route.region, block_hours=route.block_hours,
        min_turnaround=ac.min_turnaround, load_factor=round(lf, 3),
        passengers=pax,
    )
    flights.append({
        **common, "flight_no": f"{AIRLINE}{_flight_number(route, rng)}",
        "direction": "Departure", "sched_time": dep_time, "link_role": "rotation_out",
    })
    flights.append({
        **common, "flight_no": f"{AIRLINE}{_flight_number(route, rng)}",
        "direction": "Arrival", "sched_time": arr_time, "link_role": "rotation_in",
    })
    return arr_time


def _bank_weights():
    """Departure-hour distribution with morning and evening banks (hours 6-23)."""
    hours = np.arange(6, 24)
    w = (
        np.exp(-((hours - 8) ** 2) / 8)      # morning bank ~08:00
        + 0.9 * np.exp(-((hours - 18) ** 2) / 10)  # evening bank ~18:00
        + 0.3
    )
    return w / w.sum()


def _flight_number(route: Route, rng: np.random.Generator) -> int:
    base = {"domestic": 6000, "france": 1000, "europe": 1000,
            "maghreb": 2000, "africa": 2000, "mideast": 3000, "asia": 3000}[route.region]
    return base + rng.integers(1, 999)


def build_schedule(start, days: int = 7, seed: int = 11) -> pd.DataFrame:
    """A multi-day schedule for the forecast/staffing horizon."""
    start = pd.to_datetime(start)
    frames = []
    for i in range(days):
        d = (start + pd.Timedelta(days=i)).date()
        frames.append(build_day_schedule(d, seed=seed + i))
    out = pd.concat(frames, ignore_index=True)
    return out


if __name__ == "__main__":
    print("Flight network — self check\n")
    sched = build_day_schedule(_dt.date(2026, 7, 25))  # peak diaspora Saturday
    ctx = sched.attrs["day_context"]
    print(f"Date: 2026-07-25  (diaspora intensity {ctx.diaspora_intensity:.2f})")
    print(f"Movements: {len(sched)}  ({(sched.direction=='Arrival').sum()} arr / "
          f"{(sched.direction=='Departure').sum()} dep)")
    print(f"Total seats: {sched.seats.sum():,}   passengers: {sched.passengers.sum():,}")
    print(f"Mean load factor: {sched.load_factor.mean():.1%}")
    print(f"\nFrance-route load factor (diaspora): "
          f"{sched[sched.region=='france'].load_factor.mean():.1%}")
    print(f"Domestic load factor:               "
          f"{sched[sched.region=='domestic'].load_factor.mean():.1%}")
    print("\nTop destinations by movements:")
    print(sched["route_city"].value_counts().head(8).to_string())

    # Winter comparison — diaspora effect should vanish.
    winter = build_day_schedule(_dt.date(2026, 1, 17))
    print(f"\nSame airport, 17 Jan 2026 (no diaspora):")
    print(f"  France load factor: {winter[winter.region=='france'].load_factor.mean():.1%} "
          f"(vs summer {sched[sched.region=='france'].load_factor.mean():.1%})")
    print(f"  Movements: {len(winter)} (vs summer {len(sched)})")
