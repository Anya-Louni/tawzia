"""Anomaly detection: payroll and attendance, rules plus an unsupervised model."""

import streamlit as st

from core import anomalies as anom_mod, appdata, company_data as cd

appdata.sidebar_controls()

st.title("Anomaly detection")
st.caption(
    "Costly payroll errors and attendance signals, found before a CNAS or DGI "
    "audit, or a resignation. Two detectors: interpretable **Algerian rules** "
    "(SNMG, IRG, absence) and an **unsupervised model** (IsolationForest) that "
    "learns what is normal for YOUR company."
)

people = cd.people()
records = cd.attendance_records()
st.caption(f":material/database: Source: **{cd.source_label()}**, "
           f"{len(people)} employees, {len(records)} clock records.")

res = anom_mod.detect(people, records)
s = res["summary"]
anomalies = res["anomalies"]

m = st.columns(4)
m[0].metric("Anomalies", s["total"])
m[1].metric("Critical", s["critique"])
m[2].metric("Payroll", s["paie"])
m[3].metric("Attendance", s["présence"])

if s["critique"]:
    st.error(f"{s['critique']} critical anomaly(ies), to correct now "
             f"(salary below the SNMG).", icon=":material/error:")

st.divider()

_SEV_COLOUR = {"critique": "red", "élevée": "orange", "moyenne": "blue", "faible": "gray"}
_DOMAIN_ICON = {"paie": ":material/receipt_long:", "présence": ":material/schedule:"}

tab_all, tab_pay, tab_att, tab_evidence = st.tabs(
    ["All", "Payroll", "Attendance", "Source data"])


def _render(items):
    if not items:
        st.success("No anomaly in this category.", icon=":material/check_circle:")
        return
    for a in items:
        with st.container(border=True):
            head = st.columns([3, 1])
            head[0].markdown(
                f"{_DOMAIN_ICON.get(a.domain, '')} **{a.name}** ({a.emp_id}): {a.detail}")
            head[1].markdown(f":{_SEV_COLOUR[a.severity]}[**"
                             f"{anom_mod.SEVERITY_LABEL.get(a.severity, a.severity).upper()}**]")
            st.caption(f":material/lightbulb: {a.recommendation}")


with tab_all:
    _render(anomalies)
with tab_pay:
    _render([a for a in anomalies if a.domain == "paie"])
with tab_att:
    _render([a for a in anomalies if a.domain == "présence"])
with tab_evidence:
    st.markdown("**Recomputed payroll register** (SNMG + CNAS + IRG stack)")
    st.dataframe(res["payroll_frame"], hide_index=True, width="stretch")
    st.markdown("**Attendance statistics per employee**")
    st.dataframe(res["attendance_frame"], hide_index=True, width="stretch")

if anomalies:
    with st.expander("Export the anomalies", icon=":material/download:"):
        frame = anom_mod.anomalies_frame(anomalies)
        st.download_button("Download (CSV)", frame.to_csv(index=False).encode("utf-8"),
                           "anomalies.csv", "text/csv")

st.caption(":material/psychology: The model is fitted on the company's own data: "
           "what is unusual is relative to your own norm, not a generic benchmark.")
appdata.data_badge()
