"""
Airport operations AI — the Air Algérie / Aéroport d'Alger module.

Three aviation-grade features on the real ALG network and the real Algerian
calendar:
  1. Passenger-flow forecast -> terminal staffing
  2. Delay-cascade predictor (the "chaotic day", predicted)
  3. Turnaround-risk board
"""

import datetime as dt

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from core import appdata, aviation, calendar_dz

appdata.sidebar_controls()

st.title("Airport operations AI")
st.caption(
    "Aéroport d'Alger (ALG) · Air Algérie network · built on the real route "
    "map and the real Algerian calendar"
)

st.info(
    "**Why this matters now.** Air Algérie is scaling from ~8.8M passengers "
    "(2025) toward ~10M (2026) and taking ~60 new aircraft onto a hub that "
    "already congests at peak. The two expensive failure modes — unstaffed "
    "passenger surges and delays that cascade across the day — are exactly "
    "what this module predicts. Flight schedules and delays are simulated; the "
    "route network and the calendar driving demand are real.",
    icon=":material/flight_takeoff:",
)

# --- Date picker -----------------------------------------------------------
col_d, col_info = st.columns([1, 3])
with col_d:
    day = st.date_input(
        "Operations day",
        value=dt.date(2026, 7, 25),
        min_value=dt.date(2026, 1, 1),
        max_value=dt.date(2027, 12, 31),
        help="Try a summer Saturday (diaspora peak) vs a January weekday.",
    )
day_iso = day.isoformat()
ctx = calendar_dz.day_context(day)

with col_info:
    tags = []
    if ctx.diaspora_intensity > 0.1:
        tags.append(f":material/beach_access: Diaspora season ({ctx.diaspora_intensity:.0%} of peak)")
    if ctx.is_ramadan:
        tags.append(f":material/nightlight: Ramadan day {ctx.ramadan_day}")
    if ctx.is_public_holiday:
        tags.append(f":material/celebration: {ctx.holiday_name}")
    if ctx.is_weekend:
        tags.append(":material/weekend: Algerian weekend (Fri–Sat)")
    st.markdown(f"**{day:%A %d %B %Y}** — " + (" · ".join(tags) if tags else "ordinary day"))

sched = appdata.flight_day(day_iso)
day_ctx = sched.attrs["day_context"]

tab_flow, tab_cascade, tab_turnaround, tab_board = st.tabs([
    "Passenger flow & staffing",
    "Delay-cascade predictor",
    "Turnaround risk",
    "Flight board",
])

# ===========================================================================
# TAB 1 — Passenger flow & terminal staffing
# ===========================================================================
with tab_flow:
    flow = appdata.pax_flow_for(day_iso)
    s = flow.summary

    st.subheader("Passenger flow through the terminal")
    st.caption(
        "Passengers don't arrive in one lump at departure — they build up over "
        "a show-up window before each flight, longer for long-haul. Stacked "
        "across every flight, that's the crowd actually in the building each "
        "hour. The **peak**, not the daily total, sets how many desks you open."
    )

    with st.container(horizontal=True):
        st.metric("Departing today", f"{s['total_departing_pax']:,}", border=True)
        st.metric("Arriving today", f"{s['total_arriving_pax']:,}", border=True)
        st.metric(
            "Busiest terminal hour",
            f"{s['peak_hour']:%H:%M}",
            f"{s['peak_terminal_pax']:,} pax in building",
            border=True,
        )
        st.metric(
            "Peak check-in agents",
            f"{s['peak_checkin_agents']}",
            f"at {s['peak_checkin_hour']:%H:%M}",
            border=True,
        )
        st.metric("Peak security lanes", f"{s['peak_security_lanes']}", border=True)

    with st.container(border=True):
        st.markdown("**Passengers at each process, by hour**")
        h = flow.hourly.copy()
        h_long = h.melt(
            id_vars="hour",
            value_vars=["checkin", "security", "boarding", "immigration", "baggage"],
            var_name="Process", value_name="Passengers",
        )
        proc_labels = {
            "checkin": "Check-in", "security": "Security", "boarding": "Boarding",
            "immigration": "Immigration (arr)", "baggage": "Baggage (arr)",
        }
        h_long["Process"] = h_long["Process"].map(proc_labels)
        chart = (
            alt.Chart(h_long)
            .mark_area(opacity=0.75)
            .encode(
                x=alt.X("hour:T", title=None, axis=alt.Axis(format="%H:%M")),
                y=alt.Y("Passengers:Q", stack=None, title="Passengers in process"),
                color=alt.Color("Process:N",
                                scale=alt.Scale(range=["#C8102E", "#16233A", "#B78B4A",
                                                       "#1E6F5C", "#7C8494"])),
                tooltip=["hour:T", "Process:N", alt.Tooltip("Passengers:Q", format=".0f")],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, width="stretch")

    with st.container(border=True):
        st.markdown("**Recommended terminal staffing, by hour**")
        st.caption(
            "Agents per process per hour to clear demand without a queue — "
            "night hours (21:00–05:00) carry the statutory +30% premium in the "
            "costed total below."
        )
        stf = flow.staffing.copy()
        stf_show = stf[stf["total_agents"] > 0].copy()
        stf_show["hour"] = pd.to_datetime(stf_show["hour"]).dt.strftime("%a %H:%M")
        st.dataframe(
            stf_show.rename(columns={
                "hour": "Hour", "checkin": "Check-in", "security": "Security",
                "boarding": "Boarding", "immigration": "Immigration",
                "baggage": "Baggage", "total_agents": "Total",
            }),
            hide_index=True, width="stretch", height=280,
        )
        st.metric("Day's terminal staffing cost",
                  appdata.dzd(s["daily_staff_cost"], compact=True), border=True)

# ===========================================================================
# TAB 2 — Delay cascade predictor (flagship)
# ===========================================================================
with tab_cascade:
    st.subheader("Delay-cascade predictor")
    st.caption(
        "Aircraft fly chains — one tail does ALG→CDG→ALG→ORN→ALG all day. A "
        "late inbound eats its turnaround and pushes every following flight. "
        "This predicts the chain **before** it happens and names the one flight "
        "to protect to break it."
    )

    severity = st.select_slider(
        "Day severity",
        options=[0.8, 1.0, 1.3, 1.6, 2.0, 2.4],
        value=1.3,
        format_func=lambda v: {0.8: "Calm", 1.0: "Normal", 1.3: "Busy",
                               1.6: "Rough", 2.0: "Bad weather", 2.4: "Chaotic day"}[v],
        help="Scales how many flights pick up their own root delay. Watch the "
             "cascade grow as the day gets worse.",
    )

    res = appdata.cascade(day_iso, severity)
    cs = res.summary

    with st.container(horizontal=True):
        st.metric("On-time performance", f"{cs['on_time_pct']:.0f}%", border=True)
        st.metric("Delayed flights", f"{cs['delayed_flights']}",
                  f"of {cs['total_flights']}", border=True)
        st.metric(
            "Cascade share",
            f"{cs['cascade_share']:.0f}%",
            "of delays are inherited",
            border=True,
            help="Delays that were another flight's fault, not their own. "
                 "Industry-wide this 'reactionary' delay runs 40–50%.",
        )
        st.metric("Passengers on a delayed flight", f"{cs['pax_affected']:,}", border=True)

    if cs["worst_keystone"]:
        k = cs["worst_keystone"]
        st.error(
            f"**Keystone flight: {k['flight_no']} ({k['route_city']}, "
            f"{k['direction'].lower()}).** If its inbound slips, "
            f"**{int(k['downstream_flights'])} downstream flights** and "
            f"**{int(k['downstream_pax']):,} passengers** are hit "
            f"({int(k['downstream_delay_min'])} delay-minutes). Protect this "
            f"turnaround first — hold a standby crew or swap the tail.",
            icon=":material/priority_high:",
        )

    col_k, col_w = st.columns([3, 2])
    with col_k:
        with st.container(border=True):
            st.markdown("**Keystone flights — protect these first**")
            st.caption("Ranked by downstream passengers affected.")
            if len(res.keystones):
                kk = res.keystones.copy()
                kk["sched_time"] = pd.to_datetime(kk["sched_time"]).dt.strftime("%H:%M")
                st.dataframe(
                    kk[["flight_no", "route_city", "direction", "sched_time",
                        "downstream_flights", "downstream_pax", "downstream_delay_min"]]
                    .rename(columns={
                        "flight_no": "Flight", "route_city": "Route",
                        "direction": "Dir", "sched_time": "Sched",
                        "downstream_flights": "↓Flights", "downstream_pax": "↓Pax",
                        "downstream_delay_min": "↓Delay min",
                    }),
                    hide_index=True, width="stretch",
                )
            else:
                st.success("No cascades predicted at this severity.")
    with col_w:
        with st.container(border=True):
            st.markdown("**Delay breakdown**")
            breakdown = pd.DataFrame({
                "Type": ["On time", "Root cause", "Cascade (inherited)"],
                "Flights": [
                    cs["total_flights"] - cs["delayed_flights"],
                    cs["root_flights"], cs["cascade_flights"],
                ],
            })
            donut = (
                alt.Chart(breakdown)
                .mark_arc(innerRadius=55)
                .encode(
                    theta="Flights:Q",
                    color=alt.Color("Type:N", scale=alt.Scale(
                        domain=["On time", "Root cause", "Cascade (inherited)"],
                        range=["#1E6F5C", "#9C6209", "#C8102E"])),
                    tooltip=["Type:N", "Flights:Q"],
                )
                .properties(height=240)
            )
            st.altair_chart(donut, width="stretch")
            st.caption(
                "The red slice is the prize: delays you can prevent upstream "
                "instead of absorbing everywhere."
            )

    with st.container(border=True):
        st.markdown("**Rotation map — the busiest tails**")
        st.caption("Each aircraft's total predicted delay across its chain of flights today.")
        rot = res.rotations.head(12).copy()
        rot_chart = (
            alt.Chart(rot)
            .mark_bar()
            .encode(
                y=alt.Y("tail:N", sort="-x", title="Aircraft"),
                x=alt.X("total_delay:Q", title="Total predicted delay (min)"),
                color=alt.value("#C8102E"),
                tooltip=["tail:N", "aircraft:N", "legs:Q", "total_delay:Q", "pax:Q"],
            )
            .properties(height=300)
        )
        st.altair_chart(rot_chart, width="stretch")

# ===========================================================================
# TAB 3 — Turnaround risk
# ===========================================================================
with tab_turnaround:
    st.subheader("Turnaround-risk board")
    st.caption(
        "For each arriving aircraft with an onward flight, how tight is the "
        "ground time versus the minimum turnaround? Tight ground time is where "
        "a small inbound delay becomes a departure delay — Boeing's own "
        "turnaround-optimisation use case, on the ALG schedule."
    )

    res2 = appdata.cascade(day_iso, 1.3)
    fl = res2.flights.copy()

    # Compute ground slack for each tail between an arrival and its next departure.
    fl = fl.sort_values(["tail", "sched_time"])
    rows = []
    for tail, grp in fl.groupby("tail"):
        legs = grp.to_dict("records")
        for a, b in zip(legs, legs[1:]):
            if a["direction"] == "Arrival" and b["direction"] == "Departure":
                ground = (pd.Timestamp(b["sched_time"]) - pd.Timestamp(a["sched_time"])).total_seconds() / 60
                slack = ground - a["min_turnaround"]
                rows.append({
                    "Inbound": a["flight_no"], "from": a["route_city"],
                    "Outbound": b["flight_no"], "to": b["route_city"],
                    "Aircraft": a["aircraft_name"], "tail": tail,
                    "Ground (min)": int(ground), "Min turn (min)": int(a["min_turnaround"]),
                    "Slack (min)": int(slack), "Outbound pax": int(b["passengers"]),
                })
    turn = pd.DataFrame(rows)
    if not turn.empty:
        def risk(slack):
            if slack < 10:
                return "🔴 Critical"
            if slack < 25:
                return "🟠 Tight"
            return "🟢 Comfortable"
        turn["Risk"] = turn["Slack (min)"].apply(risk)
        turn = turn.sort_values("Slack (min)")

        with st.container(horizontal=True):
            st.metric("Turnarounds today", f"{len(turn)}", border=True)
            st.metric("Critical (<10 min slack)",
                      f"{(turn['Slack (min)'] < 10).sum()}", border=True)
            st.metric("Tight (<25 min slack)",
                      f"{(turn['Slack (min)'] < 25).sum()}", border=True)
            st.metric("Pax on tight turnarounds",
                      f"{turn.loc[turn['Slack (min)'] < 25, 'Outbound pax'].sum():,}",
                      border=True)

        with st.container(border=True):
            st.dataframe(
                turn[["Risk", "Inbound", "from", "Outbound", "to", "Aircraft",
                      "Ground (min)", "Min turn (min)", "Slack (min)", "Outbound pax"]],
                hide_index=True, width="stretch", height=380,
            )
    else:
        st.caption("No linked turnarounds in this schedule.")

# ===========================================================================
# TAB 4 — Flight board
# ===========================================================================
with tab_board:
    st.subheader("Predicted flight board")
    st.caption("The full day with predicted delays and their cause.")

    res3 = appdata.cascade(day_iso, 1.3)
    board = res3.flights.copy()
    board["sched_time"] = pd.to_datetime(board["sched_time"])
    board = board.sort_values("sched_time")

    c1, c2 = st.columns(2)
    with c1:
        dirs = st.multiselect("Direction", ["Arrival", "Departure"],
                              default=["Arrival", "Departure"])
    with c2:
        show_delayed = st.toggle("Delayed flights only", value=False)

    view = board[board["direction"].isin(dirs)]
    if show_delayed:
        view = view[view["is_delayed"]]

    disp = view[["sched_time", "flight_no", "direction", "route_city",
                 "aircraft_name", "passengers", "predicted_delay", "delay_source"]].copy()
    disp["sched_time"] = disp["sched_time"].dt.strftime("%H:%M")
    st.dataframe(
        disp.rename(columns={
            "sched_time": "Sched", "flight_no": "Flight", "direction": "Dir",
            "route_city": "Route", "aircraft_name": "Aircraft",
            "passengers": "Pax", "predicted_delay": "Delay (min)",
            "delay_source": "Cause",
        }),
        hide_index=True, width="stretch", height=460,
        column_config={
            "Delay (min)": st.column_config.NumberColumn("Delay (min)", format="%d"),
        },
    )

st.divider()
with st.expander("What's real vs modelled here", icon=":material/science:"):
    st.markdown(
        """
- **Real:** the ALG route network (actual destinations), realistic aircraft
  types and seat counts, published minimum turnaround times, and the Algerian
  calendar that drives load factors and traffic (diaspora summer, Ramadan, Aïd).
- **Modelled:** the specific daily schedule, tail assignments, and the delays.
  No airline publishes its live rotation plan or delay log — so these are
  simulated the way the system actually behaves.
- **The models are the real thing.** The cascade propagation and the passenger-
  flow build-up are the exact computations you'd run on live AODB/FIDS data —
  deploying on Air Algérie's real feed is a data-connection, not a rebuild.
"""
    )
appdata.data_badge()
