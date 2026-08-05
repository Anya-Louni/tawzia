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
    initial_sidebar_state="expanded",
)

# Mode secteur : adapte l'app au prospect via ?industry=hotel|delivery|...
industry.apply()
_ind = industry.current()

# "Aéroport" est un module sectoriel : affiché seulement pour l'édition aéroport
# (ou l'app complète), pour ne pas encombrer un prospect hôtel ou livraison.
_schedule = [
    st.Page("app_pages/forecast_view.py", title="Prévision de la demande",
            icon=":material/trending_up:"),
    st.Page("app_pages/roster_view.py", title="Planning & coût",
            icon=":material/groups:"),
]
if _ind["show_airport"]:
    _schedule.append(st.Page("app_pages/airport_ops.py", title="Aéroport",
                             icon=":material/flight:"))

pages = {
    "Accueil": [
        st.Page("app_pages/guide.py", title="Guide",
                icon=":material/help:", default=True),
        st.Page("app_pages/command_centre.py", title="Tableau de bord",
                icon=":material/dashboard:"),
    ],
    "Recrutement & équipe": [
        st.Page("app_pages/recruiting.py", title="Recrutement",
                icon=":material/person_search:"),
        st.Page("app_pages/people.py", title="Employés",
                icon=":material/badge:"),
        st.Page("app_pages/requests_view.py", title="Demandes & présence",
                icon=":material/how_to_reg:"),
    ],
    "Planification": _schedule,
    "Paie & conformité": [
        st.Page("app_pages/payroll_view.py", title="Paie",
                icon=":material/receipt_long:"),
        st.Page("app_pages/inspector_sim.py", title="Simulateur d'inspection",
                icon=":material/gavel:"),
        st.Page("app_pages/jo_watch.py", title="Veille Journal Officiel",
                icon=":material/policy:"),
    ],
    "Fidélisation": [
        st.Page("app_pages/attrition_view.py", title="Risque de départ",
                icon=":material/trending_down:"),
        st.Page("app_pages/retention_negotiator.py", title="Négociateur de rétention",
                icon=":material/handshake:"),
    ],
    "Copilote IA": [
        st.Page("app_pages/hr_copilot.py", title="Copilote RH",
                icon=":material/smart_toy:"),
        st.Page("app_pages/assistant.py", title="Assistant opérations",
                icon=":material/forum:"),
    ],
    "Preuves & business": [
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

st.navigation(pages).run()
