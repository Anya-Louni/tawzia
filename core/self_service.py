"""
core/self_service.py
--------------------
Le guichet salarié : le salarié demande, la plateforme répond, le service RH
n'est plus interrompu.

Le problème réglé
=================
Une grande part de la journée d'un service RH algérien part en demandes
répétitives : une attestation de travail pour un dossier de visa, de crédit ou
de logement, le solde de congés, une copie du bulletin, une demande de congé.
Chacune est simple, chacune interrompt.

Ici le salarié écrit comme il parle (français, arabe, ou darija en lettres
latines). Le message est classé, puis :
  - ce qui est un fait du dossier (solde, bulletin) reçoit sa réponse aussitôt ;
  - ce qui demande une signature (attestation) est rédigé et part dans la boîte
    de l'autopilote, signé seul si la politique le permet ;
  - ce qui demande une décision (congé, sortie) passe par le même contrôle légal
    et de charge que le reste de la plateforme.

La classification est par règles : déterministe, hors ligne, explicable. Un
message qui ne correspond à rien est transmis à un humain, jamais deviné.
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from typing import Optional

from . import attendance, labour_dz, payroll_dz

# Mots-clés par intention : français, darija en lettres latines, arabe.
INTENTS = {
    "attestation": ("attestation", "certificat de travail", "chahada", "chhada",
                    "شهادة", "visa", "dossier de credit", "logement"),
    "bulletin": ("bulletin", "fiche de paie", "fiche de paye", "salaire", "paie",
                 "net", "راتب", "الأجر", "kachf", "chehria", "chahria"),
    "solde": ("solde", "combien de jours", "jours restants", "il me reste",
              "rassid", "رصيد", "chhal men youm", "chhal bqali"),
    "sortie": ("sortie", "sortir", "rendez-vous", "rdv", "quelques heures",
               "خروج", "nkhroj"),
    "conge": ("conge", "vacances", "عطلة", "عطلة", "kongé", "konji", "repos",
              "mariage", "naissance", "deces"),
}

LABELS = {
    "attestation": "Attestation de travail",
    "bulletin": "Copie du bulletin de paie",
    "solde": "Solde de congés",
    "sortie": "Demande de sortie",
    "conge": "Demande de congé",
    "autre": "Question au service RH",
}

_MONTHS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
           "juin": 6, "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10,
           "novembre": 11, "decembre": 12}


def _plain(text: str) -> str:
    """Minuscules sans accents latins ; l'arabe est laissé tel quel."""
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def classify(text: str) -> str:
    """L'intention du message, ou « autre ». La première qui correspond gagne."""
    t = _plain(text)
    # « solde » avant « congé » : « combien de jours de congé » est une question.
    for intent in ("attestation", "solde", "bulletin", "sortie", "conge"):
        if any(_plain(k) in t for k in INTENTS[intent]):
            return intent
    return "autre"


def parse_dates(text: str, as_of: _dt.date) -> Optional[tuple]:
    """
    « du 3 au 10 novembre », « 03/11 au 10/11 », « le 12 décembre ».

    Retourne (début, fin), ou None. Une date déjà passée cette année est
    reportée à l'année suivante : personne ne demande un congé dans le passé.
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
    month_re = "|".join(_MONTHS)
    m = re.search(rf"(\d{{1,2}})\s*(?:({month_re})\s*)?(?:au|a|jusqu'au|-|l|hta|ila)\s*(\d{{1,2}})\s*({month_re})", t)
    if m:
        d1, mo1, d2, mo2 = m.groups()
        try:
            a = _fix(_dt.date(as_of.year, _MONTHS[mo1 or mo2], int(d1)))
            b = _dt.date(a.year, _MONTHS[mo2], int(d2))
            return a, (b if b >= a else b.replace(year=b.year + 1))
        except ValueError:
            return None
    m = re.search(rf"(\d{{1,2}})\s*({month_re})", t)
    if m:
        try:
            d = _fix(_dt.date(as_of.year, _MONTHS[m.group(2)], int(m.group(1))))
            return d, d
        except ValueError:
            return None
    return None


def attestation_text(emp, company: str, signatory: str, as_of: _dt.date,
                     city: str = "Alger") -> str:
    """L'attestation de travail, en français puis en arabe, remplie sur le dossier."""
    role = labour_dz.ROLES[emp.role_key].label
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
           company: str = "Votre entreprise", signatory: str = "Le responsable RH",
           ticket_id: str = "t") -> dict:
    """
    Répondre à un message de salarié.

    Retourne {"intent", "reply", "ticket" (ou None), "request" (ou None),
    "document" (ou None)}. Le ticket part dans la boîte de l'autopilote.
    """
    as_of = as_of or _dt.date.today()
    intent = classify(text)
    out = {"intent": intent, "reply": "", "ticket": None, "request": None,
           "document": None}
    first = emp.name.split()[0]

    if intent == "solde":
        bal = emp.accrued_leave(as_of)
        out["reply"] = (
            f"{first}, il vous reste **{bal:.1f} jours** de congé annuel au "
            f"{as_of:%d/%m/%Y} (droit annuel : {emp.annual_entitlement():.0f} jours, "
            f"acquis à raison de 2,5 jours par mois travaillé)."
        )
        return out

    if intent == "bulletin":
        p = payroll_dz.payslip(emp.monthly_gross(), emp.role_key,
                               emp.dependants, emp.spouse)
        out["reply"] = (
            f"Votre bulletin du mois : brut **{p.gross:,.0f} DZD**, CNAS 9 % "
            f"{p.cnas_employee:,.0f} DZD, IRG {p.irg:,.0f} DZD, "
            f"**net à payer {p.net:,.0f} DZD**. Le PDF signé suit la clôture de paie."
        ).replace(",", " ")
        return out

    if intent == "attestation":
        doc = attestation_text(emp, company, signatory, as_of)
        out["document"] = doc
        out["reply"] = ("Votre attestation de travail est rédigée. Elle part à la "
                        "signature et vous sera remise aujourd'hui.")
        out["ticket"] = {"id": ticket_id, "label": LABELS["attestation"],
                         "emp_name": emp.name, "text": text,
                         "needs_signature": True, "document": doc}
        return out

    if intent in ("conge", "sortie"):
        dates = parse_dates(text, as_of)
        if dates is None:
            out["reply"] = ("Pour quelles dates ? Écrivez par exemple « du 3 au "
                            "10 décembre » ou « le 12 décembre ».")
            return out
        start, end = dates
        kind = "sortie" if intent == "sortie" else (
            "family" if any(w in _plain(text) for w in ("mariage", "naissance", "deces"))
            else "annual")
        hrs = re.search(r"(\d{1,2})\s*h", _plain(text))
        req = attendance.Request(
            req_id=f"G-{ticket_id}", emp_id=emp.emp_id, emp_name=emp.name,
            role_key=emp.role_key, kind=kind, start=start, end=end,
            hours=float(hrs.group(1)) if (kind == "sortie" and hrs) else (2.0 if kind == "sortie" else None),
            reason=text.strip()[:80], created=as_of,
        )
        d = attendance.decide_request(req, emp, as_of=as_of, forecast=forecast)
        verdict = {
            "approve": "conforme, elle sera validée sans attente",
            "record": "enregistrée",
            "approve_with_cover": "recevable, un remplaçant est cherché pour ce jour de pic",
            "approve_with_note": "recevable, avec une réserve que votre responsable verra",
            "reject": "difficile à accorder telle quelle",
        }.get(d["recommend"], "transmise à votre responsable")
        why = " ".join((d["warnings"] or d["reasons"])[:1])
        out["reply"] = f"Demande reçue : {req.kind_label.lower()} {_span(start, end)}. Elle est {verdict}. {why}"
        out["request"] = req
        return out

    out["reply"] = ("Je n'ai pas de réponse sûre à cette question. Elle est "
                    "transmise au service RH, qui vous répond dans la journée.")
    out["ticket"] = {"id": ticket_id, "label": LABELS["autre"], "emp_name": emp.name,
                     "text": text, "needs_signature": True, "auto": False,
                     "decision": "Réponse envoyée au salarié."}
    return out


def _span(a: _dt.date, b: _dt.date) -> str:
    return f"le {a:%d/%m}" if a == b else f"du {a:%d/%m} au {b:%d/%m}"


if __name__ == "__main__":
    from . import hr
    today = _dt.date(2026, 10, 28)
    emp = hr.Employee("E1", "Amine Benali", "sorter", "Alger",
                      today - _dt.timedelta(days=900))
    cases = {
        "Bonjour, j'ai besoin d'une attestation de travail pour mon visa": "attestation",
        "chhal bqali men youm conge ?": "solde",
        "Combien de jours de congé il me reste ?": "solde",
        "Je voudrais ma fiche de paie": "bulletin",
        "أريد شهادة عمل": "attestation",
        "Je veux prendre un congé du 3 au 10 décembre": "conge",
        "Demande de sortie le 12 novembre pour un rendez-vous, 2h": "sortie",
        "Quelle est la politique télétravail ?": "autre",
    }
    for msg, want in cases.items():
        got = classify(msg)
        assert got == want, (msg, got, want)
    assert parse_dates("du 3 au 10 décembre", today) == (_dt.date(2026, 12, 3), _dt.date(2026, 12, 10))
    assert parse_dates("03/01 au 05/01", today) == (_dt.date(2027, 1, 3), _dt.date(2027, 1, 5))
    assert parse_dates("le 12 novembre", today) == (_dt.date(2026, 11, 12),) * 2
    r = answer("Je veux prendre un congé du 3 au 10 décembre", emp, as_of=today)
    assert r["request"] is not None and r["request"].kind == "annual"
    r = answer("attestation de travail svp", emp, as_of=today, company="SARL Test")
    assert "SARL Test" in r["document"] and r["ticket"]["needs_signature"]
    print("  guichet salarié : ok")
