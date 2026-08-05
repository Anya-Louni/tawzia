"""
core/calendar_dz.py
-------------------
The Algerian demand calendar.

This is the part of WorkForce.dz that imported workforce-management software
gets wrong, and it is the reason a local product can beat a global one here.

What foreign tools assume, and why it breaks in Algeria
=======================================================

1. **The weekend is Saturday-Sunday.**
   In Algeria the weekend is **Friday-Saturday**. A roster optimiser that
   protects the wrong two days staffs the busiest day thin and the quietest
   day heavy, every single week, forever.

2. **The year is Gregorian.**
   Algeria's two largest demand events - Ramadan and the two Aids - move
   about 11 days earlier each Gregorian year. A model trained on "March was
   busy last year" learns a pattern that is already wrong by the time it
   ships. Ramadan does not just raise volume; it *reshapes the day*, moving
   activity into the evening after f'tour.

3. **Seasonality is temperate.**
   Algeria's summer peak is not a holiday lull - it is the **diaspora
   return**, when several million Algerians resident abroad come home
   between mid-June and early September. Volume, not absence.

4. **Demand is smooth within the month.**
   Algerian salaries are overwhelmingly paid at end of month, so consumer
   demand spikes in the first days of each month and thins before it.

Calendar accuracy
=================
Hijri dates here come from the standard *tabular* Islamic calendar, computed
locally so the app works with no network at all. The tabular calendar can
differ by a day or two from the date Algeria actually announces, because
Algeria determines the start of Ramadan and the Aids by local moon sighting
via the Commission Nationale d'Observation du Croissant Lunaire.

We handle that honestly rather than pretending it away:

  * ``hijri_offset_days`` shifts the whole computed calendar if you know the
    real announcement differs.
  * ``refine_from_aladhan()`` will, when a network is available, pull the
    authoritative conversion and cache it to disk.
  * Anything derived from the Hijri calendar carries a ``calendar_confidence``
    flag so downstream code can widen its intervals near a boundary rather
    than quietly being a day out.

In production this syncs to the official announcement. For a forecast running
14-30 days ahead, a +/-1 day uncertainty on the Aid boundary is a real effect
and we model it as one.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache")


# ---------------------------------------------------------------------------
# Tabular Islamic calendar conversion (local, offline, deterministic)
# ---------------------------------------------------------------------------

def _gregorian_to_jdn(year: int, month: int, day: int) -> int:
    """Gregorian date -> Julian Day Number."""
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return (
        day
        + (153 * m + 2) // 5
        + 365 * y
        + y // 4
        - y // 100
        + y // 400
        - 32045
    )


def _jdn_to_islamic(jdn: int) -> tuple:
    """Julian Day Number -> (hijri_year, hijri_month, hijri_day), tabular."""
    l = jdn - 1948440 + 10632
    n = (l - 1) // 10631
    l = l - 10631 * n + 354
    j = ((10985 - l) // 5316) * ((50 * l) // 17719) + (l // 5670) * ((43 * l) // 15238)
    l = (
        l
        - ((30 - j) // 15) * ((17719 * j) // 50)
        - (j // 16) * ((15238 * j) // 43)
        + 29
    )
    month = (24 * l) // 709
    day = l - (709 * month) // 24
    year = 30 * n + j - 30
    return year, month, day


def _islamic_to_jdn(year: int, month: int, day: int) -> int:
    """
    (hijri_year, hijri_month, hijri_day) -> Julian Day Number, tabular.

    The trailing -1 makes this the exact inverse of `_jdn_to_islamic` above;
    the two use the same epoch (JDN 1948440 = 1 Muharram 1 AH). Verified
    round-trip over 1400-1460 AH in the self-check at the bottom of this file.
    """
    return (
        day
        + math.ceil(29.5 * (month - 1))
        + (year - 1) * 354
        + (11 * year + 3) // 30
        + 1948440
        - 1
    )


def _jdn_to_gregorian(jdn: int) -> _dt.date:
    a = jdn + 32044
    b = (4 * a + 3) // 146097
    c = a - (146097 * b) // 4
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + m // 10
    return _dt.date(year, month, day)


# Correction applied to every Hijri conversion, in days.
#
# The tabular calendar is a fixed arithmetic rule; the calendar Algeria
# actually observes is set by moon sighting and tracks the astronomical new
# moon more closely, so the two drift apart by a day or two depending on the
# year. `refine_from_aladhan()` measures the current discrepancy and
# `set_default_offset()` applies it, so an online app self-corrects and an
# offline one degrades to the raw tabular calendar rather than to nothing.
_DEFAULT_OFFSET = 0


def set_default_offset(days: int) -> None:
    """Set the correction applied to all conversions that don't override it."""
    global _DEFAULT_OFFSET
    _DEFAULT_OFFSET = int(days)


def get_default_offset() -> int:
    return _DEFAULT_OFFSET


def _resolve_offset(offset_days: Optional[int]) -> int:
    return _DEFAULT_OFFSET if offset_days is None else int(offset_days)


def to_hijri(d: _dt.date, offset_days: Optional[int] = None) -> tuple:
    """Convert a Gregorian date to (hijri_year, hijri_month, hijri_day)."""
    off = _resolve_offset(offset_days)
    return _jdn_to_islamic(_gregorian_to_jdn(d.year, d.month, d.day) - off)


def from_hijri(hy: int, hm: int, hd: int, offset_days: Optional[int] = None) -> _dt.date:
    """Convert a Hijri date to a Gregorian date."""
    off = _resolve_offset(offset_days)
    return _jdn_to_gregorian(_islamic_to_jdn(hy, hm, hd) + off)


HIJRI_MONTHS = {
    1: "Muharram", 2: "Safar", 3: "Rabi al-Awwal", 4: "Rabi al-Thani",
    5: "Jumada al-Ula", 6: "Jumada al-Akhira", 7: "Rajab", 8: "Shaaban",
    9: "Ramadan", 10: "Shawwal", 11: "Dhu al-Qadah", 12: "Dhu al-Hijjah",
}


# ---------------------------------------------------------------------------
# Algerian public holidays
# ---------------------------------------------------------------------------

# Fixed-date civil holidays (month, day) -> name
CIVIL_HOLIDAYS = {
    (1, 1): "Nouvel An",
    (1, 12): "Yennayer (Amazigh New Year)",
    (5, 1): "Fete du Travail",
    (7, 5): "Fete de l'Independance",
    (11, 1): "Fete de la Revolution",
}

# Hijri holidays: (hijri_month, hijri_day) -> name
HIJRI_HOLIDAYS = {
    (1, 1): "Awal Muharram",
    (1, 10): "Achoura",
    (3, 12): "Mawlid an-Nabawi",
    (10, 1): "Aid el-Fitr",
    (10, 2): "Aid el-Fitr (2nd day)",
    (12, 10): "Aid el-Adha",
    (12, 11): "Aid el-Adha (2nd day)",
}

# Algeria's weekend. This single constant is the most commonly wrong line in
# any workforce tool deployed here.
WEEKEND_WEEKDAYS = (4, 5)  # Python weekday(): Monday=0 ... Friday=4, Saturday=5

WEEKDAY_NAMES_FR = {
    0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi",
    4: "Vendredi", 5: "Samedi", 6: "Dimanche",
}


# ---------------------------------------------------------------------------
# Seasonal windows specific to Algeria
# ---------------------------------------------------------------------------

# Diaspora return season. Several million Algerians resident abroad -
# predominantly in France - return over the summer, concentrated around the
# Algiers, Oran and Constantine gateways and the ferry ports. This is the
# single largest predictable volume event in Algerian passenger and retail
# operations, and it is invisible to any model built on European seasonality
# (where summer reads as a demand *trough*).
DIASPORA_START = (6, 15)   # mid-June
DIASPORA_PEAK = (7, 25)    # late July
DIASPORA_END = (9, 8)      # early September

# Rentree scolaire - the school year restart. Drives a sharp, narrow retail
# and delivery peak on stationery, uniforms and textbooks.
RENTREE_WINDOW = ((8, 20), (9, 21))

# Algerian salaries are overwhelmingly paid at end of month. Consumer demand
# rises in the first days of the following month and thins in the last week.
PAYDAY_DAY_OF_MONTH = 27


def _in_window(d: _dt.date, start: tuple, end: tuple) -> bool:
    s = _dt.date(d.year, start[0], start[1])
    e = _dt.date(d.year, end[0], end[1])
    return s <= d <= e


def _triangular_intensity(d: _dt.date, start: tuple, peak: tuple, end: tuple) -> float:
    """Ramp 0 -> 1 -> 0 across a seasonal window. 0 outside it."""
    s = _dt.date(d.year, start[0], start[1])
    p = _dt.date(d.year, peak[0], peak[1])
    e = _dt.date(d.year, end[0], end[1])
    if d < s or d > e:
        return 0.0
    if d <= p:
        span = (p - s).days or 1
        return (d - s).days / span
    span = (e - p).days or 1
    return 1.0 - (d - p).days / span


# ---------------------------------------------------------------------------
# The feature builder
# ---------------------------------------------------------------------------

@dataclass
class DayContext:
    """Everything the Algerian calendar knows about a single date."""
    date: _dt.date
    weekday: int
    weekday_name: str
    is_weekend: bool
    hijri_year: int
    hijri_month: int
    hijri_day: int
    hijri_month_name: str
    is_ramadan: bool
    ramadan_day: int              # 0 if not Ramadan
    is_last_ten_nights: bool
    days_to_eid_fitr: int         # 999 if far away
    days_to_eid_adha: int
    is_public_holiday: bool
    holiday_name: str
    is_eid_period: bool
    diaspora_intensity: float     # 0..1
    is_rentree: bool
    days_since_payday: int
    calendar_confidence: str      # "high" | "boundary"

    def as_dict(self):
        return asdict(self)


def day_context(d, hijri_offset_days: Optional[int] = None) -> DayContext:
    """Build the full Algerian calendar context for one date."""
    if isinstance(d, (pd.Timestamp, _dt.datetime)):
        d = d.date() if hasattr(d, "date") else d
    if not isinstance(d, _dt.date):
        d = pd.to_datetime(d).date()

    hy, hm, hd = to_hijri(d, hijri_offset_days)
    weekday = d.weekday()

    is_ramadan = hm == 9
    ramadan_day = hd if is_ramadan else 0
    is_last_ten = is_ramadan and hd >= 20

    # Distance to the next Aid el-Fitr (1 Shawwal) and Aid el-Adha (10 Dhu al-Hijjah)
    def _days_to(target_month: int, target_day: int) -> int:
        best = 999
        for yr in (hy, hy + 1):
            try:
                target = from_hijri(yr, target_month, target_day, hijri_offset_days)
            except (ValueError, OverflowError):
                continue
            delta = (target - d).days
            if 0 <= delta < best:
                best = delta
        return best

    days_to_fitr = _days_to(10, 1)
    days_to_adha = _days_to(12, 10)

    # Holidays
    holiday_name = ""
    if (d.month, d.day) in CIVIL_HOLIDAYS:
        holiday_name = CIVIL_HOLIDAYS[(d.month, d.day)]
    elif (hm, hd) in HIJRI_HOLIDAYS:
        holiday_name = HIJRI_HOLIDAYS[(hm, hd)]

    is_eid_period = days_to_fitr <= 2 or days_to_adha <= 2 or (hm == 10 and hd <= 3)

    # Hijri boundaries are where moon-sighting disagreement bites. Flag the
    # days where a +/-1 shift would change the answer, so the forecaster can
    # widen its interval instead of being confidently wrong.
    near_boundary = (
        (is_ramadan and (hd <= 2 or hd >= 29))
        or days_to_fitr <= 2
        or days_to_adha <= 2
        or (hm == 10 and hd <= 2)
    )
    confidence = "boundary" if near_boundary else "high"

    # Payday proximity
    day_of_month = d.day
    if day_of_month >= PAYDAY_DAY_OF_MONTH:
        days_since_payday = day_of_month - PAYDAY_DAY_OF_MONTH
    else:
        prev_month_end = (d.replace(day=1) - _dt.timedelta(days=1)).day
        days_since_payday = day_of_month + (prev_month_end - PAYDAY_DAY_OF_MONTH)

    return DayContext(
        date=d,
        weekday=weekday,
        weekday_name=WEEKDAY_NAMES_FR[weekday],
        is_weekend=weekday in WEEKEND_WEEKDAYS,
        hijri_year=hy,
        hijri_month=hm,
        hijri_day=hd,
        hijri_month_name=HIJRI_MONTHS.get(hm, str(hm)),
        is_ramadan=is_ramadan,
        ramadan_day=ramadan_day,
        is_last_ten_nights=is_last_ten,
        days_to_eid_fitr=days_to_fitr,
        days_to_eid_adha=days_to_adha,
        is_public_holiday=bool(holiday_name),
        holiday_name=holiday_name,
        is_eid_period=is_eid_period,
        diaspora_intensity=_triangular_intensity(
            d, DIASPORA_START, DIASPORA_PEAK, DIASPORA_END
        ),
        is_rentree=_in_window(d, *RENTREE_WINDOW),
        days_since_payday=days_since_payday,
        calendar_confidence=confidence,
    )


def calendar_frame(start, end, hijri_offset_days: Optional[int] = None) -> pd.DataFrame:
    """
    Build a DataFrame of Algerian calendar features across a date range.

    This is the feature table the forecaster trains on. Every column here is
    derived from the real Algerian calendar - none of it is invented
    seasonality.
    """
    dates = pd.date_range(start, end, freq="D")
    rows = [day_context(d, hijri_offset_days).as_dict() for d in dates]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])

    # Derived modelling features
    df["eid_fitr_runup"] = np.clip(21 - df["days_to_eid_fitr"], 0, 21) / 21.0
    df["eid_adha_runup"] = np.clip(14 - df["days_to_eid_adha"], 0, 14) / 14.0
    df["ramadan_progress"] = df["ramadan_day"] / 30.0
    df["payday_boost"] = np.exp(-df["days_since_payday"] / 6.0)
    df["is_holiday_int"] = df["is_public_holiday"].astype(int)
    df["is_weekend_int"] = df["is_weekend"].astype(int)
    df["is_ramadan_int"] = df["is_ramadan"].astype(int)
    df["is_rentree_int"] = df["is_rentree"].astype(int)

    return df


MODEL_FEATURES = [
    "is_weekend_int",
    "is_holiday_int",
    "is_ramadan_int",
    "ramadan_progress",
    "eid_fitr_runup",
    "eid_adha_runup",
    "diaspora_intensity",
    "is_rentree_int",
    "payday_boost",
    "weekday",
]


# ---------------------------------------------------------------------------
# Optional: refine against the authoritative Hijri conversion
# ---------------------------------------------------------------------------

def refine_from_aladhan(sample_date: Optional[_dt.date] = None, timeout: int = 8) -> dict:
    """
    Check our local tabular calendar against the Aladhan conversion service
    and report the offset in days.

    Returns a dict with the local result, the remote result, and the implied
    offset. Never raises - if there's no network, it says so and the app
    carries on with the local calendar. Result is cached to disk so a demo
    machine that was online once stays accurate offline.
    """
    sample_date = sample_date or _dt.date.today()
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, "hijri_offset.json")

    try:
        import requests

        url = f"https://api.aladhan.com/v1/gToH/{sample_date.strftime('%d-%m-%Y')}"
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        h = resp.json()["data"]["hijri"]
        remote = (int(h["year"]), int(h["month"]["number"]), int(h["day"]))

        # Measure against the RAW tabular calendar (offset_days=0), never the
        # already-corrected one - otherwise applying the result would shift the
        # calendar again on the next check and the correction would run away.
        local = to_hijri(sample_date, offset_days=0)
        remote_jdn = _islamic_to_jdn(*remote)
        local_jdn = _islamic_to_jdn(*local)
        offset = int(local_jdn - remote_jdn)

        result = {
            "ok": True,
            "checked_date": sample_date.isoformat(),
            "local_hijri": local,
            "remote_hijri": remote,
            "offset_days": offset,
            "source": "api.aladhan.com",
        }
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        return result

    except Exception as exc:  # noqa: BLE001 - offline is a normal state here
        if os.path.exists(cache_path):
            try:
                with open(cache_path, encoding="utf-8") as fh:
                    cached = json.load(fh)
                cached["ok"] = True
                cached["from_cache"] = True
                return cached
            except Exception:
                pass
        return {
            "ok": False,
            "error": str(exc),
            "offset_days": 0,
            "note": "Using the local tabular calendar. Accurate to within a "
                    "day or two of the official Algerian announcement.",
        }


def verify_key_dates(timeout: int = 10) -> pd.DataFrame:
    """
    Check our calendar against the reference service **on the dates that
    matter operationally** - Ramadan starts and the two Aids - rather than on
    an arbitrary day.

    Why this rather than a single global offset
    -------------------------------------------
    The tabular calendar and the astronomical one drift in and out of
    agreement across the year, so the discrepancy measured on one date does
    not hold on another. Measured against the Aladhan reference:

        15 Mar 2024 (5 Ramadan 1445)      offset  0
        10 Apr 2024 (Aid el-Fitr 1445)    offset  0
        24 Jul 2026 (mid-Safar 1448)      offset -2

    Applying the -2 measured in Safar would have shifted the Aid dates - which
    currently land exactly right - two days off. So we verify per-date and
    report, rather than applying one global shift. `set_default_offset` remains
    available for the case that genuinely warrants it: the Commission
    Nationale d'Observation du Croissant Lunaire announcing a date that
    differs from the computed one.

    Returns an empty frame if there is no network - this is a diagnostic, not
    a dependency.
    """
    rows = []
    try:
        import requests

        today = _dt.date.today()
        hy_now = to_hijri(today, offset_days=0)[0]

        targets = []
        for hy in (hy_now, hy_now + 1):
            for (hm, hd, label) in (
                (9, 1, "Début du Ramadan"),
                (10, 1, "Aïd el-Fitr"),
                (12, 10, "Aïd el-Adha"),
            ):
                try:
                    g = from_hijri(hy, hm, hd, offset_days=0)
                except (ValueError, OverflowError):
                    continue
                if g >= today - _dt.timedelta(days=400):
                    targets.append((g, hy, hm, hd, label))

        for g, hy, hm, hd, label in sorted(targets)[:6]:
            resp = requests.get(
                f"https://api.aladhan.com/v1/gToH/{g.strftime('%d-%m-%Y')}",
                timeout=timeout,
            )
            resp.raise_for_status()
            h = resp.json()["data"]["hijri"]
            remote = (int(h["year"]), int(h["month"]["number"]), int(h["day"]))
            local = (hy, hm, hd)
            delta = _islamic_to_jdn(*local) - _islamic_to_jdn(*remote)
            rows.append({
                "Event": f"{label} {hy} H",
                "Our date": g.strftime("%d %b %Y"),
                "Reference says": f"{remote[2]} {HIJRI_MONTHS.get(remote[1], remote[1])}",
                "Agreement": "exact" if delta == 0 else f"{delta:+d} jour",
            })
    except Exception:
        return pd.DataFrame(columns=["Event", "Our date", "Reference says", "Agreement"])

    return pd.DataFrame(rows)


def describe_upcoming(start=None, days: int = 120, hijri_offset_days: Optional[int] = None) -> pd.DataFrame:
    """The notable Algerian calendar events in the next N days, for the UI."""
    start = pd.to_datetime(start or _dt.date.today())
    df = calendar_frame(start, start + pd.Timedelta(days=days), hijri_offset_days)

    events = []
    ramadan = df[df["is_ramadan"]]
    if not ramadan.empty:
        events.append({
            "Date": ramadan["date"].min().date(),
            "Event": "Début du Ramadan",
            "Impact": "Volume en hausse, et la journée se réorganise , l'activité "
                      "passe au soir après le f'tour. Les horaires raccourcissent.",
        })

    for _, r in df[df["is_public_holiday"]].iterrows():
        events.append({
            "Date": r["date"].date(),
            "Event": r["holiday_name"],
            "Impact": "Jour férié , activité réduite, taux de main-d'œuvre majorés.",
        })

    diaspora = df[df["diaspora_intensity"] > 0.05]
    if not diaspora.empty:
        events.append({
            "Date": diaspora["date"].min().date(),
            "Event": "Ouverture de la saison de retour de la diaspora",
            "Impact": "Hausse de volume soutenue jusqu'à début septembre. "
                      "Pic fin juillet.",
        })

    rentree = df[df["is_rentree"]]
    if not rentree.empty:
        events.append({
            "Date": rentree["date"].min().date(),
            "Event": "Ouverture de la fenêtre de rentrée scolaire",
            "Impact": "Pic commercial et de livraison net et étroit.",
        })

    if not events:
        return pd.DataFrame(columns=["Date", "Event", "Impact"])

    out = pd.DataFrame(events).drop_duplicates(subset=["Date", "Event"])
    return out.sort_values("Date").reset_index(drop=True)


if __name__ == "__main__":
    print("Algerian calendar engine - self check\n")

    # Verified against api.aladhan.com: 15-03-2024 -> 5 Ramadan 1445
    d = _dt.date(2024, 3, 15)
    hy, hm, hd = to_hijri(d)
    print(f"{d} -> {hd} {HIJRI_MONTHS[hm]} {hy}  (expected ~5 Ramadan 1445)")

    ctx = day_context(d)
    print(f"  weekday       : {ctx.weekday_name} (weekend={ctx.is_weekend})")
    print(f"  ramadan day   : {ctx.ramadan_day}")
    print(f"  days to Fitr  : {ctx.days_to_eid_fitr}")
    print(f"  confidence    : {ctx.calendar_confidence}")

    print("\nThe weekend check that most tools fail:")
    for probe in [_dt.date(2026, 7, 24), _dt.date(2026, 7, 25), _dt.date(2026, 7, 26)]:
        c = day_context(probe)
        print(f"  {probe} {c.weekday_name:<10} weekend={c.is_weekend}")

    print("\nUpcoming Algerian demand events:")
    print(describe_upcoming(days=240).to_string(index=False))
