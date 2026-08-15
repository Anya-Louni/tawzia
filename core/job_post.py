"""
core/job_post.py
----------------
Rédiger une offre d'emploi à partir de ce que le responsable dit, et la caler sur
l'équipe qui existe déjà.

Le problème que ça règle
========================
Un responsable sait ce qu'il cherche mais n'a pas le temps d'écrire une offre
publiable. Résultat : des annonces de trois lignes qui attirent des
candidatures hors sujet, ou des annonces recopiées d'un modèle étranger qui
promettent des conditions que l'entreprise ne pratique pas.

Ici le responsable dicte en une phrase. Le module écrit l'offre, et surtout il la
**confronte à l'effectif réel** : ce que l'entreprise paie déjà pour ce poste, le
type de contrat qu'elle utilise, les compétences que l'équipe possède, et les
personnes en interne qui couvrent déjà le poste. Une offre incohérente avec
l'équipe est un problème de recrutement avant d'être un problème d'écriture.

Partage du travail
==================
**Le moteur détient les faits, la couche langage ne fait que rédiger.** Le
salaire indicatif, le contrat, les horaires, les congés et le week-end sont
calculés ici, à partir du SNMG, du coefficient du poste et du droit algérien,
puis **réécrits par-dessus** ce que le modèle a produit. Le modèle ne peut donc
pas promettre un salaire ou un avantage que l'entreprise ne pratique pas. Sans
clé IA, un gabarit déterministe produit une offre publiable quand même.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from . import ai, cv_screen, hr, labour_dz, skills

# Au-delà de cette durée cumulée, un CDD n'est plus renouvelable.
CDD_MAX_MONTHS = 24

# Écart de salaire au-delà duquel on alerte sur l'équité interne : proposer
# beaucoup plus que ce que gagne l'équipe en place pour le même poste crée un
# problème le jour où l'information circule.
EQUITY_TOLERANCE = 0.40


@dataclass
class PoolFacts:
    """Ce que l'équipe actuelle dit du poste à pourvoir."""
    role_key: str
    role_label: str
    wilaya: str
    headcount_total: int
    headcount_role: int
    cdi_share: float
    avg_tenure_years: float
    gross_monthly: float
    loaded_monthly: float
    leave_days: int
    can_be_temp: bool
    required_skills: dict = field(default_factory=dict)
    internal_ready: list = field(default_factory=list)
    internal_trainable: list = field(default_factory=list)

    @property
    def weekend(self) -> str:
        return "vendredi et samedi"

    @property
    def skill_labels(self) -> list:
        """
        Les compétences en français lisible, pas les clés du référentiel.

        « scan_wms » n'a rien à faire dans une annonce publiée. Les libellés du
        référentiel utilisent la virgule comme séparateur (« Arabe , usage
        professionnel ») ; on la transforme en parenthèse, sinon le rédacteur la
        lit comme une énumération et écrit « maîtrise de l'arabe et de l'usage
        professionnel ».
        """
        out = []
        for key in self.required_skills:
            label = skills.SKILLS.get(key, key)
            if " , " in label:
                head, tail = label.split(" , ", 1)
                label = f"{head} ({tail})"
            out.append(label)
        return out

    def as_text(self) -> str:
        """Les faits, en clair, tels qu'ils sont donnés au rédacteur."""
        skills_txt = ", ".join(self.skill_labels) or "non précisées"
        return (
            f"Poste : {self.role_label} ({self.role_key}), à {self.wilaya}.\n"
            f"Effectif de l'entreprise : {self.headcount_total} salariés, dont "
            f"{self.headcount_role} sur ce poste.\n"
            f"Contrats : {self.cdi_share * 100:.0f}% de CDI dans l'équipe.\n"
            f"Ancienneté moyenne : {self.avg_tenure_years:.1f} ans.\n"
            f"Salaire brut mensuel pratiqué pour ce poste : "
            f"{self.gross_monthly:,.0f} DZD pour "
            f"{labour_dz.LEGAL_MONTHLY_HOURS} heures légales "
            f"(coût chargé employeur {self.loaded_monthly:,.0f} DZD).\n"
            f"SNMG en vigueur : {labour_dz.SNMG_MONTHLY:,.0f} DZD.\n"
            f"Congé annuel : {self.leave_days} jours ouvrables.\n"
            f"Week-end : {self.weekend}.\n"
            f"Compétences attendues sur ce poste : {skills_txt}.\n"
            f"Recours à l'intérim possible : {'oui' if self.can_be_temp else 'non'}.\n"
            f"Candidats internes déjà prêts : {len(self.internal_ready)} ; "
            f"formables : {len(self.internal_trainable)}."
        )


def pool_facts(people: list, role_key: str, wilaya: str = "Alger",
               as_of: Optional[_dt.date] = None) -> PoolFacts:
    """Les faits du poste, dérivés de l'effectif réel et du droit algérien."""
    as_of = as_of or _dt.date.today()
    role = labour_dz.ROLES.get(role_key) or labour_dz.ROLES["sorter"]

    same_role = [e for e in people if e.role_key == role_key]
    cdi = sum(1 for e in people if str(e.contract).upper() == "CDI")
    tenures = [(as_of - e.hire_date).days / 365.25 for e in people]

    fits = skills.mobility_candidates(people, role_key, top=50) if people else []
    ready = [f for f in fits if f.verdict == "prêt"]
    trainable = [f for f in fits if f.verdict == "formable"]

    leave = hr.ANNUAL_LEAVE_DAYS + (
        hr.SOUTH_BONUS_DAYS if wilaya in hr.SOUTHERN_WILAYAS else 0)

    return PoolFacts(
        role_key=role_key,
        role_label=role.label,
        wilaya=wilaya,
        headcount_total=len(people),
        headcount_role=len(same_role),
        cdi_share=(cdi / len(people)) if people else 0.0,
        avg_tenure_years=(sum(tenures) / len(tenures)) if tenures else 0.0,
        gross_monthly=role.gross_monthly,
        loaded_monthly=role.loaded_monthly,
        leave_days=leave,
        can_be_temp=role.can_be_temp,
        required_skills=dict(skills.ROLE_SKILLS.get(role_key, {})),
        internal_ready=ready,
        internal_trainable=trainable,
    )


# ---------------------------------------------------------------------------
# Ce que le responsable a dit : on en extrait ce qui est vérifiable
# ---------------------------------------------------------------------------

def read_brief(brief: str) -> dict:
    """
    Les intentions chiffrées repérées dans la phrase du responsable.

    On ne devine pas : on ne relève que ce qui est écrit noir sur blanc (un
    montant, un type de contrat, un nombre de mois, un nombre de postes). Tout le
    reste part au rédacteur comme contexte libre.
    """
    text = (brief or "").lower()
    out = {"salary": None, "contract": None, "cdd_months": None, "openings": None}

    # Un salaire : « 45000 », « 45 000 DZD », « 45k »
    m = re.search(r"(\d[\d\s.]{2,})\s*(?:da|dzd|dinars?)\b", text)
    if not m:
        m = re.search(r"(\d+)\s*k\b", text)
        if m:
            out["salary"] = float(m.group(1)) * 1000
    if m and out["salary"] is None:
        out["salary"] = float(re.sub(r"[\s.]", "", m.group(1)))

    if "cdd" in text:
        out["contract"] = "CDD"
    elif "cdi" in text:
        out["contract"] = "CDI"
    elif "interim" in text or "intérim" in text:
        out["contract"] = "intérim"

    m = re.search(r"(\d+)\s*mois", text)
    if m:
        out["cdd_months"] = int(m.group(1))

    # Le nombre de postes s'écrit de deux façons : « 3 postes » (le nom porte le
    # sens) ou « il me faut 3 agents de tri » (le verbe le porte, et le nom est
    # le métier, qu'on ne peut pas énumérer d'avance).
    m = re.search(r"(\d+)\s*(?:postes?|personnes?|recrues?|candidats?)", text)
    if not m:
        m = re.search(r"(?:faut|cherche|recrute[rz]?|besoin\s+de|embaucher|"
                      r"recrutement\s+de)\s+(\d+)", text)
    if m:
        out["openings"] = int(m.group(1))
    return out


def _fold(s: str) -> str:
    """Minuscules sans accents : « Réceptionniste » doit répondre à « receptionniste »."""
    return unicodedata.normalize("NFKD", s.lower()).encode(
        "ascii", "ignore").decode("ascii")


def guess_role(brief: str, role_options: dict) -> Optional[str]:
    """
    Le poste déduit de la phrase du responsable, ou None.

    On compare les mots de la demande aux libellés du référentiel, mot à mot :
    « il me faut 3 agents de tri » contient « agent » et « tri », donc le poste
    « Agent de tri (hub) » gagne. Renvoyer None plutôt que de deviner au hasard
    est important : l'écran dit alors qu'il n'a pas reconnu le poste, au lieu
    d'afficher le salaire d'un autre métier sans le signaler.
    """
    text = _fold(brief or "")
    if not text.strip():
        return None
    best, best_score = None, 0
    for key, label in role_options.items():
        words = [w for w in re.split(r"[^a-z]+", _fold(label)) if len(w) > 3]
        score = sum(1 for w in words if w in text)
        if score > best_score:
            best, best_score = key, score
    return best if best_score >= 1 else None


def checks(brief: str, facts: PoolFacts) -> list:
    """
    Ce qui ne colle pas entre la demande, la loi et l'équipe en place.

    Chaque entrée : (gravité, message). « bloquant » veut dire que publier
    l'offre en l'état exposerait l'entreprise ; « attention » veut dire que
    l'offre est légale mais incohérente avec l'équipe.
    """
    asked = read_brief(brief)
    out = []

    if asked["salary"] is not None:
        if asked["salary"] < labour_dz.SNMG_MONTHLY:
            out.append(("bloquant",
                        f"Le salaire évoqué ({asked['salary']:,.0f} DZD) est "
                        f"sous le SNMG ({labour_dz.SNMG_MONTHLY:,.0f} DZD). "
                        f"Une offre à ce niveau est illégale."))
        elif asked["salary"] > facts.gross_monthly * (1 + EQUITY_TOLERANCE):
            out.append(("attention",
                        f"Le salaire évoqué ({asked['salary']:,.0f} DZD) dépasse "
                        f"de plus de {EQUITY_TOLERANCE:.0%} ce que l'entreprise "
                        f"paie déjà sur ce poste "
                        f"({facts.gross_monthly:,.0f} DZD). L'écart se saura : "
                        f"soit vous l'assumez pour tout le monde, soit vous le "
                        f"justifiez par le contenu du poste."))

    if asked["contract"] == "CDD" and asked["cdd_months"]:
        if asked["cdd_months"] > CDD_MAX_MONTHS:
            out.append(("bloquant",
                        f"Un CDD de {asked['cdd_months']} mois dépasse la durée "
                        f"maximale de {CDD_MAX_MONTHS} mois. Au-delà, la "
                        f"relation devient un CDI."))

    if asked["contract"] == "intérim" and not facts.can_be_temp:
        out.append(("attention",
                    f"Ce poste ({facts.role_label}) n'est pas prévu pour de "
                    f"l'intérim dans votre organisation. Vérifiez avant de "
                    f"l'annoncer comme tel."))

    if facts.internal_ready:
        names = ", ".join(f.name for f in facts.internal_ready[:3])
        out.append(("attention",
                    f"{len(facts.internal_ready)} personne(s) de votre équipe "
                    f"couvrent déjà ce poste ({names}). Un recrutement externe "
                    f"coûte plus cher qu'une mobilité interne : regardez-les "
                    f"avant de publier."))
    elif facts.internal_trainable:
        f0 = facts.internal_trainable[0]
        out.append(("attention",
                    f"{len(facts.internal_trainable)} personne(s) de votre "
                    f"équipe sont formables sur ce poste, la plus proche est "
                    f"{f0.name} ({f0.coverage}% des exigences déjà couvertes, "
                    f"{f0.training_days} jours de formation estimés)."))

    if facts.headcount_role == 0:
        out.append(("attention",
                    f"Personne n'occupe ce poste aujourd'hui : le salaire "
                    f"indicatif vient du barème du poste, pas d'un salaire "
                    f"réellement pratiqué chez vous."))
    return out


# ---------------------------------------------------------------------------
# La rédaction
# ---------------------------------------------------------------------------

@dataclass
class JobPost:
    title: str
    summary: str
    missions: list
    required: list
    nice: list
    conditions: list
    apply_line: str
    warnings: list = field(default_factory=list)
    method: str = "règles"

    def as_markdown(self) -> str:
        def block(head, items):
            if not items:
                return ""
            body = "\n".join(f"- {i}" for i in items)
            return f"\n**{head}**\n{body}\n"

        return (
            f"# {self.title}\n\n{self.summary}\n"
            + block("Missions", self.missions)
            + block("Profil recherché", self.required)
            + block("Atouts appréciés", self.nice)
            + block("Conditions", self.conditions)
            + f"\n{self.apply_line}\n"
        )


_AI_SYSTEM = (
    "Tu es un recruteur algérien expérimenté. À partir de la demande du "
    "responsable et des FAITS de l'entreprise, rédige une offre d'emploi "
    "publiable, en français, pour le marché algérien.\n\n"
    "Règles absolues :\n"
    "- Ne parle JAMAIS de salaire, de rémunération, de congés, d'horaires "
    "légales, de CNAS ni de week-end : un autre bloc s'en charge et le tien "
    "serait supprimé. Écris seulement le titre, le résumé, les missions et le "
    "profil.\n"
    "- N'invente AUCUN chiffre. Si une information manque, ne la mentionne pas.\n"
    "- Ne promets aucun avantage qui ne figure pas dans les FAITS.\n"
    "- Le week-end algérien est vendredi et samedi ; dimanche est un jour "
    "ouvré. Ne transpose jamais une semaine étrangère.\n"
    "- Ne réinterprète pas la demande du responsable : s'il demande une "
    "disponibilité un jour donné, reprends ce jour-là tel quel.\n"
    "- Écris simplement, sans anglicismes ni formules creuses du type "
    "« environnement dynamique » ou « rejoignez une équipe passionnée ».\n"
    "- Les missions doivent être concrètes et vérifiables.\n"
    "- Pas de discrimination : ni âge, ni sexe, ni situation familiale, ni "
    "origine.\n\n"
    "Réponds UNIQUEMENT en JSON, sans texte autour :\n"
    '{"titre": "...", "resume": "2 phrases", "missions": ["..."], '
    '"profil_requis": ["..."], "atouts": ["..."], "candidature": "1 phrase"}'
)


def _repair_truncated_json(fragment: str) -> Optional[dict]:
    """
    Récupérer un JSON coupé net par la limite de jetons.

    Une offre en français est longue : si la réponse s'arrête au milieu d'une
    liste, l'accolade finale manque et tout le travail est perdu. Plutôt que de
    jeter la réponse, on coupe après le dernier élément complet et on referme les
    crochets ouverts. Purement mécanique, et borné : si ça ne donne pas un objet
    valide, l'appelant retombe sur le gabarit.
    """
    frag = fragment
    if frag.count('"') % 2:                      # une chaîne restée ouverte
        frag = frag[:frag.rfind('"')]
    cut = max(frag.rfind('"'), frag.rfind("]"), frag.rfind("}"))
    if cut <= 0:
        return None
    frag = frag[:cut + 1]
    frag += "]" * max(frag.count("[") - frag.count("]"), 0)
    frag += "}" * max(frag.count("{") - frag.count("}"), 0)
    try:
        data = json.loads(frag)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _parse_json(text: str) -> Optional[dict]:
    """Le JSON du modèle, même entouré de texte, d'un bloc de code, ou tronqué."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            data = json.loads(m.group())
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    return _repair_truncated_json(text[start:]) if start >= 0 else None


# Les mots qui n'ont rien à faire dans une mission ou un profil : ils désignent
# des conditions, et les conditions sont calculées par le moteur. Un modèle
# obéit au prompt la plupart du temps, pas toujours ; ce filtre-là ne dépend pas
# de sa bonne volonté. Il a rattrapé un « Salaire brut mensuel » glissé dans les
# atouts, et une phrase qui remplaçait le vendredi par le dimanche.
_CONDITION_WORDS = ("salaire", "rémunération", "remuneration", "dzd", " da ",
                    "snmg", "congé", "conge", "week-end", "weekend",
                    "heures légales", "heures legales", "cnas", "dimanche",
                    "brut mensuel", "prime de", "avantage")


def _looks_like_condition(s: str) -> bool:
    low = " " + s.lower() + " "
    return any(w in low for w in _CONDITION_WORDS)


def _clean_list(value, limit: int = 8) -> list:
    if not isinstance(value, list):
        return []
    out = []
    for v in value[:limit]:
        s = str(v).strip().lstrip("-•").strip()
        if 3 <= len(s) <= 240 and not _looks_like_condition(s):
            out.append(s)
    return out


def _conditions(facts: PoolFacts, asked: dict) -> list:
    """
    Les conditions, calculées et non rédigées.

    C'est le bloc que le modèle n'écrit jamais : il porte le salaire, le contrat,
    les horaires légales, les congés et le week-end. Le reformuler côté langage
    reviendrait à autoriser une promesse inexacte.
    """
    contract = asked.get("contract") or (
        "CDI" if facts.cdi_share >= 0.5 else "CDD")
    salary = asked.get("salary") or facts.gross_monthly
    cond = [
        f"Contrat : {contract}"
        + (f" de {asked['cdd_months']} mois" if asked.get("cdd_months")
           and contract == "CDD" else ""),
        f"Rémunération indicative : {salary:,.0f} DZD brut par mois pour "
        f"{labour_dz.LEGAL_MONTHLY_HOURS} heures légales "
        f"(SNMG en vigueur : {labour_dz.SNMG_MONTHLY:,.0f} DZD)",
        f"Lieu de travail : {facts.wilaya}",
        f"Congé annuel : {facts.leave_days} jours ouvrables",
        f"Repos hebdomadaire : {facts.weekend}",
        "Déclaration CNAS dès l'embauche",
    ]
    if asked.get("openings"):
        cond.insert(0, f"Postes à pourvoir : {asked['openings']}")
    return cond


def _elide(word: str) -> str:
    """« de agent » ne se publie pas : devant une voyelle, on élide."""
    return ("d'" if word[:1].lower() in "aeiouyéèêà" else "de ") + word


def _rule_draft(brief: str, facts: PoolFacts, asked: dict) -> JobPost:
    """Le gabarit déterministe : ce qui part quand il n'y a pas de clé IA."""
    seed = cv_screen.JOB_TEMPLATES_TEXT.get(facts.role_key, "")
    labels = facts.skill_labels
    role_lower = facts.role_label.lower()
    missions = [
        f"Assurer les tâches courantes du poste {_elide(role_lower)}",
        # Le libellé garde sa casse : « (HSE) » ne se met pas en minuscules.
    ] + [f"{label} : tenir le niveau attendu au quotidien"
         for label in labels[:4]]
    required = [
        "Expérience du poste ou d'un poste proche",
        "Arabe et français",
        "Service national réglé pour les candidats concernés",
    ]
    if labels:
        required.append("Maîtrise de : " + ", ".join(labels[:5]))
    return JobPost(
        title=f"{facts.role_label} , {facts.wilaya}",
        summary=(f"Nous recrutons un {role_lower} à "
                 f"{facts.wilaya}. " + (brief.strip() or seed))[:500],
        missions=missions,
        required=required,
        nice=["Connaissance du secteur", "Disponibilité en shifts"],
        conditions=_conditions(facts, asked),
        apply_line="Pour candidater, envoyez votre CV en précisant le poste.",
        method="règles",
    )


def draft(brief: str, facts: PoolFacts, use_ai: bool = True) -> JobPost:
    """
    L'offre rédigée depuis la phrase du responsable, calée sur les faits.

    La couche langage écrit le titre, le résumé, les missions et le profil. Les
    conditions sont recalculées par-dessus, et les alertes de cohérence sont
    ajoutées. En cas d'absence de clé ou d'échec, on retombe sur le gabarit.
    """
    asked = read_brief(brief)
    warnings = checks(brief, facts)

    if not use_ai or not any(ai.providers_available().values()):
        post = _rule_draft(brief, facts, asked)
        post.warnings = warnings
        return post

    user = (f"FAITS DE L'ENTREPRISE (source de vérité) :\n{facts.as_text()}\n\n"
            f"DEMANDE DU RESPONSABLE, dans ses mots :\n{brief.strip()}")
    # 1400 jetons : une offre complète en français (titre, résumé, quatre listes)
    # dépasse régulièrement 900, et une réponse coupée perd son accolade finale.
    res = ai.chat(_AI_SYSTEM, user, max_tokens=1400, temperature=0.35)
    data = _parse_json(res.text) if res.ok else None
    if not data:
        post = _rule_draft(brief, facts, asked)
        post.warnings = warnings
        post.method = "règles (le modèle n'a pas répondu en JSON)"
        return post

    title = str(data.get("titre") or facts.role_label).strip()[:120]
    summary = str(data.get("resume") or "").strip()[:600]
    post = JobPost(
        title=title,
        summary=summary,
        missions=_clean_list(data.get("missions")),
        required=_clean_list(data.get("profil_requis")),
        nice=_clean_list(data.get("atouts"), limit=5),
        # Les conditions ne viennent jamais du modèle.
        conditions=_conditions(facts, asked),
        apply_line=str(data.get("candidature")
                       or "Envoyez votre CV en précisant le poste.").strip()[:240],
        warnings=warnings,
        method=f"rédigé par {res.model}, faits et conditions calculés",
    )
    if not post.missions or not post.required:
        fallback = _rule_draft(brief, facts, asked)
        post.missions = post.missions or fallback.missions
        post.required = post.required or fallback.required
    return post


def to_screening_job(post: JobPost, facts: PoolFacts) -> cv_screen.Job:
    """
    L'offre convertie en critères de tri, pour classer le vivier dessus.

    On part du poste type quand il existe déjà dans le référentiel de tri, et on
    ne remplace que le titre : les seuils (formation, expérience, langues) sont
    ceux du référentiel, pas une invention du texte de l'annonce.
    """
    base = cv_screen.JOBS.get(facts.role_key)
    if base is None:
        base = cv_screen.Job(role_key=facts.role_key, title=post.title,
                             skills=tuple(facts.required_skills))
        return base
    return cv_screen.Job(
        role_key=base.role_key,
        title=post.title,
        min_education=base.min_education,
        min_experience_years=base.min_experience_years,
        required_languages=base.required_languages,
        skills=base.skills,
        needs_driving_licence=base.needs_driving_licence,
        needs_service_national_cleared=base.needs_service_national_cleared,
        weight=dict(base.weight),
    )


if __name__ == "__main__":
    print("Rédaction d'offre - auto-vérification\n")

    people = hr.sample_workforce("sorter", 30, "Alger")
    facts = pool_facts(people, "sorter", "Alger")

    ok = (facts.headcount_role == 30 and facts.gross_monthly > 0
          and facts.leave_days == hr.ANNUAL_LEAVE_DAYS)
    print(f"{'OK ' if ok else 'ECHEC'} faits de l'équipe : {facts.headcount_role} "
          f"sur le poste, {facts.gross_monthly:,.0f} DZD brut, "
          f"{facts.leave_days} jours de congé")

    south = pool_facts(hr.sample_workforce("sorter", 5, "Adrar"), "sorter", "Adrar")
    ok = south.leave_days == hr.ANNUAL_LEAVE_DAYS + hr.SOUTH_BONUS_DAYS
    print(f"{'OK ' if ok else 'ECHEC'} wilaya du Sud : {south.leave_days} jours "
          f"de congé au lieu de {hr.ANNUAL_LEAVE_DAYS}")

    # Lecture de la demande
    read = read_brief("il me faut 3 agents de tri en CDD de 30 mois à 18000 DA")
    ok = (read["openings"] == 3 and read["contract"] == "CDD"
          and read["cdd_months"] == 30 and read["salary"] == 18000)
    print(f"{'OK ' if ok else 'ECHEC'} demande relue : {read}")

    # Les deux garde-fous qui comptent
    warns = checks("3 agents en CDD de 30 mois à 18000 DA", facts)
    blocking = [w for lvl, w in warns if lvl == "bloquant"]
    has_snmg = any("SNMG" in w for w in blocking)
    has_cdd = any("CDD" in w for w in blocking)
    print(f"{'OK ' if has_snmg else 'ECHEC'} salaire sous le SNMG signalé comme bloquant")
    print(f"{'OK ' if has_cdd else 'ECHEC'} CDD de 30 mois signalé comme bloquant")

    equity = checks("un agent de tri à 60000 DA", facts)
    has_equity = any("dépasse" in w for lvl, w in equity if lvl == "attention")
    print(f"{'OK ' if has_equity else 'ECHEC'} écart d'équité interne signalé")

    # Le gabarit hors ligne doit produire une offre complète et légale
    post = draft("un agent de tri sérieux, disponible en shifts", facts,
                 use_ai=False)
    md = post.as_markdown()
    ok = (post.title and post.missions and post.required and post.conditions
          and "SNMG" in md and "vendredi et samedi" in md)
    print(f"{'OK ' if ok else 'ECHEC'} offre hors ligne : {len(md)} caractères, "
          f"conditions légales incluses")

    job = to_screening_job(post, facts)
    ok = job.role_key == "sorter" and job.min_education == \
        cv_screen.JOBS["sorter"].min_education
    print(f"{'OK ' if ok else 'ECHEC'} conversion en critères de tri : "
          f"seuils du référentiel conservés")

    # Une réponse coupée par la limite de jetons doit être récupérée, pas jetée.
    truncated = ('{"titre": "Agent de tri", "resume": "Deux phrases ici.", '
                 '"missions": ["Trier les colis", "Scanner les envo')
    repaired = _parse_json(truncated)
    ok = bool(repaired) and repaired.get("titre") == "Agent de tri" \
        and repaired.get("missions") == ["Trier les colis"]
    print(f"{'OK ' if ok else 'ECHEC'} JSON tronqué réparé : "
          f"{list(repaired) if repaired else 'perdu'}")

    # Les conditions n'appartiennent qu'au moteur : une puce du modèle qui parle
    # d'argent, de congés ou de dimanche doit disparaître.
    leaked = _clean_list([
        "Tri et scan des colis",
        "Salaire brut mensuel attractif",
        "Disponibilité y compris le dimanche à la place du vendredi",
        "Congés payés selon la loi",
        "Relation avec les transporteurs",
    ])
    ok = leaked == ["Tri et scan des colis", "Relation avec les transporteurs"]
    print(f"{'OK ' if ok else 'ECHEC'} puces de conditions filtrées : "
          f"{len(leaked)} gardées sur 5 -> {leaked}")

    # Un libellé à virgule doit devenir une parenthèse avant d'être publié.
    labels = facts.skill_labels
    ok = all(" , " not in lb for lb in labels) and \
        any(lb.startswith("Arabe (") for lb in labels)
    print(f"{'OK ' if ok else 'ECHEC'} libellés publiables : "
          f"{[lb for lb in labels if lb.startswith('Arabe')]}")

    print("\n--- Offre produite sans clé IA ---")
    print(md)
