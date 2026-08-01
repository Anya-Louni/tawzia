"""Retention negotiator - the cheapest move that keeps a flight-risk employee."""

import pandas as pd
import streamlit as st

from core import appdata, retention, ai

appdata.sidebar_controls()

st.title("Retention negotiator")
st.caption("Attrition says who might leave. This says the single cheapest thing "
           "that keeps them, tested through the same model, and drafts the talk.")

df = appdata.hr_attrition()
people = appdata.hr_people()
records = appdata.hr_attendance()

if df.empty:
    st.info("No workforce loaded.")
    st.stop()

# pick an employee, default to the highest risk
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
    st.metric("Quit risk (6 mo)", f"{plan.base_risk:.0%}", border=True)
    st.metric("Band", plan.band.upper(), border=True)
    st.metric("Replacement cost", appdata.dzd(plan.replacement_cost, compact=True), border=True)
    st.metric("Main driver", plan.top_driver, border=True)

with st.container(border=True):
    st.subheader("Retention levers, ranked by net value")
    st.caption("Each lever is run through the attrition model: it changes the "
               "driver it targets, re-scores the risk, and turns the drop into "
               "money saved (risk reduction x replacement cost).")
    if plan.levers:
        table = pd.DataFrame([{
            "Lever": l.label,
            "Cost (DZD/yr)": l.cost_dzd,
            "New risk": round(l.new_risk * 100, 1),
            "Risk drop (pts)": round(l.risk_drop * 100, 1),
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
            st.success(f"Recommended: **{plan.best.label}** - "
                       f"nets about {plan.best.net_dzd:,.0f} DZD versus losing them. "
                       f"{plan.best.rationale}", icon=":material/recommend:")
    else:
        st.caption("This employee is low risk - no intervention needed.")

if plan.best:
    with st.container(border=True):
        st.subheader("The conversation")
        st.caption(ai.status_line())
        c1, _ = st.columns([1, 3])
        lang = c1.radio("Language", ["fr", "en"],
                        format_func=lambda x: "Francais" if x == "fr" else "English",
                        horizontal=True, key="ret_lang")
        if c1.button("Draft the one-to-one", type="primary", icon=":material/forum:"):
            with st.spinner("Writing the script..."):
                st.session_state["ret_script"] = retention.write_script(plan, lang=lang)
        if st.session_state.get("ret_script"):
            st.markdown(st.session_state["ret_script"])

st.info("Like the attrition model, the weights are documented, not trained on real "
        "Algerian quit data, so the money figures are directional and re-fit on a "
        "pilot. The model-based counterfactual is the real method.",
        icon=":material/psychology:")
appdata.data_badge()
