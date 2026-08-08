"""
dashboard.py
------------
WorkForce.dz , la plateforme RH et de planification par l'IA, conçue pour le
droit du travail algérien.

Lancer :
    streamlit run dashboard.py
"""

import streamlit as st

from core import industry

st.set_page_config(
    page_title="WorkForce.dz",
    page_icon=":material/hub:",
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
        st.Page("app_pages/sourcing_view.py", title="Sourcing & marque employeur",
                icon=":material/travel_explore:"),
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
        st.Page("app_pages/copilot_decision.py", title="Copilote décisionnel",
                icon=":material/neurology:"),
        st.Page("app_pages/hr_copilot.py", title="Copilote RH",
                icon=":material/smart_toy:"),
        st.Page("app_pages/assistant.py", title="Assistant opérations",
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

from core import appdata, nav, tour  # noqa: E402  , après st.set_page_config

appdata.init_state()
appdata.inject_theme()
nav.render(pages, _nav)
_nav.run()
tour.maybe_run(_nav)
