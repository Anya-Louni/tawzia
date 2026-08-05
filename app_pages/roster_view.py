"""Planning & coût , le planning, ce qu'il coûte, et d'où vient le coût."""

import pandas as pd
import streamlit as st

from core import appdata, demand as demand_mod, labour_dz

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]

st.title("Planning & coût")
st.caption(f"{profile.label} · {wilaya} · rôle principal : {labour_dz.ROLES[profile.primary_role].label}")

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
        "Aucun planning légal n'existe pour cette prévision avec ces contraintes. "
        "Augmentez l'effectif permanent ou le plafond d'intérimaires dans la barre latérale.",
        icon=":material/warning:",
    )
    st.stop()

total_cost = float(roster["planned_cost"].sum())
worker_shifts = int(roster["total_staff"].sum())
ot_share = roster["overtime"].sum() / max(roster["total_staff"].sum(), 1) * 100
temp_share = roster["temp"].sum() / max(roster["total_staff"].sum(), 1) * 100

with st.container(horizontal=True):
    st.metric("Coût total de main-d'œuvre", appdata.dzd(total_cost, compact=True), border=True)
    st.metric("Shifts-employés", f"{worker_shifts:,}", border=True)
    st.metric(
        "Part heures sup", f"{ot_share:.1f}%", border=True,
        help=f"Le plafond légal est {labour_dz.MAX_OVERTIME_FRACTION:.0%} du temps "
             f"de travail légal. Imposé comme contrainte stricte, pas comme un coût.",
    )
    st.metric(
        "Part intérim", f"{temp_share:.1f}%", border=True,
        help=f"Les intérimaires coûtent {labour_dz.TEMP_AGENCY_MARKUP:.0%} de plus "
             f"que le taux chargé d'un employé direct.",
    )

col1, col2 = st.columns([3, 2])

with col1:
    with st.container(border=True):
        st.subheader("Composition d'équipe par jour")
        mix = roster.groupby("date", as_index=False)[["regular", "overtime", "temp"]].sum()
        mix = mix.set_index("date")
        mix.columns = ["Permanents", "Heures sup", "Intérim"]
        st.bar_chart(mix, height=300, color=["#16233A", "#B78B4A", "#C8102E"], stack=True)

with col2:
    with st.container(border=True):
        st.subheader("Coût par shift")
        by_shift = roster.groupby("shift", as_index=False)["planned_cost"].sum()
        by_shift["shift"] = by_shift["shift"].map(
            {k: v.label for k, v in labour_dz.SHIFTS.items()}
        )
        st.bar_chart(
            by_shift.set_index("shift")["planned_cost"],
            height=300, color="#C8102E", horizontal=True,
        )
        st.caption(
            "Les shifts de nuit portent une majoration de 30% ; le vendredi et le "
            "samedi portent la prime de repos ; les jours fériés sont payés double."
        )

_WD_FR = {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi",
          4: "Vendredi", 5: "Samedi", 6: "Dimanche"}

with st.container(border=True):
    st.subheader("Planning complet")
    show = roster[[
        "date", "shift", "required_workers", "regular", "overtime",
        "temp", "total_staff", "supervisors", "planned_cost",
    ]].copy()
    show.insert(2, "weekday", pd.to_datetime(show["date"]).dt.dayofweek.map(_WD_FR))
    show["date"] = pd.to_datetime(show["date"]).dt.strftime("%d %b")
    st.dataframe(
        show, hide_index=True, width="stretch",
        column_config={
            "date": "Date", "weekday": "Jour", "shift": "Shift",
            "required_workers": st.column_config.NumberColumn("Requis", format="%d"),
            "regular": st.column_config.NumberColumn("Permanents", format="%d"),
            "overtime": st.column_config.NumberColumn("H. sup", format="%d"),
            "temp": st.column_config.NumberColumn("Intérim", format="%d"),
            "total_staff": st.column_config.NumberColumn("Total", format="%d"),
            "supervisors": st.column_config.NumberColumn("Sup.", format="%d"),
            "planned_cost": st.column_config.NumberColumn("Coût (DZD)", format="%.0f"),
        },
    )
    st.download_button(
        "Télécharger le planning (CSV)",
        roster.to_csv(index=False).encode("utf-8"),
        file_name=f"planning_{st.session_state['profile_key']}_{wilaya}.csv",
        mime="text/csv",
        icon=":material/download:",
    )

st.divider()
st.subheader("D'où vient le chiffre du coût")
st.caption(
    "Dérivé du droit algérien, pas supposé. C'est le tableau à ouvrir quand on "
    "vous demande comment vous avez chiffré une heure de travail."
)

with st.container(border=True):
    st.dataframe(labour_dz.cost_table(), hide_index=True, width="stretch")

with st.expander("Le détail du calcul, ligne par ligne", icon=":material/calculate:"):
    for note in labour_dz.derivation_notes():
        st.markdown(f"- {note}")

with st.expander("Contraintes appliquées à ce planning", icon=":material/gavel:"):
    for line in appdata.current_constraints().describe():
        st.markdown(f"- {line}")

appdata.data_badge()
