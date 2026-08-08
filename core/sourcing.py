"""
core/sourcing.py
----------------
Sourcing & marque employeur , l'étape zéro du recrutement.

Le reste de la suite prend le candidat une fois qu'il a postulé : évaluation de
CV, appariement, entretien, embauche, paie, rétention. Ce module traite la
question posée *avant* toutes les autres : **d'où viennent les candidats ?**

Ce qui est réel, ce qui est modélisé
====================================
C'est la distinction qui compte pour un jury RH, et elle est appliquée
structurellement ici :

  * **Le répertoire de canaux est réel.** Universités, écoles nationales,
    réseau de la formation professionnelle, agences et sites d'emploi
    algériens : ce sont des institutions existantes et vérifiables, nommées
    telles quelles. Rien n'est inventé par un modèle de langage.
  * **Les volumes, coûts et délais sont modélisés.** Aucun opérateur algérien
    ne publie son coût par embauche par canal. Les chiffres portés par chaque
    canal sont des hypothèses de cadrage, marquées comme telles, qu'un pilote
    remplace par les vrais chiffres du client dès la première campagne.
  * **Aucune liste de personnes n'est générée.** Un modèle qui « trouve des
    influenceurs » invente des noms plausibles et faux , le pire résultat
    possible face à un DRH qui connaît son écosystème. À la place, le module
    produit des **profils de partenaires à rechercher** (critères, où chercher,
    quoi demander), et l'IA rédige la prise de contact. Les noms se vérifient,
    ils ne se devinent pas.

L'IA (Groq) n'intervient qu'à la fin, pour rédiger le message d'approche à
partir d'un canal et d'un poste déjà choisis par le moteur. Le classement, lui,
est déterministe : mêmes entrées, même résultat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from . import ai, labour_dz, sources

# ---------------------------------------------------------------------------
# Familles de métiers
# ---------------------------------------------------------------------------
# Un canal ne recrute pas « un poste », il alimente une famille de métiers.
# Cette table relie les rôles de core/labour_dz aux viviers réels.

FAMILIES = {
    "operations": "Opérations & logistique",
    "terrain": "Terrain & conduite",
    "client": "Relation client & accueil",
    "encadrement": "Encadrement & pilotage",
    "technique": "Technique & maintenance",
    "education": "Enseignement & vie scolaire",
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

# Niveau de qualification typiquement requis, par famille. Sert à orienter vers
# l'université (bac+3 et plus) ou vers la formation professionnelle.
FAMILY_LEVEL = {
    "operations": "professionnel",
    "terrain": "professionnel",
    "client": "mixte",
    "encadrement": "superieur",
    "technique": "mixte",
    "education": "superieur",
}

# ---------------------------------------------------------------------------
# Régions , pour la proximité géographique
# ---------------------------------------------------------------------------

REGIONS = {
    "centre": ["Alger", "Blida", "Tizi Ouzou", "Bejaia", "Djelfa", "Medea", "Boumerdes"],
    "ouest": ["Oran", "Tlemcen", "Mostaganem", "Sidi Bel Abbes", "Chlef", "Bechar"],
    "est": ["Constantine", "Annaba", "Setif", "Batna", "Skikda", "Biskra"],
    "sud": ["Ouargla", "Ghardaia", "Tamanrasset", "Adrar", "Illizi", "El Oued"],
}


def region_of(wilaya: str) -> str:
    for reg, wilayas in REGIONS.items():
        if wilaya in wilayas:
            return reg
    return "centre"


# ---------------------------------------------------------------------------
# Le répertoire , institutions réelles
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Channel:
    """
    Un canal de sourcing réel.

    `name`, `kind`, `wilaya` et `url` décrivent une institution existante.
    `volume`, `cost_dzd`, `lead_days` et `quality` sont des **hypothèses de
    cadrage** (voir le docstring du module) : ordres de grandeur pour comparer
    les canaux entre eux, pas des chiffres mesurés.
    """
    key: str
    name: str
    kind: str                 # universite | formation | emploi | institution
    wilaya: str               # wilaya d'implantation, ou "National"
    families: tuple           # familles de métiers alimentées
    volume: int               # candidatures attendues par campagne (hypothèse)
    cost_dzd: int             # coût d'une campagne (hypothèse)
    lead_days: int            # délai avant première short-list (hypothèse)
    quality: float            # adéquation moyenne attendue 0..1 (hypothèse)
    url: str = ""
    note: str = ""

    @property
    def is_national(self) -> bool:
        return self.wilaya == "National"


# Universités et écoles nationales. Noms et implantations réels.
_UNIVERSITIES = [
    Channel("usthb", "USTHB , Univ. des Sciences et de la Technologie Houari Boumediene",
            "universite", "Alger", ("technique", "encadrement"),
            140, 45_000, 21, 0.62, "https://www.usthb.dz",
            "Le plus gros vivier scientifique et technique du pays."),
    Channel("esi", "ESI Alger , École nationale Supérieure d'Informatique",
            "universite", "Alger", ("technique", "encadrement"),
            60, 40_000, 18, 0.78, "https://www.esi.dz",
            "Filière informatique la plus sélective. Faible volume, forte qualité."),
    Channel("enp", "ENP , École Nationale Polytechnique d'El Harrach",
            "universite", "Alger", ("technique", "encadrement"),
            55, 40_000, 18, 0.76, "https://www.enp.edu.dz",
            "Ingénierie généraliste, profil encadrement technique."),
    Channel("esc_alger", "ESC Alger , École Supérieure de Commerce (Koléa)",
            "universite", "Alger", ("encadrement", "client"),
            70, 38_000, 20, 0.70, "https://www.esc-alger.dz",
            "Commerce, gestion et relation client, niveau encadrement."),
    Channel("univ_oran", "Université d'Oran 1 Ahmed Ben Bella",
            "universite", "Oran", ("technique", "encadrement", "client"),
            120, 40_000, 21, 0.60, "https://www.univ-oran1.dz",
            "Principal pôle universitaire de l'Ouest."),
    Channel("univ_constantine", "Université Constantine 1 Frères Mentouri",
            "universite", "Constantine", ("technique", "encadrement", "education"),
            120, 40_000, 21, 0.60, "https://www.umc.edu.dz",
            "Principal pôle universitaire de l'Est."),
    Channel("univ_annaba", "Université Badji Mokhtar , Annaba",
            "universite", "Annaba", ("technique", "encadrement"),
            95, 36_000, 21, 0.58, "https://www.univ-annaba.dz",
            "Bassin industriel et portuaire de l'Est."),
    Channel("univ_setif", "Université Ferhat Abbas , Sétif 1",
            "universite", "Setif", ("technique", "encadrement", "education"),
            95, 36_000, 21, 0.58, "https://www.univ-setif.dz",
            "Pôle des Hauts-Plateaux, fort en sciences et technologie."),
    Channel("univ_tlemcen", "Université Abou Bekr Belkaïd , Tlemcen",
            "universite", "Tlemcen", ("encadrement", "education", "client"),
            80, 34_000, 21, 0.56, "https://www.univ-tlemcen.dz"),
    Channel("univ_bejaia", "Université Abderrahmane Mira , Béjaïa",
            "universite", "Bejaia", ("technique", "encadrement", "client"),
            85, 34_000, 21, 0.57, "https://www.univ-bejaia.dz"),
    Channel("ummto", "Université Mouloud Mammeri , Tizi Ouzou",
            "universite", "Tizi Ouzou", ("technique", "encadrement", "education"),
            85, 34_000, 21, 0.57, "https://www.ummto.dz"),
    Channel("univ_batna", "Université Hadj Lakhdar , Batna 1",
            "universite", "Batna", ("technique", "education"),
            80, 32_000, 21, 0.55, ""),
    Channel("univ_ouargla", "Université Kasdi Merbah , Ouargla",
            "universite", "Ouargla", ("technique", "education"),
            70, 32_000, 24, 0.55, "https://www.univ-ouargla.dz",
            "Le vivier du Sud , décisif pour un site saharien, où le "
            "recrutement depuis le Nord échoue sur la mobilité."),
    Channel("univ_blida", "Université Saad Dahlab , Blida 1",
            "universite", "Blida", ("technique", "encadrement", "client"),
            90, 34_000, 21, 0.58, "https://www.univ-blida.dz"),
]

# Formation professionnelle : le réseau public CFPA / INSFP, sous tutelle du
# Ministère de la Formation et de l'Enseignement Professionnels. C'est le vivier
# réel des métiers opérationnels, très largement sous-utilisé par les
# recruteurs privés qui publient tout sur les mêmes sites d'emploi.
_VOCATIONAL = [
    Channel("cfpa_local", "Réseau CFPA , Centres de Formation Professionnelle (wilaya)",
            "formation", "National", ("operations", "terrain", "client", "technique"),
            110, 18_000, 14, 0.64, "https://www.mfep.gov.dz",
            "Un CFPA par daïra. Formations logistique, conduite, magasinage, "
            "accueil. Le canal le moins cher par embauche sur les métiers "
            "opérationnels."),
    Channel("insfp", "Réseau INSFP , Instituts Nationaux Spécialisés",
            "formation", "National", ("technique", "operations", "encadrement"),
            75, 22_000, 16, 0.68, "https://www.mfep.gov.dz",
            "Niveau technicien supérieur. Le bon canal quand le CFPA est trop "
            "junior et l'université trop théorique."),
    Channel("apprentissage", "Contrats d'apprentissage MFEP",
            "formation", "National", ("operations", "terrain", "client"),
            60, 12_000, 30, 0.72,
            "https://www.mfep.gov.dz",
            "L'apprenti est formé au poste réel puis embauché. Délai plus long, "
            "mais la meilleure rétention à 12 mois de tous les canaux."),
]

# Agences et sites d'emploi algériens.
_JOB_MARKET = [
    Channel("anem", "ANEM , Agence Nationale de l'Emploi",
            "institution", "National", ("operations", "terrain", "client", "technique"),
            180, 0, 12, 0.42, "https://www.anem.dz",
            "Service public, gratuit, obligatoire à connaître : c'est aussi par "
            "l'ANEM que passent les dispositifs d'aide à l'emploi."),
    Channel("emploitic", "Emploitic.com",
            "emploi", "National", ("client", "encadrement", "technique", "operations"),
            220, 55_000, 7, 0.48, "https://www.emploitic.com",
            "Le plus grand site d'emploi algérien. Volume élevé, tri à faire , "
            "c'est exactement là que l'appariement automatique paie."),
    Channel("emploipartner", "Emploipartner",
            "emploi", "National", ("encadrement", "client", "technique"),
            90, 35_000, 9, 0.52, "https://www.emploipartner.com",
            "Plus orienté cadres et profils qualifiés."),
    Channel("linkedin", "LinkedIn , recherche et annonces",
            "emploi", "National", ("encadrement", "technique", "client"),
            70, 60_000, 10, 0.66, "https://www.linkedin.com",
            "Le seul canal efficace sur l'encadrement expérimenté. Cher au "
            "candidat, inutile sur les métiers opérationnels."),
    Channel("reseaux_sociaux", "Groupes emploi Facebook (wilaya)",
            "emploi", "National", ("operations", "terrain", "client"),
            250, 5_000, 4, 0.28,
            "",
            "Volume immédiat et quasi gratuit, qualité faible : à n'utiliser "
            "que couplé à un filtrage automatique des candidatures."),
    Channel("cooptation", "Cooptation interne (prime de parrainage)",
            "institution", "National", ("operations", "terrain", "client", "technique",
                                        "encadrement", "education"),
            35, 25_000, 6, 0.74, "",
            "Les salariés connaissent le métier et le site. Meilleure "
            "rétention, coût maîtrisé, mais volume plafonné par l'effectif."),
]

CHANNELS = {c.key: c for c in (_UNIVERSITIES + _VOCATIONAL + _JOB_MARKET)}


# ---------------------------------------------------------------------------
# Profils de partenaires , des critères, jamais des noms inventés
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PartnerProfile:
    """
    Un *type* de partenaire ou de relais d'influence à aller chercher.

    Volontairement dépourvu de noms de personnes : un nom d'influenceur produit
    par un modèle de langage est plausible et faux une fois sur deux. Le module
    dit quoi chercher, où, et quoi demander , la vérification reste humaine.
    """
    key: str
    label: str
    where: str                # où trouver ce partenaire
    criteria: tuple           # critères de sélection vérifiables
    ask: str                  # ce qu'on lui demande concrètement
    families: tuple


PARTNER_PROFILES = [
    PartnerProfile(
        "club_etudiant", "Club étudiant / association de filière",
        "Pages Facebook et Instagram des clubs scientifiques et associations "
        "de filière de l'université ciblée ; le service des stages de "
        "l'établissement les recense.",
        ("Actif sur les 6 derniers mois (événements datés)",
         "Filière alignée sur le poste",
         "Un référent joignable et un compte officiel de l'établissement"),
        "Co-organiser une journée métier ou un atelier CV sur le campus, avec "
        "collecte de candidatures le jour même.",
        ("technique", "encadrement", "education"),
    ),
    PartnerProfile(
        "communaute_tech", "Communauté technique locale",
        "Meetups et communautés de développeurs des grandes villes "
        "(Alger, Oran, Constantine) ; les événements publics sont annoncés "
        "sur Meetup, LinkedIn et Facebook.",
        ("Réunions régulières et publiques",
         "Audience locale, pas une communauté diaspora",
         "Thème technique correspondant au besoin"),
        "Sponsoriser une session et présenter un cas technique réel, pas une "
        "offre d'emploi : le recrutement suit la crédibilité.",
        ("technique", "encadrement"),
    ),
    PartnerProfile(
        "createur_metier", "Créateur de contenu métier (pas généraliste)",
        "Recherche par mots-clés métier en arabe et en français sur "
        "TikTok, Instagram et LinkedIn ; filtrer sur une audience algérienne.",
        ("Audience majoritairement algérienne et vérifiable",
         "Contenu lié au métier ou à l'orientation professionnelle",
         "Taux d'engagement réel, pas seulement un nombre d'abonnés",
         "Aucune controverse publique , un partenariat engage la marque"),
        "Un format « une journée dans le poste » tourné sur site. C'est le "
        "contenu qui convertit sur les métiers opérationnels, où l'annonce "
        "écrite ne dit rien du travail réel.",
        ("operations", "terrain", "client"),
    ),
    PartnerProfile(
        "referent_cfpa", "Référent d'un CFPA ou INSFP de la wilaya",
        "Direction de la formation professionnelle de la wilaya ; chaque "
        "centre a un responsable des relations entreprises.",
        ("Centre situé à moins de 45 min du site",
         "Spécialité correspondant au poste",
         "Promotion sortante dans les 3 mois"),
        "Une convention de stage-embauche sur la promotion sortante, avec "
        "visite du site avant la fin de formation.",
        ("operations", "terrain", "technique", "client"),
    ),
    PartnerProfile(
        "ambassadeur_interne", "Ambassadeur interne (salarié)",
        "Vos propres salariés : les plus anciens sur le poste, ceux dont le "
        "risque de départ est faible dans le module Risque de départ.",
        ("Plus de 2 ans d'ancienneté sur le poste visé",
         "Risque de départ faible",
         "Volontaire , un ambassadeur contraint dessert la marque"),
        "Témoignage vidéo court et parrainage rémunéré. Le canal le moins cher "
        "et le plus crédible, et le seul que la concurrence ne peut pas copier.",
        ("operations", "terrain", "client", "encadrement", "technique", "education"),
    ),
]


# ---------------------------------------------------------------------------
# Hypothèses du modèle de plan
# ---------------------------------------------------------------------------
# Exposées comme constantes nommées pour qu'un client les remplace par ses
# vrais ratios dès la première campagne mesurée.

APPLICANTS_PER_HIRE = sources.value("applicants_per_hire")
SHORTLIST_RATE = sources.value("sourcing_shortlist_rate")
QUALITY_FLOOR = 0.20           # qualité en deçà de laquelle un canal ne convertit plus


# ---------------------------------------------------------------------------
# Classement des canaux
# ---------------------------------------------------------------------------

@dataclass
class ScoredChannel:
    channel: Channel
    fit: float                 # adéquation métier 0..1
    geo: float                 # proximité géographique 0..1
    score: int                 # 0..100
    expected_applicants: int
    expected_hires: float
    cost_per_hire: Optional[int]
    reasons: list = field(default_factory=list)


def _fit_score(channel: Channel, family: str) -> float:
    if family in channel.families:
        return 1.0
    # Familles voisines : l'encadrement se recrute aussi dans le technique, etc.
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
    Adéquation du niveau de qualification.

    Sourcer un poste opérationnel dans une université n'est pas neutre : le
    diplômé accepte le poste faute de mieux et repart dès qu'il trouve. C'est
    une des causes de turnover les plus coûteuses et les plus évitables, donc
    elle est pénalisée explicitement plutôt que laissée au hasard du score.
    """
    level = FAMILY_LEVEL.get(family, "mixte")
    if level == "professionnel" and channel.kind == "universite":
        return 0.25          # surqualification : embauche fragile
    if level == "superieur" and channel.kind == "formation":
        return 0.55          # sous-qualifié pour un poste d'encadrement
    return 1.0


def _geo_score(channel: Channel, wilaya: str) -> float:
    if channel.is_national:
        return 0.72          # accessible partout, sans ancrage local
    if channel.wilaya == wilaya:
        return 1.0
    if region_of(channel.wilaya) == region_of(wilaya):
        return 0.55          # même région : mobilité réaliste
    return 0.18              # autre région : la mobilité fait échouer l'embauche


def rank_channels(
    role_key: str,
    wilaya: str,
    headcount: int = 10,
    *,
    urgency_days: int = 45,
    budget_dzd: Optional[int] = None,
) -> list:
    """
    Classer les canaux de sourcing pour un poste, une wilaya et un volume.

    Déterministe : mêmes entrées, même classement. Les volumes et coûts sont
    des hypothèses de cadrage (voir le docstring du module).
    """
    family = ROLE_FAMILY.get(role_key, "operations")
    out = []

    for ch in CHANNELS.values():
        fit = _fit_score(ch, family)
        if fit <= 0:
            continue
        geo = _geo_score(ch, wilaya)
        level = _level_score(ch, family)

        # Volume attendu : le vivier du canal, dégradé par l'adéquation métier
        # et la distance (un candidat lointain postule moins et vient moins).
        applicants = ch.volume * fit * (0.55 + 0.45 * geo)
        # La qualité effective intègre le niveau : un profil surqualifié compte
        # comme une embauche fragile, pas comme une embauche.
        effective_quality = ch.quality * (0.6 + 0.4 * fit) * level
        hires = 0.0
        if effective_quality >= QUALITY_FLOOR:
            hires = applicants * SHORTLIST_RATE * effective_quality

        cost_per_hire = int(ch.cost_dzd / hires) if hires >= 0.5 and ch.cost_dzd else (
            0 if ch.cost_dzd == 0 and hires >= 0.5 else None)

        # Vitesse : pénalise un canal plus lent que l'urgence du besoin.
        speed = 1.0 if ch.lead_days <= urgency_days else max(
            0.0, 1.0 - (ch.lead_days - urgency_days) / max(urgency_days, 1))

        # Efficacité coût, normalisée sur une échelle 0..1 (gratuit = 1).
        cph = cost_per_hire if cost_per_hire is not None else 400_000
        cost_eff = max(0.0, 1.0 - min(cph, 400_000) / 400_000)

        score = (0.30 * fit + 0.19 * geo + 0.16 * ch.quality + 0.13 * level
                 + 0.12 * speed + 0.10 * cost_eff) * 100

        if budget_dzd is not None and ch.cost_dzd > budget_dzd:
            score *= 0.55      # hors budget : rétrogradé, pas supprimé

        reasons = []
        if fit >= 1.0:
            reasons.append(f"Alimente directement la famille « {FAMILIES[family]} »")
        elif fit > 0:
            reasons.append("Famille de métiers voisine, vivier partiellement adapté")
        if ch.wilaya == wilaya:
            reasons.append(f"Implanté à {wilaya} , pas de problème de mobilité")
        elif not ch.is_national and region_of(ch.wilaya) != region_of(wilaya):
            reasons.append(f"Hors région ({ch.wilaya}) , mobilité à vérifier avant contact")
        if ch.lead_days > urgency_days:
            reasons.append(f"Délai {ch.lead_days} j, au-delà du besoin ({urgency_days} j)")
        if ch.cost_dzd == 0:
            reasons.append("Canal gratuit")
        if level < 1.0 and ch.kind == "universite":
            reasons.append("Profil surqualifié pour ce poste , risque de départ rapide")
        elif level < 1.0:
            reasons.append("Niveau de formation en deçà du poste visé")
        if budget_dzd is not None and ch.cost_dzd > budget_dzd:
            reasons.append("Au-dessus du budget indiqué")

        out.append(ScoredChannel(
            channel=ch, fit=round(fit, 2), geo=round(geo, 2), score=int(round(score)),
            expected_applicants=int(round(applicants)),
            expected_hires=round(hires, 1), cost_per_hire=cost_per_hire,
            reasons=reasons,
        ))

    return sorted(out, key=lambda s: (s.score, s.expected_hires), reverse=True)


def build_plan(scored: list, headcount: int) -> dict:
    """
    Composer le plan minimal : empiler les meilleurs canaux jusqu'à couvrir le
    besoin, puis chiffrer coût total, délai et coût par embauche.
    """
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


def rank_frame(scored: list) -> pd.DataFrame:
    """Le classement en table française, prête pour l'UI et l'export."""
    rows = []
    for i, s in enumerate(scored, 1):
        rows.append({
            "Rang": i,
            "Canal": s.channel.name,
            "Type": {"universite": "Université", "formation": "Formation pro",
                     "emploi": "Site d'emploi", "institution": "Institution"}[s.channel.kind],
            "Wilaya": s.channel.wilaya,
            "Score": s.score,
            "Candidatures attendues": s.expected_applicants,
            "Embauches attendues": s.expected_hires,
            "Coût campagne (DZD)": s.channel.cost_dzd,
            "Coût par embauche (DZD)": s.cost_per_hire if s.cost_per_hire is not None else 0,
            "Délai (j)": s.channel.lead_days,
        })
    return pd.DataFrame(rows)


def partner_profiles_for(role_key: str) -> list:
    """Les profils de partenaires pertinents pour la famille du poste."""
    family = ROLE_FAMILY.get(role_key, "operations")
    return [p for p in PARTNER_PROFILES if family in p.families]


# ---------------------------------------------------------------------------
# Rédaction de l'approche (couche IA, facultative)
# ---------------------------------------------------------------------------

_SYSTEM = (
    "Tu es responsable du recrutement d'une entreprise algérienne. Tu écris en "
    "français professionnel, direct et court. Tu ne promets jamais de salaire, "
    "d'effectif ni de date que l'on ne t'a pas donnés. Tu n'inventes aucun nom "
    "de personne. Pas de superlatifs, pas de formules creuses."
)


def _fallback_message(channel: Channel, role_label: str, company: str,
                      headcount: int, wilaya: str) -> str:
    """Modèle déterministe, utilisé sans clé IA (l'app ne doit jamais bloquer)."""
    return (
        f"Objet : Partenariat recrutement , {role_label} ({wilaya})\n\n"
        f"Madame, Monsieur,\n\n"
        f"{company} recrute {headcount} {role_label.lower()} sur son site de "
        f"{wilaya} et souhaite établir un contact avec {channel.name}.\n\n"
        f"Concrètement, nous proposons :\n"
        f"- une présentation du métier et du site auprès de vos sortants ;\n"
        f"- une session de recrutement sur place, dates à convenir ;\n"
        f"- un retour individuel à chaque candidat rencontré.\n\n"
        f"Pourriez-vous nous indiquer la personne en charge des relations "
        f"entreprises, ainsi que le calendrier de vos prochaines sorties de "
        f"promotion ?\n\n"
        f"Cordialement,\n{company} , Ressources Humaines"
    )


def draft_outreach(
    channel: Channel,
    role_key: str,
    company: str,
    headcount: int,
    wilaya: str,
    *,
    use_ai: bool = True,
) -> dict:
    """
    Rédiger le message d'approche pour un canal donné.

    Retourne toujours un message : sans clé IA, un modèle déterministe.
    """
    role_label = labour_dz.ROLES[role_key].label if role_key in labour_dz.ROLES else role_key
    fallback = _fallback_message(channel, role_label, company, headcount, wilaya)

    if not use_ai or not any(ai.providers_available().values()):
        return {"text": fallback, "method": "modèle"}

    prompt = (
        f"Rédige un e-mail de prise de contact, 150 mots maximum, de la part de "
        f"l'entreprise « {company} » vers « {channel.name} » "
        f"({channel.kind}, {channel.wilaya}).\n"
        f"Objectif : recruter {headcount} personnes au poste de « {role_label} » "
        f"sur le site de {wilaya}.\n"
        f"Contexte sur ce canal : {channel.note or 'aucun'}\n\n"
        f"Contraintes : commence par une ligne « Objet : ». Propose une action "
        f"précise et réalisable. Termine par une question qui appelle une réponse. "
        f"N'invente ni salaire, ni date, ni nom de personne."
    )
    res = ai.chat(_SYSTEM, prompt, max_tokens=420, temperature=0.4)
    if res.ok and res.text.strip():
        return {"text": res.text.strip(), "method": f"IA ({res.model})"}
    return {"text": fallback, "method": "modèle (IA indisponible)"}


if __name__ == "__main__":
    print("Sourcing & marque employeur , auto-contrôle\n")
    ranked = rank_channels("sorter", "Alger", headcount=25, urgency_days=30)
    print(rank_frame(ranked).head(8).to_string(index=False))

    plan = build_plan(ranked, 25)
    print(f"\n  Plan : {len(plan['channels'])} canaux, couverture {plan['coverage_pct']}%, "
          f"coût {plan['total_cost']:,} DZD, "
          f"coût/embauche {plan['cost_per_hire']:,} DZD, délai {plan['lead_days']} j")

    print("\n  Un poste d'encadrement à Ouargla classe différemment :")
    print(rank_frame(rank_channels("supervisor", "Ouargla", 4)).head(4).to_string(index=False))

    print(f"\n  Profils de partenaires (agent de tri) : "
          f"{[p.label for p in partner_profiles_for('sorter')]}")
    print("\n  Message (sans IA) :\n")
    print(draft_outreach(CHANNELS["cfpa_local"], "sorter", "Ooredoo", 25, "Alger",
                         use_ai=False)["text"][:400])
