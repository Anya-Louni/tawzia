"""Command centre — the operational view a shift manager opens each morning."""

import pandas as pd
import streamlit as st

from core import appdata, calendar_dz, demand as demand_mod

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]
horizon = st.session_state["horizon"]

st.title("Command centre")
st.caption(
    f"{profile.label} · {wilaya} · next {horizon} days · "
    f"demand measured in {profile.demand_unit}"
)

plan = appdata.load_forward_plan(
    st.session_state["profile_key"],
    wilaya,
    horizon,
    st.session_state["regular_pool"],
    st.session_state["temp_ceiling"],
    st.session_state["service_level"],
    st.session_state["allow_network"],
)

fc = plan["forecast"]
roster = plan["roster"]

if plan["infeasible"]:
    st.error(
        "**This site cannot legally cover the forecast.** The permanent pool "
        "plus the temp ceiling is not enough, within the statutory overtime "
        "cap and weekly rest requirement, to serve forecast demand. That is a "
        "real finding, not an error — the site needs more headcount. Raise the "
        "permanent workforce or the temp ceiling in the sidebar to see what "
        "it would take.",
        icon=":material/warning:",
    )

daily = fc.groupby("date", as_index=False).agg(
    forecast=("forecast", "sum"), p10=("p10", "sum"), p90=("p90", "sum")
)
daily_staff = roster.groupby("date", as_index=False).agg(
    staff=("total_staff", "sum"), cost=("planned_cost", "sum")
)

peak_row = daily.loc[daily["forecast"].idxmax()]
total_cost = float(daily_staff["cost"].sum())
peak_staff = int(roster.groupby("date")["total_staff"].sum().max())
temp_share = (
    roster["temp"].sum() / roster["total_staff"].sum() * 100
    if roster["total_staff"].sum() else 0
)

with st.container(horizontal=True):
    st.metric(
        f"Forecast {profile.demand_unit}",
        f"{daily['forecast'].sum():,.0f}",
        border=True,
        chart_data=daily["forecast"].tolist(),
        chart_type="line",
        help=f"Total over the next {horizon} days.",
    )
    st.metric(
        "Peak day",
        pd.to_datetime(peak_row["date"]).strftime("%d %b"),
        f"{peak_row['forecast']:,.0f}",
        border=True,
    )
    st.metric(
        "Peak crew",
        f"{peak_staff}",
        border=True,
        chart_data=daily_staff["staff"].tolist(),
        chart_type="bar",
        help="Busiest day, all shifts combined.",
    )
    st.metric(
        "Planned labour cost",
        appdata.dzd(total_cost, compact=True),
        border=True,
        help="Loaded cost including CNAS employer charges and statutory premiums.",
    )
    st.metric(
        "Temp reliance",
        f"{temp_share:.0f}%",
        border=True,
        help="Share of rostered worker-shifts filled by agency temps, which "
             "carry a 35% markup.",
    )

st.divider()

left, right = st.columns([3, 2])

with left:
    with st.container(border=True):
        st.subheader("Forecast demand")
        st.caption(
            "Shaded band is the p10–p90 interval, derived from realised "
            "backtest error at each horizon — not an assumed distribution."
        )
        chart_df = daily.set_index("date")[["p10", "forecast", "p90"]]
        chart_df.columns = ["Low (p10)", "Forecast", "High (p90)"]
        st.line_chart(chart_df, height=280, color=["#C9CFD9", "#C8102E", "#C9CFD9"])

with right:
    with st.container(border=True):
        st.subheader("What's driving the next few weeks")
        events = appdata.load_calendar_events(days=max(horizon + 60, 120))
        if events.empty:
            st.caption("No major Algerian calendar events in this window.")
        else:
            for _, e in events.head(5).iterrows():
                st.markdown(f"**{e['Date']:%d %b}** — {e['Event']}")
                st.caption(e["Impact"])

st.divider()

with st.container(border=True):
    st.subheader("Recommended roster")
    st.caption(
        f"Built to the p{st.session_state['service_level'] * 100:.0f} demand "
        f"quantile, within the statutory overtime cap and weekly rest rules."
    )
    show = roster[[
        "date", "shift", "forecast_for_roster", "required_workers",
        "regular", "overtime", "temp", "total_staff", "supervisors", "planned_cost",
    ]].copy()
    show["date"] = pd.to_datetime(show["date"]).dt.strftime("%a %d %b")
    st.dataframe(
        show,
        hide_index=True,
        width="stretch",
        column_config={
            "date": "Date",
            "shift": "Shift",
            "forecast_for_roster": st.column_config.NumberColumn(
                f"Forecast {profile.demand_unit}", format="%d"
            ),
            "required_workers": st.column_config.NumberColumn("Needed", format="%d"),
            "regular": st.column_config.NumberColumn("Regular", format="%d"),
            "overtime": st.column_config.NumberColumn("Overtime", format="%d"),
            "temp": st.column_config.NumberColumn("Temp", format="%d"),
            "total_staff": st.column_config.NumberColumn("Total", format="%d"),
            "supervisors": st.column_config.NumberColumn("Sup.", format="%d"),
            "planned_cost": st.column_config.NumberColumn("Cost (DZD)", format="%.0f"),
        },
    )

st.caption(f":material/cloud: Forecast weather: {plan['weather_provenance']}")
appdata.data_badge()
