"""Négociateur de rétention , l'action la moins chère pour garder un employé à risque."""

import pandas as pd
import streamlit as st

from core import appdata, retention, ai

appdata.sidebar_controls()

st.title("Négociateur de rétention")
st.caption("Le risque de départ dit qui pourrait partir. Ceci dit l'action la "
           "moins chère pour le garder, testée via le même modèle, et rédige "
           "l'entretien.")

df = appdata.hr_attrition()
people = appdata.hr_people()
records = appdata.hr_attendance()

if df.empty:
    st.info("Aucun effectif chargé.")
    st.stop()

_BAND_FR = {"high": "ÉLEVÉ", "medium": "MOYEN", "low": "FAIBLE"}

names = df["Name"].tolist()
ids = df["ID"].tolist()
choice = st.selectbox("Employé", range(len(names)),
                      format_func=lambda i: f"{names[i]}  ({df.iloc[i]['Risk %']:.0f}% de risque)")
emp_id = ids[choice]

plan = retention.plan_for_employee(people, records, emp_id)
if plan is None:
    st.warning("Impossible de construire un plan pour cet employé.")
    st.stop()

with st.container(horizontal=True):
    st.metric("Risque de départ (6 mois)", f"{plan.base_risk:.0%}", border=True)
    st.metric("Bande", _BAND_FR.get(plan.band, plan.band.upper()), border=True)
    st.metric("Coût de remplacement", appdata.dzd(plan.replacement_cost, compact=True), border=True)
    st.metric("Cause principale", plan.top_driver, border=True)

with st.container(border=True):
    st.subheader("Leviers de rétention, classés par valeur nette")
    st.caption("Chaque levier passe par le modèle de risque : il modifie la cause "
               "qu'il vise, recalcule le risque, et convertit la baisse en argent "
               "économisé (baisse de risque x coût de remplacement).")
    if plan.levers:
        table = pd.DataFrame([{
            "Levier": l.label,
            "Coût (DZD/an)": l.cost_dzd,
            "Nouveau risque": round(l.new_risk * 100, 1),
            "Baisse (points)": round(l.risk_drop * 100, 1),
            "Valeur économisée (DZD)": l.value_dzd,
            "Net (DZD)": l.net_dzd,
        } for l in plan.levers])
        st.dataframe(
            table, hide_index=True, width="stretch",
            column_config={
                "Coût (DZD/an)": st.column_config.NumberColumn(format="%d"),
                "Nouveau risque": st.column_config.NumberColumn(format="%.1f%%"),
                "Valeur économisée (DZD)": st.column_config.NumberColumn(format="%d"),
                "Net (DZD)": st.column_config.NumberColumn(format="%d"),
            },
        )
        if plan.best:
            st.success(f"Recommandé : **{plan.best.label}** , rapporte environ "
                       f"{plan.best.net_dzd:,.0f} DZD par rapport à une perte. "
                       f"{plan.best.rationale}", icon=":material/recommend:")
    else:
        st.caption("Cet employé est à faible risque , aucune intervention nécessaire.")

if plan.best:
    with st.container(border=True):
        st.subheader("L'entretien")
        st.caption(ai.status_line())
        if st.button("Rédiger l'entretien", type="primary", icon=":material/forum:"):
            with st.spinner("Rédaction du script..."):
                st.session_state["ret_script"] = retention.write_script(plan, lang="fr")
        if st.session_state.get("ret_script"):
            st.markdown(st.session_state["ret_script"])

st.info("Comme le modèle de risque, les pondérations sont documentées, pas "
        "entraînées sur de vrais départs algériens ; les montants sont donc "
        "indicatifs et réajustés sur un pilote. Le contrefactuel via le modèle "
        "est la vraie méthode.", icon=":material/psychology:")
appdata.data_badge()
