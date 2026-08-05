"""Employés , les fiches et profils du personnel."""

import datetime as dt

import streamlit as st

from core import appdata, hr, labour_dz

appdata.sidebar_controls()

st.title("Employés")
st.caption("Les personnes derrière le planning, avec les droits algériens intégrés.")

people = appdata.hr_people()
today = dt.date.today()
frame = hr.workforce_frame(people, today)

south = sum(1 for e in people if e.is_southern)
avg_bal = frame["Solde acquis (j)"].mean()
avg_sen = frame["Ancienneté (ans)"].mean()

with st.container(horizontal=True):
    st.metric("Effectif", f"{len(people)}", border=True)
    st.metric("Ancienneté moyenne", f"{avg_sen:.1f} ans", border=True)
    st.metric("Solde de congés moyen", f"{avg_bal:.1f} j", border=True)
    st.metric("Sud (40 jours)", f"{south}", border=True,
              help="Les employés des wilayas sahariennes ont 40 jours de congé annuel, pas 30.")

st.caption(
    ":material/info: Les fiches employés ici sont des données de démonstration. "
    "Un déploiement réel importe votre fichier du personnel. Droits, acquisition "
    "et ancienneté sont calculés selon le droit du travail algérien."
)

col_list, col_detail = st.columns([3, 2])

with col_list:
    with st.container(border=True):
        st.subheader("Liste des employés")
        st.dataframe(
            frame, hide_index=True, width="stretch", height=460,
            column_config={
                "Brut mensuel (DZD)": st.column_config.NumberColumn(format="%d"),
                "Solde acquis (j)": st.column_config.NumberColumn(format="%.1f"),
            },
        )

with col_detail:
    with st.container(border=True):
        st.subheader("Profil")
        names = {f"{e.name} ({e.emp_id})": e for e in people}
        pick = st.selectbox("Employé", list(names), label_visibility="collapsed")
        e = names[pick]
        role = labour_dz.ROLES[e.role_key]
        st.markdown(f"### {e.name}")
        st.caption(f"{role.label} · {e.wilaya} · {e.contract}")

        st.markdown(
            f"""
| | |
|---|---|
| **Matricule** | {e.emp_id} |
| **Embauché le** | {e.hire_date:%d %b %Y} |
| **Ancienneté** | {e.seniority_years(today)} ans (prime {e.seniority_premium(today):.0%}) |
| **Droit annuel** | {e.annual_entitlement()} jours |
| **Solde acquis** | {e.accrued_leave(today):.1f} jours |
| **Personnes à charge** | {e.dependants}{' + conjoint' if e.spouse else ''} |
| **Brut mensuel** | {e.monthly_gross():,.0f} DZD |
"""
        )
        if e.is_southern:
            st.info("Wilaya du sud : 40 jours de congé annuel (30 + 10).", icon=":material/wb_sunny:")

appdata.data_badge()
