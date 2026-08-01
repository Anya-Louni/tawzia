"""
core/pipeline.py
----------------
The end-to-end honest run: forecast -> roster -> money, scored against what
actually happened.

This is the module that answers the only question an investor or a jury really
has - *does this save a real operator real money, and how do you know?*

The protocol
============
For each forecast origin in the backtest:

  1. Stand at that date. Train the forecaster on history up to it, nothing more.
  2. Forecast the next H days.
  3. Build the optimised roster from **that forecast** - not from hindsight.
  4. Build the fixed roster the way the incumbent would have, from the same
     forecast-time information.
  5. Reveal the realised demand and score both rosters against it, with
     identical cost and penalty structures.

Then roll the origin forward and repeat. The saving reported is the aggregate
across every origin - a genuine out-of-sample result, not a single lucky window.

Why the number is smaller than the earlier prototype's
======================================================
The old code reported a large saving because it compared against a baseline it
had rigged (a rush surcharge only the baseline paid). Removing that, and making
the optimiser work from real forecasts rather than perfect foresight, brings
the figure down to something an operator would recognise. A defensible
single-digit-to-low-double-digit percentage is worth far more in a pitch than
an indefensible large one, because the first survives diligence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from . import demand as demand_mod
from . import forecast as forecast_mod
from . import labour_dz, staffing, sources


@dataclass
class EvidenceRun:
    comparison: pd.DataFrame
    delta: dict
    per_origin: pd.DataFrame
    backtest: forecast_mod.BacktestResult
    history: pd.DataFrame
    notes: list = field(default_factory=list)


def _service_level_forecast(
    point: np.ndarray,
    horizons: np.ndarray,
    residual_q: pd.DataFrame,
    service_level: float,
) -> np.ndarray:
    """
    Lift a point forecast to the chosen service-level quantile using realised
    backtest error at each horizon.

    Staffing to the mean guarantees you are short about half the time. The
    quantile is chosen deliberately and priced, rather than inherited by
    accident from the estimator.
    """
    if residual_q is None or residual_q.empty:
        return point

    q = residual_q.set_index("horizon")
    available = sorted(c for c in ("q10", "q25", "q50", "q75", "q90") if c in q.columns)
    levels = {"q10": 0.10, "q25": 0.25, "q50": 0.50, "q75": 0.75, "q90": 0.90}
    col = min(available, key=lambda c: abs(levels[c] - service_level))

    max_h = int(q.index.max())
    factors = pd.Series(horizons).clip(upper=max_h).map(q[col]).astype(float).to_numpy()
    return point * np.nan_to_num(factors, nan=1.0)


def run_evidence(
    profile_key: str = "ecom_hub",
    wilaya: str = "Alger",
    start: str = "2023-01-01",
    end: Optional[str] = None,
    horizon: int = 14,
    step: int = 28,
    min_train_days: int = 400,
    constraints: Optional[staffing.SiteConstraints] = None,
    seed: int = 7,
    allow_network: bool = True,
    history: Optional[pd.DataFrame] = None,
    backtest: Optional[forecast_mod.BacktestResult] = None,
) -> EvidenceRun:
    """
    Run the full out-of-sample forecast -> roster -> cost comparison.

    `history` and `backtest` can be supplied to reuse work already done
    elsewhere (the dashboard does this so a single run serves every tab).
    """
    profile = demand_mod.PROFILES[profile_key]
    constraints = constraints or staffing.SiteConstraints(role=profile.primary_role)

    if history is None:
        history = demand_mod.build_history(
            profile_key, wilaya, start, end, seed=seed, allow_network=allow_network
        )
    if backtest is None:
        backtest = forecast_mod.walk_forward(
            history, horizon=horizon, step=step, min_train_days=min_train_days
        )

    preds = backtest.predictions
    role = constraints.role

    per_origin_rows = []
    opt_frames, fix_frames = [], []

    for origin, grp in preds.groupby("origin"):
        window = grp.sort_values(["date", "shift"]).copy()

        # Lift the point forecast to the service level using realised error.
        window["forecast"] = _service_level_forecast(
            window["WorkForce.dz"].to_numpy(),
            window["horizon"].to_numpy(),
            backtest.residual_quantiles,
            constraints.service_level,
        )

        # Reattach the weather and holiday context the roster needs.
        ctx_cols = [
            c for c in ("weather_productivity", "is_holiday_int", "is_ramadan_int")
            if c in history.columns
        ]
        ctx = history[["date", "shift"] + ctx_cols].drop_duplicates(["date", "shift"])
        window = window.merge(ctx, on=["date", "shift"], how="left")

        req = staffing.required_workers(window, role=role, volume_col="forecast")

        # What the incumbent would have rostered: recent average demand,
        # measured only from data available at this origin.
        past = history[history["date"] <= origin]
        recent = past[past["date"] > origin - pd.Timedelta(days=90)]
        if recent.empty:
            recent = past
        shift_hours = labour_dz.SHIFTS["morning"].hours
        prod = labour_dz.ROLES[role].productivity_per_hour
        mean_by_shift = (
            recent.groupby("shift")["volume"].mean() / (shift_hours * prod)
        ).to_dict()

        try:
            opt = staffing.optimise_roster(req, constraints)
        except RuntimeError:
            # Infeasible at this origin - the site genuinely cannot cover the
            # forecast legally. Skip rather than silently relax a legal limit.
            continue

        fix = staffing.fixed_roster(req, mean_by_shift, constraints)

        actual = window[["date", "shift", "volume"]]
        opt_eval = staffing.evaluate_against_actual(opt, actual, constraints)
        fix_eval = staffing.evaluate_against_actual(fix, actual, constraints)

        opt_frames.append(opt_eval)
        fix_frames.append(fix_eval)

        o = staffing.summarise(opt_eval, "opt")
        f = staffing.summarise(fix_eval, "fix")
        per_origin_rows.append({
            "origin": origin,
            "demand": float(actual["volume"].sum()),
            "fixed_total": f["Total cost (DZD)"],
            "opt_total": o["Total cost (DZD)"],
            "saving": f["Total cost (DZD)"] - o["Total cost (DZD)"],
            "saving_pct": (f["Total cost (DZD)"] - o["Total cost (DZD)"])
            / f["Total cost (DZD)"] * 100 if f["Total cost (DZD)"] else 0.0,
            "fixed_service": f["Service level"],
            "opt_service": o["Service level"],
        })

    if not opt_frames:
        raise RuntimeError(
            "No feasible origins. The site constraints cannot cover forecast "
            "demand anywhere in the backtest - raise the permanent pool or the "
            "temp ceiling."
        )

    all_opt = pd.concat(opt_frames, ignore_index=True)
    all_fix = pd.concat(fix_frames, ignore_index=True)

    comparison = pd.DataFrame([
        staffing.summarise(all_fix, "Fixed roster (current practice)"),
        staffing.summarise(all_opt, "WorkForce.dz optimised"),
    ])

    fixed_total = comparison.loc[0, "Total cost (DZD)"]
    opt_total = comparison.loc[1, "Total cost (DZD)"]
    per_origin = pd.DataFrame(per_origin_rows)

    delta = {
        "saving_dzd": fixed_total - opt_total,
        "saving_pct": (fixed_total - opt_total) / fixed_total * 100 if fixed_total else 0.0,
        "service_gain_pp": (comparison.loc[1, "Service level"]
                            - comparison.loc[0, "Service level"]) * 100,
        "origins": len(per_origin),
        "days_scored": int(all_opt["date"].nunique()),
        "win_rate": float((per_origin["saving"] > 0).mean() * 100) if len(per_origin) else 0.0,
        "worst_origin_pct": float(per_origin["saving_pct"].min()) if len(per_origin) else 0.0,
        "best_origin_pct": float(per_origin["saving_pct"].max()) if len(per_origin) else 0.0,
    }

    notes = [
        f"Scored over {delta['origins']} independent forecast origins covering "
        f"{delta['days_scored']} operating days.",
        "Both rosters were built from information available at the forecast "
        "origin. Neither saw the demand it would face.",
        "Both pay identical wage rates, identical statutory premiums, and an "
        "identical penalty for demand they failed to cover. The only "
        "difference between them is forecast quality.",
        f"The optimised plan beat the fixed roster on "
        f"{delta['win_rate']:.0f}% of origins "
        f"(worst {delta['worst_origin_pct']:+.1f}%, best "
        f"{delta['best_origin_pct']:+.1f}%).",
        f"Understaffing is priced at "
        f"{sources.value('understaffing_penalty_multiple')}x the marginal cost "
        f"of covering the work - an assumption, and the one most worth "
        f"challenging. It is a slider in the app.",
        "Demand volumes are simulated on a real Algerian calendar and real "
        "observed weather. The saving validates the method; the magnitude "
        "needs a pilot to confirm.",
    ]

    return EvidenceRun(
        comparison=comparison,
        delta=delta,
        per_origin=per_origin,
        backtest=backtest,
        history=history,
        notes=notes,
    )


if __name__ == "__main__":
    print("End-to-end evidence run\n")
    for key in ("ecom_hub", "retail_dc"):
        p = demand_mod.PROFILES[key]
        cons = staffing.SiteConstraints(
            role=p.primary_role, regular_pool=80, temp_available_per_shift=60
        )
        run = run_evidence(key, "Alger", horizon=14, step=28, constraints=cons)
        print(f"=== {p.label} ===")
        print(run.comparison.to_string(index=False, float_format=lambda v: f"{v:,.1f}"))
        d = run.delta
        print(f"\n  saving      : {d['saving_dzd']:,.0f} DZD ({d['saving_pct']:.1f}%)")
        print(f"  service     : {d['service_gain_pp']:+.1f} pp")
        print(f"  win rate    : {d['win_rate']:.0f}% of {d['origins']} origins")
        print(f"  range       : {d['worst_origin_pct']:+.1f}% .. {d['best_origin_pct']:+.1f}%")
        print()
