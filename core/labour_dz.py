"""
core/labour_dz.py
-----------------
What an hour of Algerian labour actually costs.

The prototype this replaces priced a worker at "3000 DZD per shift" - a number
with no derivation behind it. Every savings figure computed on top of that
inherited its arbitrariness. This module rebuilds the cost stack from
Algerian statute and published rates, so the cost side of the business case
is defensible line by line.

The stack
=========

    SNMG (24,000 DZD/month, in force January 2026)
      / 173.33 legal hours per month        -> base hourly, 138.46 DZD
      x role coefficient                     -> role gross hourly
      x (1 + CNAS employer 26%)              -> LOADED hourly, the real cost
      x premium (overtime / night / holiday) -> cost of that specific hour

The number that matters is the **loaded** hourly cost. Algerian employers
routinely plan against gross wage and are then surprised by roughly a quarter
again on top. A staffing tool that quotes gross is quoting a number the
finance director will not recognise.

Reference: Loi 90-11 on labour relations sets the 40-hour week, caps overtime
and fixes minimum premiums. Where the statute gives a floor and practice sits
above it, we use the floor and say so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from . import sources


# ---------------------------------------------------------------------------
# Statutory constants
# ---------------------------------------------------------------------------

SNMG_MONTHLY = sources.value("snmg_monthly_dzd")          # 24,000 DZD
LEGAL_MONTHLY_HOURS = sources.value("legal_monthly_hours")  # 173.33
CNAS_EMPLOYER = sources.value("cnas_employer_rate")        # 0.26
CNAS_EMPLOYEE = sources.value("cnas_employee_rate")        # 0.09

BASE_HOURLY_DZD = SNMG_MONTHLY / LEGAL_MONTHLY_HOURS       # 138.46 DZD/h

# Statutory minimum premiums (Loi 90-11). These are floors; a given collective
# agreement may sit above them.
OVERTIME_PREMIUM = sources.value("overtime_premium")       # +50%
NIGHT_PREMIUM = 0.30       # work between 21:00 and 05:00
RESTDAY_PREMIUM = 0.50     # the weekly rest day (Friday in Algeria)
HOLIDAY_PREMIUM = 1.00     # gazetted public holiday: double time

# Overtime is capped at 20% of legal working time. Exceeding it is not a
# costlier option - it is unlawful, so the optimiser treats it as infeasible.
MAX_OVERTIME_FRACTION = 0.20

TEMP_AGENCY_MARKUP = sources.value("temp_agency_markup")   # +35%


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Role:
    """
    A staffing role.

    `snmg_coefficient` is the role's gross wage as a multiple of the national
    minimum. These reflect typical Algerian logistics and ground-handling pay
    bands; a pilot customer overrides them with their own grid on day one.
    """
    key: str
    label: str
    snmg_coefficient: float
    productivity_per_hour: float   # units of demand handled per hour
    can_be_temp: bool = True
    note: str = ""

    @property
    def gross_hourly(self) -> float:
        return BASE_HOURLY_DZD * self.snmg_coefficient

    @property
    def loaded_hourly(self) -> float:
        """Gross plus employer social contributions - the true cost to the firm."""
        return self.gross_hourly * (1.0 + CNAS_EMPLOYER)

    @property
    def gross_monthly(self) -> float:
        return self.gross_hourly * LEGAL_MONTHLY_HOURS

    @property
    def loaded_monthly(self) -> float:
        return self.loaded_hourly * LEGAL_MONTHLY_HOURS

    def hour_cost(
        self,
        overtime: bool = False,
        night: bool = False,
        rest_day: bool = False,
        holiday: bool = False,
        temp: bool = False,
    ) -> float:
        """Cost of one hour worked by this role under the given conditions."""
        premium = 0.0
        if overtime:
            premium += OVERTIME_PREMIUM
        if night:
            premium += NIGHT_PREMIUM
        # A public holiday supersedes the ordinary rest-day premium rather
        # than stacking with it.
        if holiday:
            premium += HOLIDAY_PREMIUM
        elif rest_day:
            premium += RESTDAY_PREMIUM

        cost = self.loaded_hourly * (1.0 + premium)
        if temp:
            cost *= 1.0 + TEMP_AGENCY_MARKUP
        return cost


ROLES = {
    "sorter": Role(
        key="sorter",
        label="Agent de tri (hub)",
        snmg_coefficient=1.15,
        productivity_per_hour=sources.value("productivity_parcels_per_hour"),
        note="Manual sort with handheld scanning. The volume role - most of "
             "the roster, and where mis-forecasting costs the most.",
    ),
    "courier": Role(
        key="courier",
        label="Livreur dernier kilomètre",
        snmg_coefficient=1.35,
        productivity_per_hour=6.5,
        note="Urban drops per hour including collection of cash on delivery. "
             "Materially weather-sensitive.",
    ),
    "supervisor": Role(
        key="supervisor",
        label="Superviseur de shift",
        snmg_coefficient=2.10,
        productivity_per_hour=0.0,
        can_be_temp=False,
        note="Span of control, not throughput. Sized as a ratio to the "
             "rostered team, and cannot be filled by an agency temp.",
    ),
    "ramp_agent": Role(
        key="ramp_agent",
        label="Agent de piste / bagages",
        snmg_coefficient=1.45,
        productivity_per_hour=1.6,
        note="Aircraft turnarounds per hour per agent. Airport ground "
             "handling vertical.",
    ),
    "checkin_agent": Role(
        key="checkin_agent",
        label="Agent d'enregistrement / embarquement",
        snmg_coefficient=1.50,
        productivity_per_hour=28.0,
        note="Passengers processed per hour. Airport ground handling vertical.",
    ),
    "warehouse_op": Role(
        key="warehouse_op",
        label="Agent d'entrepôt",
        snmg_coefficient=1.20,
        productivity_per_hour=32.0,
        note="Picking and put-away for retail distribution.",
    ),
    # --- Hospitality vertical ---
    "housekeeper": Role(
        key="housekeeper",
        label="Femme/valet de chambre",
        snmg_coefficient=1.10,
        productivity_per_hour=2.6,
        note="Rooms turned per hour. The volume role in a hotel, and the one "
             "most exposed to occupancy swings.",
    ),
    "front_desk": Role(
        key="front_desk",
        label="Réceptionniste",
        snmg_coefficient=1.45,
        productivity_per_hour=11.0,
        note="Guests checked in/out per hour. Peaks hard around arrival waves.",
    ),
    "fnb_staff": Role(
        key="fnb_staff",
        label="Personnel restauration (F&B)",
        snmg_coefficient=1.20,
        productivity_per_hour=14.0,
        note="Covers served per hour. In Ramadan the whole load moves to the "
             "post-f'tour evening.",
    ),
    # --- Transport & fleet vertical ---
    "driver": Role(
        key="driver",
        label="Chauffeur",
        snmg_coefficient=1.55,
        productivity_per_hour=7.5,
        note="Passenger-trips (or shipments) handled per driver-hour. Cannot "
             "exceed statutory driving-time limits.",
    ),
    "loader": Role(
        key="loader",
        label="Manutentionnaire / bagagiste",
        snmg_coefficient=1.15,
        productivity_per_hour=26.0,
        note="Bags or parcels loaded per hour at the depot / station.",
    ),
    "dispatcher": Role(
        key="dispatcher",
        label="Répartiteur",
        snmg_coefficient=1.70,
        productivity_per_hour=0.0,
        can_be_temp=False,
        note="Coordinates the fleet; sized as a ratio to drivers, not by "
             "throughput. Not an agency-temp role.",
    ),
}

SUPERVISOR_SPAN = 12  # one supervisor per N front-line workers


# ---------------------------------------------------------------------------
# Shifts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Shift:
    key: str
    label: str
    start_hour: int
    hours: float

    @property
    def is_night(self) -> bool:
        """True if any part of the shift falls in the 21:00-05:00 night band."""
        for h in range(int(self.hours)):
            hour_of_day = (self.start_hour + h) % 24
            if hour_of_day >= 21 or hour_of_day < 5:
                return True
        return False


SHIFTS = {
    "morning":   Shift("morning",   "Matin (06:00-14:00)",       6,  8.0),
    "afternoon": Shift("afternoon", "Après-midi (14:00-22:00)", 14, 8.0),
    "night":     Shift("night",     "Nuit (22:00-06:00)",       22, 8.0),
}


# ---------------------------------------------------------------------------
# Cost engine
# ---------------------------------------------------------------------------

def shift_cost(
    role_key: str,
    shift_key: str,
    workers: float,
    *,
    is_holiday: bool = False,
    is_rest_day: bool = False,
    overtime_workers: float = 0.0,
    temp_workers: float = 0.0,
) -> dict:
    """
    Cost of staffing one (role, shift) cell.

    `workers` is the total headcount on the shift. `overtime_workers` and
    `temp_workers` are subsets of it, priced at their respective premiums.
    Returns a breakdown rather than a single number, because the breakdown is
    what makes the saving credible to a CFO.
    """
    role = ROLES[role_key]
    shift = SHIFTS[shift_key]
    night = shift.is_night

    regular = max(0.0, workers - overtime_workers - temp_workers)

    regular_cost = regular * shift.hours * role.hour_cost(
        night=night, rest_day=is_rest_day, holiday=is_holiday
    )
    ot_cost = overtime_workers * shift.hours * role.hour_cost(
        overtime=True, night=night, rest_day=is_rest_day, holiday=is_holiday
    )
    temp_cost = temp_workers * shift.hours * role.hour_cost(
        night=night, rest_day=is_rest_day, holiday=is_holiday, temp=True
    )

    return {
        "regular_workers": regular,
        "overtime_workers": overtime_workers,
        "temp_workers": temp_workers,
        "regular_cost": regular_cost,
        "overtime_cost": ot_cost,
        "temp_cost": temp_cost,
        "total_cost": regular_cost + ot_cost + temp_cost,
        "hours": shift.hours,
        "is_night": night,
    }


def capacity(role_key: str, workers: float, shift_key: str,
             productivity_multiplier: float = 1.0) -> float:
    """
    How many units of demand a rostered team can actually clear.

    `productivity_multiplier` is where real weather lands: heat and rain
    reduce the fraction of a nominal shift that converts into completed work.
    """
    role = ROLES[role_key]
    shift = SHIFTS[shift_key]
    return workers * shift.hours * role.productivity_per_hour * productivity_multiplier


def workers_required(role_key: str, demand_units: float, shift_key: str,
                     productivity_multiplier: float = 1.0) -> float:
    """Inverse of `capacity` - headcount needed to clear a given demand."""
    role = ROLES[role_key]
    shift = SHIFTS[shift_key]
    per_worker = shift.hours * role.productivity_per_hour * productivity_multiplier
    if per_worker <= 0:
        return 0.0
    return demand_units / per_worker


def supervisors_for(front_line: float) -> float:
    import math
    return math.ceil(front_line / SUPERVISOR_SPAN) if front_line > 0 else 0.0


def cost_table() -> pd.DataFrame:
    """The full role cost stack - the table to put on screen when asked
    'where does your cost number come from?'"""
    rows = []
    for role in ROLES.values():
        rows.append({
            "Poste": role.label,
            "Coeff. SNMG": role.snmg_coefficient,
            "Brut mensuel (DZD)": round(role.gross_monthly),
            "Brut horaire (DZD)": round(role.gross_hourly, 2),
            "Charges patronales (DZD/h)": round(role.loaded_hourly - role.gross_hourly, 2),
            "Coût horaire chargé (DZD)": round(role.loaded_hourly, 2),
            "Heure sup. (DZD)": round(role.hour_cost(overtime=True), 2),
            "Heure intérim (DZD)": round(role.hour_cost(temp=True), 2)
            if role.can_be_temp else None,
            "Heure jour férié (DZD)": round(role.hour_cost(holiday=True), 2),
        })
    return pd.DataFrame(rows)


def derivation_notes() -> list:
    """Plain-language derivation of the cost stack, for the evidence tab."""
    return [
        f"Le SNMG est de {SNMG_MONTHLY:,.0f} DZD/mois, en vigueur depuis janvier "
        f"2026 (une hausse de 20% par rapport à 20 000 DZD).",
        f"La semaine légale de travail est de 40 heures, soit {LEGAL_MONTHLY_HOURS} "
        f"heures payées par mois.",
        f"Cela fixe le taux horaire plancher légal à {BASE_HOURLY_DZD:.2f} DZD.",
        f"Les cotisations patronales CNAS ajoutent {CNAS_EMPLOYER:.0%} au-dessus "
        f"du brut. C'est la ligne que la plupart des plannings oublient.",
        f"Les heures supplémentaires portent une majoration d'au moins "
        f"{OVERTIME_PREMIUM:.0%} et sont plafonnées à {MAX_OVERTIME_FRACTION:.0%} "
        f"du temps de travail légal , l'optimiseur traite donc les heures sup. "
        f"excédentaires comme infaisables, pas seulement comme coûteuses.",
        f"Le travail de nuit (21:00-05:00) ajoute {NIGHT_PREMIUM:.0%} ; le jour de "
        f"repos du vendredi ajoute {RESTDAY_PREMIUM:.0%} ; les jours fériés "
        f"officiels sont payés au double.",
        f"Les intérimaires d'agence coûtent {TEMP_AGENCY_MARKUP:.0%} de plus sur "
        f"le taux chargé , la prime que l'on paie pour ne pas avoir anticipé la "
        f"journée.",
    ]


if __name__ == "__main__":
    print("Algerian labour cost stack - self check\n")
    print(f"  SNMG                 : {SNMG_MONTHLY:,.0f} DZD/month")
    print(f"  Legal monthly hours  : {LEGAL_MONTHLY_HOURS}")
    print(f"  Statutory base hourly: {BASE_HOURLY_DZD:.2f} DZD  "
          f"(published figure: 138.46 DZD)")
    print()
    print(cost_table().to_string(index=False))
    print()
    sorter = ROLES["sorter"]
    print(f"One night shift, 10 sorters, public holiday:")
    res = shift_cost("sorter", "night", 10, is_holiday=True)
    print(f"  cost = {res['total_cost']:,.0f} DZD  (night={res['is_night']})")
    print(f"Same shift, ordinary weekday:")
    res2 = shift_cost("sorter", "morning", 10)
    print(f"  cost = {res2['total_cost']:,.0f} DZD")
    print(f"  -> the holiday night shift costs "
          f"{res['total_cost'] / res2['total_cost']:.2f}x the ordinary one.")
    print()
    for note in derivation_notes():
        print(f"  - {note}")
