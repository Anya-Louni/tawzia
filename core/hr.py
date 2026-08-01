"""
core/hr.py
----------
The employee record and the Algerian leave-law brain.

This is where WorkForce.dz stops being a scheduling tool and starts being an
HR system: it holds the people, not just the shifts. Everything here is bound
to Algerian labour law, and it is wired to the demand forecast so that the
single most contested HR decision - "can this person take leave then?" - is
answered legally AND with an eye on whether the operation can afford to lose
them that week.

What is real
============
The leave entitlements are the real statutory figures (see core/sources.py,
cited): 30 days annual leave accrued at 2.5/month, +10 days in the southern
provinces, 14 weeks maternity at full pay, and the sick-pay step-up at day 15.
Individual employee records in the demo are synthetic sample data, clearly
generated - a real deployment imports the customer's staff file.

The money angle
===============
`suggest_leave_windows` reads the demand forecast and steers leave into the
low-demand troughs. Approving leave in a forecast peak is exactly how an
operation ends up paying temp-agency rates to backfill; steering it into a
trough is quiet, recurring savings that HR and operations usually fight about
because neither could see the other's calendar. Here they share one.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from . import labour_dz, sources

# Southern (Saharan) wilayas that carry the extra 10 days of annual leave.
SOUTHERN_WILAYAS = {
    "Ouargla", "Ghardaia", "Biskra", "Bechar", "Tamanrasset", "Adrar",
    "Illizi", "Tindouf", "El Oued", "Djelfa", "Laghouat",
}

ANNUAL_LEAVE_DAYS = sources.value("annual_leave_days")          # 30
SOUTH_BONUS_DAYS = sources.value("south_leave_bonus_days")      # 10
ACCRUAL_PER_MONTH = 2.5
MATERNITY_WEEKS = sources.value("maternity_leave_weeks")        # 14
SICK_SPLIT_DAY = sources.value("sick_leave_split_day")         # 15

# A seniority premium ("prime d'anciennete") is standard in Algerian pay: a
# small percentage per year of service. Exposed as an assumption; a real grid
# comes from the customer's collective agreement.
SENIORITY_PCT_PER_YEAR = 0.02
SENIORITY_CAP = 0.30

LEAVE_NOTICE_DAYS = 14  # customary minimum notice before a leave start


@dataclass
class Employee:
    """One person on the payroll."""
    emp_id: str
    name: str
    role_key: str
    wilaya: str
    hire_date: _dt.date
    dependants: int = 0
    spouse: bool = False
    contract: str = "CDI"          # CDI (permanent) | CDD (fixed-term) | temp
    leave_taken_ytd: float = 0.0   # annual-leave days already used this year

    # --- entitlements -------------------------------------------------------
    @property
    def is_southern(self) -> bool:
        return self.wilaya in SOUTHERN_WILAYAS

    def annual_entitlement(self) -> float:
        return ANNUAL_LEAVE_DAYS + (SOUTH_BONUS_DAYS if self.is_southern else 0)

    def months_of_service(self, as_of: _dt.date) -> float:
        days = (as_of - self.hire_date).days
        return max(days / 30.44, 0.0)

    def seniority_years(self, as_of: _dt.date) -> int:
        return int(self.months_of_service(as_of) // 12)

    def seniority_premium(self, as_of: _dt.date) -> float:
        return min(self.seniority_years(as_of) * SENIORITY_PCT_PER_YEAR, SENIORITY_CAP)

    def accrued_leave(self, as_of: _dt.date) -> float:
        """
        Annual-leave days accrued so far this calendar year, capped at the
        yearly entitlement, minus what has already been taken.
        """
        year_start = _dt.date(as_of.year, 1, 1)
        start = max(self.hire_date, year_start)
        months = max((as_of - start).days / 30.44, 0.0)
        accrued = min(months * ACCRUAL_PER_MONTH, self.annual_entitlement())
        return round(max(accrued - self.leave_taken_ytd, 0.0), 1)

    def monthly_gross(self) -> float:
        role = labour_dz.ROLES[self.role_key]
        return role.gross_monthly * (1 + self.seniority_premium(_dt.date.today()))


# ---------------------------------------------------------------------------
# Leave decisioning
# ---------------------------------------------------------------------------

@dataclass
class LeaveVerdict:
    allowed: bool
    reasons: list
    warnings: list
    days_requested: int
    balance_after: float
    demand_load: Optional[str] = None   # "low" | "normal" | "peak" | None


def _working_days(start: _dt.date, end: _dt.date) -> int:
    """Count days that are NOT the Friday-Saturday weekend."""
    n = 0
    d = start
    while d <= end:
        if d.weekday() not in labour_dz_weekend():
            n += 1
        d += _dt.timedelta(days=1)
    return n


def labour_dz_weekend():
    # Friday=4, Saturday=5 (see core/calendar_dz.WEEKEND_WEEKDAYS)
    return (4, 5)


def can_take_leave(
    employee: Employee,
    start: _dt.date,
    end: _dt.date,
    as_of: Optional[_dt.date] = None,
    forecast: Optional[pd.DataFrame] = None,
    forecast_value_col: str = "forecast",
) -> LeaveVerdict:
    """
    Decide whether an employee may take leave for [start, end].

    Legal gate first (balance, notice, contract), then an operational advisory
    from the demand forecast. The law can block it; the forecast only warns.
    """
    as_of = as_of or _dt.date.today()
    reasons, warnings = [], []

    days = _working_days(start, end)
    balance = employee.accrued_leave(as_of)
    balance_after = round(balance - days, 1)

    allowed = True

    # 1. Enough accrued balance?
    if days > balance:
        allowed = False
        reasons.append(
            f"Not enough accrued leave: {days} working days requested, "
            f"{balance:.1f} available."
        )
    else:
        reasons.append(f"{days} working days within the {balance:.1f}-day balance.")

    # 2. Notice period.
    notice = (start - as_of).days
    if notice < LEAVE_NOTICE_DAYS:
        warnings.append(
            f"Short notice: {notice} days (customary minimum {LEAVE_NOTICE_DAYS})."
        )

    # 3. Start not on the weekly rest day (wasted leave).
    if start.weekday() in labour_dz_weekend():
        warnings.append("Starts on the Friday-Saturday weekend - wastes a leave day.")

    # 4. Operational load from the forecast.
    demand_load = None
    if forecast is not None and not forecast.empty and forecast_value_col in forecast.columns:
        fc = forecast.copy()
        fc["date"] = pd.to_datetime(fc["date"])
        window = fc[(fc["date"] >= pd.Timestamp(start)) & (fc["date"] <= pd.Timestamp(end))]
        if not window.empty:
            daily = fc.groupby("date")[forecast_value_col].sum()
            win_mean = window.groupby("date")[forecast_value_col].sum().mean()
            p70, p40 = daily.quantile(0.70), daily.quantile(0.40)
            if win_mean >= p70:
                demand_load = "peak"
                warnings.append(
                    "Falls in a forecast demand PEAK - approving means backfilling "
                    "at temp-agency rates. Suggest a quieter window."
                )
            elif win_mean <= p40:
                demand_load = "low"
                reasons.append("Falls in a forecast demand trough - cheapest time to be short a head.")
            else:
                demand_load = "normal"

    return LeaveVerdict(
        allowed=allowed, reasons=reasons, warnings=warnings,
        days_requested=days, balance_after=balance_after, demand_load=demand_load,
    )


def suggest_leave_windows(
    forecast: pd.DataFrame,
    days: int = 7,
    top: int = 3,
    value_col: str = "forecast",
) -> pd.DataFrame:
    """
    Find the cheapest `days`-long windows to grant leave, by lowest forecast
    demand. This is the money-saving core: leave lands in the troughs.
    """
    if forecast.empty or value_col not in forecast.columns:
        return pd.DataFrame(columns=["start", "end", "avg_demand", "vs_peak_pct"])

    fc = forecast.copy()
    fc["date"] = pd.to_datetime(fc["date"])
    daily = fc.groupby("date")[value_col].sum().sort_index()
    if len(daily) < days:
        return pd.DataFrame(columns=["start", "end", "avg_demand", "vs_peak_pct"])

    roll = daily.rolling(days).mean().dropna()
    peak = daily.rolling(days).mean().max()
    rows = []
    for end_date, avg in roll.sort_values().items():
        start_date = end_date - pd.Timedelta(days=days - 1)
        rows.append({
            "start": start_date.date(),
            "end": end_date.date(),
            "avg_demand": round(float(avg)),
            "vs_peak_pct": round(float(avg) / float(peak) * 100 - 100, 1),
        })
    out = pd.DataFrame(rows)
    # de-overlap: keep the best, skip windows overlapping an already-picked one
    picked, used = [], []
    for _, r in out.iterrows():
        if any(not (r["end"] < s or r["start"] > e) for s, e in used):
            continue
        picked.append(r)
        used.append((r["start"], r["end"]))
        if len(picked) >= top:
            break
    return pd.DataFrame(picked).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Sample workforce (clearly synthetic demo data)
# ---------------------------------------------------------------------------

_FIRST = ["Amine", "Yacine", "Sofiane", "Karim", "Bilal", "Riad", "Nadir",
          "Lamia", "Sara", "Imene", "Nawel", "Meriem", "Hana", "Sabrina",
          "Walid", "Adel", "Fares", "Toufik", "Djamel", "Rachid"]
_LAST = ["Benali", "Haddad", "Cherif", "Boumediene", "Zerrouki", "Belkacem",
         "Meziane", "Saidi", "Bouzid", "Ferhat", "Khelifi", "Mansouri"]


def sample_workforce(role_key: str, n: int, wilaya: str = "Alger", seed: int = 3) -> list:
    """Generate a synthetic staff list for the demo."""
    rng = np.random.default_rng(seed)
    today = _dt.date.today()
    people = []
    for i in range(n):
        hire = today - _dt.timedelta(days=int(rng.integers(60, 8 * 365)))
        ent = ANNUAL_LEAVE_DAYS + (SOUTH_BONUS_DAYS if wilaya in SOUTHERN_WILAYAS else 0)
        people.append(Employee(
            emp_id=f"E{1000 + i}",
            name=f"{_FIRST[i % len(_FIRST)]} {_LAST[i % len(_LAST)]}",
            role_key=role_key,
            wilaya=wilaya,
            hire_date=hire,
            dependants=int(rng.integers(0, 4)),
            spouse=bool(rng.random() < 0.55),
            contract=rng.choice(["CDI", "CDI", "CDI", "CDD"]),
            leave_taken_ytd=float(rng.integers(0, int(ent * 0.6))),
        ))
    return people


def workforce_frame(people: list, as_of: Optional[_dt.date] = None) -> pd.DataFrame:
    as_of = as_of or _dt.date.today()
    rows = []
    for e in people:
        rows.append({
            "ID": e.emp_id, "Name": e.name, "Role": labour_dz.ROLES[e.role_key].label,
            "Wilaya": e.wilaya, "Contract": e.contract,
            "Seniority (yrs)": e.seniority_years(as_of),
            "Entitlement (d)": e.annual_entitlement(),
            "Accrued balance (d)": e.accrued_leave(as_of),
            "Dependants": e.dependants,
            "Monthly gross (DZD)": round(e.monthly_gross()),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("HR / leave engine - self check\n")
    today = _dt.date.today()

    alg = Employee("E1", "Amine Benali", "sorter", "Alger", today - _dt.timedelta(days=900),
                   dependants=2, spouse=True)
    sud = Employee("E2", "Sara Bouzid", "sorter", "Ouargla", today - _dt.timedelta(days=900))
    print(f"  Alger worker entitlement : {alg.annual_entitlement()} days")
    print(f"  Ouargla (south) entitlement: {sud.annual_entitlement()} days (expect 40)")
    print(f"  Alger accrued so far this year: {alg.accrued_leave(today):.1f} days")
    print(f"  Seniority premium (2.4y): {alg.seniority_premium(today):.0%}")

    # A leave request in a demand peak vs a trough
    import pandas as pd
    dates = pd.date_range(today, periods=30, freq="D")
    demand = [500 + (300 if 10 <= i <= 16 else 0) for i in range(30)]  # peak mid-window
    fc = pd.DataFrame({"date": dates, "shift": "morning", "forecast": demand})

    start = (today + _dt.timedelta(days=12))
    v = can_take_leave(alg, start, start + _dt.timedelta(days=5), as_of=today, forecast=fc)
    print(f"\n  Leave in the peak week -> allowed={v.allowed}, load={v.demand_load}")
    for w in v.warnings:
        print(f"    warn: {w}")

    print("\n  AI-suggested cheapest 7-day leave windows:")
    print(suggest_leave_windows(fc, days=7, top=3).to_string(index=False))
