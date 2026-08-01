"""
core/pax_flow.py
----------------
Turn a flight schedule into the passenger flow through the terminal, hour by
hour, and then into the terminal staffing needed to serve it without queues.

Why this is the airport-side of the WorkForce.dz engine
=======================================================
A flight is not a single lump of passengers at departure time. For a departure,
travellers arrive at the terminal over a **window before** the flight — earlier
and more spread out for long-haul, tighter for domestic — hit **check-in**,
then **security**, then **boarding**. For an arrival, they hit **immigration**
and **baggage** in a sharp burst *after* landing.

Stack every flight's curve on top of each other and you get the real thing an
airport rosters against: the number of passengers physically at each process,
each hour. That peak — not the daily total — is what decides how many check-in
and security desks you open, and it is exactly what jams at ALG during the
diaspora summer.

This module builds that curve from the schedule and converts it into a staffing
requirement using the same loaded Algerian labour cost model as the rest of the
product.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from . import labour_dz


# ---------------------------------------------------------------------------
# Show-up profiles: how passengers arrive relative to their flight
# ---------------------------------------------------------------------------
# Minutes-before-departure buckets and the share of departing passengers that
# show up in each. Long-haul travellers arrive earlier and more spread out.

SHOWUP_PROFILE = {
    # region : list of (minutes_before_departure, share)
    "long":   [(240, 0.05), (210, 0.10), (180, 0.18), (150, 0.22),
               (120, 0.20), (90, 0.15), (60, 0.08), (30, 0.02)],
    "medium": [(180, 0.06), (150, 0.14), (120, 0.24), (90, 0.26),
               (60, 0.20), (30, 0.08), (15, 0.02)],
    "short":  [(120, 0.10), (90, 0.24), (60, 0.34), (45, 0.20),
               (30, 0.10), (15, 0.02)],
}


def _profile_for(region: str, block_hours: float) -> str:
    if region == "domestic" or block_hours < 1.3:
        return "short"
    if block_hours > 4.5 or region in ("asia", "mideast", "africa"):
        return "long"
    return "medium"


# Terminal processes and how much of the passenger population each sees.
# Departing pax pass check-in -> security -> boarding. Arriving pax pass
# immigration -> baggage. Numbers are passengers processed per agent per hour.
PROCESS_RATE = {
    "checkin": 28,      # pax/agent/hour at a check-in desk
    "security": 90,     # pax/lane/hour (an agent runs a lane)
    "boarding": 120,    # pax/agent/hour at the gate
    "immigration": 45,  # arriving pax/booth/hour
    "baggage": 150,     # arriving pax/handler/hour (belt-side)
}

PROCESS_ROLE = {
    "checkin": "checkin_agent",
    "security": "checkin_agent",   # priced at the same band
    "boarding": "checkin_agent",
    "immigration": "checkin_agent",
    "baggage": "ramp_agent",
}


@dataclass
class FlowResult:
    hourly: pd.DataFrame       # passengers at each process, per hour
    staffing: pd.DataFrame     # agents needed at each process, per hour
    peaks: dict
    summary: dict


def _spread_departure(row, hours_index):
    """Distribute a departing flight's passengers across the show-up window."""
    prof = SHOWUP_PROFILE[_profile_for(row["region"], row["block_hours"])]
    dep = pd.Timestamp(row["sched_time"])
    out = {}
    for mins_before, share in prof:
        t = (dep - pd.Timedelta(minutes=mins_before)).floor("h")
        out[t] = out.get(t, 0.0) + row["passengers"] * share
    return out


def _spread_arrival(row):
    """Arriving passengers hit immigration/baggage in a sharp post-landing burst."""
    arr = pd.Timestamp(row["sched_time"])
    # Deplane + walk: bulk in the first hour after arrival, tail into the next.
    h0 = arr.floor("h")
    h1 = h0 + pd.Timedelta(hours=1)
    return {h0: row["passengers"] * 0.7, h1: row["passengers"] * 0.3}


def compute_flow(schedule: pd.DataFrame) -> FlowResult:
    """
    Build the hourly terminal passenger flow and the staffing it implies.
    """
    sched = schedule.copy()
    sched["sched_time"] = pd.to_datetime(sched["sched_time"])

    start = sched["sched_time"].min().floor("h") - pd.Timedelta(hours=4)
    end = sched["sched_time"].max().ceil("h") + pd.Timedelta(hours=2)
    hours = pd.date_range(start, end, freq="h")

    checkin = pd.Series(0.0, index=hours)
    security = pd.Series(0.0, index=hours)
    boarding = pd.Series(0.0, index=hours)
    immigration = pd.Series(0.0, index=hours)
    baggage = pd.Series(0.0, index=hours)

    dep = sched[sched["direction"] == "Departure"]
    arr = sched[sched["direction"] == "Arrival"]

    for _, row in dep.iterrows():
        spread = _spread_departure(row, hours)
        for t, n in spread.items():
            if t in checkin.index:
                checkin[t] += n
            # security ~30 min after check-in, boarding ~30 min before flight
            ts = t + pd.Timedelta(minutes=30)
            ts = ts.floor("h")
            if ts in security.index:
                security[ts] += n
        board_hour = pd.Timestamp(row["sched_time"]).floor("h")
        if board_hour in boarding.index:
            boarding[board_hour] += row["passengers"]

    for _, row in arr.iterrows():
        for t, n in _spread_arrival(row).items():
            if t in immigration.index:
                immigration[t] += n
                baggage[t] += n

    hourly = pd.DataFrame({
        "hour": hours,
        "checkin": checkin.values,
        "security": security.values,
        "boarding": boarding.values,
        "immigration": immigration.values,
        "baggage": baggage.values,
    })
    hourly["terminal_total"] = (
        hourly[["checkin", "security", "boarding", "immigration", "baggage"]].sum(axis=1)
    )

    # Staffing: agents needed per process per hour = ceil(pax / rate), floored
    # at 1 whenever there's any demand so a desk is always open.
    staffing = pd.DataFrame({"hour": hours})
    for proc, rate in PROCESS_RATE.items():
        need = np.ceil(hourly[proc] / rate)
        need = np.where(hourly[proc] > 0, np.maximum(need, 1), 0)
        staffing[proc] = need.astype(int)
    staffing["total_agents"] = staffing[list(PROCESS_RATE)].sum(axis=1)

    # Peaks — the numbers that decide desk counts.
    peaks = {}
    for proc in PROCESS_RATE:
        j = hourly[proc].idxmax()
        peaks[proc] = {
            "hour": hourly.loc[j, "hour"],
            "pax": float(hourly.loc[j, proc]),
            "agents": int(staffing.loc[j, proc]),
        }

    # Cost of the day's terminal staffing, using the real labour model.
    total_cost = 0.0
    for proc, role_key in PROCESS_ROLE.items():
        role = labour_dz.ROLES[role_key]
        for _, r in staffing.iterrows():
            hour = pd.Timestamp(r["hour"]).hour
            night = hour >= 21 or hour < 5
            total_cost += r[proc] * role.hour_cost(night=night)

    busiest = hourly.loc[hourly["terminal_total"].idxmax()]
    summary = {
        "total_departing_pax": int(dep["passengers"].sum()),
        "total_arriving_pax": int(arr["passengers"].sum()),
        "peak_hour": pd.Timestamp(busiest["hour"]),
        "peak_terminal_pax": int(busiest["terminal_total"]),
        "peak_checkin_agents": peaks["checkin"]["agents"],
        "peak_security_lanes": peaks["security"]["agents"],
        "daily_staff_cost": total_cost,
        "peak_checkin_hour": peaks["checkin"]["hour"],
    }

    return FlowResult(hourly=hourly, staffing=staffing, peaks=peaks, summary=summary)


if __name__ == "__main__":
    import datetime as _dt
    from . import aviation

    print("Passenger flow & terminal staffing — self check\n")
    sched = aviation.build_day_schedule(_dt.date(2026, 7, 25))
    flow = compute_flow(sched)
    s = flow.summary

    print(f"Departing pax: {s['total_departing_pax']:,}   "
          f"arriving pax: {s['total_arriving_pax']:,}")
    print(f"Busiest terminal hour: {s['peak_hour']:%H:%M} "
          f"with {s['peak_terminal_pax']:,} passengers in the building")
    print(f"Peak check-in: {s['peak_checkin_agents']} agents at "
          f"{s['peak_checkin_hour']:%H:%M}")
    print(f"Peak security: {s['peak_security_lanes']} lanes")
    print(f"Day's terminal staff cost: {s['daily_staff_cost']:,.0f} DZD")

    print("\nCheck-in demand by hour (top 6):")
    top = flow.hourly.nlargest(6, "checkin")[["hour", "checkin", "boarding", "immigration"]]
    for _, r in top.iterrows():
        print(f"  {r['hour']:%a %H:%M}  check-in {r['checkin']:>5.0f}  "
              f"boarding {r['boarding']:>5.0f}  arrivals {r['immigration']:>5.0f}")
