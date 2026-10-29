"""
core/autopilot.py
-----------------
The HR autopilot: every engine of the platform goes over today's data, does the
work, and leaves only the decisions to the manager.

The principle
=============
Classic HR software waits for someone to open its screens. Here the agents run
first (attendance, payroll, compliance, filings, retention, hiring, employee
desk) and produce a **decision inbox**: each card says what was done, why, what
approval triggers and the money at stake.

No agent sends, files, pays or rejects anything without a human click. What is
lawful and carries no operational risk (`auto=True`) is grouped so it can be
signed with one click; everything else gets its own card. The engine prepares
and recommends, the human signs.

The "minutes saved" are an **assumption** (average manual time per task,
`MANUAL_MINUTES`) and are presented as such.

Agent names ("Présence", "Paie"...) are internal ids; core/i18n.py displays them.
"""

from __future__ import annotations

import calendar
import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from . import (anomalies as anom_mod, attendance, compliance, cv_screen,
               deadlines_dz as dl, retention, talent)

# Average manual time per task, in minutes. An assumption, not a measurement:
# what an HR officer spends checking a request, recomputing a payslip, preparing
# a filing. A pilot replaces it with real timings.
MANUAL_MINUTES = {
    "request": 8,        # check balance, notice, schedule, reply
    "anomaly": 25,       # find the gap, recompute, correct
    "deadline": 90,      # prepare a CNAS / G50 / DAS filing
    "compliance": 30,    # read the text, check the file
    "retention": 45,     # analyse a likely departure, prepare the meeting
    "shortlist": 120,    # sort the CVs received for a post
    "ticket": 12,        # certificate, balance, payslip copy
    "payroll": 240,      # monthly payroll close, checks included
    "anem": 40,          # follow the ANEM vacancy and report per candidate
    "affiliation": 30,   # CNAS affiliation file for a new hire
}

# ANEM window: working days left to the agency to refer candidates before any
# direct hire (law 04-19 amended by law 20-03).
ANEM_WINDOW_DAYS = 5
CNAS_AFFILIATION_DAYS = 10

AGENTS = ("Présence", "Paie", "Conformité", "Déclarations", "Rétention",
          "Recrutement", "Guichet")


def working_days_between(a: _dt.date, b: _dt.date) -> int:
    """Working days from a (excluded) to b (included), outside the Friday-Saturday weekend."""
    n, d = 0, a
    while d < b:
        d += _dt.timedelta(days=1)
        if d.weekday() not in (4, 5):
            n += 1
    return n


@dataclass
class Action:
    key: str                 # stable id, to remember the decision
    agent: str               # the agent that produced the card
    title: str               # the decision, in one line
    detail: str              # what the agent found and did
    decision: str            # what "Approve" triggers
    urgency: int             # 0 critical, 1 high, 2 normal, 3 info
    minutes: float           # manual time avoided (assumption)
    stakes_dzd: float = 0.0  # money at stake, when it can be costed
    auto: bool = False       # lawful and needs no judgement: can be signed in a batch
    page: str = ""           # detail screen (app_pages/... path)
    law: str = ""            # the rule or source applied
    payload: dict = field(default_factory=dict)


@dataclass
class Run:
    actions: list            # every card produced
    log: list                # (agent, what was processed) for the log

    def pending(self, decided: dict) -> list:
        return [a for a in self.actions if a.key not in decided]

    def handled(self, decided: dict) -> list:
        return [a for a in self.actions if a.key in decided]


# ---------------------------------------------------------------------------
# The agents
# ---------------------------------------------------------------------------

_REC = {
    "approve": "approve", "approve_with_cover": "approve with cover",
    "approve_with_note": "approve with a note", "reject": "decline",
    "record": "record", "review": "manual review",
}


def _n(v: float) -> str:
    return f"{v:,.0f}"


def _requests_agent(requests, people, forecast, as_of) -> tuple[list, str]:
    lookup = {e.emp_id: e for e in people}
    out = []
    for r in requests:
        emp = lookup.get(r.emp_id)
        if emp is None or r.status != "pending":
            continue
        d = attendance.decide_request(r, emp, as_of=as_of, forecast=forecast)
        rec = d["recommend"]
        span = (f"on {r.start:%d/%m}" if r.is_sortie
                else f"from {r.start:%d/%m} to {r.end:%d/%m}")
        why = " ".join((d["warnings"] or d["reasons"])[:1])
        out.append(Action(
            key=f"req:{r.req_id}", agent="Présence",
            title=f"{r.kind_label} for {r.emp_name} {span}: {_REC.get(rec, rec)}",
            detail=f"“{r.reason}”. {why}",
            decision=("Reply sent to the employee, schedule updated."
                      if rec != "reject" else
                      "Reasoned refusal sent to the employee, with possible dates."),
            urgency=1 if rec in ("reject", "approve_with_cover") else 2,
            minutes=MANUAL_MINUTES["request"],
            # Lawful and no peak: nothing to judge, the agent replies on its own.
            auto=rec in ("approve", "record"),
            page="app_pages/requests_view.py",
            law=("Law 83-11, social insurance" if r.kind == "sick" else
                 "Law 90-11, art. 54 (special leave)" if r.kind == "family" else
                 "Law 90-11, art. 39 to 42 (annual leave)" if r.kind == "annual" else
                 "Internal rules, short absences"),
            payload={"recommend": rec, "req_id": r.req_id},
        ))
    return out, f"{len(out)} leave and short-absence requests checked (balance, notice, forecast load)"


def _payroll_agent(people, records, as_of) -> tuple[list, str]:
    """The month's payroll, recomputed and checked: one card to sign."""
    res = anom_mod.detect(people, records, as_of)
    pay = res["payroll_frame"]
    issues, seen = [], set()
    for a in res["anomalies"]:
        # Only broken payroll rules count here. The model's "unusual profiles"
        # and attendance signals stay on the detail screen.
        if a.domain != "paie" or a.kind == "profil_atypique" or a.emp_id in seen:
            continue
        seen.add(a.emp_id)
        issues.append(f"{a.name}: {a.detail.rstrip('.')}")
    # The month's overtime against the 20% cap on legal hours (art. 31),
    # brought to the month: 8 h a week x 52 / 12.
    from . import rules
    h = rules.payroll()["hours"]
    cap_month = h["legal_week"] * h["overtime_cap_fraction"] * 52 / 12
    for e in people:
        ot = getattr(e, "overtime_hours_month", 0) or 0
        if ot > cap_month and e.emp_id not in seen:
            seen.add(e.emp_id)
            issues.insert(0, f"{e.name}: {ot:.0f} h overtime this month, above the "
                             f"{cap_month:.0f} h cap (Law 90-11, art. 31)")
    if pay.empty:
        return [], "no payslip to compute"
    net = float(pay["net"].sum()) if "net" in pay else 0.0
    month = calendar.month_name[as_of.month]
    found = (f"{len(issues)} item(s) to fix: " + "; ".join(issues[:3])
             + ("…" if len(issues) > 3 else "")) if issues else \
        "No gap with the SNMG, CNAS or the IRG scale."
    return [Action(
        key=f"pay:{as_of:%Y-%m}", agent="Paie",
        title=(f"{month} payroll ready: {len(pay)} employees, total net "
               f"{_n(net)} DZD, {len(issues)} item(s) to check"),
        detail=f"{len(pay)} payslips recomputed: gross, CNAS, IRG, net. {found}",
        decision="Payslips published, bank transfer file and journal entries generated.",
        urgency=1 if issues else 2, minutes=MANUAL_MINUTES["payroll"],
        page="app_pages/payroll_view.py",
        law="SNMG (decree 26-01), CNAS, IRG scale art. 104, overtime art. 31",
        payload={"issues": issues},
    )], f"{len(pay)} payslips recomputed, {len(issues)} payroll gaps"


def _draft_figure(o, people) -> str:
    """The amount of the draft prepared for this deadline, when it can be computed."""
    from . import filings
    parts = o.key.split("_")
    try:
        if o.key.startswith("g50_"):
            d = filings.g50_draft(people, int(parts[1]), int(parts[2]))
            return f" Draft ready: IRG withheld {_n(d['irg_total'])} DZD across {d['employees']} employees."
        if o.key.startswith("cnas_mensuel_"):
            d = filings.cnas_draft(people, int(parts[2]), int(parts[3]))
            return (f" Draft ready: {_n(d['total_due'])} DZD to pay "
                    f"(employer {_n(d['employer_total'])}, employee {_n(d['employee_total'])}).")
        if o.key.startswith("das_"):
            d = filings.das_draft(people, int(parts[1]))
            return f" Draft ready: {d['employees']} employee lines."
    except (ValueError, IndexError):
        pass
    return ""


def _deadlines_agent(headcount, as_of, people=()) -> tuple[list, str]:
    items = dl.upcoming(as_of, headcount=headcount, horizon_days=45)
    out = []
    for o in items:
        st = o.status(as_of)
        if st not in ("en_retard", "urgent", "a_venir"):
            continue
        days = o.days_left(as_of)
        when = ("overdue, settle it now" if days < 0 else
                "file today" if days == 0 else f"file within {days} days")
        out.append(Action(
            key=f"dl:{o.key}:{o.due.isoformat()}", agent="Déclarations",
            title=f"{o.label} · {o.body}: {when}",
            detail=f"{o.period}. {o.what}" + (_draft_figure(o, people) if people else ""),
            decision=f"Draft approved and sent to the accountant, who files on "
                     f"{o.portal}. Calendar reminder 3 days before. The agent files nothing.",
            urgency=0 if st in ("en_retard", "urgent") else 2,
            minutes=MANUAL_MINUTES["deadline"],
            page="app_pages/deadlines_view.py", law=o.source,
            payload={"penalty": o.penalty},
        ))
    return out, f"{len(items)} CNAS, G50 and DAS deadlines computed over 45 days"


def _compliance_agent(people, as_of) -> tuple[list, str]:
    alerts = compliance.scan(people=people, as_of=as_of)
    out = []
    for a in alerts:
        if a.severity == "info":
            continue
        out.append(Action(
            key=f"comp:{a.category}:{a.message[:60]}", agent="Conformité",
            title=a.message, detail=a.action, law=a.rule,
            decision="The file is brought into compliance and the document archived.",
            urgency=0 if a.severity == "critical" else 1,
            minutes=MANUAL_MINUTES["compliance"],
            page="app_pages/inspector_sim.py",
        ))
    return out, f"{len(people)} files checked against the labour code"


def _retention_agent(attrition_df, people, records, as_of, top: int = 3) -> tuple[list, str]:
    out = []
    if attrition_df is None or attrition_df.empty:
        return out, "no workforce to analyse"
    high = attrition_df[attrition_df["Band"] == "high"].head(top)
    for _, row in high.iterrows():
        plan = retention.plan_for_employee(people, records, row["ID"], as_of)
        if plan is None or plan.best is None or plan.best.net_dzd <= 0:
            continue
        b = plan.best
        out.append(Action(
            key=f"ret:{row['ID']}", agent="Rétention",
            title=f"Keep {row['Name']}: {b.label[0].lower()}{b.label[1:]}",
            detail=(f"Leaving risk {plan.base_risk * 100:.0f}% (main cause: "
                    f"{plan.top_driver.lower()}). The action brings it to "
                    f"{b.new_risk * 100:.0f}% "
                    + (f"for {_n(b.cost_dzd)} DZD a year." if b.cost_dzd > 0
                       else "at no direct cost.")),
            decision="Meeting booked with the manager, talking points attached.",
            urgency=1, minutes=MANUAL_MINUTES["retention"], stakes_dzd=b.net_dzd,
            page="app_pages/retention_negotiator.py",
            law="Rule-based early warning (not yet trained on your departures)",
        ))
    return out, (f"{len(attrition_df)} employees scored, {int((attrition_df['Band'] == 'high').sum())} "
                 f"at high risk")


def _recruiting_agent(role_key: str) -> tuple[list, str]:
    key = role_key if role_key in cv_screen.JOBS else next(iter(cv_screen.JOBS))
    job = cv_screen.JOBS[key]
    ranked = talent.rank_pool(talent.sample_pool(key, n=28), job)
    strong = [s for s in ranked if s.band == "strong"][:3]
    out = []
    if strong:
        names = ", ".join(s.candidate.name for s in strong)
        out.append(Action(
            key=f"rec:{key}:{'|'.join(s.candidate.name for s in strong)}",
            agent="Recrutement",
            title=f"Invite {len(strong)} candidates to interview ({job.title})",
            detail=(f"{len(ranked)} applications read and ranked. Shortlisted: {names}. "
                    f"Every ranking is explained in the candidate pool."),
            decision="Invitations sent with three proposed slots.",
            urgency=2, minutes=MANUAL_MINUTES["shortlist"],
            page="app_pages/talent_pool.py",
            law="Explainable rule-based score: education, experience, languages, licence",
        ))
    return out, f"{len(ranked)} CVs read and ranked for {job.title}"


def _anem_agent(role_title: str, filed_on: _dt.date, as_of: _dt.date) -> tuple[list, str]:
    """The ANEM window of the open vacancy: the countdown, and what comes next."""
    used = working_days_between(filed_on, as_of)
    left = ANEM_WINDOW_DAYS - used
    law = "Law 04-19 amended by law 20-03 (5 working days)"
    if left > 0:
        act = Action(
            key=f"anem:{filed_on.isoformat()}:{used}", agent="Recrutement",
            title=(f"{role_title.capitalize()} vacancy at ANEM: day {used} of {ANEM_WINDOW_DAYS}, "
                   f"{left} working day(s) left"),
            detail=(f"Filed on {filed_on:%d/%m}. Every candidate the agency refers is "
                    "contacted and the outcome recorded for the per-candidate report."),
            decision="Per-candidate report sent to ANEM.",
            urgency=1 if left <= 1 else 2, minutes=MANUAL_MINUTES["anem"],
            page="app_pages/job_post_view.py", law=law)
    else:
        act = Action(
            key=f"anem:{filed_on.isoformat()}:open", agent="Recrutement",
            title=f"ANEM window closed for {role_title}: direct hiring allowed",
            detail="Five working days passed without a placement. The internal pool "
                   "and the other channels can be opened.",
            decision="Direct hiring opened; ANEM will be told of the hire.",
            urgency=1, minutes=MANUAL_MINUTES["anem"],
            page="app_pages/sourcing_view.py", law=law)
    return [act], (f"{role_title} vacancy tracked at ANEM, day "
                   f"{min(used, ANEM_WINDOW_DAYS)} of {ANEM_WINDOW_DAYS}")


def _affiliation_agent(people, as_of) -> tuple[list, str]:
    """Every new hire must be affiliated with CNAS within ten days."""
    out = []
    for e in people:
        age = (as_of - e.hire_date).days
        if 0 <= age <= CNAS_AFFILIATION_DAYS:
            left = CNAS_AFFILIATION_DAYS - age
            out.append(Action(
                key=f"aff:{e.emp_id}", agent="Déclarations",
                title=f"CNAS affiliation for {e.name}: {left} day(s) left",
                detail=(f"Hired on {e.hire_date:%d/%m}. Form, contract and a copy of the "
                        f"ID document gathered."),
                decision="Affiliation file ready to submit on the CNAS portal.",
                urgency=0 if left <= 3 else 1, minutes=MANUAL_MINUTES["affiliation"],
                page="app_pages/people.py",
                law="CNAS affiliation within 10 days of hiring"))
    return out, f"{len(out)} new hire(s) to affiliate"


def _tickets_agent(tickets: list) -> tuple[list, str]:
    out = []
    for t in tickets:
        if not t.get("needs_signature"):
            continue
        out.append(Action(
            key=f"tk:{t['id']}", agent="Guichet",
            title=(f"{t['label']} for {t['emp_name']}: ready to sign"
                   if t.get("document") else f"{t['label']} from {t['emp_name']}"),
            detail=f"Asked at the employee desk: “{t['text']}”. Written from the employee's file.",
            decision=t.get("decision", "Document signed and handed to the employee."),
            urgency=2, minutes=MANUAL_MINUTES["ticket"],
            # A document signed on behalf of the company gets its own card.
            auto=False, page="app_pages/self_service.py",
            law="Facts from the employee file", payload={"ticket": t["id"]},
        ))
    answered = sum(1 for t in tickets if not t.get("needs_signature"))
    return out, f"{len(tickets)} employee requests received, {answered} answered automatically"


def run(*, people: list, records: list, requests: list, attrition_df: pd.DataFrame,
        forecast: Optional[pd.DataFrame], headcount: int, role_key: str,
        tickets: Optional[list] = None, as_of: Optional[_dt.date] = None,
        anem_filed: Optional[_dt.date] = None, open_role_title: str = "") -> Run:
    """Run every agent, in the order a manager would."""
    as_of = as_of or _dt.date.today()
    steps = [
        ("Présence", lambda: _requests_agent(requests, people, forecast, as_of)),
        ("Paie", lambda: _payroll_agent(people, records, as_of)),
        ("Déclarations", lambda: _deadlines_agent(headcount, as_of, people)),
        ("Affiliations", lambda: _affiliation_agent(people, as_of)),
        ("Conformité", lambda: _compliance_agent(people, as_of)),
        ("Rétention", lambda: _retention_agent(attrition_df, people, records, as_of)),
        ("Recrutement", lambda: _recruiting_agent(role_key)),
        ("ANEM", lambda: _anem_agent(open_role_title or "open",
                                     anem_filed or as_of - _dt.timedelta(days=6), as_of)),
        ("Guichet", lambda: _tickets_agent(tickets or [])),
    ]
    actions, log = [], []
    for agent, fn in steps:
        try:
            acts, note = fn()
        except Exception as exc:  # noqa: BLE001 , one failing agent does not block the others
            acts, note = [], f"unavailable ({type(exc).__name__})"
        actions += acts
        log.append((agent, note))
    actions.sort(key=lambda a: (a.urgency, -a.stakes_dzd))
    return Run(actions=actions, log=log)


def totals(actions: list) -> dict:
    return {
        "count": len(actions),
        "minutes": sum(a.minutes for a in actions),
        "stakes": sum(a.stakes_dzd for a in actions),
    }


if __name__ == "__main__":
    from . import attrition, hr
    people = hr.sample_workforce("sorter", 60, "Alger")
    records = attendance.sample_attendance(people)
    r = run(people=people, records=records,
            requests=attendance.sample_requests(people),
            attrition_df=attrition.score_workforce(people, records),
            forecast=None, headcount=60, role_key="sorter",
            tickets=[{"id": "t1", "label": "Work certificate",
                      "emp_name": "Test", "text": "attestation",
                      "needs_signature": True}])
    for agent, note in r.log:
        print(f"  {agent:12s} {note}")
    assert r.actions, "the autopilot must produce at least one card"
    assert all(a.agent in AGENTS for a in r.actions)
    assert len({a.key for a in r.actions}) == len(r.actions), "duplicate keys"
    batch = [a for a in r.pending({}) if a.auto]
    assert batch, "compliant requests must be signable in a batch"
    assert not any(a.agent == "Guichet" for a in batch), "a signed document has its own card"
    print(f"  {len(r.actions)} cards, {len(batch)} signable in one click")
    print("  ok")
