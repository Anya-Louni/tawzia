"""
core/cv_screen.py
-----------------
The CV reader, built for the Algerian CV.

An Algerian CV is not a US resume. It is written in French, and it carries
fields a foreign screener ignores or mis-reads:

  * **Formation** in the Algerian system - Baccalaureat (with a serie),
    Licence / Master (LMD), Ingeniorat d'etat, BTS, DEUA, CAP - from Algerian
    institutions (USTHB, ENP, universities, CFPA centres).
  * **Service national** - "degage" / "exempte" / "en cours" - a real
    eligibility gate for many roles and male candidates.
  * **Langues** - Arabe, Francais, Anglais, and often Tamazight, each with a
    level.
  * **Wilaya** of residence and **mobilite** - decisive for shift work with an
    early start.
  * **Permis de conduire** - required for courier/driver roles.

How it scores
=============
Two-stage so the result is both smart and defensible:

  1. **Extract** the structured fields from the CV text. If an AI key is set,
     the LLM (core/ai.py) does the messy French parsing; otherwise a rule-based
     extractor handles it. Either way the output is the same structured record.
  2. **Score** those fields against the job with a transparent, deterministic
     rubric - education, experience, languages, skills, licence, service
     national, mobility. The AI never invents the score; it only reads the CV.
     So two runs give the same number, and you can see exactly why.

Sample CVs here are synthetic and clearly Algerian in format, for the demo.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from . import ai

# Education levels, ranked, with the French terms an Algerian CV uses.
EDUCATION_RANK = {
    "sans": 0, "cap": 1, "cfpa": 1, "bac": 2, "baccalaureat": 2,
    "bts": 3, "deua": 3, "ts": 3, "technicien": 3,
    "licence": 4, "dut": 3, "master": 5, "ingeniorat": 5, "ingenieur": 5,
    "magister": 6, "doctorat": 7,
}

LANGUAGES = ["arabe", "francais", "anglais", "tamazight"]


@dataclass
class Job:
    """What a role needs from a candidate."""
    role_key: str
    title: str
    min_education: str = "bac"          # key in EDUCATION_RANK
    min_experience_years: float = 0.0
    required_languages: tuple = ("arabe", "francais")
    skills: tuple = ()
    needs_driving_licence: bool = False
    needs_service_national_cleared: bool = True
    weight: dict = field(default_factory=lambda: {
        "education": 0.20, "experience": 0.28, "languages": 0.16,
        "skills": 0.20, "licence": 0.08, "service_national": 0.08,
    })


JOBS = {
    "sorter": Job("sorter", "Agent de tri / magasinier", min_education="bac",
                  min_experience_years=1, skills=("logistique", "manutention", "scan", "stock")),
    "courier": Job("courier", "Chauffeur-livreur", min_education="bac",
                   min_experience_years=1, needs_driving_licence=True,
                   skills=("livraison", "conduite", "relation client")),
    "checkin_agent": Job("checkin_agent", "Agent d'escale / check-in", min_education="licence",
                         min_experience_years=1, required_languages=("arabe", "francais", "anglais"),
                         skills=("accueil", "aeroport", "billetterie", "relation client")),
    "front_desk": Job("front_desk", "Receptionniste", min_education="licence",
                      required_languages=("arabe", "francais", "anglais"),
                      skills=("accueil", "reservation", "hotellerie")),
}


@dataclass
class Candidate:
    name: str
    wilaya: str
    education: str            # normalised key
    education_raw: str
    establishment: str
    experience_years: float
    positions: list
    skills: list
    languages: list          # normalised keys present
    driving_licence: bool
    service_national: str     # "degage" | "exempte" | "en cours" | "n/a" | "inconnu"
    mobility: str


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _normalise(s: str) -> str:
    s = s.lower()
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("â", "a"),
                 ("î", "i"), ("ï", "i"), ("ô", "o"), ("û", "u"), ("ç", "c")):
        s = s.replace(a, b)
    return s


def _best_education(text_norm: str) -> tuple:
    found = ("sans", "sans", 0)
    for term, rank in EDUCATION_RANK.items():
        if term in text_norm and rank >= found[2]:
            found = (term, term, rank)
    return found[0], found[2]


def _rule_extract(cv_text: str) -> Candidate:
    norm = _normalise(cv_text)
    edu_key, _ = _best_education(norm)

    # experience years: look for "X ans"
    yrs = 0.0
    for m in re.findall(r"(\d+)\s*an", norm):
        yrs = max(yrs, float(m))

    langs = [l for l in LANGUAGES if l in norm]
    licence = bool(re.search(r"permis", norm))
    if "degage" in norm:
        sn = "degage"
    elif "exempt" in norm:
        sn = "exempte"
    elif "en cours" in norm and "service" in norm:
        sn = "en cours"
    else:
        sn = "inconnu"

    wilaya = "-"
    for w in ("alger", "oran", "constantine", "annaba", "blida", "setif", "batna",
              "ouargla", "bejaia", "tizi", "tlemcen", "ghardaia"):
        if w in norm:
            wilaya = w.title()
            break

    name = cv_text.strip().splitlines()[0][:40] if cv_text.strip() else "Candidat"
    return Candidate(
        name=name, wilaya=wilaya, education=edu_key, education_raw=edu_key,
        establishment="-", experience_years=yrs, positions=[],
        skills=[s for s in ("logistique", "manutention", "livraison", "conduite",
                            "accueil", "reservation", "scan", "stock", "aeroport",
                            "relation client", "billetterie") if s in norm],
        languages=langs, driving_licence=licence, service_national=sn,
        mobility="mobile" if "mobil" in norm or "disponible" in norm else "-",
    )


_AI_EXTRACT_SYSTEM = (
    "You extract structured data from an Algerian CV written in French. Return "
    "ONLY a JSON object, no prose, with keys: name, wilaya, education "
    "(one of: sans, cap, bac, bts, deua, licence, master, ingeniorat, magister, "
    "doctorat), establishment, experience_years (number), positions (list of "
    "strings), skills (list of lowercased strings), languages (subset of "
    "[arabe, francais, anglais, tamazight]), driving_licence (boolean), "
    "service_national (one of: degage, exempte, en cours, n/a, inconnu), "
    "mobility (short string). Infer education from Algerian diplomas. If a field "
    "is absent use a sensible empty value."
)


def _parse_json(text: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _ai_extract(cv_text: str) -> Optional[Candidate]:
    res = ai.chat(_AI_EXTRACT_SYSTEM, cv_text, max_tokens=600, temperature=0.0)
    if not res.ok:
        return None
    data = _parse_json(res.text)
    if not data:
        return None
    edu = _normalise(str(data.get("education", "sans")))
    edu = edu if edu in EDUCATION_RANK else "sans"
    langs = [_normalise(l) for l in data.get("languages", []) if _normalise(l) in LANGUAGES]
    return Candidate(
        name=str(data.get("name", "Candidat"))[:60],
        wilaya=str(data.get("wilaya", "-")),
        education=edu, education_raw=str(data.get("education", "")),
        establishment=str(data.get("establishment", "-")),
        experience_years=float(data.get("experience_years", 0) or 0),
        positions=list(data.get("positions", []))[:6],
        skills=[_normalise(s) for s in data.get("skills", [])][:12],
        languages=langs,
        driving_licence=bool(data.get("driving_licence", False)),
        service_national=_normalise(str(data.get("service_national", "inconnu"))),
        mobility=str(data.get("mobility", "-")),
    )


def extract(cv_text: str, use_ai: bool = True) -> tuple:
    """Extract a Candidate. Returns (candidate, method_used)."""
    if use_ai and any(ai.providers_available().values()):
        c = _ai_extract(cv_text)
        if c is not None:
            return c, "ai"
    return _rule_extract(cv_text), "rules"


# ---------------------------------------------------------------------------
# Scoring (deterministic)
# ---------------------------------------------------------------------------

@dataclass
class Screening:
    candidate: Candidate
    job: Job
    score: int
    band: str                 # strong | possible | weak
    pluses: list
    flags: list
    method: str


def score(candidate: Candidate, job: Job, method: str = "rules") -> Screening:
    w = job.weight
    pluses, flags = [], []
    parts = {}

    # Education
    need = EDUCATION_RANK.get(job.min_education, 2)
    have = EDUCATION_RANK.get(candidate.education, 0)
    parts["education"] = 1.0 if have >= need else max(0.0, have / max(need, 1) * 0.7)
    if have >= need:
        pluses.append(f"Formation OK ({candidate.education})")
    else:
        flags.append(f"Formation below the {job.min_education} required")

    # Experience
    if job.min_experience_years <= 0:
        parts["experience"] = 1.0
    else:
        parts["experience"] = min(candidate.experience_years / job.min_experience_years, 1.0)
        if candidate.experience_years >= job.min_experience_years:
            pluses.append(f"{candidate.experience_years:.0f} yrs experience")
        else:
            flags.append(f"Only {candidate.experience_years:.0f} yrs (needs {job.min_experience_years:.0f})")

    # Languages
    req = set(job.required_languages)
    have_lang = set(candidate.languages)
    missing = req - have_lang
    parts["languages"] = 1.0 - (len(missing) / max(len(req), 1))
    if not missing:
        pluses.append("All required languages")
    else:
        flags.append("Missing language(s): " + ", ".join(sorted(missing)))

    # Skills
    if job.skills:
        overlap = len(set(candidate.skills) & set(job.skills))
        parts["skills"] = min(overlap / len(job.skills), 1.0)
        if overlap:
            pluses.append(f"{overlap}/{len(job.skills)} target skills")
    else:
        parts["skills"] = 1.0

    # Driving licence
    if job.needs_driving_licence:
        parts["licence"] = 1.0 if candidate.driving_licence else 0.0
        (pluses if candidate.driving_licence else flags).append(
            "Permis de conduire" + ("" if candidate.driving_licence else " missing (required)"))
    else:
        parts["licence"] = 1.0

    # Service national
    if job.needs_service_national_cleared:
        cleared = candidate.service_national in ("degage", "exempte", "n/a")
        parts["service_national"] = 1.0 if cleared else (0.4 if candidate.service_national == "en cours" else 0.5)
        if cleared:
            pluses.append(f"Service national: {candidate.service_national}")
        elif candidate.service_national == "en cours":
            flags.append("Service national en cours")
        else:
            flags.append("Service national status unclear")
    else:
        parts["service_national"] = 1.0

    total = sum(parts[k] * w.get(k, 0) for k in parts)
    pct = int(round(total / sum(w.values()) * 100))
    band = "strong" if pct >= 70 else ("possible" if pct >= 45 else "weak")
    return Screening(candidate=candidate, job=job, score=pct, band=band,
                     pluses=pluses, flags=flags, method=method)


def screen(cv_text: str, job: Job, use_ai: bool = True) -> Screening:
    cand, method = extract(cv_text, use_ai=use_ai)
    return score(cand, job, method)


def rank(cvs: dict, job: Job, use_ai: bool = True) -> list:
    """Screen and rank a batch of CVs. `cvs` maps a label -> cv text."""
    results = [screen(text, job, use_ai=use_ai) for text in cvs.values()]
    return sorted(results, key=lambda s: s.score, reverse=True)


# ---------------------------------------------------------------------------
# Sample Algerian CVs (synthetic, French)
# ---------------------------------------------------------------------------

SAMPLE_CVS = {
    "Yacine Meziane": """Yacine Meziane
Adresse: Bab Ezzouar, Alger  |  Ne le 12/03/1998  |  Celibataire
Service national: degage
Permis de conduire: B

FORMATION
- Licence en Logistique et Transport, USTHB Alger, 2021
- Baccalaureat serie Gestion, 2018

EXPERIENCE PROFESSIONNELLE
- Agent logistique, Yalidine Express (2 ans) - tri, scan, gestion de stock
- Manutentionnaire, entrepot Cevital (1 an)

COMPETENCES: logistique, manutention, scan, gestion de stock, travail en equipe
LANGUES: Arabe (courant), Francais (courant), Anglais (moyen), Tamazight (notions)
DISPONIBILITE: immediate, mobile
""",
    "Sofiane Belkacem": """Sofiane Belkacem
Oran  |  Ne en 2002  |  Service national: en cours
FORMATION
- Baccalaureat serie Sciences, 2020
EXPERIENCE
- Livreur occasionnel (6 mois)
COMPETENCES: livraison, relation client
LANGUES: Arabe, Francais
""",
    "Imene Cherif": """Imene Cherif
Constantine  |  Nee le 05/07/1996
FORMATION
- Master en Management, Universite de Constantine, 2020
- Baccalaureat serie Lettres, 2014
EXPERIENCE PROFESSIONNELLE
- Receptionniste, Hotel Marriott Constantine (3 ans) - accueil, reservation
- Agent d'accueil, agence de voyage (1 an)
COMPETENCES: accueil, reservation, hotellerie, relation client
LANGUES: Arabe (courant), Francais (courant), Anglais (courant)
Service national: n/a  |  Disponible, mobile
""",
    "Karim Saidi": """Karim Saidi
Alger  |  Permis B
FORMATION
- CAP en mecanique, CFPA Rouiba, 2015
EXPERIENCE
- Chauffeur-livreur, ZR Express (4 ans) - livraison, conduite, encaissement
COMPETENCES: conduite, livraison, relation client
LANGUES: Arabe, Francais
Service national: degage  |  Mobile
""",
}


if __name__ == "__main__":
    print("Algerian CV screener - self check\n")
    job = JOBS["sorter"]
    print(f"Job: {job.title} (needs {job.min_education}+, "
          f"{job.min_experience_years:.0f}y, {', '.join(job.required_languages)})\n")
    for s in rank(SAMPLE_CVS, job, use_ai=False):
        c = s.candidate
        print(f"  {s.score:>3}%  {s.band:<9} {c.name[:22]:<22} "
              f"edu={c.education:<10} exp={c.experience_years:.0f}y  "
              f"[{s.method}]")
        if s.flags:
            print(f"        flags: {'; '.join(s.flags[:2])}")
