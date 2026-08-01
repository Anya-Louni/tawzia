"""
core/delay_cascade.py
---------------------
Predict how a single late aircraft turns into a bad day across the whole
airport — before it happens.

The problem, in one picture
===========================
Aircraft don't fly one flight and rest. A tail flies a **chain**:

    ALG --> CDG --> ALG --> ORN --> ALG --> MRS ...

Each hop needs a **turnaround** on the ground (clean, refuel, board, ~40 min
for a 737). If a flight lands late and the delay is bigger than the slack in
its turnaround, the *next* flight that aircraft flies departs late too — and
the one after that. One weather delay in Paris at 07:00 can still be delaying
flights at ALG at 22:00. That is exactly the "chaotic day" ALG has publicly
had.

What this model does
====================
1. Reconstructs aircraft rotations from the schedule (which tail flies which
   legs, in order).
2. Seeds **root delays** — the delays that start on their own (weather at the
   outstation, ATC slots, a late crew), using realistic Algerian-network rates.
3. **Propagates** them along each rotation: departure delay = max(its own root
   delay, inherited delay from the previous leg minus the turnaround slack).
4. Scores every flight with a **cascade risk** and attributes each delay to
   whether it was a root cause or an inherited one.

Why it's genuinely useful (and genuinely AI)
============================================
The value isn't "this flight is late" — FIDS already shows that. The value is
**forward attribution**: at 06:00 the model can say "AH1003's inbound is the
keystone — if it slips 30 minutes, six downstream flights and ~900 passengers
are affected, and here's the one swap that breaks the chain." That is a
sequential/graph propagation model doing something a human dispatcher does
slowly and a FIDS board cannot do at all.

Honest note
==========
Root-delay *rates* here are modelled (no airline publishes its delay log). The
propagation logic is the real thing — it is the same computation you would run
on live AODB data, and it is deterministic given the inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


# Root-delay model: the probability a flight generates its OWN delay, and how
# big, before any inheritance. Long-haul and peak-bank departures are more
# exposed. These are modelling assumptions, tunable per airport.
ROOT_DELAY_PROB = {
    "france": 0.30, "europe": 0.28, "maghreb": 0.22, "africa": 0.30,
    "mideast": 0.26, "asia": 0.32, "domestic": 0.18,
}
# Congestion multiplier by hour of day — the evening bank at ALG is where
# delays breed.
def _congestion(hour: int) -> float:
    peak = np.exp(-((hour - 19) ** 2) / 12) + 0.6 * np.exp(-((hour - 8) ** 2) / 10)
    return 0.7 + 0.9 * peak


@dataclass
class CascadeResult:
    flights: pd.DataFrame      # every flight with predicted delay + attribution
    rotations: pd.DataFrame    # per-tail chain summary
    keystones: pd.DataFrame    # the flights whose delay causes the most downstream harm
    summary: dict


def _reconstruct_rotations(schedule: pd.DataFrame) -> pd.DataFrame:
    """Order each tail's legs by scheduled time to recover the rotation chain."""
    df = schedule.sort_values(["tail", "sched_time"]).copy()
    df["leg_index"] = df.groupby("tail").cumcount()
    df["rotation_len"] = df.groupby("tail")["tail"].transform("size")
    return df


def _seed_root_delays(df: pd.DataFrame, seed: int, severity: float) -> np.ndarray:
    """
    Draw each flight's independent (root) delay in minutes.

    `severity` scales the whole day 0..2 — a lever the UI exposes so an ops
    manager can ask "what does a rough-weather morning do to my afternoon?".
    """
    rng = np.random.default_rng(seed)
    n = len(df)
    root = np.zeros(n)
    for i, (_, r) in enumerate(df.iterrows()):
        hour = pd.Timestamp(r["sched_time"]).hour
        p = ROOT_DELAY_PROB.get(r["region"], 0.25) * _congestion(hour) * severity
        if rng.random() < min(p, 0.95):
            # Delay magnitude: mostly small, a fat tail of big ones.
            root[i] = rng.choice(
                [12, 20, 30, 45, 70, 110],
                p=[0.34, 0.26, 0.18, 0.12, 0.07, 0.03],
            )
    return root


def predict_cascade(
    schedule: pd.DataFrame,
    seed: int = 5,
    severity: float = 1.0,
) -> CascadeResult:
    """
    Propagate delays along aircraft rotations and score cascade risk.

    Returns per-flight predicted delays split into root vs inherited, a
    per-rotation view, and the ranked keystone flights.
    """
    df = _reconstruct_rotations(schedule).reset_index(drop=True)
    df["root_delay"] = _seed_root_delays(df, seed, severity)

    # Propagate within each tail's chain, in scheduled order.
    #
    # Physical semantics matter here. Each tail's timeline alternates
    # Departure, Arrival, Departure, Arrival ...:
    #   * Departure -> its own Arrival is the SAME flight: the departure delay
    #     carries straight to arrival, minus a little airborne recovery, plus
    #     any fresh delay picked up at the outstation.
    #   * Arrival -> the NEXT Departure is a TURNAROUND: the inbound delay only
    #     propagates if it exceeds the ground slack (scheduled ground time
    #     minus the minimum turnaround).
    # Treating those two transitions the same was the bug that kept every
    # cascade one flight long.
    predicted = np.zeros(len(df))
    inherited = np.zeros(len(df))

    for tail, grp in df.groupby("tail"):
        idx = grp.sort_values("sched_time").index.to_list()
        carried = 0.0             # delay leaving the previous event
        prev_arr_time = None      # scheduled time of the last arrival
        pending_dep_delay = 0.0   # the delay on the departure awaiting its arrival

        for i in idx:
            row = df.loc[i]
            if row["direction"] == "Departure":
                if prev_arr_time is not None:
                    min_turn = float(row["min_turnaround"])
                    sched_ground = (
                        pd.Timestamp(row["sched_time"]) - prev_arr_time
                    ).total_seconds() / 60.0
                    slack = max(sched_ground - min_turn, 0.0)
                    inh = max(carried - slack, 0.0)
                else:
                    inh = 0.0
                this = max(row["root_delay"], inh)
                inherited[i] = inh
                predicted[i] = this
                pending_dep_delay = this
                carried = this  # if the arrival somehow precedes, stay safe
            else:  # Arrival — same flight as the pending departure
                recovery = min(pending_dep_delay * 0.25, 15) if row["block_hours"] > 1.5 else 0
                # Its own root_delay here represents outstation/enroute trouble.
                this = max(pending_dep_delay - recovery, row["root_delay"])
                inherited[i] = max(pending_dep_delay - recovery, 0)
                predicted[i] = this
                carried = this
                prev_arr_time = pd.Timestamp(row["sched_time"])

    df["inherited_delay"] = np.round(inherited).astype(int)
    df["predicted_delay"] = np.round(predicted).astype(int)
    df["is_delayed"] = df["predicted_delay"] >= 15
    df["delay_source"] = np.where(
        df["inherited_delay"] >= df["root_delay"].values,
        np.where(df["inherited_delay"] > 0, "Cascade (inherited)", "On plan"),
        "Root cause",
    )
    df.loc[df["predicted_delay"] < 15, "delay_source"] = "On time"

    # --- Keystone attribution ---------------------------------------------
    # For each flight, how much downstream delay does it cause? Walk each
    # rotation and credit a flight's root delay with the delay minutes and
    # passengers it pushes onto later legs in the same chain.
    downstream_delay = np.zeros(len(df))
    downstream_flights = np.zeros(len(df), dtype=int)
    downstream_pax = np.zeros(len(df), dtype=int)

    for tail, grp in df.groupby("tail"):
        idx = grp.index.to_list()
        for a_pos, i in enumerate(idx):
            if df.loc[i, "root_delay"] <= 0:
                continue
            # Everything after this leg in the chain that ended up delayed and
            # inherited (not its own root) is attributable downstream harm.
            for i2 in idx[a_pos + 1:]:
                if df.loc[i2, "inherited_delay"] > 0:
                    downstream_delay[i] += df.loc[i2, "inherited_delay"]
                    downstream_flights[i] += 1
                    downstream_pax[i] += int(df.loc[i2, "passengers"])
                else:
                    break  # chain broke (recovered) — stop crediting

    df["downstream_delay_min"] = downstream_delay.astype(int)
    df["downstream_flights"] = downstream_flights
    df["downstream_pax"] = downstream_pax
    # Cascade risk score: a blend of own-delay likelihood and downstream blast
    # radius, normalised 0-100 for the UI.
    raw = df["downstream_pax"] * (df["root_delay"] > 0) + df["predicted_delay"] * 3
    df["cascade_risk"] = (100 * raw / raw.max()).round(1) if raw.max() > 0 else 0.0

    # --- Rotation view -----------------------------------------------------
    rot = (
        df.groupby("tail")
        .agg(
            legs=("flight_no", "size"),
            aircraft=("aircraft_name", "first"),
            total_delay=("predicted_delay", "sum"),
            max_delay=("predicted_delay", "max"),
            pax=("passengers", "sum"),
        )
        .reset_index()
        .sort_values("total_delay", ascending=False)
    )

    keystones = (
        df[df["downstream_flights"] > 0]
        .sort_values("downstream_pax", ascending=False)
        [["flight_no", "route_city", "direction", "sched_time", "aircraft_name",
          "root_delay", "downstream_flights", "downstream_pax", "downstream_delay_min",
          "tail", "cascade_risk"]]
        .head(12)
        .reset_index(drop=True)
    )

    delayed = df[df["is_delayed"]]
    summary = {
        "total_flights": len(df),
        "delayed_flights": int(df["is_delayed"].sum()),
        "on_time_pct": float((1 - df["is_delayed"].mean()) * 100),
        "cascade_flights": int((df["delay_source"] == "Cascade (inherited)").sum()),
        "root_flights": int((df["delay_source"] == "Root cause").sum()),
        "avg_delay": float(delayed["predicted_delay"].mean()) if len(delayed) else 0.0,
        "pax_affected": int(delayed["passengers"].sum()),
        "cascade_share": float(
            (df["delay_source"] == "Cascade (inherited)").sum()
            / max(df["is_delayed"].sum(), 1) * 100
        ),
        "worst_keystone": keystones.iloc[0].to_dict() if len(keystones) else None,
    }

    return CascadeResult(flights=df, rotations=rot, keystones=keystones, summary=summary)


def what_if_protect(result: CascadeResult, flight_no: str) -> dict:
    """
    Quantify the value of protecting one keystone flight's turnaround.

    If dispatch holds a spare aircraft or a standby crew for the keystone so it
    departs on time, the whole downstream chain is spared. This returns the
    delay-minutes and passengers saved — the number that justifies the
    operational cost of the intervention.
    """
    df = result.flights
    row = df[df["flight_no"] == flight_no]
    if row.empty:
        return {"found": False}
    row = row.iloc[0]
    return {
        "found": True,
        "flight_no": flight_no,
        "route": row["route_city"],
        "downstream_flights_saved": int(row["downstream_flights"]),
        "downstream_pax_saved": int(row["downstream_pax"]),
        "delay_minutes_saved": int(row["downstream_delay_min"]),
    }


if __name__ == "__main__":
    import datetime as _dt
    from . import aviation

    print("Delay cascade model — self check\n")
    sched = aviation.build_day_schedule(_dt.date(2026, 7, 25))
    res = predict_cascade(sched, severity=1.2)
    s = res.summary

    print(f"Flights: {s['total_flights']}   on-time: {s['on_time_pct']:.0f}%")
    print(f"Delayed: {s['delayed_flights']}  "
          f"(root causes: {s['root_flights']}, cascades: {s['cascade_flights']})")
    print(f"Cascade share of all delays: {s['cascade_share']:.0f}%  "
          f"<- delays that were someone else's fault")
    print(f"Passengers on a delayed flight: {s['pax_affected']:,}")
    print(f"Avg delay when delayed: {s['avg_delay']:.0f} min")

    print("\nKeystone flights — protect these first:")
    if len(res.keystones):
        print(res.keystones[["flight_no", "route_city", "direction",
                             "downstream_flights", "downstream_pax",
                             "downstream_delay_min"]].head(6).to_string(index=False))
        top = res.keystones.iloc[0]
        wi = what_if_protect(res, top["flight_no"])
        print(f"\nWhat-if: protecting {wi['flight_no']} ({wi['route']}) saves "
              f"{wi['downstream_flights_saved']} flights, "
              f"{wi['downstream_pax_saved']:,} passengers, "
              f"{wi['delay_minutes_saved']} delay-minutes.")
    else:
        print("  (no cascades today — try a higher severity)")
