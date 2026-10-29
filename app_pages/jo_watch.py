"""Official Journal watch: keep the rules current and cost any change."""

import pandas as pd
import streamlit as st

from core import appdata, regwatch, ai, labour_dz

appdata.sidebar_controls()

st.title("Official Journal watch")
st.caption("The Algerian labour and payroll rules the platform tracks, whether "
           "your settings are current, and the cost of any change before it lands.")

rows = regwatch.status()
out_of_date = [r for r in rows if r["Status"] != "Up to date"]
with st.container(horizontal=True):
    st.metric("Rules tracked", f"{len(rows)}", border=True)
    st.metric("Out of date", f"{len(out_of_date)}", border=True)
    st.metric("SNMG in force", f"{labour_dz.SNMG_MONTHLY:,.0f} DZD", border=True)

if out_of_date:
    st.error(f"{len(out_of_date)} rule(s) no longer match the current legal value.",
             icon=":material/error:")
else:
    st.success("Every tracked rule matches the current legal value.",
               icon=":material/verified:")

with st.container(border=True):
    st.subheader("Your compliance status")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                 column_config={"Reference": st.column_config.TextColumn(width="medium")})

with st.container(border=True):
    st.subheader("Simulate a rule change")
    st.caption("A rule change is money. Set a proposed value and see who is "
               "affected and what it costs, on your actual workforce.")
    people = appdata.hr_people()
    c1, c2 = st.columns([1.2, 1])
    param = c1.selectbox("Rule", ["snmg", "cnas_employer"],
                         format_func=lambda p: {"snmg": "SNMG (minimum wage)",
                                                "cnas_employer": "CNAS employer rate"}[p])
    if param == "snmg":
        new_value = c2.number_input("Proposed SNMG (DZD/month)",
                                    value=float(labour_dz.SNMG_MONTHLY + 6000),
                                    step=1000.0, min_value=0.0)
    else:
        new_value = c2.number_input("Proposed employer rate",
                                    value=float(labour_dz.CNAS_EMPLOYER + 0.02),
                                    step=0.01, min_value=0.0, max_value=1.0, format="%.2f")

    imp = regwatch.simulate_change(people, param, new_value)
    m1, m2 = st.columns(2)
    m1.metric("Employees affected", f"{imp.affected} / {imp.workforce}", border=True)
    m2.metric("Annual cost change", appdata.dzd(imp.annual_cost_delta, compact=True), border=True)
    st.caption(ai.status_line())
    if st.button("Draft the compliance notice", type="primary", icon=":material/edit_note:"):
        with st.spinner("Drafting the notice..."):
            st.session_state["jo_notice"] = regwatch.impact_notice(imp, lang="en")
    if st.session_state.get("jo_notice"):
        st.info(st.session_state["jo_notice"], icon=":material/campaign:")

with st.container(border=True):
    st.subheader("Tracked register")
    reg = pd.DataFrame([{"Rule": r["title"], "Area": r["domain"],
                         "Summary": r["summary"], "Reference": r["ref"]}
                        for r in regwatch.REGISTER])
    st.dataframe(reg, hide_index=True, width="stretch",
                 column_config={"Summary": st.column_config.TextColumn(width="large")})

st.caption(":material/info: In this demo the register is a curated summary of "
           "the tracked rules. In production it is fed by automatic ingestion of "
           "the Official Journal and CNAS/DGI publications. The status check and "
           "the simulator run on your actual workforce.")
appdata.data_badge()
