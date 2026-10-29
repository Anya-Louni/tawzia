"""Demand forecast: the forecast itself, and why each day looks the way it does."""

import pandas as pd
import streamlit as st

from core import appdata, demand as demand_mod, labour_dz

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

_SHIFT_FR = {k: v.label for k, v in labour_dz.SHIFTS.items()}
_SHIFT_COLOURS = ["#0A2540", "#1355C4", "#B45309"]

# Only cite calendar drivers whose coefficient shows a real effect for this
# activity (see demand.material_drivers).
drivers = profile.material_drivers()
_CONF_FR = {
    "high": "high", "boundary": "borderline (moon sighting)",
    "medium": "medium", "low": "low",
}

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
        help="Mean half-width of the p10-p90 band, from realised backtest error.",
    )
    boundary = int((fc["calendar_confidence"] == "boundary").sum()) if "calendar_confidence" in fc else 0
    st.metric(
        "Moon-sighting risk days",
        f"{boundary}",
        border=True,
        help="Days near a Hijri month boundary, where Algeria's official crescent "
             "sighting can shift the date by one day.",
    )

with st.container(border=True):
    st.subheader("Forecast with uncertainty")
    chart = daily.set_index("date")[["p10", "forecast", "p90"]]
    chart.columns = ["Low (p10)", "Forecast", "High (p90)"]
    st.line_chart(chart, height=320, color=["#C9CFD9", "#0B57A8", "#C9CFD9"])
    st.caption(
        "The band comes from the empirical distribution of backtest residuals at "
        "each horizon: it widens further out because measured error widens, not "
        "because we assumed it."
    )

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("By shift")
        # Only the shifts this activity actually runs (a school has no night slot).
        active = profile.active_shifts()
        by_shift = fc[fc["shift"].isin(active)].pivot_table(
            index="date", columns="shift", values="forecast", aggfunc="sum"
        )
        by_shift = by_shift[[s for s in active if s in by_shift.columns]]
        by_shift = by_shift.rename(columns=_SHIFT_FR)
        st.line_chart(by_shift, height=280,
                      color=_SHIFT_COLOURS[:by_shift.shape[1]])
        if (profile.runs_night() and "ramadan" in drivers
                and "is_ramadan_int" in fc.columns and fc["is_ramadan_int"].sum() > 0):
            st.caption(
                ":material/nightlight: Ramadan falls in this window: note the "
                "night shift rising as activity moves to after iftar."
            )
        elif not profile.runs_night():
            st.caption(
                f":material/schedule: {profile.label} , "
                f"{len(active)} day shifts, no night work."
            )

with col2:
    with st.container(border=True):
        st.subheader("Real weather over the horizon")
        wx = fc.drop_duplicates("date").set_index("date")[["temp_max", "precip_mm"]]
        wx.columns = ["Max temp (°C)", "Rainfall (mm)"]
        st.line_chart(wx, height=280, color=["#9C6209", "#1F5AA6"])
        st.caption(f"Source: {plan['weather_provenance']}")

with st.container(border=True):
    st.subheader("Day by day, with the reason")
    rows = []
    for _, r in fc.drop_duplicates("date").iterrows():
        reasons = []
        if r.get("holiday_name"):
            reasons.append(str(r["holiday_name"]))
        if "ramadan" in drivers and r.get("is_ramadan_int", 0):
            reasons.append(f"Ramadan day {int(r.get('ramadan_day', 0))}")
        if "diaspora" in drivers and r.get("diaspora_intensity", 0) > 0.15:
            reasons.append(f"diaspora season ({r['diaspora_intensity']:.0%} of peak)")
        if "rentree" in drivers and r.get("is_rentree_int", 0):
            reasons.append("back to school")
        wd = pd.Timestamp(r["date"]).weekday()
        if "weekend" in drivers and wd == 4:
            reasons.append("Friday, Algerian weekend")
        elif "weekend" in drivers and wd == 5:
            reasons.append("Saturday, Algerian weekend")
        if "weather" in drivers and r.get("temp_max", 0) >= 38:
            reasons.append(f"heat {r['temp_max']:.0f}°C, slows productivity")
        if "weather" in drivers and r.get("precip_mm", 0) >= 1:
            reasons.append(f"rain {r['precip_mm']:.1f} mm: {profile.weather_impact}")

        day_total = fc.loc[fc["date"] == r["date"], "forecast"].sum()
        conf = r.get("calendar_confidence", "high")
        rows.append({
            "Date": pd.Timestamp(r["date"]).strftime("%a %d %b"),
            "Forecast": int(day_total),
            "Why": "; ".join(reasons) if reasons else "ordinary working day",
            "Calendar certainty": _CONF_FR.get(conf, conf),
        })

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        column_config={
            "Date": "Date",
            "Forecast": st.column_config.NumberColumn(
                f"Forecast ({profile.demand_unit})", format="%d"
            ),
            "Why": st.column_config.TextColumn("Why this day looks this way", width="large"),
            "Calendar certainty": "Calendar certainty",
        },
    )

with st.expander("Raw forecast data", icon=":material/table:"):
    st.dataframe(fc, hide_index=True, width="stretch")

appdata.data_badge()
