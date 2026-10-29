"""
core/deadlines_dz.py
--------------------
The Algerian employer's obligation calendar: what must be filed, with whom, by
when, and what forgetting costs.

The problem it solves
=====================
An Algerian SME does not lose money because it computes a payslip wrong. It
loses money because a filing goes in late: the contribution is still due and a
late surcharge is added. The accountant knows these deadlines, but carries them
in their head, and nobody in the company knows where things stand before the
agency's reminder.

This module turns the recurring obligations into real dates, set by the site's
headcount (headcount decides the CNAS frequency), with the portal where the
filing is actually done.

Honesty
=======
The frequencies and deadlines below are sourced and dated, with the official
portal link. What is NOT certain is marked as such in `confidence`:

  * ``sourcee``     checked against a named source, cited in `source`.
  * ``a_confirmer`` the rule exists, but its amount or date varies with finance
                    laws and agency practice. The platform says so instead of
                    pretending.

No penalty amount is stated as a scale: several recent finance laws rescheduled
or removed surcharges, so the module gives the order of magnitude and refers to
the agency. That is the only defensible position in front of an accountant.

This module does not replace an accountant: it stops them forgetting.
"""

from __future__ import annotations

import calendar
import datetime as _dt
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import labour_dz, rules

# The official portals where the filing is actually done.
PORTAL_CNAS = "https://teledeclaration.cnas.dz"
PORTAL_CNAS_MAIN = "https://www.cnas.dz"
PORTAL_DGI = "https://jibayatic.dz"
PORTAL_CASNOS = "https://www.casnos.com.dz"

# From this headcount, CNAS contributions are filed monthly; below it, quarterly.
CNAS_MONTHLY_THRESHOLD = rules.payroll()["filings"]["cnas_monthly_from_headcount"]

# Filing and payment delay after the end of the contribution period.
CNAS_FILING_DAYS = rules.payroll()["filings"]["cnas_days_after_period"]  # [verify]

# Last day to file the monthly G50 (following month).
G50_DAY = rules.payroll()["filings"]["g50_day"]

# Deadline of the annual salary declaration (DAS): 31 January.
DAS_MONTH, DAS_DAY = rules.payroll()["filings"]["das_month"], rules.payroll()["filings"]["das_day"]

# Status codes are internal ids; STATUS_FR keeps its name for callers and now
# holds the English display labels.
_SEVERITY_ORDER = {"en_retard": 0, "urgent": 1, "a_venir": 2, "plus_tard": 3}

STATUS_FR = {
    "en_retard": "Overdue",
    "urgent": "Urgent",
    "a_venir": "To prepare",
    "plus_tard": "Later",
}


@dataclass
class Obligation:
    """A dated deadline, with its portal and its provenance."""
    key: str
    label: str
    body: str                    # the receiving body
    due: _dt.date
    period: str                  # the period covered, in words
    what: str                    # what to do, in one sentence
    portal: str
    penalty: str
    source: str
    confidence: str = "sourcee"  # sourcee | a_confirmer
    as_of: str = ""

    def days_left(self, as_of: _dt.date) -> int:
        return (self.due - as_of).days

    def status(self, as_of: _dt.date) -> str:
        d = self.days_left(as_of)
        if d < 0:
            return "en_retard"
        if d <= 7:
            return "urgent"
        if d <= 30:
            return "a_venir"
        return "plus_tard"


def _eom(year: int, month: int) -> _dt.date:
    return _dt.date(year, month, calendar.monthrange(year, month)[1])


def _add_months(d: _dt.date, n: int) -> _dt.date:
    """Shift by n months keeping the day, capped at the end of the target month."""
    total = d.month - 1 + n
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return _dt.date(year, month, day)


def _quarter_end(d: _dt.date) -> _dt.date:
    q_last_month = ((d.month - 1) // 3) * 3 + 3
    return _eom(d.year, q_last_month)


def _month(d: _dt.date) -> str:
    return f"{calendar.month_name[d.month]} {d.year}"


# ---------------------------------------------------------------------------
# The recurring obligations
# ---------------------------------------------------------------------------

def _cnas_contributions(as_of: _dt.date, headcount: int,
                        horizon_days: int) -> list:
    """
    Filing and payment of CNAS contributions.

    Frequency by headcount: monthly from 10 employees, quarterly below. Filing
    and payment within the delay set in the configuration after the period ends.
    """
    monthly = headcount >= CNAS_MONTHLY_THRESHOLD
    out = []
    limit = as_of + _dt.timedelta(days=horizon_days)
    split = (f"(employee share {labour_dz.CNAS_EMPLOYEE:.0%} + employer share "
             f"{labour_dz.CNAS_EMPLOYER:.1%}).")

    if monthly:
        # Start from the previous month: its deadline may still be ahead.
        cursor = _eom(*_add_months(as_of.replace(day=1), -1).timetuple()[:2])
        while cursor <= limit:
            due = cursor + _dt.timedelta(days=CNAS_FILING_DAYS)
            if due >= as_of - _dt.timedelta(days=45) and due <= limit:
                out.append(Obligation(
                    key=f"cnas_mensuel_{cursor:%Y_%m}",
                    label="Monthly CNAS contributions",
                    body="CNAS",
                    due=due,
                    period=_month(cursor),
                    what="File and pay the month's social contributions " + split,
                    portal=PORTAL_CNAS,
                    penalty="Late surcharges on unpaid contributions. The rate has "
                            "changed several times: have your agency confirm the "
                            "amount due.",
                    source="CNAS, monthly above 10 employees, filing and payment "
                           f"within {CNAS_FILING_DAYS} days [verify]",
                    confidence="a_confirmer",
                    as_of="2026",
                ))
            cursor = _eom(*_add_months(cursor.replace(day=1), 1).timetuple()[:2])
    else:
        q_end = _quarter_end(_add_months(as_of, -3))
        while q_end <= limit:
            due = q_end + _dt.timedelta(days=CNAS_FILING_DAYS)
            if due >= as_of - _dt.timedelta(days=45) and due <= limit:
                out.append(Obligation(
                    key=f"cnas_trimestre_{q_end:%Y_%m}",
                    label="Quarterly CNAS contributions",
                    body="CNAS",
                    due=due,
                    period=f"quarter ending {q_end:%d/%m/%Y}",
                    what="File and pay the quarter's social contributions " + split,
                    portal=PORTAL_CNAS,
                    penalty="Late surcharges on unpaid contributions. Have your "
                            "agency confirm the amount due.",
                    source="CNAS, quarterly below 10 employees, filing and payment "
                           f"within {CNAS_FILING_DAYS} days [verify]",
                    confidence="a_confirmer",
                    as_of="2026",
                ))
            q_end = _quarter_end(_add_months(q_end, 3))
    return out


def _g50(as_of: _dt.date, horizon_days: int) -> list:
    """
    Monthly G50 return, filed between the 1st and the 20th of the following month.

    It carries the IRG withheld on salaries and VAT. The TAP was abolished by the
    2024 finance law and no longer appears on it.
    """
    out = []
    limit = as_of + _dt.timedelta(days=horizon_days)
    month = _add_months(as_of.replace(day=1), -1)
    while True:
        due = _dt.date(*_add_months(month, 1).timetuple()[:2], G50_DAY)
        if due > limit:
            break
        if due >= as_of - _dt.timedelta(days=45):
            out.append(Obligation(
                key=f"g50_{month:%Y_%m}",
                label="Monthly G50 return",
                body="DGI (tax)",
                due=due,
                period=_month(month),
                what="File the G50: IRG withheld on the month's salaries and VAT. "
                     "Filing from the 1st to the 20th of the following month.",
                portal=PORTAL_DGI,
                penalty="Late penalties on duties declared after the deadline. The "
                        "DGI sometimes extends the deadline: check current notices "
                        "on Jibaya'tic.",
                source="DGI, G series no. 50 return, filed before the 20th of the "
                       "following month (Jibaya'tic)",
                confidence="sourcee",
                as_of="2026",
            ))
        month = _add_months(month, 1)
    return out


def _das(as_of: _dt.date, horizon_days: int) -> list:
    """Annual declaration of salaries and employees, before 31 January."""
    out = []
    limit = as_of + _dt.timedelta(days=horizon_days)
    for year in (as_of.year, as_of.year + 1):
        due = _dt.date(year, DAS_MONTH, DAS_DAY)
        if due < as_of - _dt.timedelta(days=45) or due > limit:
            continue
        out.append(Obligation(
            key=f"das_{year}",
            label="Annual salary declaration (DAS)",
            body="CNAS",
            due=due,
            period=f"year {year - 1} (1 January to 31 December)",
            what="File the named DAS: every employee, their salary and their "
                 "contributions for the past year.",
            portal=PORTAL_CNAS,
            penalty="CNAS chases employers who miss it; failing to file is "
                    "penalised. File before 31 January.",
            source="CNAS, filed before 31 January on teledeclaration.cnas.dz "
                   "(APS and Algerian Radio reminders, January)",
            confidence="sourcee",
            as_of="2026",
        ))
    return out


# One-off obligations, triggered by an event rather than the calendar.
EVENT_DRIVEN = [
    {
        "label": "Affiliation of a new employee",
        "body": "CNAS",
        "trigger": "At every hire",
        "what": "Declare the employee to CNAS as soon as they start, before the "
                "first payslip.",
        "portal": PORTAL_CNAS,
        "note": "The legal delay is short and counted in days (10 in the rules "
                "file). Have your CNAS agency confirm the exact count.",
        "confidence": "a_confirmer",
    },
    {
        "label": "Employer activity declaration",
        "body": "CNAS",
        "trigger": "When the business opens",
        "what": "Declare the company's existence as an employer.",
        "portal": PORTAL_CNAS_MAIN,
        "note": "Failing to declare activity is fined, with a surcharge per month "
                "of delay. Amount to confirm with CNAS.",
        "confidence": "a_confirmer",
    },
]


def upcoming(as_of: Optional[_dt.date] = None, headcount: int = 80,
             horizon_days: int = 120) -> list:
    """
    Every deadline in the window, most urgent first.

    `headcount` decides the CNAS frequency: it is the only parameter that changes
    the list, on purpose, because it is the only rule that truly depends on the
    company.
    """
    as_of = as_of or _dt.date.today()
    items = (_cnas_contributions(as_of, headcount, horizon_days)
             + _g50(as_of, horizon_days)
             + _das(as_of, horizon_days))
    return sorted(items, key=lambda o: (_SEVERITY_ORDER[o.status(as_of)], o.due))


def frame(as_of: Optional[_dt.date] = None, headcount: int = 80,
          horizon_days: int = 120) -> pd.DataFrame:
    """The same deadlines as a table, for display and export."""
    as_of = as_of or _dt.date.today()
    rows = []
    for o in upcoming(as_of, headcount, horizon_days):
        rows.append({
            "Due": o.due,
            "Days left": o.days_left(as_of),
            "Status": STATUS_FR[o.status(as_of)],
            "Obligation": o.label,
            "Body": o.body,
            "Period": o.period,
            "To do": o.what,
            "Portal": o.portal,
            "If late": o.penalty,
            "Source": o.source,
            "Reliability": ("Sourced" if o.confidence == "sourcee" else "To confirm"),
        })
    return pd.DataFrame(rows)


def next_critical(as_of: Optional[_dt.date] = None, headcount: int = 80) -> Optional[Obligation]:
    """The next deadline that needs action, for the inbox alert."""
    as_of = as_of or _dt.date.today()
    for o in upcoming(as_of, headcount, horizon_days=60):
        if o.status(as_of) in ("en_retard", "urgent", "a_venir"):
            return o
    return None


def counts(as_of: Optional[_dt.date] = None, headcount: int = 80,
           horizon_days: int = 120) -> dict:
    """How many deadlines per status: enough for an alert badge."""
    as_of = as_of or _dt.date.today()
    out = {k: 0 for k in STATUS_FR}
    for o in upcoming(as_of, headcount, horizon_days):
        out[o.status(as_of)] += 1
    return out


def to_ics(obligations: list, reminder_days: int = 7) -> str:
    """
    The deadlines as an .ics file, importable into any calendar.

    This is the most useful form for an accountant: they will not open the
    platform every morning, but their calendar warns them on its own. Each event
    carries a reminder `reminder_days` before, and the portal link in the
    description.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Tawzia//Employer deadlines//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Tawzia employer deadlines",
    ]
    for o in obligations:
        # A one-day event: DTEND is exclusive, hence the +1 day.
        start = o.due.strftime("%Y%m%d")
        end = (o.due + _dt.timedelta(days=1)).strftime("%Y%m%d")
        desc = (f"{o.what} Body: {o.body}. Period: {o.period}. "
                f"Portal: {o.portal}").replace(",", "\\,").replace(";", "\\;")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{o.key}@tawzia",
            f"DTSTART;VALUE=DATE:{start}",
            f"DTEND;VALUE=DATE:{end}",
            f"SUMMARY:{o.label} ({o.body})",
            f"DESCRIPTION:{desc}",
            f"URL:{o.portal}",
            "BEGIN:VALARM",
            f"TRIGGER:-P{int(reminder_days)}D",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{o.label} in {int(reminder_days)} days",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


if __name__ == "__main__":
    print("Employer deadlines: self check\n")

    today = _dt.date.today()

    # 1. The CNAS frequency follows headcount.
    small = [o for o in upcoming(today, headcount=6) if o.body == "CNAS"
             and "contributions" in o.label]
    big = [o for o in upcoming(today, headcount=80) if o.body == "CNAS"
           and "contributions" in o.label]
    ok = all("Quarterly" in o.label for o in small) and \
        all("Monthly" in o.label for o in big)
    print(f"{'OK ' if ok else 'FAIL'} 6 employees -> quarterly "
          f"({len(small)} deadlines), 80 -> monthly ({len(big)})")
    assert ok

    # 2. The G50 always falls on the 20th.
    g50 = [o for o in upcoming(today, 80, 200) if o.key.startswith("g50")]
    ok = g50 and all(o.due.day == G50_DAY for o in g50)
    print(f"{'OK ' if ok else 'FAIL'} G50: {len(g50)} deadlines, all on the "
          f"{G50_DAY}th")

    # 3. The DAS always falls on 31 January.
    das = [o for o in upcoming(today, 80, 400) if o.key.startswith("das")]
    ok = all(o.due.month == 1 and o.due.day == 31 for o in das)
    print(f"{'OK ' if ok else 'FAIL'} DAS: {len(das)} deadline(s), "
          f"{'31 January' if ok else 'unexpected date'}")

    # 4. Sorting puts the urgent first.
    ups = upcoming(today, 80, 120)
    order = [_SEVERITY_ORDER[o.status(today)] for o in ups]
    print(f"{'OK ' if order == sorted(order) else 'FAIL'} sorting: most urgent first")

    # 5. Every obligation carries a portal and a source.
    ok = all(o.portal.startswith("https://") and o.source for o in ups)
    print(f"{'OK ' if ok else 'FAIL'} every deadline has a portal and a source")

    # 6. The calendar export is well formed and holds every deadline.
    ics = to_ics(ups)
    ok = (ics.startswith("BEGIN:VCALENDAR")
          and ics.rstrip().endswith("END:VCALENDAR")
          and ics.count("BEGIN:VEVENT") == len(ups)
          and ics.count("BEGIN:VEVENT") == ics.count("END:VEVENT"))
    print(f"{'OK ' if ok else 'FAIL'} calendar export: "
          f"{ics.count('BEGIN:VEVENT')} events for {len(ups)} deadlines")

    print("\nNext action: ", end="")
    nxt = next_critical(today, 80)
    if nxt:
        print(f"{nxt.label} on {nxt.due:%d/%m/%Y} "
              f"(in {nxt.days_left(today)} days) -> {nxt.portal}")
    else:
        print("none in the next 60 days")

    print(f"\n{len(ups)} deadlines over 120 days:")
    for o in ups[:8]:
        print(f"  {o.due:%d/%m/%Y}  {STATUS_FR[o.status(today)]:12s} "
              f"{o.label} ({o.body})")
