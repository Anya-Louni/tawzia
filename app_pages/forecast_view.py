"""Prévision de la demande — la prévision elle-même, et pourquoi chaque jour a cette allure."""

import pandas as pd
import streamlit as st

from core import appdata, demand as demand_mod, labour_dz

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]
horizon = st.session_state["horizon"]

st.title("Prévision de la demande")
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
_CONF_FR = {
    "high": "élevée", "boundary": "limite (observation lunaire)",
    "medium": "moyenne", "low": "faible",
}

daily = fc.groupby("date", as_index=False).agg(
    forecast=("forecast", "sum"), p10=("p10", "sum"), p90=("p90", "sum")
)

with st.container(horizontal=True):
    st.metric(f"Total {profile.demand_unit}", f"{daily['forecast'].sum():,.0f}", border=True)
    st.metric("Moyenne quotidienne", f"{daily['forecast'].mean():,.0f}", border=True)
    st.metric(
        "Largeur de l'intervalle",
        f"±{((daily['p90'] - daily['p10']) / daily['forecast']).mean() * 50:.0f}%",
        border=True,
        help="Demi-largeur moyenne de la bande p10-p90, issue de l'erreur de "
             "backtest réalisée.",
    )
    boundary = int((fc["calendar_confidence"] == "boundary").sum()) if "calendar_confidence" in fc else 0
    st.metric(
        "Jours à risque d'observation lunaire",
        f"{boundary}",
        border=True,
        help="Jours proches d'une frontière hégirienne, où l'annonce officielle "
             "algérienne d'observation du croissant peut décaler la date d'un jour.",
    )

with st.container(border=True):
    st.subheader("Prévision avec incertitude")
    chart = daily.set_index("date")[["p10", "forecast", "p90"]]
    chart.columns = ["Basse (p10)", "Prévision", "Haute (p90)"]
    st.line_chart(chart, height=320, color=["#C9CFD9", "#C8102E", "#C9CFD9"])
    st.caption(
        "La bande provient de la distribution empirique des résidus de backtest "
        "à chaque horizon , elle s'élargit plus loin parce que l'erreur mesurée "
        "s'élargit, pas parce que nous l'avons supposé."
    )

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("Par shift")
        by_shift = fc.pivot_table(
            index="date", columns="shift", values="forecast", aggfunc="sum"
        )
        by_shift = by_shift.rename(columns=_SHIFT_FR)
        st.line_chart(by_shift, height=280, color=["#16233A", "#C8102E", "#B78B4A"])
        if "is_ramadan_int" in fc.columns and fc["is_ramadan_int"].sum() > 0:
            st.caption(
                ":material/nightlight: Le Ramadan tombe dans cette fenêtre , "
                "notez le shift de nuit qui monte à mesure que l'activité passe "
                "à après le f'tour."
            )

with col2:
    with st.container(border=True):
        st.subheader("Météo réelle sur l'horizon")
        wx = fc.drop_duplicates("date").set_index("date")[["temp_max", "precip_mm"]]
        wx.columns = ["Temp. max (°C)", "Précipitations (mm)"]
        st.line_chart(wx, height=280, color=["#9C6209", "#1F5AA6"])
        st.caption(f"Source : {plan['weather_provenance']}")

with st.container(border=True):
    st.subheader("Jour par jour, avec la raison")
    rows = []
    for _, r in fc.drop_duplicates("date").iterrows():
        reasons = []
        if r.get("holiday_name"):
            reasons.append(str(r["holiday_name"]))
        if r.get("is_ramadan_int", 0):
            reasons.append(f"Ramadan jour {int(r.get('ramadan_day', 0))}")
        if r.get("diaspora_intensity", 0) > 0.15:
            reasons.append(f"saison diaspora ({r['diaspora_intensity']:.0%} du pic)")
        if r.get("is_rentree_int", 0):
            reasons.append("rentrée scolaire")
        wd = pd.Timestamp(r["date"]).weekday()
        if wd == 4:
            reasons.append("vendredi — week-end algérien")
        elif wd == 5:
            reasons.append("samedi — week-end algérien")
        if r.get("temp_max", 0) >= 38:
            reasons.append(f"chaleur {r['temp_max']:.0f}°C — frein à la productivité")
        if r.get("precip_mm", 0) >= 1:
            reasons.append(f"pluie {r['precip_mm']:.1f}mm — dernier kilomètre ralenti")

        day_total = fc.loc[fc["date"] == r["date"], "forecast"].sum()
        conf = r.get("calendar_confidence", "high")
        rows.append({
            "Date": pd.Timestamp(r["date"]).strftime("%a %d %b"),
            "Forecast": int(day_total),
            "Why": "; ".join(reasons) if reasons else "jour ouvré ordinaire",
            "Calendar certainty": _CONF_FR.get(conf, conf),
        })

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        column_config={
            "Date": "Date",
            "Forecast": st.column_config.NumberColumn(
                f"Prévision {profile.demand_unit}", format="%d"
            ),
            "Why": st.column_config.TextColumn("Pourquoi ce jour est ainsi", width="large"),
            "Calendar certainty": "Certitude du calendrier",
        },
    )

with st.expander("Données brutes de prévision", icon=":material/table:"):
    st.dataframe(fc, hide_index=True, width="stretch")

appdata.data_badge()
