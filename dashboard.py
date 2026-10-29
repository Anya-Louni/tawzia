"""
dashboard.py
------------
Tawzia, the AI HR department built on Algerian labour law. The name comes
from the Arabic توزيع, "distribution": putting the right people in the right
posts is what the engine does.

Run:
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

# Sector mode: tailors the app to a prospect via ?industry=hotel|delivery|...
industry.apply()
_ind = industry.current()

# "Aéroport" is a sector module: it appears only in the airport
# edition (?industry=airport), so the default platform stays sector-neutral and
# reads as built for any company, not for airports.
_planification = [
    st.Page("app_pages/schedule_view.py", title="Planning de la semaine",
            icon=":material/calendar_view_week:"),
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

# Five screens plus Settings. The decision inbox does the work of the other
# four: agents drop every finished task there and the manager signs. The rest
# is for looking at the detail or correcting a card. Page titles are the
# navigation ids (French); core/i18n.py displays them in the chosen language.
pages = {
    "Décisions": [
        st.Page("app_pages/autopilot.py", title="Boîte de décisions",
                icon=":material/inbox:", default=True),
        st.Page("app_pages/self_service.py", title="Guichet salarié",
                icon=":material/support_agent:"),
    ],
    "Personnel": [
        st.Page("app_pages/people.py", title="Employés",
                icon=":material/badge:"),
        st.Page("app_pages/requests_view.py", title="Demandes & présence",
                icon=":material/how_to_reg:"),
        st.Page("app_pages/skills_view.py", title="Compétences & mobilité",
                icon=":material/school:"),
        st.Page("app_pages/retention_negotiator.py", title="Rétention",
                icon=":material/handshake:"),
    ],
    "Planning": _planification,
    "Recrutement": [
        st.Page("app_pages/job_post_view.py", title="Rédiger une offre",
                icon=":material/edit_note:"),
        st.Page("app_pages/sourcing_view.py", title="Canaux de sourcing",
                icon=":material/travel_explore:"),
        st.Page("app_pages/talent_pool.py", title="Candidats",
                icon=":material/groups_2:"),
        st.Page("app_pages/onboarding_view.py", title="Intégration",
                icon=":material/person_add:"),
    ],
    "Paie & déclarations": [
        st.Page("app_pages/payroll_view.py", title="Paie",
                icon=":material/receipt_long:"),
        st.Page("app_pages/deadlines_view.py", title="Échéances & déclarations",
                icon=":material/event_available:"),
        st.Page("app_pages/anomalies_view.py", title="Détection d'anomalies",
                icon=":material/error:"),
        st.Page("app_pages/inspector_sim.py", title="Simulateur d'inspection",
                icon=":material/gavel:"),
        st.Page("app_pages/jo_watch.py", title="Veille Journal Officiel",
                icon=":material/policy:"),
    ],
    "Réglages": [
        st.Page("app_pages/assistant.py", title="Demander à Tawzia",
                icon=":material/forum:"),
        st.Page("app_pages/pdf_tool.py", title="PDF vers texte IA",
                icon=":material/picture_as_pdf:"),
        st.Page("app_pages/company_data_view.py", title="Données de l'entreprise",
                icon=":material/database:"),
        st.Page("app_pages/privacy_view.py", title="Confidentialité",
                icon=":material/lock:"),
        st.Page("app_pages/scenarios_view.py", title="Simulateur de scénarios",
                icon=":material/tune:"),
        st.Page("app_pages/command_centre.py", title="Tableau de bord",
                icon=":material/dashboard:"),
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

# Hand-built navigation (see core/nav.py). Streamlit's native `position="top"`
# folds every section into an "N more" menu when it cannot measure them, which
# is unacceptable on a projected demo. `position="hidden"` turns the native one
# off, and whatever is written before `.run()` shows at the top (see DESIGN.md).
_nav = st.navigation(pages, position="hidden")

from core import appdata, gate, nav, tour  # noqa: E402  , after st.set_page_config

appdata.init_state()
appdata.inject_theme()

# The access gate: required only when an APP_PASSWORD is set, so a demo never
# hits a needless sign-in screen. Placed after the theme so the sign-in screen
# already carries the brand.
if not gate.require_access():
    st.stop()
nav.render(pages, _nav)
_nav.run()
tour.maybe_run(_nav)
