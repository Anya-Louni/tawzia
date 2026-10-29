"""
core/retention.py
-----------------
The Retention Negotiator.

Attrition tells you WHO is likely to quit. This module answers the next, harder
question: what is the single cheapest thing you can do to keep them, and would
it actually pay off?

For a flight-risk employee it reads the attrition model's own drivers, then for
each realistic lever (a raise, a CDD->CDI conversion, overdue leave, an
attendance conversation, better onboarding) it runs a counterfactual THROUGH THE
SAME MODEL: it changes the driver the lever targets, re-scores the quit risk,
and turns the drop in risk into money saved (risk reduction x replacement cost).
The best net-value lever wins. An AI layer then writes the manager's actual
one-to-one script.

Honesty: like the attrition model, the weights are documented, not trained on
real Algerian quit data (none is public). So the money figures are directional
and re-fit on a pilot. The method - model-based counterfactuals - is the real
part.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import List, Optional

from . import attrition, labour_dz, ai
from . import attendance as attendance_mod


@dataclass
class Lever:
    key: str
    label: str
    cost_dzd: float        # indicative annual cost of the intervention
    new_risk: float        # quit probability after the lever
    risk_drop: float       # base - new (>= 0)
    value_dzd: float       # risk_drop * replacement cost
    net_dzd: float         # value - cost
    rationale: str


@dataclass
class RetentionPlan:
    emp_id: str
    name: str
    base_risk: float
    band: str
    replacement_cost: float
    top_driver: str
    levers: List[Lever]
    best: Optional[Lever]
    script: str = ""


def _score_from_features(f: dict) -> float:
    linear = attrition.W["intercept"] + sum(attrition.W[k] * f[k] for k in f)
    return attrition._logistic(linear)


def _mk(key, label, cost, new_p, base_p, repl, rationale) -> Lever:
    drop = max(0.0, base_p - new_p)
    value = drop * repl
    return Lever(key, label, round(cost), round(new_p, 4), round(drop, 4),
                 round(value), round(value - cost), rationale)


def _levers_for(emp, att_row, as_of) -> RetentionPlan:
    base = attrition.score_employee(emp, att_row, as_of)
    f = attrition._features(emp, att_row, as_of)
    base_p = base.probability
    repl = base.replacement_cost
    gross = emp.monthly_gross()
    levers: List[Lever] = []

    # 1. Pay raise toward the comfort band
    if f["low_pay"] > 0.05:
        target = attrition.PAY_COMFORT
        raise_amt = max(0.0, target - gross)
        annual_cost = raise_amt * 12 * (1 + labour_dz.CNAS_EMPLOYER)
        f2 = dict(f); f2["low_pay"] = 0.0
        levers.append(_mk(
            "pay", f"Raise pay to {target:,.0f} DZD a month",
            annual_cost, _score_from_features(f2), base_p, repl,
            f"Raise base pay by about {raise_amt:,.0f} DZD a month. Pay close to "
            f"the SNMG floor is one of the strongest drivers of leaving."))

    # 2. Convert CDD -> CDI
    if f["cdd"] > 0:
        f2 = dict(f); f2["cdd"] = 0.0
        levers.append(_mk(
            "cdi", "Convert the CDD to a permanent CDI", 0.0,
            _score_from_features(f2), base_p, repl,
            "Offer a permanent contract. People on CDD leave more often, and it also "
            "removes the requalification risk beyond 24 months."))

    # 3. Book overdue leave (burnout)
    if f["unused_leave"] > 0.3:
        f2 = dict(f); f2["unused_leave"] = f["unused_leave"] * 0.3
        cost = gross / 22.0 * 3.0   # ~3 days of cover
        levers.append(_mk(
            "leave", "Book the overdue leave never taken", cost,
            _score_from_features(f2), base_p, repl,
            "Schedule the unused annual leave. Never taking leave is a burnout "
            "signal that comes before resignation."))

    # 4. Attendance conversation + schedule fit
    if f["absence"] > 0.1 or f["lateness"] > 0.1:
        f2 = dict(f); f2["absence"] = f["absence"] * 0.5; f2["lateness"] = f["lateness"] * 0.5
        levers.append(_mk(
            "coach", "An attendance talk and a better-fitting shift", 0.0,
            _score_from_features(f2), base_p, repl,
            "A structured talk about attendance, and a shift pattern that fits "
            "real constraints (prayer, school runs, a second job)."))

    # 5. Onboarding / early-tenure engagement
    if f["short_tenure"] > 0.1:
        f2 = dict(f); f2["short_tenure"] = f["short_tenure"] * 0.5
        levers.append(_mk(
            "onboard", "Assign a buddy and a 90-day check-in", 0.0,
            _score_from_features(f2), base_p, repl,
            "Turnover peaks in the first year. Structured onboarding and an early "
            "check-in reduce it at low cost."))

    levers.sort(key=lambda l: l.net_dzd, reverse=True)
    best = levers[0] if levers else None
    return RetentionPlan(
        emp_id=emp.emp_id, name=emp.name, base_risk=base_p, band=base.band,
        replacement_cost=repl,
        top_driver=base.drivers[0][0] if base.drivers else "-",
        levers=levers, best=best,
    )


def plan_for_employee(people, records, emp_id, as_of: Optional[_dt.date] = None) -> Optional[RetentionPlan]:
    as_of = as_of or _dt.date.today()
    summ = attendance_mod.lateness_summary(records)
    att_by_id = {r["ID"]: r for r in summ.to_dict("records")} if not summ.empty else {}
    emp = next((e for e in people if e.emp_id == emp_id), None)
    if emp is None:
        return None
    return _levers_for(emp, att_by_id.get(emp_id), as_of)


def write_script(plan: RetentionPlan, lang: str = "en") -> str:
    if plan is None or plan.best is None:
        return ""
    lang_name = "French" if lang == "fr" else "English"
    system = (
        "You are an experienced Algerian HR manager preparing a retention "
        "one-to-one. Be warm, specific and brief. Do not promise anything beyond "
        f"the chosen action. Output only the script, in {lang_name}."
    )
    user = (
        f"Employee: {plan.name}. Quit risk: {plan.base_risk:.0%}. "
        f"Main reason: {plan.top_driver}. Chosen action: {plan.best.label} "
        f"({plan.best.rationale}). Write a short one-to-one script in 3 to 5 "
        f"beats the manager can follow, respectful and human."
    )
    r = ai.chat(system, user, max_tokens=420, temperature=0.45)
    if r.ok and r.text.strip():
        return r.text.strip()
    return _template_script(plan, lang)


def _template_script(plan: RetentionPlan, lang: str) -> str:
    b = plan.best
    if lang == "fr":
        return (
            f"1. Ouvrir avec de la reconnaissance : dire a {plan.name} que son "
            f"travail compte.\n"
            f"2. Ecouter : demander comment il/elle se sent dans son poste en ce moment.\n"
            f"3. Proposer : {b.label}.\n"
            f"4. Expliquer pourquoi : {b.rationale}\n"
            f"5. Convenir d'un suivi dans deux semaines."
        )
    return (
        f"1. Open with recognition: tell {plan.name} their work matters.\n"
        f"2. Listen: ask how they feel about the role right now.\n"
        f"3. Offer: {b.label}.\n"
        f"4. Explain why: {b.rationale}\n"
        f"5. Agree a follow-up in two weeks."
    )


if __name__ == "__main__":
    from . import hr
    print("Retention negotiator - self check\n")
    people = hr.sample_workforce("sorter", 40, "Alger")
    records = attendance_mod.sample_attendance(people, days=14)
    # score everyone, take the highest risk
    df = attrition.score_workforce(people, records)
    top_id = df.iloc[0]["ID"]
    plan = plan_for_employee(people, records, top_id)
    print(f"{plan.name}: risk {plan.base_risk:.0%}, replacement {plan.replacement_cost:,.0f} DZD")
    for l in plan.levers:
        print(f"  - {l.label}: cost {l.cost_dzd:,.0f}, new risk {l.new_risk:.0%}, "
              f"saves {l.value_dzd:,.0f}, net {l.net_dzd:,.0f}")
    print("BEST:", plan.best.label if plan.best else "none")
    print("\nscript (template):\n", _template_script(plan, "fr"))
