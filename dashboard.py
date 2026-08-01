"""
dashboard.py
------------
WorkForce.dz - the AI HR and workforce platform built for Algerian labour law.

Run:
    streamlit run dashboard.py

The navigation follows the HR lifecycle - hire, schedule, pay, comply, retain -
so the product reads as one clear story, not a pile of tools. Shared expensive
work (weather fetches, the walk-forward backtest, roster optimisation) lives in
`core/appdata.py` behind `st.cache_data`, so switching pages is instant.
"""

import streamlit as st

from core import industry

st.set_page_config(
    page_title="WorkForce.dz",
    page_icon=":material/hub:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Industry mode: tailor the app to the prospect from ?industry=hotel|delivery|...
industry.apply()
_ind = industry.current()

# Airport ops is an industry pack; show it only for the airport edition (or the
# full all-industries app), so a hotel or delivery prospect sees no noise.
_schedule = [
    st.Page("app_pages/forecast_view.py", title="Demand forecast",
            icon=":material/trending_up:"),
    st.Page("app_pages/roster_view.py", title="Roster & cost",
            icon=":material/groups:"),
]
if _ind["show_airport"]:
    _schedule.append(st.Page("app_pages/airport_ops.py", title="Airport ops",
                             icon=":material/flight:"))

pages = {
    "Overview": [
        st.Page("app_pages/command_centre.py", title="Command centre",
                icon=":material/dashboard:", default=True),
    ],
    "Hire & team": [
        st.Page("app_pages/recruiting.py", title="Recruiting",
                icon=":material/person_search:"),
        st.Page("app_pages/people.py", title="People",
                icon=":material/badge:"),
        st.Page("app_pages/requests_view.py", title="Requests & attendance",
                icon=":material/how_to_reg:"),
    ],
    "Schedule": _schedule,
    "Pay & comply": [
        st.Page("app_pages/payroll_view.py", title="Payroll",
                icon=":material/receipt_long:"),
        st.Page("app_pages/inspector_sim.py", title="Inspection simulator",
                icon=":material/gavel:"),
        st.Page("app_pages/jo_watch.py", title="Journal Officiel watch",
                icon=":material/policy:"),
    ],
    "Retain": [
        st.Page("app_pages/attrition_view.py", title="Attrition risk",
                icon=":material/trending_down:"),
        st.Page("app_pages/retention_negotiator.py", title="Retention negotiator",
                icon=":material/handshake:"),
    ],
    "AI copilot": [
        st.Page("app_pages/hr_copilot.py", title="AI HR copilot",
                icon=":material/smart_toy:"),
        st.Page("app_pages/assistant.py", title="Ops assistant",
                icon=":material/forum:"),
    ],
    "Proof & business": [
        st.Page("app_pages/evidence.py", title="Evidence",
                icon=":material/fact_check:"),
        st.Page("app_pages/calendar_view.py", title="Algerian calendar",
                icon=":material/calendar_month:"),
        st.Page("app_pages/business_case.py", title="Business case",
                icon=":material/payments:"),
        st.Page("app_pages/sources_view.py", title="Sources & assumptions",
                icon=":material/menu_book:"),
    ],
}

st.navigation(pages).run()
