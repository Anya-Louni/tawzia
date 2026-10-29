"""Inspection simulator: a labour-inspection dry run before the inspector comes."""

import streamlit as st

from core import appdata, inspector, ai

appdata.sidebar_controls()

st.title("Inspection simulator")
st.caption("Run the labour inspection on yourself first. Each finding is a real "
           "rule check, with the article, an indicative fine range and the fix.")

people = appdata.hr_people()

# Overtime and coverage checks need the forecast (heavier), so they are opt-in.
deep = st.toggle(
    "Also check overtime and coverage (runs the forecast, about 1 min)",
    value=False,
    help="Adds the overtime-cap and understaffing checks, which need the "
         "forecast and the schedule.",
)
roster, cons = None, None
if deep:
    with st.spinner("Building the schedule from the forecast..."):
        plan = appdata.load_forward_plan(
            st.session_state["profile_key"], st.session_state["wilaya"],
            st.session_state["horizon"], st.session_state["regular_pool"],
            st.session_state["temp_ceiling"], st.session_state["service_level"],
            st.session_state["allow_network"],
        )
    roster = plan["roster"]
    cons = appdata.current_constraints()

res = inspector.audit(roster=roster, people=people, constraints=cons)

with st.container(horizontal=True):
    st.metric("Inspection risk", f"{res['score']}/100", border=True)
    st.metric("Findings", f"{len(res['findings'])}", border=True,
              help=f"{res['scorecard']['critical']} critical, {res['scorecard']['warning']} warnings")
    st.metric("Estimated exposure",
              f"{res['exposure_low']:,} - {res['exposure_high']:,} DZD", border=True,
              help="Indicative ranges for prioritising, not legal advice.")

_labels = {
    "ok": "Would probably pass an inspection today",
    "warning": "Moderate exposure: fix these",
    "critical": "High exposure: fix before any inspection",
}
_msg = _labels.get(res["status"], res["label"])
if res["status"] == "ok":
    st.success(_msg, icon=":material/verified_user:")
elif res["status"] == "warning":
    st.warning(_msg, icon=":material/warning:")
else:
    st.error(_msg, icon=":material/gpp_bad:")

with st.container(border=True):
    st.subheader("What an inspector would note")
    st.dataframe(
        inspector.to_frame(res["findings"]), hide_index=True, width="stretch",
        column_config={
            "Violation": st.column_config.TextColumn(width="large"),
            "Fix": st.column_config.TextColumn(width="large"),
        },
    )

with st.container(border=True):
    st.subheader("The inspector's report")
    st.caption(ai.status_line())
    if st.button("Draft the report", type="primary", icon=":material/gavel:"):
        with st.spinner("Simulating the inspection..."):
            st.session_state["insp_report"] = inspector.report(res, lang="en")
    st.markdown(st.session_state.get("insp_report") or inspector._template_report(res, "en"))

st.caption(":material/balance: Fine ranges are indicative, to prioritise fixes. "
           "Actual penalties follow the Algerian labour code and the inspector's "
           "judgement. Check with counsel before acting.")
appdata.data_badge()
