"""
core/job_post.py
----------------
Write a job post from what the manager says, and fit it to the existing team.

A manager knows what they want but has no time to write a publishable post.
The result is three-line ads that attract off-target applicants, or ads copied
from a foreign template that promise conditions the company does not offer.

Here the manager dictates one sentence. The module writes the post and, above
all, checks it against the actual workforce: what the company already pays for
the role, the contract type it uses, the skills the team has, and the people in
house who already cover the role.

Division of labour: the engine owns the facts, the language layer only writes.
Indicative salary, contract, hours, leave and weekend are calculated here from
the SNMG, the role coefficient and Algerian law, then written over whatever the
model produced. Without an AI key, a deterministic template still produces a
publishable post.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from . import ai, cv_screen, hr, labour_dz, skills

# Beyond this cumulative length a CDD can no longer be renewed.
CDD_MAX_MONTHS = 24

# Pay gap above which we warn about internal equity: offering far more than the
# current team earns for the same role is a problem the day it gets out.
EQUITY_TOLERANCE = 0.40


@dataclass
class PoolFacts:
    """What the current team says about the role to fill."""
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
        return "Friday and Saturday"

    @property
    def skill_labels(self) -> list:
        """Readable skill labels, never framework keys like 'scan_wms'."""
        return [skills.SKILLS.get(key, key) for key in self.required_skills]

    def as_text(self) -> str:
        """The facts, in plain text, as given to the writer."""
        skills_txt = ", ".join(self.skill_labels) or "not specified"
        return (
            f"Role: {self.role_label} ({self.role_key}), in {self.wilaya}.\n"
            f"Company headcount: {self.headcount_total} employees, "
            f"{self.headcount_role} in this role.\n"
            f"Contracts: {self.cdi_share * 100:.0f}% CDI in the team.\n"
            f"Average tenure: {self.avg_tenure_years:.1f} years.\n"
            f"Monthly gross paid for this role: {self.gross_monthly:,.0f} DZD for "
            f"{labour_dz.LEGAL_MONTHLY_HOURS} legal hours "
            f"(loaded employer cost {self.loaded_monthly:,.0f} DZD).\n"
            f"SNMG in force: {labour_dz.SNMG_MONTHLY:,.0f} DZD.\n"
            f"Annual leave: {self.leave_days} working days.\n"
            f"Weekend: {self.weekend}.\n"
            f"Skills expected in this role: {skills_txt}.\n"
            f"Temps allowed: {'yes' if self.can_be_temp else 'no'}.\n"
            f"Internal candidates ready: {len(self.internal_ready)}; "
            f"trainable: {len(self.internal_trainable)}."
        )


def pool_facts(people: list, role_key: str, wilaya: str = "Alger",
               as_of: Optional[_dt.date] = None) -> PoolFacts:
    """The role's facts, derived from the actual workforce and Algerian law."""
    as_of = as_of or _dt.date.today()
    role = labour_dz.ROLES.get(role_key) or labour_dz.ROLES["sorter"]

    same_role = [e for e in people if e.role_key == role_key]
    cdi = sum(1 for e in people if str(e.contract).upper() == "CDI")
    tenures = [(as_of - e.hire_date).days / 365.25 for e in people]

    fits = skills.mobility_candidates(people, role_key, top=50) if people else []
    ready = [f for f in fits if f.verdict == "ready"]
    trainable = [f for f in fits if f.verdict == "trainable"]

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


def read_brief(brief: str) -> dict:
    """
    The figures stated in the manager's sentence (English or French).

    No guessing: only what is written in black and white (an amount, a contract
    type, a number of months, a number of openings).
    """
    text = (brief or "").lower()
    out = {"salary": None, "contract": None, "cdd_months": None, "openings": None}

    m = re.search(r"(\d[\d\s.,]{2,})\s*(?:da|dzd|dinars?)\b", text)
    if not m:
        m = re.search(r"(\d+)\s*k\b", text)
        if m:
            out["salary"] = float(m.group(1)) * 1000
    if m and out["salary"] is None:
        out["salary"] = float(re.sub(r"[\s.,]", "", m.group(1)))

    if "cdd" in text or "fixed-term" in text or "fixed term" in text:
        out["contract"] = "CDD"
    elif "cdi" in text or "permanent" in text:
        out["contract"] = "CDI"
    elif "interim" in text or "intérim" in text or "temp " in text:
        out["contract"] = "temp"

    m = re.search(r"(\d+)\s*(?:-\s*)?(?:months?|mois)", text)
    if m:
        out["cdd_months"] = int(m.group(1))

    m = re.search(r"(\d+)\s*(?:openings?|positions?|people|hires?|postes?|personnes?)", text)
    if not m:
        m = re.search(r"(?:need|hire|hiring|recruit|looking\s+for|faut|cherche|"
                      r"recrute[rz]?|besoin\s+de|embaucher)\s+(\d+)", text)
    if m:
        out["openings"] = int(m.group(1))
    return out


def _fold(s: str) -> str:
    """Lowercase without accents."""
    return unicodedata.normalize("NFKD", s.lower()).encode(
        "ascii", "ignore").decode("ascii")


# Words that describe working conditions, not a trade ("available for shifts").
_GENERIC = {"shift", "shifts", "night", "team", "equipe", "agent", "staff"}


def guess_role(brief: str, role_options: dict) -> Optional[str]:
    """
    The role inferred from the manager's sentence, or None.

    Words in the request are matched against role labels. Returning None rather
    than guessing lets the screen say it did not recognise the role instead of
    quietly showing another trade's salary.
    """
    text = _fold(brief or "")
    if not text.strip():
        return None
    best, best_score = None, 0
    for key, label in role_options.items():
        # English label and French title both count: briefs come in either.
        label = f"{label} {labour_dz.LABEL_FR.get(key, '')}"
        words = [w for w in re.split(r"[^a-z]+", _fold(label)) if len(w) > 3 and w not in _GENERIC]
        score = sum(1 for w in words if w in text)
        if score > best_score:
            best, best_score = key, score
    return best if best_score >= 1 else None


def checks(brief: str, facts: PoolFacts) -> list:
    """
    What does not fit between the request, the law and the current team.

    Each entry is (level, message). "bloquant" means publishing as is would
    expose the company; "attention" means legal but inconsistent with the team.
    """
    asked = read_brief(brief)
    out = []

    if asked["salary"] is not None:
        if asked["salary"] < labour_dz.SNMG_MONTHLY:
            out.append(("bloquant",
                        f"The salary mentioned ({asked['salary']:,.0f} DZD) is "
                        f"below the SNMG ({labour_dz.SNMG_MONTHLY:,.0f} DZD). "
                        f"An offer at that level is illegal."))
        elif asked["salary"] > facts.gross_monthly * (1 + EQUITY_TOLERANCE):
            out.append(("attention",
                        f"The salary mentioned ({asked['salary']:,.0f} DZD) exceeds "
                        f"what the company already pays for this role "
                        f"({facts.gross_monthly:,.0f} DZD) by more than "
                        f"{EQUITY_TOLERANCE:.0%}. The gap will get out: either "
                        f"apply it to everyone or justify it by the job content."))

    if asked["contract"] == "CDD" and asked["cdd_months"]:
        if asked["cdd_months"] > CDD_MAX_MONTHS:
            out.append(("bloquant",
                        f"A {asked['cdd_months']}-month CDD exceeds the "
                        f"{CDD_MAX_MONTHS}-month maximum. Beyond that, the "
                        f"relationship becomes a CDI."))

    if asked["contract"] == "temp" and not facts.can_be_temp:
        out.append(("attention",
                    f"This role ({facts.role_label}) is not set up for temps in "
                    f"your organisation. Check before advertising it as such."))

    if facts.internal_ready:
        names = ", ".join(f.name for f in facts.internal_ready[:3])
        out.append(("attention",
                    f"{len(facts.internal_ready)} person(s) on your team already "
                    f"cover this role ({names}). External hiring costs more than "
                    f"internal mobility: look at them before publishing."))
    elif facts.internal_trainable:
        f0 = facts.internal_trainable[0]
        out.append(("attention",
                    f"{len(facts.internal_trainable)} person(s) on your team are "
                    f"trainable for this role; the closest is {f0.name} "
                    f"({f0.coverage}% of requirements covered, about "
                    f"{f0.training_days} training days)."))

    if facts.headcount_role == 0:
        out.append(("attention",
                    "Nobody holds this role today: the indicative salary comes "
                    "from the role scale, not from a salary you actually pay."))
    return out


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
    method: str = "rules"

    def as_markdown(self) -> str:
        def block(head, items):
            if not items:
                return ""
            body = "\n".join(f"- {i}" for i in items)
            return f"\n**{head}**\n{body}\n"

        return (
            f"# {self.title}\n\n{self.summary}\n"
            + block("Responsibilities", self.missions)
            + block("Profile", self.required)
            + block("Nice to have", self.nice)
            + block("Conditions", self.conditions)
            + f"\n{self.apply_line}\n"
        )


_AI_SYSTEM = (
    "You are an experienced Algerian recruiter. From the manager's request and "
    "the company FACTS, write a publishable job post in English for the "
    "Algerian market.\n\n"
    "Absolute rules:\n"
    "- NEVER mention salary, pay, leave, legal hours, CNAS or the weekend: "
    "another block handles them and yours would be removed. Write only the "
    "title, summary, responsibilities and profile.\n"
    "- Invent NO figure. If information is missing, leave it out.\n"
    "- Promise no benefit that is not in the FACTS.\n"
    "- The Algerian weekend is Friday and Saturday; Sunday is a working day.\n"
    "- Do not reinterpret the request: if a given day is asked, keep it.\n"
    "- Write plainly, without empty phrases like 'dynamic environment'.\n"
    "- Responsibilities must be concrete and checkable.\n"
    "- No discrimination: no age, sex, family status or origin.\n\n"
    "Answer ONLY in JSON, with no surrounding text:\n"
    '{"title": "...", "summary": "2 sentences", "missions": ["..."], '
    '"required": ["..."], "nice": ["..."], "apply": "1 sentence"}'
)


def _repair_truncated_json(fragment: str) -> Optional[dict]:
    """Recover JSON cut off by the token limit: cut after the last complete item."""
    frag = fragment
    if frag.count('"') % 2:
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
    """The model's JSON, even wrapped in text, a code block, or truncated."""
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


# Words that belong to conditions, which the engine calculates. This filter does
# not depend on the model obeying the prompt.
_CONDITION_WORDS = ("salary", "pay ", "wage", "dzd", " da ", "snmg", "leave",
                    "weekend", "week-end", "legal hours", "cnas", "sunday",
                    "gross monthly", "bonus", "benefit",
                    "salaire", "rémunération", "congé", "dimanche")


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
    """The conditions, calculated not written: the block the model never writes."""
    contract = asked.get("contract") or (
        "CDI" if facts.cdi_share >= 0.5 else "CDD")
    salary = asked.get("salary") or facts.gross_monthly
    cond = [
        f"Contract: {contract}"
        + (f", {asked['cdd_months']} months" if asked.get("cdd_months")
           and contract == "CDD" else ""),
        f"Indicative pay: {salary:,.0f} DZD gross per month for "
        f"{labour_dz.LEGAL_MONTHLY_HOURS} legal hours "
        f"(SNMG in force: {labour_dz.SNMG_MONTHLY:,.0f} DZD)",
        f"Place of work: {facts.wilaya}",
        f"Annual leave: {facts.leave_days} working days",
        f"Weekly rest: {facts.weekend}",
        "CNAS registration from day one",
    ]
    if asked.get("openings"):
        cond.insert(0, f"Openings: {asked['openings']}")
    return cond


def _rule_draft(brief: str, facts: PoolFacts, asked: dict) -> JobPost:
    """The deterministic template, used when there is no AI key."""
    seed = cv_screen.JOB_TEMPLATES_TEXT.get(facts.role_key, "")
    labels = facts.skill_labels
    role_lower = facts.role_label.lower()
    missions = [f"Carry out the day-to-day work of a {role_lower}"] + [
        f"{label}: hold the expected level every day" for label in labels[:4]]
    required = [
        "Experience in the role or a close one",
        "Arabic and French",
        "National service settled, for candidates concerned",
    ]
    if labels:
        required.append("Command of: " + ", ".join(labels[:5]))
    return JobPost(
        title=f"{facts.role_label}, {facts.wilaya}",
        summary=(f"We are hiring a {role_lower} in {facts.wilaya}. "
                 + (brief.strip() or seed))[:500],
        missions=missions,
        required=required,
        nice=["Knowledge of the sector", "Available for shift work"],
        conditions=_conditions(facts, asked),
        apply_line="To apply, send your CV and name the role.",
        method="rules",
    )


def draft(brief: str, facts: PoolFacts, use_ai: bool = True) -> JobPost:
    """
    The post written from the manager's sentence, fitted to the facts.

    The language layer writes title, summary, responsibilities and profile.
    Conditions are recalculated on top, and consistency warnings are added.
    Without a key, or on failure, the template is used.
    """
    asked = read_brief(brief)
    warnings = checks(brief, facts)

    if not use_ai or not any(ai.providers_available().values()):
        post = _rule_draft(brief, facts, asked)
        post.warnings = warnings
        return post

    user = (f"COMPANY FACTS (source of truth):\n{facts.as_text()}\n\n"
            f"MANAGER'S REQUEST, in their words:\n{brief.strip()}")
    res = ai.chat(_AI_SYSTEM, user, max_tokens=1400, temperature=0.35)
    data = _parse_json(res.text) if res.ok else None
    if not data:
        post = _rule_draft(brief, facts, asked)
        post.warnings = warnings
        post.method = "rules (the model did not answer in JSON)"
        return post

    def pick(*keys):
        for k in keys:
            if data.get(k):
                return data[k]
        return None

    post = JobPost(
        title=str(pick("title", "titre") or facts.role_label).strip()[:120],
        summary=str(pick("summary", "resume") or "").strip()[:600],
        missions=_clean_list(pick("missions")),
        required=_clean_list(pick("required", "profil_requis")),
        nice=_clean_list(pick("nice", "atouts"), limit=5),
        conditions=_conditions(facts, asked),   # never from the model
        apply_line=str(pick("apply", "candidature")
                       or "Send your CV and name the role.").strip()[:240],
        warnings=warnings,
        method=f"written by {res.model}, facts and conditions calculated",
    )
    if not post.missions or not post.required:
        fallback = _rule_draft(brief, facts, asked)
        post.missions = post.missions or fallback.missions
        post.required = post.required or fallback.required
    return post


def to_screening_job(post: JobPost, facts: PoolFacts) -> cv_screen.Job:
    """
    The post turned into screening criteria, to rank the pool against it.

    Thresholds (education, experience, languages) stay those of the framework;
    only the title comes from the post.
    """
    base = cv_screen.JOBS.get(facts.role_key)
    if base is None:
        return cv_screen.Job(role_key=facts.role_key, title=post.title,
                             skills=tuple(facts.required_skills))
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
    print("Job post writer, self check\n")

    people = hr.sample_workforce("sorter", 30, "Alger")
    facts = pool_facts(people, "sorter", "Alger")
    assert facts.headcount_role == 30 and facts.gross_monthly > 0
    assert facts.leave_days == hr.ANNUAL_LEAVE_DAYS

    south = pool_facts(hr.sample_workforce("sorter", 5, "Adrar"), "sorter", "Adrar")
    assert south.leave_days == hr.ANNUAL_LEAVE_DAYS + hr.SOUTH_BONUS_DAYS

    read = read_brief("I need 3 sorters on a CDD of 30 months at 18000 DA")
    assert (read["openings"], read["contract"], read["cdd_months"], read["salary"]) == \
        (3, "CDD", 30, 18000), read
    read_fr = read_brief("il me faut 3 agents de tri en CDD de 30 mois à 18000 DA")
    assert read_fr["openings"] == 3 and read_fr["cdd_months"] == 30, read_fr

    blocking = [w for lvl, w in checks("3 sorters, CDD of 30 months at 18000 DA", facts)
                if lvl == "bloquant"]
    assert any("SNMG" in w for w in blocking) and any("CDD" in w for w in blocking)
    assert any("exceeds" in w for lvl, w in checks("a sorter at 60000 DA", facts)
               if lvl == "attention")

    post = draft("a reliable sorter, available for shifts", facts, use_ai=False)
    md = post.as_markdown()
    assert post.missions and post.required and "SNMG" in md and "Friday and Saturday" in md

    job = to_screening_job(post, facts)
    assert job.min_education == cv_screen.JOBS["sorter"].min_education

    repaired = _parse_json('{"title": "Sorter", "summary": "Two lines.", '
                           '"missions": ["Sort parcels", "Scan the shipm')
    assert repaired and repaired.get("missions") == ["Sort parcels"], repaired

    kept = _clean_list(["Sort and scan parcels", "Attractive gross monthly salary",
                        "Available Sunday instead of Friday", "Paid leave by law",
                        "Work with carriers"])
    assert kept == ["Sort and scan parcels", "Work with carriers"], kept
    print("all checks passed\n")
    print(md)
