"""Tableau de bord , l'écran qu'un responsable ouvre chaque matin."""

import pandas as pd
import streamlit as st

from core import appdata, calendar_dz, demand as demand_mod, industry

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]
horizon = st.session_state["horizon"]

st.title("Tableau de bord")
st.caption(
    f"{profile.label} · {wilaya} · {horizon} prochains jours · "
    f"demande mesurée en {profile.demand_unit}"
)
industry.banner()

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
        "**Ce site ne peut pas couvrir légalement la prévision.** L'effectif "
        "permanent plus le plafond d'intérimaires ne suffit pas, dans les limites "
        "du plafond d'heures supplémentaires et du repos hebdomadaire, à servir la "
        "demande prévue. C'est un vrai constat, pas une erreur : le site a besoin "
        "de plus d'effectif. Augmentez l'effectif permanent ou le plafond "
        "d'intérimaires dans la barre latérale pour voir ce qu'il faudrait.",
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
        f"Prévision , {profile.demand_unit}",
        f"{daily['forecast'].sum():,.0f}",
        border=True,
        chart_data=daily["forecast"].tolist(),
        chart_type="line",
        help=f"Total sur les {horizon} prochains jours.",
    )
    st.metric(
        "Jour de pic",
        pd.to_datetime(peak_row["date"]).strftime("%d %b"),
        f"{peak_row['forecast']:,.0f}",
        border=True,
    )
    st.metric(
        "Effectif de pic",
        f"{peak_staff}",
        border=True,
        chart_data=daily_staff["staff"].tolist(),
        chart_type="bar",
        help="Jour le plus chargé, tous shifts confondus.",
    )
    st.metric(
        "Coût de main-d'œuvre planifié",
        appdata.dzd(total_cost, compact=True),
        border=True,
        help="Coût chargé incluant les charges patronales CNAS et les primes légales.",
    )
    st.metric(
        "Recours à l'intérim",
        f"{temp_share:.0f}%",
        border=True,
        help="Part des shifts couverts par des intérimaires, qui portent une "
             "majoration de 35%.",
    )

st.divider()

left, right = st.columns([3, 2])

with left:
    with st.container(border=True):
        st.subheader("Demande prévue")
        st.caption(
            "La zone ombrée est l'intervalle p10-p90, dérivé de l'erreur réelle "
            "du backtest à chaque horizon , ce n'est pas une distribution supposée."
        )
        chart_df = daily.set_index("date")[["p10", "forecast", "p90"]]
        chart_df.columns = ["Bas (p10)", "Prévision", "Haut (p90)"]
        st.line_chart(chart_df, height=280, color=["#C9CFD9", "#C8102E", "#C9CFD9"])

with right:
    with st.container(border=True):
        st.subheader("Ce qui influence les prochaines semaines")
        events = appdata.load_calendar_events(days=max(horizon + 60, 120))
        if events.empty:
            st.caption("Aucun grand événement du calendrier algérien dans cette fenêtre.")
        else:
            for _, e in events.head(5).iterrows():
                st.markdown(f"**{e['Date']:%d %b}** , {e['Event']}")
                st.caption(e["Impact"])

st.divider()

with st.container(border=True):
    st.subheader("Planning recommandé")
    st.caption(
        f"Construit au quantile de demande p{st.session_state['service_level'] * 100:.0f}, "
        f"dans les limites du plafond d'heures supplémentaires et du repos hebdomadaire."
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
                f"Prévision , {profile.demand_unit}", format="%d"
            ),
            "required_workers": st.column_config.NumberColumn("Requis", format="%d"),
            "regular": st.column_config.NumberColumn("Permanents", format="%d"),
            "overtime": st.column_config.NumberColumn("Heures sup", format="%d"),
            "temp": st.column_config.NumberColumn("Intérim", format="%d"),
            "total_staff": st.column_config.NumberColumn("Total", format="%d"),
            "supervisors": st.column_config.NumberColumn("Superviseurs", format="%d"),
            "planned_cost": st.column_config.NumberColumn("Coût (DZD)", format="%.0f"),
        },
    )

st.caption(f":material/cloud: Météo de la prévision : {plan['weather_provenance']}")
appdata.data_badge()
