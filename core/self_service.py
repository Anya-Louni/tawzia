"""
core/self_service.py
--------------------
The employee desk: the employee asks, the platform answers, HR is no longer
interrupted.

The problem it solves
=====================
A large part of an Algerian HR team's day goes to repetitive requests: a work
certificate for a visa, loan or housing file, the leave balance, a payslip copy,
a leave request. Each is simple, each interrupts.

Here the employee writes the way they speak (English, French, Arabic, or Darija
in Latin letters). The message is classified, then:
  - what is a fact from the file (balance, payslip) is answered at once;
  - what needs a signature (certificate) is written and goes to the decision
    inbox, where HR signs it;
  - what needs a decision (leave, short absence) goes through the same legal and
    load check as the rest of the platform.

Classification is rule-based: deterministic, offline, explainable. A message
that matches nothing goes to a human, never guessed.

The work certificate itself stays French and Arabic: that is the document an
Algerian bank, landlord or consulate accepts.
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from typing import Optional

from . import attendance, labour_dz, payroll_dz

# Keywords per intent: English, French, Darija in Latin letters, Arabic.
INTENTS = {
    "attestation": ("attestation", "certificat de travail", "chahada", "chhada",
                    "شهادة", "visa", "dossier de credit", "logement",
                    "certificate", "employment letter", "proof of employment"),
    "bulletin": ("bulletin", "fiche de paie", "fiche de paye", "salaire", "paie",
                 "net", "راتب", "الأجر", "kachf", "chehria", "chahria",
                 "payslip", "pay slip", "salary", "my pay"),
    "solde": ("solde", "combien de jours", "jours restants", "il me reste",
              "rassid", "رصيد", "chhal men youm", "chhal bqali",
              "balance", "how many days", "days left"),
    "sortie": ("sortie", "sortir", "rendez-vous", "rdv", "quelques heures",
               "خروج", "nkhroj", "appointment", "a few hours", "leave early"),
    "conge": ("conge", "vacances", "عطلة", "kongé", "konji", "repos",
              "mariage", "naissance", "deces", "holiday", "vacation", "day off",
              "time off", "annual leave", "take leave", "wedding", "funeral"),
}

LABELS = {
    "attestation": "Work certificate",
    "bulletin": "Payslip copy",
    "solde": "Leave balance",
    "sortie": "Short absence request",
    "conge": "Leave request",
    "autre": "Question for HR",
}

_MONTHS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
           "juin": 6, "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10,
           "novembre": 11, "decembre": 12,
           "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
           "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
           "november": 11, "december": 12}


def _plain(text: str) -> str:
    """Lowercase without Latin accents; Arabic is left as is."""
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def classify(text: str) -> str:
    """The message's intent, or "autre". The first match wins."""
    t = _plain(text)
    # Balance before leave: "how many leave days do I have" is a question.
    for intent in ("attestation", "solde", "bulletin", "sortie", "conge"):
        if any(_plain(k) in t for k in INTENTS[intent]):
            return intent
    return "autre"


def parse_dates(text: str, as_of: _dt.date) -> Optional[tuple]:
    """
    "from 3 to 10 December", "du 3 au 10 novembre", "03/11 to 10/11", "12 December".

    Returns (start, end), or None. A date already past this year moves to next
    year: nobody asks for leave in the past.
    """
    t = _plain(text)

    def _fix(d: _dt.date) -> _dt.date:
        return d.replace(year=d.year + 1) if d < as_of else d

    m = re.search(r"(\d{1,2})/(\d{1,2})\D+(\d{1,2})/(\d{1,2})", t)
    if m:
        d1, m1, d2, m2 = map(int, m.groups())
        try:
            a = _fix(_dt.date(as_of.year, m1, d1))
            b = _dt.date(a.year, m2, d2)
            return a, (b if b >= a else b.replace(year=b.year + 1))
        except ValueError:
            return None
    month_re = "|".join(sorted(_MONTHS, key=len, reverse=True))
    m = re.search(rf"(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:({month_re})\s*)?"
                  rf"(?:au|a|to|until|jusqu'au|-|l|hta|ila)\s*(\d{{1,2}})(?:st|nd|rd|th)?\s*({month_re})", t)
    if m:
        d1, mo1, d2, mo2 = m.groups()
        try:
            a = _fix(_dt.date(as_of.year, _MONTHS[mo1 or mo2], int(d1)))
            b = _dt.date(a.year, _MONTHS[mo2], int(d2))
            return a, (b if b >= a else b.replace(year=b.year + 1))
        except ValueError:
            return None
    m = re.search(rf"(\d{{1,2}})(?:st|nd|rd|th)?\s*({month_re})", t)
    if m:
        try:
            d = _fix(_dt.date(as_of.year, _MONTHS[m.group(2)], int(m.group(1))))
            return d, d
        except ValueError:
            return None
    return None


def attestation_text(emp, company: str, signatory: str, as_of: _dt.date,
                     city: str = "Alger") -> str:
    """The work certificate, in French then Arabic, filled from the file."""
    role = labour_dz.LABEL_FR.get(emp.role_key, labour_dz.ROLES[emp.role_key].label)
    contract_ar = {"CDI": "عقد عمل غير محدد المدة",
                   "CDD": "عقد عمل محدد المدة"}.get(emp.contract, emp.contract)
    contract = {"CDI": "contrat à durée indéterminée (CDI)",
                "CDD": "contrat à durée déterminée (CDD)"}.get(emp.contract, emp.contract)
    return (
        f"{company}\n\n"
        f"ATTESTATION DE TRAVAIL\n\n"
        f"Je soussigné(e), {signatory}, agissant pour le compte de {company}, "
        f"atteste que {emp.name} est employé(e) au sein de notre entreprise "
        f"depuis le {emp.hire_date:%d/%m/%Y}, en qualité de {role.lower()}, "
        f"sous {contract}, et fait toujours partie de nos effectifs à ce jour.\n\n"
        f"La présente attestation est délivrée à l'intéressé(e), à sa demande, "
        f"pour servir et valoir ce que de droit.\n\n"
        f"Fait à {city}, le {as_of:%d/%m/%Y}.\n\n"
        f"{signatory}\nSignature et cachet\n\n"
        f"------------------------------------------------------------\n\n"
        f"شهادة عمل\n\n"
        f"أنا الموقع(ة) أدناه، {signatory}، بصفتي ممثلا عن {company}، أشهد أن "
        f"السيد(ة) {emp.name} يعمل(تعمل) لدى مؤسستنا منذ {emp.hire_date:%d/%m/%Y} "
        f"بصفة ({role})، بموجب {contract_ar}، ولا يزال(تزال) ضمن مستخدمينا "
        f"إلى غاية هذا التاريخ.\n\n"
        f"سلمت هذه الشهادة للمعني(ة) بطلب منه(ا) للإدلاء بها في حدود ما يسمح به القانون.\n\n"
        f"حرر بـ {city} في {as_of:%d/%m/%Y}.\n\n"
        f"الإمضاء والختم"
    )


def answer(text: str, emp, *, as_of: Optional[_dt.date] = None, forecast=None,
           company: str = "Your company", signatory: str = "The HR manager",
           ticket_id: str = "t") -> dict:
    """
    Answer an employee message.

    Returns {"intent", "reply", "ticket" (or None), "request" (or None),
    "document" (or None)}. The ticket goes to the decision inbox.
    """
    as_of = as_of or _dt.date.today()
    intent = classify(text)
    out = {"intent": intent, "reply": "", "ticket": None, "request": None,
           "document": None}
    first = emp.name.split()[0]

    if intent == "solde":
        bal = emp.accrued_leave(as_of)
        out["reply"] = (
            f"{first}, you have **{bal:.1f} days** of annual leave left on "
            f"{as_of:%d/%m/%Y} (annual entitlement: {emp.annual_entitlement():.0f} days, "
            f"accrued at 2.5 days per month worked)."
        )
        return out

    if intent == "bulletin":
        p = payroll_dz.payslip(emp.monthly_gross(), emp.role_key,
                               emp.dependants, emp.spouse)
        out["reply"] = (
            f"Your payslip this month: gross **{p.gross:,.0f} DZD**, CNAS 9% "
            f"{p.cnas_employee:,.0f} DZD, IRG {p.irg:,.0f} DZD, "
            f"**net pay {p.net:,.0f} DZD**. The signed PDF follows the payroll close."
        )
        return out

    if intent == "attestation":
        doc = attestation_text(emp, company, signatory, as_of)
        out["document"] = doc
        out["reply"] = ("Your work certificate is written (French and Arabic). It "
                        "goes for signature and you will receive it today.")
        out["ticket"] = {"id": ticket_id, "label": LABELS["attestation"],
                         "emp_name": emp.name, "text": text,
                         "needs_signature": True, "document": doc}
        return out

    if intent in ("conge", "sortie"):
        dates = parse_dates(text, as_of)
        if dates is None:
            out["reply"] = ("Which dates? Write for example \"from 3 to 10 December\" "
                            "or \"12 December\".")
            return out
        start, end = dates
        family_words = ("mariage", "naissance", "deces", "wedding", "funeral", "birth")
        kind = "sortie" if intent == "sortie" else (
            "family" if any(w in _plain(text) for w in family_words) else "annual")
        hrs = re.search(r"(\d{1,2})\s*h", _plain(text))
        req = attendance.Request(
            req_id=f"G-{ticket_id}", emp_id=emp.emp_id, emp_name=emp.name,
            role_key=emp.role_key, kind=kind, start=start, end=end,
            hours=float(hrs.group(1)) if (kind == "sortie" and hrs) else (2.0 if kind == "sortie" else None),
            reason=text.strip()[:80], created=as_of,
        )
        d = attendance.decide_request(req, emp, as_of=as_of, forecast=forecast)
        verdict = {
            "approve": "compliant, and will be approved without waiting",
            "record": "recorded",
            "approve_with_cover": "acceptable; cover is being found for this peak day",
            "approve_with_note": "acceptable, with a note your manager will see",
            "reject": "hard to grant as it stands",
        }.get(d["recommend"], "sent to your manager")
        why = " ".join((d["warnings"] or d["reasons"])[:1])
        out["reply"] = f"Request received: {req.kind_label.lower()} {_span(start, end)}. It is {verdict}. {why}"
        out["request"] = req
        return out

    out["reply"] = ("I do not have a reliable answer to that. It has gone to HR, "
                    "who will reply today.")
    out["ticket"] = {"id": ticket_id, "label": LABELS["autre"], "emp_name": emp.name,
                     "text": text, "needs_signature": True, "auto": False,
                     "decision": "Reply sent to the employee."}
    return out


def _span(a: _dt.date, b: _dt.date) -> str:
    return f"on {a:%d/%m}" if a == b else f"from {a:%d/%m} to {b:%d/%m}"


if __name__ == "__main__":
    from . import hr
    today = _dt.date(2026, 10, 28)
    emp = hr.Employee("E1", "Amine Benali", "sorter", "Alger",
                      today - _dt.timedelta(days=900))
    cases = {
        "Bonjour, j'ai besoin d'une attestation de travail pour mon visa": "attestation",
        "nheb attestation de travail lel bank": "attestation",
        "I need a work certificate for my bank": "attestation",
        "chhal bqali men youm conge ?": "solde",
        "How many days of leave do I have left?": "solde",
        "Je voudrais ma fiche de paie": "bulletin",
        "Can I get my payslip?": "bulletin",
        "أريد شهادة عمل": "attestation",
        "Je veux prendre un congé du 3 au 10 décembre": "conge",
        "I'd like to take time off from 3 to 10 December": "conge",
        "Demande de sortie le 12 novembre pour un rendez-vous, 2h": "sortie",
        "What is the remote work policy?": "autre",
    }
    for msg, want in cases.items():
        got = classify(msg)
        assert got == want, (msg, got, want)
    assert parse_dates("du 3 au 10 décembre", today) == (_dt.date(2026, 12, 3), _dt.date(2026, 12, 10))
    assert parse_dates("from 3 to 10 December", today) == (_dt.date(2026, 12, 3), _dt.date(2026, 12, 10))
    assert parse_dates("03/01 au 05/01", today) == (_dt.date(2027, 1, 3), _dt.date(2027, 1, 5))
    assert parse_dates("le 12 novembre", today) == (_dt.date(2026, 11, 12),) * 2
    r = answer("I'd like to take time off from 3 to 10 December", emp, as_of=today)
    assert r["request"] is not None and r["request"].kind == "annual"
    r = answer("work certificate please", emp, as_of=today, company="SARL Test")
    assert "SARL Test" in r["document"] and "agent de tri" in r["document"].lower()
    assert r["ticket"]["needs_signature"]
    print("  employee desk: ok")
