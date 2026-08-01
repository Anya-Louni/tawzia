"""People, the employee records and profiles."""

import datetime as dt

import pandas as pd
import streamlit as st

from core import appdata, hr, labour_dz

appdata.sidebar_controls()

st.title("People")
st.caption("The workforce behind the roster, with Algerian entitlements built in.")

people = appdata.hr_people()
today = dt.date.today()
frame = hr.workforce_frame(people, today)

south = sum(1 for e in people if e.is_southern)
avg_bal = frame["Accrued balance (d)"].mean()
avg_sen = frame["Seniority (yrs)"].mean()

with st.container(horizontal=True):
    st.metric("Headcount", f"{len(people)}", border=True)
    st.metric("Avg seniority", f"{avg_sen:.1f} yrs", border=True)
    st.metric("Avg leave balance", f"{avg_bal:.1f} d", border=True)
    st.metric("Southern (40-day)", f"{south}", border=True,
              help="Workers in Saharan wilayas get 40 days annual leave, not 30.")

st.caption(
    ":material/info: Employee records here are synthetic demo data. A real "
    "deployment imports your staff file. Entitlements, accrual and seniority "
    "are computed from Algerian labour law."
)

col_list, col_detail = st.columns([3, 2])

with col_list:
    with st.container(border=True):
        st.subheader("Roster of employees")
        st.dataframe(
            frame, hide_index=True, width="stretch", height=460,
            column_config={
                "Monthly gross (DZD)": st.column_config.NumberColumn(format="%d"),
                "Accrued balance (d)": st.column_config.NumberColumn(format="%.1f"),
            },
        )

with col_detail:
    with st.container(border=True):
        st.subheader("Profile")
        names = {f"{e.name} ({e.emp_id})": e for e in people}
        pick = st.selectbox("Employee", list(names), label_visibility="collapsed")
        e = names[pick]
        role = labour_dz.ROLES[e.role_key]
        st.markdown(f"### {e.name}")
        st.caption(f"{role.label} - {e.wilaya} - {e.contract}")

        st.markdown(
            f"""
| | |
|---|---|
| **Employee ID** | {e.emp_id} |
| **Hired** | {e.hire_date:%d %b %Y} |
| **Seniority** | {e.seniority_years(today)} years ({e.seniority_premium(today):.0%} premium) |
| **Annual entitlement** | {e.annual_entitlement()} days |
| **Accrued balance** | {e.accrued_leave(today):.1f} days |
| **Dependants** | {e.dependants}{' + spouse' if e.spouse else ''} |
| **Monthly gross** | {e.monthly_gross():,.0f} DZD |
"""
        )
        if e.is_southern:
            st.info("Southern wilaya: 40 days annual leave (30 + 10).", icon=":material/wb_sunny:")

appdata.data_badge()
