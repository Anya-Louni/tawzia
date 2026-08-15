"""
dashboard.py
------------
Tawzia , la plateforme RH et de planification par l'IA, conçue pour le droit du
travail algérien. Le nom vient de l'arabe توزيع, « répartition » : affecter les
bonnes personnes aux bons postes est le geste que fait le moteur.

Lancer :
    streamlit run dashboard.py
"""

from pathlib import Path

import streamlit as st

from core import industry

_ICON = Path(__file__).parent / "assets" / "brand" / "tawzia-mark.svg"

st.set_page_config(
    page_title="Tawzia",
    page_icon=str(_ICON) if _ICON.exists() else ":material/groups:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Mode secteur : adapte l'app au prospect via ?industry=hotel|delivery|...
industry.apply()
_ind = industry.current()

# "Aéroport" est un module sectoriel : affiché seulement pour l'édition aéroport
# (ou l'app complète), pour ne pas encombrer un prospect hôtel ou livraison.
# Planification. "Aéroport" is a sector module: it appears only in the airport
# edition (?industry=airport), so the default platform stays sector-neutral and
# reads as built for any company, not for airports.
_planification = [
    st.Page("app_pages/forecast_view.py", title="Prévision de la demande",
            icon=":material/trending_up:"),
    st.Page("app_pages/roster_view.py", title="Planning & coût",
            icon=":material/groups:"),
    st.Page("app_pages/sector_view.py", title="Analyse sectorielle",
            icon=":material/insights:"),
]
if _ind["show_airport"]:
    _planification.append(st.Page("app_pages/airport_ops.py", title="Aéroport",
                                  icon=":material/flight:"))

# Seven intent-based sections, each mapping to one job a manager does. The AI
# decision tools (KPI, scenarios, the three copilots, the company-data import)
# live together in "Décision IA" instead of being scattered, and team-risk work
# sits with the team it concerns.
pages = {
    "Accueil": [
        st.Page("app_pages/guide.py", title="Accueil",
                icon=":material/home:", default=True),
        st.Page("app_pages/command_centre.py", title="Tableau de bord",
                icon=":material/dashboard:"),
    ],
    "Recrutement": [
        # Sourcing d'abord : c'est l'étape zéro, avant qu'un CV existe.
        # L'offre se rédige avant de sourcer : c'est elle qui dit quoi publier
        # et sur quels critères le vivier sera trié.
        st.Page("app_pages/job_post_view.py", title="Rédiger une offre",
                icon=":material/edit_note:"),
        st.Page("app_pages/sourcing_view.py", title="Sourcing & marque employeur",
                icon=":material/travel_explore:"),
        # Puis le vivier : le classement de toutes les candidatures reçues, qui
        # est le geste quotidien du recrutement. Les deux écrans suivants
        # traitent une candidature à la fois.
        st.Page("app_pages/talent_pool.py", title="Vivier de candidats",
                icon=":material/groups_2:"),
        st.Page("app_pages/recruiting.py", title="Évaluation de CV",
                icon=":material/person_search:"),
        st.Page("app_pages/matching_view.py", title="Appariement CV/poste",
                icon=":material/join_inner:"),
    ],
    "Équipe & présence": [
        st.Page("app_pages/people.py", title="Employés",
                icon=":material/badge:"),
        st.Page("app_pages/requests_view.py", title="Demandes & présence",
                icon=":material/how_to_reg:"),
        st.Page("app_pages/skills_view.py", title="Compétences & mobilité",
                icon=":material/school:"),
        st.Page("app_pages/attrition_view.py", title="Risque de départ",
                icon=":material/trending_down:"),
        st.Page("app_pages/retention_negotiator.py", title="Négociateur de rétention",
                icon=":material/handshake:"),
    ],
    "Planification": _planification,
    "Paie & conformité": [
        st.Page("app_pages/payroll_view.py", title="Paie",
                icon=":material/receipt_long:"),
        # Les échéances passent tôt dans la section : c'est la seule page qui
        # porte une date butoir, donc la seule qui coûte de l'argent si on
        # l'ouvre trop tard.
        st.Page("app_pages/deadlines_view.py", title="Échéances & déclarations",
                icon=":material/event_available:"),
        st.Page("app_pages/anomalies_view.py", title="Détection d'anomalies",
                icon=":material/error:"),
        st.Page("app_pages/document_check.py", title="Contrôle de documents",
                icon=":material/document_scanner:"),
        st.Page("app_pages/inspector_sim.py", title="Simulateur d'inspection",
                icon=":material/gavel:"),
        st.Page("app_pages/jo_watch.py", title="Veille Journal Officiel",
                icon=":material/policy:"),
    ],
    "Décision IA": [
        st.Page("app_pages/kpi_view.py", title="Tableau de KPI",
                icon=":material/monitoring:"),
        st.Page("app_pages/scenarios_view.py", title="Simulateur de scénarios",
                icon=":material/tune:"),
        # Un seul assistant. Les trois écrans de conversation d'avant posaient
        # la même question à trois endroits : le routeur de core/copilot.py
        # choisit maintenant le domaine tout seul.
        st.Page("app_pages/assistant.py", title="Assistant",
                icon=":material/forum:"),
        st.Page("app_pages/company_data_view.py", title="Données de l'entreprise",
                icon=":material/database:"),
    ],
    "Preuves & sources": [
        st.Page("app_pages/evidence.py", title="Preuves",
                icon=":material/fact_check:"),
        st.Page("app_pages/calendar_view.py", title="Calendrier algérien",
                icon=":material/calendar_month:"),
        st.Page("app_pages/business_case.py", title="Analyse économique",
                icon=":material/payments:"),
        st.Page("app_pages/sources_view.py", title="Sources & hypothèses",
                icon=":material/menu_book:"),
        # La confidentialité vit avec les preuves : c'est la même promesse,
        # « voilà ce que nous faisons vraiment de vos données et de vos chiffres ».
        st.Page("app_pages/privacy_view.py", title="Confidentialité",
                icon=":material/lock:"),
    ],
}

# Navigation faite main (voir core/nav.py) : les sept sections restent visibles
# en grand, et cliquer sur l'une d'elles ouvre un sélecteur qui assombrit le
# reste de l'écran. La navigation native `position="top"` est écartée , elle
# replie toutes les sections dans un menu « N more » dès qu'elle ne parvient pas
# à les mesurer, ce qui est un risque inacceptable sur une démonstration
# projetée. `position="hidden"` désactive donc le rendu natif, et tout ce qui est
# écrit avant `.run()` s'affiche en haut de la page (voir DESIGN.md).
_nav = st.navigation(pages, position="hidden")

from core import appdata, gate, nav, tour  # noqa: E402  , après st.set_page_config

appdata.init_state()
appdata.inject_theme()

# Le portillon d'accès : exigé seulement si un APP_PASSWORD est configuré, pour
# qu'une démonstration ne se heurte pas à un écran de connexion inutile. Placé
# après le thème, afin que l'écran de connexion porte déjà la marque.
if not gate.require_access():
    st.stop()
nav.render(pages, _nav)
_nav.run()
tour.maybe_run(_nav)
