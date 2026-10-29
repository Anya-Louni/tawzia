"""Schedule and cost: the schedule, what it costs, and where the cost comes from."""

import pandas as pd
import streamlit as st

from core import appdata, demand as demand_mod, labour_dz

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]

st.title("Schedule and cost")
st.caption(f"{profile.label} · {wilaya} · main role: {labour_dz.ROLES[profile.primary_role].label}")

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
        "No legal schedule exists for this forecast under these constraints. "
        "Raise permanent staff or the temp ceiling in Settings.",
        icon=":material/warning:",
    )
    st.stop()

total_cost = float(roster["planned_cost"].sum())
worker_shifts = int(roster["total_staff"].sum())
ot_share = roster["overtime"].sum() / max(roster["total_staff"].sum(), 1) * 100
temp_share = roster["temp"].sum() / max(roster["total_staff"].sum(), 1) * 100

with st.container(horizontal=True):
    st.metric("Total labour cost", appdata.dzd(total_cost, compact=True), border=True)
    st.metric("Staff shifts", f"{worker_shifts:,}", border=True)
    st.metric(
        "Overtime share", f"{ot_share:.1f}%", border=True,
        help=f"The legal cap is {labour_dz.MAX_OVERTIME_FRACTION:.0%} of legal working "
             f"time. Enforced as a hard constraint, not a cost.",
    )
    st.metric(
        "Temp share", f"{temp_share:.1f}%", border=True,
        help=f"Temps cost {labour_dz.TEMP_AGENCY_MARKUP:.0%} more than a direct "
             f"employee's loaded rate.",
    )

col1, col2 = st.columns([3, 2])

with col1:
    with st.container(border=True):
        st.subheader("Team mix by day")
        mix = roster.groupby("date", as_index=False)[["regular", "overtime", "temp"]].sum()
        mix = mix.set_index("date")
        mix.columns = ["Permanent", "Overtime", "Temps"]
        st.bar_chart(mix, height=300, color=["#0A2540", "#0B57A8", "#6CBEF5"], stack=True)

with col2:
    with st.container(border=True):
        st.subheader("Cost by shift")
        by_shift = roster.groupby("shift", as_index=False)["planned_cost"].sum()
        by_shift["shift"] = by_shift["shift"].map(
            {k: v.label for k, v in labour_dz.SHIFTS.items()}
        )
        st.bar_chart(
            by_shift.set_index("shift")["planned_cost"],
            height=300, color="#0B57A8", horizontal=True,
        )
        st.caption(
            "Night shifts carry a 30% premium; Friday and Saturday carry the "
            "rest-day premium; public holidays are paid double."
        )

_WD_FR = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
          4: "Friday", 5: "Saturday", 6: "Sunday"}

with st.container(border=True):
    st.subheader("Full schedule")
    show = roster[[
        "date", "shift", "required_workers", "regular", "overtime",
        "temp", "total_staff", "supervisors", "planned_cost",
    ]].copy()
    show.insert(2, "weekday", pd.to_datetime(show["date"]).dt.dayofweek.map(_WD_FR))
    show["date"] = pd.to_datetime(show["date"]).dt.strftime("%d %b")
    st.dataframe(
        show, hide_index=True, width="stretch",
        column_config={
            "date": "Date", "weekday": "Day", "shift": "Shift",
            "required_workers": st.column_config.NumberColumn("Required", format="%d"),
            "regular": st.column_config.NumberColumn("Permanent", format="%d"),
            "overtime": st.column_config.NumberColumn("Overtime", format="%d"),
            "temp": st.column_config.NumberColumn("Temps", format="%d"),
            "total_staff": st.column_config.NumberColumn("Total", format="%d"),
            "supervisors": st.column_config.NumberColumn("Sup.", format="%d"),
            "planned_cost": st.column_config.NumberColumn("Cost (DZD)", format="%.0f"),
        },
    )
    st.download_button(
        "Download the schedule (CSV)",
        roster.to_csv(index=False).encode("utf-8"),
        file_name=f"schedule_{st.session_state['profile_key']}_{wilaya}.csv",
        mime="text/csv",
        icon=":material/download:",
    )

st.divider()
st.subheader("Where the cost figure comes from")
st.caption(
    "Derived from Algerian law, not assumed. The table to open when someone "
    "asks how you priced an hour of work."
)

with st.container(border=True):
    st.dataframe(labour_dz.cost_table(), hide_index=True, width="stretch")

with st.expander("The calculation, line by line", icon=":material/calculate:"):
    for note in labour_dz.derivation_notes():
        st.markdown(f"- {note}")

with st.expander("Constraints applied to this schedule", icon=":material/gavel:"):
    for line in appdata.current_constraints().describe():
        st.markdown(f"- {line}")

appdata.data_badge()
