"""Demand forecast — the forecast itself, and why each day looks the way it does."""

import pandas as pd
import streamlit as st

from core import appdata, demand as demand_mod

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]
horizon = st.session_state["horizon"]

st.title("Demand forecast")
st.caption(f"{profile.label} · {wilaya} · {profile.demand_unit}")

plan = appdata.load_forward_plan(
    st.session_state["profile_key"],
    wilaya,
    horizon,
    st.session_state["regular_pool"],
    st.session_state["temp_ceiling"],
    st.session_state["service_level"],
    st.session_state["allow_network"],
)
fc = plan["forecast"].copy()

daily = fc.groupby("date", as_index=False).agg(
    forecast=("forecast", "sum"), p10=("p10", "sum"), p90=("p90", "sum")
)

with st.container(horizontal=True):
    st.metric(f"Total {profile.demand_unit}", f"{daily['forecast'].sum():,.0f}", border=True)
    st.metric("Daily average", f"{daily['forecast'].mean():,.0f}", border=True)
    st.metric(
        "Interval width",
        f"±{((daily['p90'] - daily['p10']) / daily['forecast']).mean() * 50:.0f}%",
        border=True,
        help="Average half-width of the p10–p90 band, from realised backtest error.",
    )
    boundary = int((fc["calendar_confidence"] == "boundary").sum()) if "calendar_confidence" in fc else 0
    st.metric(
        "Moon-sighting risk days",
        f"{boundary}",
        border=True,
        help="Days near a Hijri boundary, where Algeria's official "
             "moon-sighting announcement could shift the date by one day.",
    )

with st.container(border=True):
    st.subheader("Forecast with uncertainty")
    chart = daily.set_index("date")[["p10", "forecast", "p90"]]
    chart.columns = ["Low (p10)", "Forecast", "High (p90)"]
    st.line_chart(chart, height=320, color=["#C9CFD9", "#C8102E", "#C9CFD9"])
    st.caption(
        "The band comes from the empirical distribution of backtest residuals "
        "at each horizon — it widens further out because the measured error "
        "does, not because we assumed it would."
    )

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("By shift")
        by_shift = fc.pivot_table(
            index="date", columns="shift", values="forecast", aggfunc="sum"
        )
        st.line_chart(by_shift, height=280, color=["#16233A", "#C8102E", "#B78B4A"])
        if "is_ramadan_int" in fc.columns and fc["is_ramadan_int"].sum() > 0:
            st.caption(
                ":material/nightlight: Ramadan falls in this window — note the "
                "night shift rising as activity moves to after f'tour."
            )

with col2:
    with st.container(border=True):
        st.subheader("Real weather over the horizon")
        wx = fc.drop_duplicates("date").set_index("date")[["temp_max", "precip_mm"]]
        wx.columns = ["Max temp (°C)", "Rainfall (mm)"]
        st.line_chart(wx, height=280, color=["#9C6209", "#1F5AA6"])
        st.caption(f"Source: {plan['weather_provenance']}")

with st.container(border=True):
    st.subheader("Day-by-day, with the reason")
    rows = []
    for _, r in fc.drop_duplicates("date").iterrows():
        reasons = []
        if r.get("holiday_name"):
            reasons.append(str(r["holiday_name"]))
        if r.get("is_ramadan_int", 0):
            reasons.append(f"Ramadan day {int(r.get('ramadan_day', 0))}")
        if r.get("diaspora_intensity", 0) > 0.15:
            reasons.append(f"diaspora season ({r['diaspora_intensity']:.0%} of peak)")
        if r.get("is_rentree_int", 0):
            reasons.append("rentrée scolaire")
        wd = pd.Timestamp(r["date"]).weekday()
        if wd == 4:
            reasons.append("Friday — Algerian weekend")
        elif wd == 5:
            reasons.append("Saturday — Algerian weekend")
        if r.get("temp_max", 0) >= 38:
            reasons.append(f"heat {r['temp_max']:.0f}°C — productivity drag")
        if r.get("precip_mm", 0) >= 1:
            reasons.append(f"rain {r['precip_mm']:.1f}mm — slower last mile")

        day_total = fc.loc[fc["date"] == r["date"], "forecast"].sum()
        rows.append({
            "Date": pd.Timestamp(r["date"]).strftime("%a %d %b"),
            "Forecast": int(day_total),
            "Why": "; ".join(reasons) if reasons else "ordinary working day",
            "Calendar certainty": r.get("calendar_confidence", "high"),
        })

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        column_config={
            "Forecast": st.column_config.NumberColumn(
                f"Forecast {profile.demand_unit}", format="%d"
            ),
            "Why": st.column_config.TextColumn("Why this day looks like this", width="large"),
        },
    )

with st.expander("Raw forecast data", icon=":material/table:"):
    st.dataframe(fc, hide_index=True, width="stretch")

appdata.data_badge()
