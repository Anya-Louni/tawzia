"""
core/skills.py
--------------
Skills map and internal mobility.

External hiring is the default answer to a vacancy. It is also the most
expensive and the slowest. In most workforces someone is already two skills
away from the open role, and nobody knows, because skills are written nowhere.

This module writes down what is missing:
  1. The framework: which skills, at what level, each role requires.
  2. Each employee's profile, derived from the role held and seniority.
  3. The team gap: skills where staff sit below their own role's level.
  4. Internal mobility: who is closest to an open role, what they lack, and
     how many days away they are.
  5. Train or hire: both costs side by side, with the lead time.

The role framework is an explicit modelling choice, built from the roles in
core/labour_dz, and the first thing a client replaces with its own grid.
Demo profiles are derived from the synthetic workforce; in production they come
from the annual review or the imported HR file. The derivation is deterministic.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import labour_dz, sources

# ---------------------------------------------------------------------------
# The skills framework
# ---------------------------------------------------------------------------

SKILLS = {
    "securite": "Workplace safety (HSE)",
    "manutention": "Handling and technique",
    "scan_wms": "Scanning and warehouse system",
    "inventaire": "Stock and inventory",
    "conduite": "Driving and highway code",
    "itineraire": "Route optimisation",
    "cash": "Cash handling",
    "service_client": "Customer service",
    "langue_ar": "Arabic, professional",
    "langue_fr": "French, professional",
    "langue_en": "English, professional",
    "informatique": "Digital and office tools",
    "reservation": "Booking and ticketing systems",
    "hygiene": "Hygiene and cleaning",
    "restauration": "Food service",
    "planification": "Planning and organisation",
    "encadrement": "Team leadership",
    "droit_travail": "Algerian labour law",
    "kpi": "Managing by indicators",
    "maintenance": "First-line maintenance",
    "surete": "Airport security procedures",
    "pedagogie": "Teaching and classroom management",
}

# Required level per role, from 1 (basics) to 5 (mastery, can train others).
ROLE_SKILLS = {
    "sorter": {"securite": 3, "manutention": 3, "scan_wms": 3, "inventaire": 2,
               "langue_ar": 2, "informatique": 2},
    "warehouse_op": {"securite": 3, "manutention": 3, "scan_wms": 3, "inventaire": 3,
                     "maintenance": 2, "informatique": 2},
    "loader": {"securite": 3, "manutention": 4, "inventaire": 2, "langue_ar": 2},
    "courier": {"conduite": 4, "itineraire": 3, "cash": 3, "service_client": 3,
                "securite": 2, "langue_ar": 3},
    "driver": {"conduite": 4, "itineraire": 3, "securite": 3, "maintenance": 2,
               "langue_ar": 2},
    "ramp_agent": {"securite": 4, "manutention": 3, "surete": 3, "maintenance": 2,
                   "langue_en": 2},
    "checkin_agent": {"service_client": 4, "reservation": 3, "surete": 3,
                      "langue_fr": 3, "langue_en": 3, "langue_ar": 3, "informatique": 3},
    "front_desk": {"service_client": 4, "reservation": 3, "langue_fr": 3,
                   "langue_en": 3, "langue_ar": 3, "informatique": 3, "cash": 2},
    "fnb_staff": {"service_client": 3, "restauration": 3, "hygiene": 3,
                  "langue_fr": 2, "langue_ar": 2, "cash": 2},
    "housekeeper": {"hygiene": 4, "securite": 2, "manutention": 2, "service_client": 2},
    "supervisor": {"encadrement": 4, "planification": 4, "kpi": 3, "droit_travail": 3,
                   "securite": 3, "informatique": 3, "service_client": 2},
    "dispatcher": {"planification": 4, "itineraire": 3, "kpi": 3, "informatique": 3,
                   "encadrement": 2, "langue_ar": 2},
    "teacher": {"pedagogie": 4, "langue_ar": 4, "langue_fr": 3, "planification": 3,
                "informatique": 2},
    "school_life": {"pedagogie": 3, "encadrement": 3, "service_client": 3,
                    "langue_ar": 3, "planification": 2, "securite": 2},
}

# ---------------------------------------------------------------------------
# Cost assumptions, named so the client can replace them
# ---------------------------------------------------------------------------

TRAINING_DAYS_PER_LEVEL = 4        # training days to gain one level
# Both amounts come from the sources register so they match the Sources page.
TRAINING_COST_PER_DAY = sources.value("training_cost_per_day")
MAX_TRAINABLE_GAP = 2              # beyond 2 levels it is another trade
ONBOARDING_MONTHS = 2.0            # ramp-up of an external hire
EXTERNAL_RECRUIT_COST = sources.value("external_recruit_cost")
READY_THRESHOLD = 85               # coverage % above which someone is ready


# ---------------------------------------------------------------------------
# Employee skill profile
# ---------------------------------------------------------------------------

def _jitter(emp_id: str, skill: str) -> float:
    """
    Stable individual variation in [-1, +1], hashed from (staff id, skill), so
    two people in the same role differ but each keeps their own profile.
    """
    h = hashlib.sha256(f"{emp_id}:{skill}".encode()).hexdigest()
    return (int(h[:8], 16) % 2000) / 1000.0 - 1.0


def employee_skills(employee, as_of: Optional[_dt.date] = None) -> dict:
    """
    An employee's skill profile, derived from role and seniority: about the
    required level, a little below when new, a little above after some years.
    Cross-cutting skills (languages, safety, IT) are low but not zero.
    """
    as_of = as_of or _dt.date.today()
    years = employee.seniority_years(as_of)
    required = ROLE_SKILLS.get(employee.role_key, {})

    # cela le plan de formation ressort vide, ce qui n'arrive dans aucun
    experience = min(years * 0.22, 1.1)

    profile = {}
    for skill in SKILLS:
        if skill in required:
            base = required[skill] - 1.0 + experience
        else:
            base = 0.8 + experience * 0.45
        level = base + _jitter(employee.emp_id, skill) * 0.6
        profile[skill] = int(max(0, min(5, round(level))))
    return profile


def skill_matrix(people: list, as_of: Optional[_dt.date] = None) -> pd.DataFrame:
    """The staff x skills matrix, levels 0-5."""
    rows = []
    for e in people:
        prof = employee_skills(e, as_of)
        row = {"ID": e.emp_id, "Name": e.name,
               "Role": labour_dz.ROLES[e.role_key].label,
               "Seniority (yrs)": e.seniority_years(as_of or _dt.date.today())}
        row.update({SKILLS[k]: v for k, v in prof.items()})
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

def team_gaps(people: list, as_of: Optional[_dt.date] = None) -> pd.DataFrame:
    """
    For each skill the held roles require, the mean gap between the staff's
    actual level and the required level.

    A positive gap is a skill where the team is below what its own job needs:
    that is the training plan, in priority order.
    """
    if not people:
        return pd.DataFrame(columns=["Skill", "Required level", "Average level",
                                     "Gap", "Below level", "Staff concerned"])

    as_of = as_of or _dt.date.today()
    agg = {}
    for e in people:
        required = ROLE_SKILLS.get(e.role_key, {})
        prof = employee_skills(e, as_of)
        for skill, req in required.items():
            a = agg.setdefault(skill, {"req_sum": 0.0, "lvl_sum": 0.0, "n": 0, "below": 0})
            a["req_sum"] += req
            a["lvl_sum"] += prof[skill]
            a["n"] += 1
            if prof[skill] < req:
                a["below"] += 1

    rows = []
    for skill, a in agg.items():
        req = a["req_sum"] / a["n"]
        lvl = a["lvl_sum"] / a["n"]
        rows.append({
            "Skill": SKILLS[skill],
            "Required level": round(req, 1),
            "Average level": round(lvl, 1),
            "Gap": round(req - lvl, 2),
            "Below level": a["below"],
            "Staff concerned": a["n"],
        })
    return (pd.DataFrame(rows)
            .sort_values(["Gap", "Below level"], ascending=False)
            .reset_index(drop=True))


def training_plan(people: list, top: int = 5, as_of: Optional[_dt.date] = None) -> dict:
    """Cost the upskilling of the widest-gap skills."""
    gaps = team_gaps(people, as_of)
    gaps = gaps[gaps["Gap"] > 0].head(top)
    if gaps.empty:
        return {"lines": [], "total_days": 0, "total_cost": 0}

    lines, total_days, total_cost = [], 0.0, 0.0
    for _, g in gaps.iterrows():
        days = g["Gap"] * TRAINING_DAYS_PER_LEVEL * g["Below level"]
        cost = days * TRAINING_COST_PER_DAY
        lines.append({
            "Skill": g["Skill"],
            "People to train": int(g["Below level"]),
            "Training days": round(days),
            "Cost (DZD)": round(cost),
        })
        total_days += days
        total_cost += cost
    return {"lines": lines, "total_days": round(total_days),
            "total_cost": round(total_cost)}


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

@dataclass
class Fit:
    emp_id: str
    name: str
    current_role: str
    coverage: int              # % of the target role's requirements already covered
    missing: list              # [(skill, current level, required level)]
    training_days: int
    training_cost: int
    blocked: bool              # a gap too wide for training
    verdict: str               # ready | trainable | gap too wide


def role_fit(employee, target_role: str, as_of: Optional[_dt.date] = None) -> Fit:
    """How well an employee fits a target role, and what it takes to get there."""
    required = ROLE_SKILLS.get(target_role, {})
    prof = employee_skills(employee, as_of)

    covered, total, missing, days, blocked = 0.0, 0.0, [], 0.0, False
    for skill, req in required.items():
        have = prof.get(skill, 0)
        total += req
        covered += min(have, req)
        if have < req:
            gap = req - have
            missing.append((SKILLS[skill], have, req))
            days += gap * TRAINING_DAYS_PER_LEVEL
            if gap > MAX_TRAINABLE_GAP:
                blocked = True

    coverage = int(round(covered / total * 100)) if total else 0
    missing.sort(key=lambda m: m[2] - m[1], reverse=True)

    if blocked:
        verdict = "gap too wide"
    elif coverage >= READY_THRESHOLD and not missing:
        verdict = "ready"
    elif coverage >= READY_THRESHOLD:
        verdict = "ready after short upskilling"
    else:
        verdict = "trainable"

    return Fit(
        emp_id=employee.emp_id, name=employee.name,
        current_role=labour_dz.ROLES[employee.role_key].label,
        coverage=coverage, missing=missing,
        training_days=int(round(days)),
        training_cost=int(round(days * TRAINING_COST_PER_DAY)),
        blocked=blocked, verdict=verdict,
    )


def mobility_candidates(people: list, target_role: str, top: int = 10,
                        as_of: Optional[_dt.date] = None) -> list:
    """
    Rank staff for an open role: closest first, and at equal coverage the
    cheapest to train.

    Staff already in the target role are excluded: we are looking for a move.
    """
    fits = [role_fit(e, target_role, as_of) for e in people
            if e.role_key != target_role]
    fits.sort(key=lambda f: (not f.blocked, f.coverage, -f.training_days), reverse=True)
    return fits[:top]


def mobility_frame(fits: list) -> pd.DataFrame:
    rows = []
    for i, f in enumerate(fits, 1):
        rows.append({
            "Rank": i,
            "Employee": f.name,
            "Current role": f.current_role,
            "Coverage %": f.coverage,
            "Verdict": f.verdict,
            "Missing skills": len(f.missing),
            "To close": "; ".join(f"{m[0]} ({m[1]}→{m[2]})" for m in f.missing[:3]) or "-",
            "Training (days)": f.training_days,
            "Training cost (DZD)": f.training_cost,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Former ou recruter
# ---------------------------------------------------------------------------

def reskill_vs_recruit(fit: Fit, target_role: str) -> dict:
    """
    Both options costed side by side for an open role.

    Internal cost is the training days. External cost is sourcing plus the
    ramp-up period, when the role is paid but not fully held. Lead time is
    included, because a vacant role costs money too.
    """
    role = labour_dz.ROLES[target_role]
    monthly = role.loaded_monthly

    internal_cost = fit.training_cost
    internal_days = fit.training_days

    ramp_loss = monthly * ONBOARDING_MONTHS * 0.5
    external_cost = EXTERNAL_RECRUIT_COST + ramp_loss
    external_days = int(round(ONBOARDING_MONTHS * 30))

    saving = external_cost - internal_cost
    return {
        "internal_cost": round(internal_cost),
        "internal_days": internal_days,
        "external_cost": round(external_cost),
        "external_days": external_days,
        "saving": round(saving),
        "days_saved": external_days - internal_days,
        "recommendation": (
            "Train internally" if (saving > 0 and not fit.blocked)
            else "Hire externally"
        ),
    }


def role_options() -> dict:
    """Available target roles, for a UI selector."""
    return {k: labour_dz.ROLES[k].label for k in ROLE_SKILLS if k in labour_dz.ROLES}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    from . import hr

    print("Skills and internal mobility, self check")
    people = hr.sample_workforce("sorter", 40, "Alger")
    print(team_gaps(people).head(6).to_string(index=False))
    plan = training_plan(people)
    print(f"  Training plan: {plan['total_days']} days, {plan['total_cost']:,} DZD")
    fits = mobility_candidates(people, "supervisor", top=5)
    print(mobility_frame(fits).to_string(index=False))
    arb = reskill_vs_recruit(fits[0], "supervisor")
    print(f"  {fits[0].name}: {arb['recommendation']} (saving {arb['saving']:,} DZD)")
    assert employee_skills(people[0]) == employee_skills(people[0])
    print("  deterministic: True")
