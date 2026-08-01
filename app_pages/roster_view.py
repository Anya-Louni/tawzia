"""Roster & cost — the schedule, what it costs, and where the cost comes from."""

import pandas as pd
import streamlit as st

from core import appdata, demand as demand_mod, labour_dz

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]

st.title("Roster & cost")
st.caption(f"{profile.label} · {wilaya} · primary role: {labour_dz.ROLES[profile.primary_role].label}")

plan = appdata.load_forward_plan(
    st.session_state["profile_key"],
    wilaya,
    st.session_state["horizon"],
    st.session_state["regular_pool"],
    st.session_state["temp_ceiling"],
    st.session_state["service_level"],
    st.session_state["allow_network"],
)
roster = plan["roster"]

if plan["infeasible"]:
    st.error(
        "No legal roster exists for this forecast at these constraints. Raise "
        "the permanent workforce or the temp ceiling in the sidebar.",
        icon=":material/warning:",
    )
    st.stop()

total_cost = float(roster["planned_cost"].sum())
worker_shifts = int(roster["total_staff"].sum())
ot_share = roster["overtime"].sum() / max(roster["total_staff"].sum(), 1) * 100
temp_share = roster["temp"].sum() / max(roster["total_staff"].sum(), 1) * 100

with st.container(horizontal=True):
    st.metric("Total labour cost", appdata.dzd(total_cost, compact=True), border=True)
    st.metric("Worker-shifts", f"{worker_shifts:,}", border=True)
    st.metric(
        "Overtime share", f"{ot_share:.1f}%", border=True,
        help=f"Statutory cap is {labour_dz.MAX_OVERTIME_FRACTION:.0%} of legal "
             f"working time. Enforced as a hard constraint, not a cost.",
    )
    st.metric(
        "Temp share", f"{temp_share:.1f}%", border=True,
        help=f"Agency temps cost {labour_dz.TEMP_AGENCY_MARKUP:.0%} more than "
             f"the loaded rate for a direct employee.",
    )

col1, col2 = st.columns([3, 2])

with col1:
    with st.container(border=True):
        st.subheader("Crew mix by day")
        mix = roster.groupby("date", as_index=False)[["regular", "overtime", "temp"]].sum()
        mix = mix.set_index("date")
        mix.columns = ["Regular", "Overtime", "Temp"]
        st.bar_chart(mix, height=300, color=["#16233A", "#B78B4A", "#C8102E"], stack=True)

with col2:
    with st.container(border=True):
        st.subheader("Cost by shift")
        by_shift = roster.groupby("shift", as_index=False)["planned_cost"].sum()
        by_shift["shift"] = by_shift["shift"].map(
            {k: v.label for k, v in labour_dz.SHIFTS.items()}
        )
        st.bar_chart(
            by_shift.set_index("shift")["planned_cost"],
            height=300, color="#C8102E", horizontal=True,
        )
        st.caption(
            "Night shifts carry a 30% premium; Friday and Saturday carry the "
            "rest-day premium; gazetted holidays are double time."
        )

with st.container(border=True):
    st.subheader("Full schedule")
    show = roster[[
        "date", "shift", "required_workers", "regular", "overtime",
        "temp", "total_staff", "supervisors", "planned_cost",
    ]].copy()
    show.insert(2, "weekday", pd.to_datetime(show["date"]).dt.day_name())
    show["date"] = pd.to_datetime(show["date"]).dt.strftime("%d %b")
    st.dataframe(
        show, hide_index=True, width="stretch",
        column_config={
            "date": "Date", "weekday": "Day", "shift": "Shift",
            "required_workers": st.column_config.NumberColumn("Needed", format="%d"),
            "regular": st.column_config.NumberColumn("Regular", format="%d"),
            "overtime": st.column_config.NumberColumn("OT", format="%d"),
            "temp": st.column_config.NumberColumn("Temp", format="%d"),
            "total_staff": st.column_config.NumberColumn("Total", format="%d"),
            "supervisors": st.column_config.NumberColumn("Sup.", format="%d"),
            "planned_cost": st.column_config.NumberColumn("Cost (DZD)", format="%.0f"),
        },
    )
    st.download_button(
        "Download roster (CSV)",
        roster.to_csv(index=False).encode("utf-8"),
        file_name=f"roster_{st.session_state['profile_key']}_{wilaya}.csv",
        mime="text/csv",
        icon=":material/download:",
    )

st.divider()
st.subheader("Where the cost number comes from")
st.caption(
    "Derived from Algerian statute, not assumed. This is the table to open "
    "when someone asks how you priced an hour of labour."
)

with st.container(border=True):
    st.dataframe(labour_dz.cost_table(), hide_index=True, width="stretch")

with st.expander("The derivation, line by line", icon=":material/calculate:"):
    for note in labour_dz.derivation_notes():
        st.markdown(f"- {note}")

with st.expander("Constraints applied to this roster", icon=":material/gavel:"):
    for line in appdata.current_constraints().describe():
        st.markdown(f"- {line}")

appdata.data_badge()
