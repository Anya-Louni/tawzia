"""
core/sourcing.py
----------------
Sourcing and employer brand: step zero of recruitment.

The rest of the suite takes the candidate once they have applied. This module
answers the question asked before all the others: where do candidates come from?

What is real and what is modelled:
  * The channel directory is real. Universities, national schools, the
    vocational-training network, Algerian agencies and job sites: existing,
    verifiable institutions, named as they are. Nothing is invented by a model.
  * Volumes, costs and lead times are modelled. No Algerian operator publishes
    cost per hire by channel. The figures are framing assumptions, marked as
    such, which a pilot replaces with the client's real numbers.
  * No list of people is generated. A model that "finds influencers" invents
    plausible, false names. Instead the module produces partner profiles to look
    for (criteria, where to look, what to ask), and the AI writes the outreach.

AI only writes the outreach message at the end, from a channel and role the
engine already picked. The ranking is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from . import ai, labour_dz, sources

# A channel does not recruit "a role", it feeds a job family.
FAMILIES = {
    "operations": "Operations and logistics",
    "terrain": "Field and driving",
    "client": "Customer service and reception",
    "encadrement": "Management and supervision",
    "technique": "Technical and maintenance",
    "education": "Teaching and school life",
}

ROLE_FAMILY = {
    "sorter": "operations",
    "warehouse_op": "operations",
    "loader": "operations",
    "courier": "terrain",
    "driver": "terrain",
    "ramp_agent": "technique",
    "checkin_agent": "client",
    "front_desk": "client",
    "fnb_staff": "client",
    "housekeeper": "client",
    "supervisor": "encadrement",
    "dispatcher": "encadrement",
    "teacher": "education",
    "school_life": "education",
}

# Typical qualification level per family: university (bac+3 and up) or vocational.
FAMILY_LEVEL = {
    "operations": "professionnel",
    "terrain": "professionnel",
    "client": "mixte",
    "encadrement": "superieur",
    "technique": "mixte",
    "education": "superieur",
}

REGIONS = {
    "centre": ["Alger", "Blida", "Tizi Ouzou", "Bejaia", "Djelfa", "Medea", "Boumerdes"],
    "ouest": ["Oran", "Tlemcen", "Mostaganem", "Sidi Bel Abbes", "Chlef", "Bechar"],
    "est": ["Constantine", "Annaba", "Setif", "Batna", "Skikda", "Biskra"],
    "sud": ["Ouargla", "Ghardaia", "Tamanrasset", "Adrar", "Illizi", "El Oued"],
}
REGION_LABEL = {"centre": "Centre", "ouest": "West", "est": "East", "sud": "South"}


def region_of(wilaya: str) -> str:
    for reg, wilayas in REGIONS.items():
        if wilaya in wilayas:
            return reg
    return "centre"


@dataclass(frozen=True)
class Channel:
    """
    A real sourcing channel.

    `name`, `kind`, `wilaya` and `url` describe an existing institution.
    `volume`, `cost_dzd`, `lead_days` and `quality` are framing assumptions:
    orders of magnitude to compare channels, not measured figures.
    """
    key: str
    name: str
    kind: str                 # universite | formation | emploi | institution
    wilaya: str               # wilaya, or "National"
    families: tuple
    volume: int               # applications per campaign (assumption)
    cost_dzd: int             # campaign cost (assumption)
    lead_days: int            # days to first shortlist (assumption)
    quality: float            # expected average fit 0..1 (assumption)
    url: str = ""
    note: str = ""

    @property
    def is_national(self) -> bool:
        return self.wilaya == "National"


# Universities and national schools. Real names and locations.
_UNIVERSITIES = [
    Channel("usthb", "USTHB, Houari Boumediene University of Science and Technology",
            "universite", "Alger", ("technique", "encadrement"),
            140, 45_000, 21, 0.62, "https://www.usthb.dz",
            "The country's largest science and engineering pool."),
    Channel("esi", "ESI Algiers, National Higher School of Computer Science",
            "universite", "Alger", ("technique", "encadrement"),
            60, 40_000, 18, 0.78, "https://www.esi.dz",
            "The most selective computing track. Low volume, high quality."),
    Channel("enp", "ENP, National Polytechnic School, El Harrach",
            "universite", "Alger", ("technique", "encadrement"),
            55, 40_000, 18, 0.76, "https://www.enp.edu.dz",
            "General engineering, technical-management profile."),
    Channel("esc_alger", "ESC Algiers, Higher School of Commerce (Kolea)",
            "universite", "Alger", ("encadrement", "client"),
            70, 38_000, 20, 0.70, "https://www.esc-alger.dz",
            "Business, management and customer relations, management level."),
    Channel("univ_oran", "University of Oran 1 Ahmed Ben Bella",
            "universite", "Oran", ("technique", "encadrement", "client"),
            120, 40_000, 21, 0.60, "https://www.univ-oran1.dz",
            "The main university hub of the West."),
    Channel("univ_constantine", "University of Constantine 1 Freres Mentouri",
            "universite", "Constantine", ("technique", "encadrement", "education"),
            120, 40_000, 21, 0.60, "https://www.umc.edu.dz",
            "The main university hub of the East."),
    Channel("univ_annaba", "Badji Mokhtar University, Annaba",
            "universite", "Annaba", ("technique", "encadrement"),
            95, 36_000, 21, 0.58, "https://www.univ-annaba.dz",
            "Industrial and port basin of the East."),
    Channel("univ_setif", "Ferhat Abbas University, Setif 1",
            "universite", "Setif", ("technique", "encadrement", "education"),
            95, 36_000, 21, 0.58, "https://www.univ-setif.dz",
            "High Plateaux hub, strong in science and technology."),
    Channel("univ_tlemcen", "Abou Bekr Belkaid University, Tlemcen",
            "universite", "Tlemcen", ("encadrement", "education", "client"),
            80, 34_000, 21, 0.56, "https://www.univ-tlemcen.dz"),
    Channel("univ_bejaia", "Abderrahmane Mira University, Bejaia",
            "universite", "Bejaia", ("technique", "encadrement", "client"),
            85, 34_000, 21, 0.57, "https://www.univ-bejaia.dz"),
    Channel("ummto", "Mouloud Mammeri University, Tizi Ouzou",
            "universite", "Tizi Ouzou", ("technique", "encadrement", "education"),
            85, 34_000, 21, 0.57, "https://www.ummto.dz"),
    Channel("univ_batna", "Hadj Lakhdar University, Batna 1",
            "universite", "Batna", ("technique", "education"),
            80, 32_000, 21, 0.55, ""),
    Channel("univ_ouargla", "Kasdi Merbah University, Ouargla",
            "universite", "Ouargla", ("technique", "education"),
            70, 32_000, 24, 0.55, "https://www.univ-ouargla.dz",
            "The southern pool: decisive for a Saharan site, where hiring from "
            "the North fails on mobility."),
    Channel("univ_blida", "Saad Dahlab University, Blida 1",
            "universite", "Blida", ("technique", "encadrement", "client"),
            90, 34_000, 21, 0.58, "https://www.univ-blida.dz"),
]

# Vocational training: the public CFPA / INSFP network (Ministry of Vocational
# Training). The real pool for operational trades, heavily under-used.
_VOCATIONAL = [
    Channel("cfpa_local", "CFPA network, vocational training centres (wilaya)",
            "formation", "National", ("operations", "terrain", "client", "technique"),
            110, 18_000, 14, 0.64, "https://www.mfep.gov.dz",
            "One CFPA per daira. Logistics, driving, warehousing and reception "
            "courses. The cheapest channel per hire for operational trades."),
    Channel("insfp", "INSFP network, national specialised institutes",
            "formation", "National", ("technique", "operations", "encadrement"),
            75, 22_000, 16, 0.68, "https://www.mfep.gov.dz",
            "Senior-technician level. The right channel when CFPA is too junior "
            "and university too theoretical."),
    Channel("apprentissage", "MFEP apprenticeship contracts",
            "formation", "National", ("operations", "terrain", "client"),
            60, 12_000, 30, 0.72, "https://www.mfep.gov.dz",
            "The apprentice is trained in the real job, then hired. Longer lead "
            "time, but the best 12-month retention of any channel."),
]

# Algerian agencies and job sites.
_JOB_MARKET = [
    Channel("anem", "ANEM, National Employment Agency",
            "institution", "National", ("operations", "terrain", "client", "technique"),
            180, 0, 12, 0.42, "https://www.anem.dz",
            "Public and free, and a must: employment-support schemes go through ANEM."),
    Channel("emploitic", "Emploitic.com",
            "emploi", "National", ("client", "encadrement", "technique", "operations"),
            220, 55_000, 7, 0.48, "https://www.emploitic.com",
            "The largest Algerian job site. High volume, sorting needed: that is "
            "where automatic matching pays."),
    Channel("emploipartner", "Emploipartner",
            "emploi", "National", ("encadrement", "client", "technique"),
            90, 35_000, 9, 0.52, "https://www.emploipartner.com",
            "More oriented to managers and qualified profiles."),
    Channel("linkedin", "LinkedIn, search and ads",
            "emploi", "National", ("encadrement", "technique", "client"),
            70, 60_000, 10, 0.66, "https://www.linkedin.com",
            "The only effective channel for experienced managers. Expensive per "
            "candidate, useless for operational trades."),
    Channel("reseaux_sociaux", "Facebook job groups (wilaya)",
            "emploi", "National", ("operations", "terrain", "client"),
            250, 5_000, 4, 0.28, "",
            "Immediate volume, almost free, low quality: use only with automatic "
            "application screening."),
    Channel("cooptation", "Employee referrals (referral bonus)",
            "institution", "National", ("operations", "terrain", "client", "technique",
                                        "encadrement", "education"),
            35, 25_000, 6, 0.74, "",
            "Staff know the job and the site. Best retention, controlled cost, "
            "volume capped by headcount."),
]

CHANNELS = {c.key: c for c in (_UNIVERSITIES + _VOCATIONAL + _JOB_MARKET)}


@dataclass(frozen=True)
class PartnerProfile:
    """
    A type of partner or relay to look for. Deliberately without names of
    people: what to look for, where, and what to ask. Verification stays human.
    """
    key: str
    label: str
    where: str
    criteria: tuple
    ask: str
    families: tuple


PARTNER_PROFILES = [
    PartnerProfile(
        "club_etudiant", "Student club or programme association",
        "Facebook and Instagram pages of the target university's science clubs "
        "and programme associations; the internship office lists them.",
        ("Active in the last 6 months (dated events)",
         "Programme aligned with the role",
         "A reachable contact and an official school account"),
        "Co-host a careers day or CV workshop on campus, collecting applications "
        "on the day.",
        ("technique", "encadrement", "education"),
    ),
    PartnerProfile(
        "communaute_tech", "Local tech community",
        "Developer meetups and communities in the big cities (Algiers, Oran, "
        "Constantine); public events are posted on Meetup, LinkedIn and Facebook.",
        ("Regular, public meetings",
         "Local audience, not a diaspora community",
         "Technical theme matching the need"),
        "Sponsor a session and present a real technical case, not a job ad: "
        "hiring follows credibility.",
        ("technique", "encadrement"),
    ),
    PartnerProfile(
        "createur_metier", "Trade content creator (not a generalist)",
        "Search by trade keywords in Arabic and French on TikTok, Instagram and "
        "LinkedIn; filter on an Algerian audience.",
        ("Mostly Algerian, verifiable audience",
         "Content about the trade or career guidance",
         "Real engagement, not just follower count",
         "No public controversy: a partnership commits the brand"),
        "A \"day in the job\" format filmed on site. That is what converts for "
        "operational trades, where a written ad says nothing about the real work.",
        ("operations", "terrain", "client"),
    ),
    PartnerProfile(
        "referent_cfpa", "Contact at a CFPA or INSFP in the wilaya",
        "The wilaya's vocational-training directorate; each centre has a "
        "business-relations officer.",
        ("Centre within 45 minutes of the site",
         "Specialty matching the role",
         "A class graduating within 3 months"),
        "An internship-to-hire agreement on the graduating class, with a site "
        "visit before the course ends.",
        ("operations", "terrain", "technique", "client"),
    ),
    PartnerProfile(
        "ambassadeur_interne", "Internal ambassador (employee)",
        "Your own staff: the longest-serving in the role, with low leaving risk "
        "in the Retention module.",
        ("More than 2 years in the target role",
         "Low leaving risk",
         "Volunteer: a forced ambassador hurts the brand"),
        "A short video testimony and a paid referral. The cheapest, most "
        "credible channel, and the only one competitors cannot copy.",
        ("operations", "terrain", "client", "encadrement", "technique", "education"),
    ),
]

# Plan-model assumptions, named so a client can replace them with real ratios.
APPLICANTS_PER_HIRE = sources.value("applicants_per_hire")
SHORTLIST_RATE = sources.value("sourcing_shortlist_rate")
QUALITY_FLOOR = 0.20           # quality below which a channel no longer converts


@dataclass
class ScoredChannel:
    channel: Channel
    fit: float
    geo: float
    score: int
    expected_applicants: int
    expected_hires: float
    cost_per_hire: Optional[int]
    reasons: list = field(default_factory=list)


def _fit_score(channel: Channel, family: str) -> float:
    if family in channel.families:
        return 1.0
    neighbours = {
        "operations": {"terrain", "technique"},
        "terrain": {"operations"},
        "client": {"encadrement"},
        "encadrement": {"technique", "client"},
        "technique": {"operations", "encadrement"},
        "education": {"encadrement"},
    }
    return 0.45 if channel.families and set(channel.families) & neighbours.get(family, set()) else 0.0


def _level_score(channel: Channel, family: str) -> float:
    """
    Qualification-level fit. Sourcing an operational role at a university is not
    neutral: the graduate takes the job for lack of better and leaves as soon as
    they can. One of the most expensive, most avoidable causes of turnover.
    """
    level = FAMILY_LEVEL.get(family, "mixte")
    if level == "professionnel" and channel.kind == "universite":
        return 0.25
    if level == "superieur" and channel.kind == "formation":
        return 0.55
    return 1.0


def _geo_score(channel: Channel, wilaya: str) -> float:
    if channel.is_national:
        return 0.72
    if channel.wilaya == wilaya:
        return 1.0
    if region_of(channel.wilaya) == region_of(wilaya):
        return 0.55
    return 0.18


def rank_channels(role_key: str, wilaya: str, headcount: int = 10, *,
                  urgency_days: int = 45, budget_dzd: Optional[int] = None) -> list:
    """Rank sourcing channels for a role, wilaya and volume. Deterministic."""
    family = ROLE_FAMILY.get(role_key, "operations")
    out = []

    for ch in CHANNELS.values():
        fit = _fit_score(ch, family)
        if fit <= 0:
            continue
        geo = _geo_score(ch, wilaya)
        level = _level_score(ch, family)

        applicants = ch.volume * fit * (0.55 + 0.45 * geo)
        effective_quality = ch.quality * (0.6 + 0.4 * fit) * level
        hires = 0.0
        if effective_quality >= QUALITY_FLOOR:
            hires = applicants * SHORTLIST_RATE * effective_quality

        cost_per_hire = int(ch.cost_dzd / hires) if hires >= 0.5 and ch.cost_dzd else (
            0 if ch.cost_dzd == 0 and hires >= 0.5 else None)

        speed = 1.0 if ch.lead_days <= urgency_days else max(
            0.0, 1.0 - (ch.lead_days - urgency_days) / max(urgency_days, 1))

        cph = cost_per_hire if cost_per_hire is not None else 400_000
        cost_eff = max(0.0, 1.0 - min(cph, 400_000) / 400_000)

        score = (0.30 * fit + 0.19 * geo + 0.16 * ch.quality + 0.13 * level
                 + 0.12 * speed + 0.10 * cost_eff) * 100

        if budget_dzd is not None and ch.cost_dzd > budget_dzd:
            score *= 0.55      # over budget: demoted, not removed

        reasons = []
        if fit >= 1.0:
            reasons.append(f"Feeds the \"{FAMILIES[family]}\" family directly")
        elif fit > 0:
            reasons.append("Neighbouring job family, pool partly suited")
        if ch.wilaya == wilaya:
            reasons.append(f"Based in {wilaya}: no mobility problem")
        elif not ch.is_national and region_of(ch.wilaya) != region_of(wilaya):
            reasons.append(f"Out of region ({ch.wilaya}): check mobility before contact")
        if ch.lead_days > urgency_days:
            reasons.append(f"Lead time {ch.lead_days} d, beyond the need ({urgency_days} d)")
        if ch.cost_dzd == 0:
            reasons.append("Free channel")
        if level < 1.0 and ch.kind == "universite":
            reasons.append("Overqualified for this role: risk of a quick departure")
        elif level < 1.0:
            reasons.append("Training level below the target role")
        if budget_dzd is not None and ch.cost_dzd > budget_dzd:
            reasons.append("Above the stated budget")

        out.append(ScoredChannel(
            channel=ch, fit=round(fit, 2), geo=round(geo, 2), score=int(round(score)),
            expected_applicants=int(round(applicants)),
            expected_hires=round(hires, 1), cost_per_hire=cost_per_hire,
            reasons=reasons,
        ))

    return sorted(out, key=lambda s: (s.score, s.expected_hires), reverse=True)


def build_plan(scored: list, headcount: int) -> dict:
    """Stack the best channels until the need is covered, then cost the plan."""
    picked, hires, cost = [], 0.0, 0
    for s in scored:
        if hires >= headcount:
            break
        if s.expected_hires < 0.5:
            continue
        picked.append(s)
        hires += s.expected_hires
        cost += s.channel.cost_dzd

    covered = min(hires, float(headcount))
    return {
        "channels": picked,
        "expected_hires": round(hires, 1),
        "coverage_pct": int(round(min(hires / headcount, 1.0) * 100)) if headcount else 0,
        "total_cost": cost,
        "cost_per_hire": int(cost / covered) if covered >= 1 else None,
        "lead_days": max((s.channel.lead_days for s in picked), default=0),
        "gap": max(0.0, round(headcount - hires, 1)),
    }


_KIND_LABEL = {"universite": "University", "formation": "Vocational",
               "emploi": "Job site", "institution": "Institution"}


def rank_frame(scored: list) -> pd.DataFrame:
    """The ranking as a table, ready for the UI and export."""
    return pd.DataFrame([{
        "Rank": i,
        "Channel": s.channel.name,
        "Type": _KIND_LABEL[s.channel.kind],
        "Wilaya": s.channel.wilaya,
        "Score": s.score,
        "Expected applications": s.expected_applicants,
        "Expected hires": s.expected_hires,
        "Campaign cost (DZD)": s.channel.cost_dzd,
        "Cost per hire (DZD)": s.cost_per_hire if s.cost_per_hire is not None else 0,
        "Lead time (d)": s.channel.lead_days,
    } for i, s in enumerate(scored, 1)])


def partner_profiles_for(role_key: str) -> list:
    """Partner profiles relevant to the role's family."""
    family = ROLE_FAMILY.get(role_key, "operations")
    return [p for p in PARTNER_PROFILES if family in p.families]


_SYSTEM = (
    "You are the recruitment lead of an Algerian company. You write professional, "
    "direct, short English. You never promise a salary, headcount or date you were "
    "not given. You invent no person's name. No superlatives, no empty phrases."
)


def _fallback_message(channel: Channel, role_label: str, company: str,
                      headcount: int, wilaya: str) -> str:
    """Deterministic template, used without an AI key."""
    return (
        f"Subject: Recruitment partnership, {role_label} ({wilaya})\n\n"
        f"Dear Sir or Madam,\n\n"
        f"{company} is hiring {headcount} {role_label.lower()} at its {wilaya} "
        f"site and would like to establish contact with {channel.name}.\n\n"
        f"Concretely, we offer:\n"
        f"- a presentation of the job and the site to your graduates;\n"
        f"- an on-site recruitment session, dates to agree;\n"
        f"- individual feedback to every candidate we meet.\n\n"
        f"Could you tell us who handles business relations, and the calendar of "
        f"your next graduating classes?\n\n"
        f"Kind regards,\n{company}, Human Resources"
    )


def draft_outreach(channel: Channel, role_key: str, company: str, headcount: int,
                   wilaya: str, *, use_ai: bool = True) -> dict:
    """Write the outreach message for a channel. Always returns a message."""
    role_label = labour_dz.ROLES[role_key].label if role_key in labour_dz.ROLES else role_key
    fallback = _fallback_message(channel, role_label, company, headcount, wilaya)

    if not use_ai or not any(ai.providers_available().values()):
        return {"text": fallback, "method": "template"}

    prompt = (
        f"Write an outreach email, 150 words max, from the company \"{company}\" "
        f"to \"{channel.name}\" ({_KIND_LABEL[channel.kind]}, {channel.wilaya}).\n"
        f"Goal: hire {headcount} people as \"{role_label}\" at the {wilaya} site.\n"
        f"Context on this channel: {channel.note or 'none'}\n\n"
        f"Constraints: start with a \"Subject:\" line. Propose one precise, doable "
        f"action. End with a question that invites a reply. Invent no salary, date "
        f"or person's name."
    )
    res = ai.chat(_SYSTEM, prompt, max_tokens=420, temperature=0.4)
    if res.ok and res.text.strip():
        return {"text": res.text.strip(), "method": f"AI ({res.model})"}
    return {"text": fallback, "method": "template (AI unavailable)"}


if __name__ == "__main__":
    print("Sourcing and employer brand, self check\n")
    ranked = rank_channels("sorter", "Alger", headcount=25, urgency_days=30)
    print(rank_frame(ranked).head(8).to_string(index=False))
    plan = build_plan(ranked, 25)
    assert plan["channels"] and plan["coverage_pct"] > 0
    print(f"\n  Plan: {len(plan['channels'])} channels, coverage {plan['coverage_pct']}%, "
          f"cost {plan['total_cost']:,} DZD, lead {plan['lead_days']} d")
    print(rank_frame(rank_channels("supervisor", "Ouargla", 4)).head(4).to_string(index=False))
    print(draft_outreach(CHANNELS["cfpa_local"], "sorter", "Demo company", 25, "Alger",
                         use_ai=False)["text"][:300])
