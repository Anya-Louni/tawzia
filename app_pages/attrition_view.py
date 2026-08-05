"""Risque de départ , qui risque de partir, et ce que ça coûterait."""

import altair as alt
import streamlit as st

from core import appdata, attrition

appdata.sidebar_controls()

st.title("Risque de départ")
st.caption("Qui risque de partir dans les 6 prochains mois, pourquoi, et ce que "
           "coûte son remplacement.")

df = appdata.hr_attrition()
s = attrition.summary(df)

_BAND_FR = {"high": "élevé", "medium": "moyen", "low": "faible"}

with st.container(horizontal=True):
    st.metric("Risque élevé", f"{s['high']}", border=True)
    st.metric("Risque moyen", f"{s['medium']}", border=True)
    st.metric("Départs attendus (6 mois)", f"{s['expected_leavers']}", border=True,
              help="Somme des probabilités de départ individuelles.")
    st.metric("Coût à risque", appdata.dzd(s["cost_at_risk"], compact=True), border=True,
              help="Coût de remplacement attendu sur l'ensemble de l'effectif.")

st.info(
    "Modèle de risque transparent, construit sur des données réelles de présence, "
    "d'ancienneté, de salaire et de contrat, pondérées par les facteurs que la "
    "recherche RH lie au turnover. Il n'est pas entraîné sur un historique réel de "
    "départs (aucun n'est public) , un pilote réajuste les pondérations sur les "
    "vrais départs du client.",
    icon=":material/psychology:",
)

col_a, col_b = st.columns([3, 2])
with col_a:
    with st.container(border=True):
        st.subheader("Classement des risques")
        show = df.rename(columns={
            "Name": "Nom", "Risk %": "Risque %", "Band": "Bande",
            "Top driver": "Cause principale", "2nd driver": "2e cause",
            "Replacement cost (DZD)": "Coût de remplacement (DZD)",
            "Expected cost (DZD)": "Coût attendu (DZD)",
        }).copy()
        show["Bande"] = show["Bande"].map(_BAND_FR).fillna(show["Bande"])
        st.dataframe(
            show, hide_index=True, width="stretch", height=420,
            column_config={
                "Risque %": st.column_config.ProgressColumn(
                    "Risque %", min_value=0, max_value=100, format="%.0f%%"),
                "Coût de remplacement (DZD)": st.column_config.NumberColumn(format="%d"),
                "Coût attendu (DZD)": st.column_config.NumberColumn(format="%d"),
            },
        )

with col_b:
    with st.container(border=True):
        st.subheader("Risque par bande")
        band = (df["Band"].map(_BAND_FR)
                .value_counts().rename_axis("Bande").reset_index(name="Nombre"))
        chart = (
            alt.Chart(band).mark_arc(innerRadius=50).encode(
                theta="Nombre:Q",
                color=alt.Color("Bande:N", scale=alt.Scale(
                    domain=["élevé", "moyen", "faible"],
                    range=["#DB4A31", "#EAB24C", "#8FB65A"])),
                tooltip=["Bande:N", "Nombre:Q"],
            ).properties(height=220)
        )
        st.altair_chart(chart, width="stretch")

    with st.container(border=True):
        st.subheader("À faire en priorité")
        actions = attrition.retention_actions(df)
        if actions:
            for a in actions:
                st.markdown(f":material/arrow_right: {a}")
        else:
            st.caption("Aucun employé à risque élevé pour l'instant.")

appdata.data_badge()
