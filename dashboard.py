"""
dashboard.py
------------
WorkForce.dz — shift-labour intelligence for Algerian operations.

Run:
    streamlit run dashboard.py

The app is organised as a multipage navigation. Shared, expensive work
(real weather fetches, the walk-forward backtest, roster optimisation) lives
in `core/appdata.py` behind `st.cache_data`, so switching pages is instant.
"""

import streamlit as st

st.set_page_config(
    page_title="WorkForce.dz",
    page_icon=":material/insights:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Grouped navigation: the operations engine, the HR platform on top of it,
# and the business/reference material.
pages = {
    "Operations": [
        st.Page("app_pages/command_centre.py", title="Command centre",
                icon=":material/dashboard:", default=True),
        st.Page("app_pages/forecast_view.py", title="Demand forecast",
                icon=":material/trending_up:"),
        st.Page("app_pages/roster_view.py", title="Roster & cost",
                icon=":material/groups:"),
        st.Page("app_pages/airport_ops.py", title="Airport ops AI",
                icon=":material/flight:"),
    ],
    "HR platform": [
        st.Page("app_pages/people.py", title="People",
                icon=":material/badge:"),
        st.Page("app_pages/requests_view.py", title="Requests & attendance",
                icon=":material/how_to_reg:"),
        st.Page("app_pages/attrition_view.py", title="Attrition risk",
                icon=":material/trending_down:"),
        st.Page("app_pages/recruiting.py", title="Recruiting",
                icon=":material/person_search:"),
        st.Page("app_pages/payroll_view.py", title="Payroll & compliance",
                icon=":material/receipt_long:"),
        st.Page("app_pages/hr_copilot.py", title="AI HR copilot",
                icon=":material/smart_toy:"),
    ],
    "Evidence & business": [
        st.Page("app_pages/evidence.py", title="Evidence",
                icon=":material/fact_check:"),
        st.Page("app_pages/calendar_view.py", title="Algerian calendar",
                icon=":material/calendar_month:"),
        st.Page("app_pages/business_case.py", title="Business case",
                icon=":material/payments:"),
        st.Page("app_pages/sources_view.py", title="Sources & assumptions",
                icon=":material/menu_book:"),
        st.Page("app_pages/assistant.py", title="Ops assistant",
                icon=":material/forum:"),
    ],
}

st.navigation(pages).run()
