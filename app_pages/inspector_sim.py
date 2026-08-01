"""Inspection simulator - a dry run of the labour inspection before it happens."""

import streamlit as st

from core import appdata, inspector, ai

appdata.sidebar_controls()

st.title("Inspection simulator")
st.caption("Run the labour inspection on yourself first. Every finding is a real "
           "rule check, with the article, an indicative fine band and the fix.")

# Contract / wage / leave checks run on the workforce and are instant.
people = appdata.hr_people()

# Roster overtime + coverage checks need the forecast (heavier), so they are
# optional - this keeps the page instant instead of waiting on the backtest.
deep = st.toggle(
    "Also check roster overtime & coverage (runs the forecast, about a minute)",
    value=False,
    help="Adds the weekly overtime-cap and understaffing checks, which need the "
         "demand forecast and roster.",
)
roster, cons = None, None
if deep:
    with st.spinner("Building the roster from the forecast..."):
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
              help=f"{res['scorecard']['critical']} critical, {res['scorecard']['warning']} warning")
    st.metric("Est. fine exposure",
              f"{res['exposure_low']:,} - {res['exposure_high']:,} DZD", border=True,
              help="Indicative bands for prioritisation, not legal advice.")

if res["status"] == "ok":
    st.success(res["label"], icon=":material/verified_user:")
elif res["status"] == "warning":
    st.warning(res["label"], icon=":material/warning:")
else:
    st.error(res["label"], icon=":material/gpp_bad:")

with st.container(border=True):
    st.subheader("What an inspector would write up")
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
    c1, c2 = st.columns([1, 3])
    lang = c1.radio("Language", ["en", "fr"], format_func=lambda x: "English" if x == "en" else "Francais",
                    horizontal=True, key="insp_lang")
    if c1.button("Write the report", type="primary", icon=":material/gavel:"):
        with st.spinner("Simulating the inspection..."):
            st.session_state["insp_report"] = inspector.report(res, lang=lang)
    st.markdown(st.session_state.get("insp_report") or inspector._template_report(res, lang))

st.caption(":material/balance: Fine bands are indicative, for prioritising fixes. "
           "Actual penalties follow the Algerian labour code and the inspector's "
           "discretion. Confirm with counsel before acting.")
appdata.data_badge()
