"""
core/onboarding.py
------------------
From "offer accepted" to "fully productive", without HR typing anything
(brief §6.6).

1. The new hire fills their file from their phone (one-time link, 7 days). In
   the demo, document reading (OCR) is **simulated** from the fictional file:
   the interface says so.
2. The agent checks: ID not expired, names identical across documents, NIN and
   RIB format, minimum age, under 19 (no nights, art. 28), blurry or missing
   documents. Whatever is wrong goes back to the new hire, not to HR.
3. One card for HR. On approval, everything launches in parallel: contract,
   CNAS affiliation, ANEM notice, payroll, schedule, access and equipment,
   welcome message, then the journey (day 1, week 1, day 30/60/90, end of trial).

A role marked sensitive adds references, background check and access review on
its own. Nothing is sent or filed without a human click: the agent prepares.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field

from . import legal, rules, seed_company

_C = rules.payroll()["onboarding"]
_WT = rules.payroll()["work_time"]

DOC_LABELS = {
    "cni": "National ID card (front, back)", "extrait_naissance": "Birth certificate",
    "photo": "ID photo", "rib": "Bank details (RIB or CCP)", "diplome": "Diploma",
    "certificat_travail": "Previous work certificates",
    "aptitude_medicale": "Medical fitness certificate",
    "service_national": "National service status",
    "reglement_interieur_signe": "Signed internal rules",
    "charte_donnees_25_11": "Signed data-protection notice (law 25-11)",
    "contact_urgence": "Emergency contact",
    "references": "Reference checks", "enquete": "Background check (result only)",
    "revue_acces": "Access rights review",
}


@dataclass
class Registration:
    candidate: str
    role_key: str
    site: str
    start: _dt.date
    contract: str = "CDI"
    cdd_reason: str = ""
    gender: str = "F"
    docs: dict = field(default_factory=dict)   # code -> {"status", "fields"}


def checklist(role_key: str, gender: str) -> list:
    docs = list(_C["documents"])
    if gender != "M":                          # national service concerns men
        docs = [d for d in docs if d != "service_national"]
    if role_key in seed_company.SENSITIVE_ROLES:
        docs += list(_C["sensitive_extra"])
    return docs


def simulate_upload(reg: Registration, birth: _dt.date, id_expiry: _dt.date,
                    blurry: tuple = ("diplome",)) -> Registration:
    """Demo: what OCR would have read on each document. One blurry document on purpose."""
    for code in checklist(reg.role_key, reg.gender):
        if code in _C["sensitive_extra"]:
            continue
        reg.docs[code] = {"status": "blurry" if code in blurry else "ok", "fields": {}}
    reg.docs["cni"]["fields"] = {"name": reg.candidate, "birth": birth.isoformat(),
                                 "nin": "1" + "0" * 16 + "7", "expiry": id_expiry.isoformat()}
    reg.docs["extrait_naissance"]["fields"] = {"name": reg.candidate, "birth": birth.isoformat()}
    reg.docs["rib"]["fields"] = {"name": reg.candidate, "rib": "00799999000123456789"}
    return reg


def verify(reg: Registration, today: _dt.date | None = None) -> dict:
    """The agent's checks. `bounce` goes back to the new hire, `notes` go to HR."""
    today = today or _dt.date.today()
    need = [d for d in checklist(reg.role_key, reg.gender) if d not in _C["sensitive_extra"]]
    bounce, notes = [], []
    for d in need:
        st = reg.docs.get(d, {}).get("status")
        if st is None:
            bounce.append(f"{DOC_LABELS[d]}: missing, please add it.")
        elif st == "blurry":
            bounce.append(f"{DOC_LABELS[d]}: the photo is blurry, please retake it.")
    cni = reg.docs.get("cni", {}).get("fields", {})
    names = {v["fields"].get("name") for v in reg.docs.values() if v.get("fields", {}).get("name")}
    if len(names) > 1:
        bounce.append("The name differs between documents: check the spelling.")
    if cni:
        exp = _dt.date.fromisoformat(cni["expiry"])
        if exp < today:
            bounce.append("The ID card has expired.")
        elif (exp - today).days < 180:
            notes.append(f"The ID document expires in {(exp - today).days // 30} months.")
        if not re.fullmatch(r"\d{18}", cni.get("nin", "")):
            bounce.append("The NIN must have 18 digits.")
        b = _dt.date.fromisoformat(cni["birth"])
        age = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
        if age < _C["min_age"]:
            notes.append(f"Age {age}, below the minimum of {_C['min_age']} (art. 15) [verify].")
        elif age < _WT["night_min_age"]:
            notes.append(f"Aged {age}: no night shift possible (art. 28); the schedule knows.")
    rib = reg.docs.get("rib", {}).get("fields", {}).get("rib", "")
    if rib and not re.fullmatch(r"\d{20}", rib):
        bounce.append("The RIB must have 20 digits.")
    if reg.contract == "CDD":
        c = legal.check_cdd(reg.cdd_reason, reg.start, reg.start + _dt.timedelta(days=180))
        if not c["valid"]:
            notes.append("CDD reason outside art. 12: the contract should be a CDI.")
    done = len(need) - sum(1 for d in need if reg.docs.get(d, {}).get("status") != "ok")
    return {"complete": not bounce, "documents_ok": done, "documents_needed": len(need),
            "bounce": bounce, "notes": notes,
            "sensitive": reg.role_key in seed_company.SENSITIVE_ROLES}


def plan(reg: Registration) -> list:
    """Everything that launches on approval, with an owner and a date."""
    s = reg.start
    d = lambda n: (s + _dt.timedelta(days=n)).isoformat()  # noqa: E731
    trial_months = _WT["trial_max_months"]
    trial_end = s + _dt.timedelta(days=int(trial_months * 30.44))
    tasks = [
        (f"{reg.contract} contract generated, sent for e-signature (fallback: print and scan, law 26-02)", "HR", d(-5)),
        ("CNAS affiliation draft, to submit on teledeclaration.cnas.dz", "HR", d(10)),
        ("ANEM hire notice, draft", "HR", d(3)),
        ("Payroll: salary, allowances, IRG status, RIB (waits for the first payroll)", "Payroll", d(-2)),
        ("Schedule for the first two weeks, with a buddy on the same shifts", "Planning", d(-3)),
        ("Badge and site access", "Security", d(-1)),
        ("Uniform and protective equipment", "Logistics", d(-1)),
        ("Accounts: email and app", "IT", d(-1)),
        ("Welcome message: date, address, contact, what to bring", "Employee desk", d(-2)),
        ("Manager preparation (3 days before)", "Manager", d(-3)),
        ("Day 1: welcome, safety briefing, buddy", "Manager", d(0)),
        ("Week 1: safety, data protection, conduct and anti-harassment training, with quiz", "HR", d(5)),
    ]
    tasks += [(f"Day {n} check-in in the employee desk", "Employee desk", d(n)) for n in _C["checkins_days"]]
    tasks.append((f"End of trial on {trial_end:%d/%m/%Y}: confirm, extend or end "
                  f"(art. 18, 20), reminder {_C['trial_reminder_days_before']} days before", "Manager",
                  (trial_end - _dt.timedelta(days=_C["trial_reminder_days_before"])).isoformat()))
    if reg.role_key in seed_company.SENSITIVE_ROLES:
        tasks += [("Reference checks: emails drafted, sent by HR", "HR", d(-7)),
                  ("Background check: result, date, by whom (never the document)", "Security", d(-3)),
                  ("Access rights review: buildings and systems", "Security", d(-1))]
    return [{"task": t, "owner": o, "due": due} for t, o, due in tasks]


def offboarding(emp, last_day: _dt.date) -> list:
    """The mirror journey for a departure."""
    return [{"task": t, "owner": o, "due": last_day.isoformat()} for t, o in (
        ("Certificate of employment (certificat de travail)", "HR"),
        ("Final settlement, remaining leave paid", "Payroll"),
        ("Badge and equipment returned", "Logistics"),
        ("Accounts closed and access revoked", "IT"),
        ("CNAS and ANEM updates", "HR"),
        ("Exit survey", "Employee desk"),
    )]


def approval_card(reg: Registration, v: dict) -> dict:
    notes = " ".join(v["notes"]) if v["notes"] else "No remarks."
    return {
        "agent": "Intégration",
        "title": (f"{reg.candidate}'s file is complete and verified: "
                  f"{v['documents_ok']}/{v['documents_needed']} documents"),
        "detail": notes + (" Sensitive role: references, background check and access "
                           "review added automatically." if v["sensitive"] else ""),
        "law": "CNAS affiliation within 10 days · Law 90-11 art. 12, 18, 28 · law 25-11",
        "decision": f"Hire approved: {len(plan(reg))} tasks launched in parallel.",
    }


def launch(con, reg: Registration, emp_id: str) -> int:
    """After the "Approve hire" click: the tasks go into the database."""
    from . import db
    for t in plan(reg):
        con.execute("INSERT INTO onboarding_tasks (employee_id, task, owner, due, status) "
                    "VALUES (?,?,?,?, 'to do')", (emp_id, t["task"], t["owner"], t["due"]))
    for code, d in reg.docs.items():
        con.execute("INSERT INTO documents (employee_id, kind, status, created) VALUES (?,?,?,?)",
                    (emp_id, code, "verified" if d["status"] == "ok" else d["status"],
                     _dt.date.today().isoformat()))
    con.commit()
    db.log(con, "hr", "hr", "hire_approved", emp_id, reg.candidate)
    return len(plan(reg))


if __name__ == "__main__":
    today = _dt.date(2026, 10, 28)
    reg = Registration("Amina Belkacem", "ramp_agent", "ALG", today + _dt.timedelta(days=12),
                       gender="F")
    simulate_upload(reg, birth=_dt.date(2000, 3, 4), id_expiry=today + _dt.timedelta(days=120))
    v = verify(reg, today)
    assert not v["complete"] and any("blurry" in b for b in v["bounce"])
    reg.docs["diplome"]["status"] = "ok"          # the new hire retakes the photo
    v = verify(reg, today)
    assert v["complete"] and v["sensitive"] and any("expires" in n for n in v["notes"])
    tasks = plan(reg)
    assert any("Background check" in t["task"] for t in tasks) and any("Day 90" in t["task"] for t in tasks)
    assert "service_national" not in checklist("ramp_agent", "F")
    young = Registration("Test", "sorter", "ALG", today, gender="M")
    simulate_upload(young, birth=_dt.date(2008, 1, 1), id_expiry=today.replace(year=2030), blurry=())
    assert any("art. 28" in n for n in verify(young, today)["notes"])
    print(f"  onboarding: {len(tasks)} tasks for a sensitive role: ok")
