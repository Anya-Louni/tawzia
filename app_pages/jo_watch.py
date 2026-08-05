"""Veille Journal Officiel , garder les règles à jour et chiffrer tout changement."""

import pandas as pd
import streamlit as st

from core import appdata, regwatch, ai, labour_dz

appdata.sidebar_controls()

st.title("Veille Journal Officiel")
st.caption("Les règles algériennes du travail et de la paie que la plateforme "
           "suit, si vos paramètres sont à jour, et le coût de tout changement "
           "avant qu'il n'arrive.")

# --- statut de conformité de la configuration réelle ----------------------
rows = regwatch.status()
out_of_date = [r for r in rows if r["Statut"] != "À jour"]
with st.container(horizontal=True):
    st.metric("Règles suivies", f"{len(rows)}", border=True)
    st.metric("Obsolètes", f"{len(out_of_date)}", border=True)
    st.metric("SNMG en vigueur", f"{labour_dz.SNMG_MONTHLY:,.0f} DZD", border=True)

if out_of_date:
    st.error(f"{len(out_of_date)} règle(s) ne correspondent plus à la valeur légale actuelle.",
             icon=":material/error:")
else:
    st.success("Chaque règle suivie correspond à la valeur légale actuelle.",
               icon=":material/verified:")

with st.container(border=True):
    st.subheader("Votre statut de conformité")
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch",
                 column_config={"Référence": st.column_config.TextColumn(width="medium")})

# --- simulation d'un changement de règle ----------------------------------
with st.container(border=True):
    st.subheader("Simuler un changement de règle")
    st.caption("Un changement de règle, c'est de l'argent. Fixez une valeur "
               "proposée et voyez qui est affecté et ce que cela coûte, sur votre "
               "effectif réel.")
    people = appdata.hr_people()
    c1, c2 = st.columns([1.2, 1])
    param = c1.selectbox("Règle", ["snmg", "cnas_employer"],
                         format_func=lambda p: {"snmg": "SNMG (salaire minimum)",
                                                "cnas_employer": "Taux CNAS employeur"}[p])
    if param == "snmg":
        new_value = c2.number_input("SNMG proposé (DZD/mois)", value=float(labour_dz.SNMG_MONTHLY + 6000),
                                    step=1000.0, min_value=0.0)
    else:
        new_value = c2.number_input("Taux employeur proposé", value=float(labour_dz.CNAS_EMPLOYER + 0.02),
                                    step=0.01, min_value=0.0, max_value=1.0, format="%.2f")

    imp = regwatch.simulate_change(people, param, new_value)
    m1, m2 = st.columns(2)
    m1.metric("Employés affectés", f"{imp.affected} / {imp.workforce}", border=True)
    m2.metric("Variation annuelle de coût", appdata.dzd(imp.annual_cost_delta, compact=True), border=True)
    st.caption(ai.status_line())
    if st.button("Rédiger la note de conformité", type="primary", icon=":material/edit_note:"):
        with st.spinner("Rédaction de la note..."):
            st.session_state["jo_notice"] = regwatch.impact_notice(imp, lang="fr")
    if st.session_state.get("jo_notice"):
        st.info(st.session_state["jo_notice"], icon=":material/campaign:")

with st.container(border=True):
    st.subheader("Registre suivi")
    reg = pd.DataFrame([{"Règle": r["title"], "Domaine": r["domain"],
                         "Résumé": r["summary"], "Référence": r["ref"]}
                        for r in regwatch.REGISTER])
    st.dataframe(reg, hide_index=True, width="stretch",
                 column_config={"Résumé": st.column_config.TextColumn(width="large")})

st.caption(":material/info: Dans cette démonstration, le registre est un résumé "
           "curé des règles suivies. En production, il est alimenté par l'ingestion "
           "automatique du Journal Officiel et des publications CNAS/DGI. Le "
           "contrôle de statut et le simulateur tournent sur votre effectif réel.")
appdata.data_badge()
