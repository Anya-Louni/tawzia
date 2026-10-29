"""Retention: the cheapest action to keep an at-risk employee."""

import pandas as pd
import streamlit as st

from core import ai, appdata, retention

appdata.sidebar_controls()

st.title("Retention")
st.caption("Leaving risk says who might go. This says the cheapest action to keep "
           "them, tested through the same model, and writes the conversation.")

df = appdata.hr_attrition()
people = appdata.hr_people()
records = appdata.hr_attendance()

if df.empty:
    st.info("No workforce loaded.")
    st.stop()

_BAND = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}

names = df["Name"].tolist()
ids = df["ID"].tolist()
choice = st.selectbox("Employee", range(len(names)),
                      format_func=lambda i: f"{names[i]}  ({df.iloc[i]['Risk %']:.0f}% risk)")
emp_id = ids[choice]

plan = retention.plan_for_employee(people, records, emp_id)
if plan is None:
    st.warning("Could not build a plan for this employee.")
    st.stop()

with st.container(horizontal=True):
    st.metric("Leaving risk (6 months)", f"{plan.base_risk:.0%}", border=True)
    st.metric("Band", _BAND.get(plan.band, plan.band.upper()), border=True)
    st.metric("Replacement cost", appdata.dzd(plan.replacement_cost, compact=True), border=True)
    st.metric("Main cause", plan.top_driver, border=True)

with st.container(border=True):
    st.subheader("Retention levers, ranked by net value")
    st.caption("Each lever goes through the risk model: it changes the cause it "
               "targets, recomputes the risk, and turns the drop into money saved "
               "(risk drop x replacement cost).")
    if plan.levers:
        table = pd.DataFrame([{
            "Lever": l.label,
            "Cost (DZD/yr)": l.cost_dzd,
            "New risk": round(l.new_risk * 100, 1),
            "Drop (points)": round(l.risk_drop * 100, 1),
            "Value saved (DZD)": l.value_dzd,
            "Net (DZD)": l.net_dzd,
        } for l in plan.levers])
        st.dataframe(
            table, hide_index=True, width="stretch",
            column_config={
                "Cost (DZD/yr)": st.column_config.NumberColumn(format="%d"),
                "New risk": st.column_config.NumberColumn(format="%.1f%%"),
                "Value saved (DZD)": st.column_config.NumberColumn(format="%d"),
                "Net (DZD)": st.column_config.NumberColumn(format="%d"),
            },
        )
        if plan.best:
            st.success(f"Recommended: **{plan.best.label}**, worth about "
                       f"{plan.best.net_dzd:,.0f} DZD compared with losing them. "
                       f"{plan.best.rationale}", icon=":material/recommend:")
    else:
        st.caption("This employee is at low risk: no action needed.")

if plan.best:
    with st.container(border=True):
        st.subheader("The conversation")
        st.caption(ai.status_line())
        if st.button("Write the talking points", type="primary", icon=":material/forum:"):
            with st.spinner("Writing the script..."):
                st.session_state["ret_script"] = retention.write_script(plan, lang="en")
        if st.session_state.get("ret_script"):
            st.markdown(st.session_state["ret_script"])

st.info("Like the risk model, the weights are documented, not trained on real "
        "Algerian departures; amounts are indicative and refitted during a pilot. "
        "The counterfactual through the model is the real method.",
        icon=":material/psychology:")
appdata.data_badge()
