"""Détection d'anomalies , paie & présence, règles + modèle non supervisé."""

import streamlit as st

from core import anomalies as anom_mod, appdata, company_data as cd

appdata.sidebar_controls()

st.title("Détection d'anomalies")
st.caption(
    "Les erreurs coûteuses de paie et les signaux de présence, repérés avant "
    "l'audit CNAS/DGI ou la démission. Deux détecteurs : des **règles "
    "algériennes** interprétables (SNMG, IRG, absentéisme) et un **modèle non "
    "supervisé** (IsolationForest) qui apprend le « normal » de VOTRE entreprise."
)

people = cd.people()
records = cd.attendance_records()
st.caption(f":material/database: Source : **{cd.source_label()}** , "
           f"{len(people)} employés, {len(records)} pointages.")

res = anom_mod.detect(people, records)
s = res["summary"]
anomalies = res["anomalies"]

m = st.columns(4)
m[0].metric("Anomalies", s["total"])
m[1].metric("Critiques", s["critique"])
m[2].metric("Paie", s["paie"])
m[3].metric("Présence", s["présence"])

if s["critique"]:
    st.error(f"{s['critique']} anomalie(s) critique(s) , à régulariser "
             f"immédiatement (salaire sous le SNMG).", icon=":material/error:")

st.divider()

_SEV_COLOUR = {"critique": "red", "élevée": "orange", "moyenne": "blue",
               "faible": "gray"}
_DOMAIN_ICON = {"paie": ":material/receipt_long:", "présence": ":material/schedule:"}

tab_all, tab_pay, tab_att, tab_evidence = st.tabs(
    ["Toutes", "Paie", "Présence", "Données sources"])


def _render(items):
    if not items:
        st.success("Aucune anomalie dans cette catégorie.",
                   icon=":material/check_circle:")
        return
    for a in items:
        with st.container(border=True):
            head = st.columns([3, 1])
            head[0].markdown(
                f"{_DOMAIN_ICON.get(a.domain, '')} **{a.name}** "
                f"({a.emp_id}) , {a.detail}")
            head[1].markdown(f":{_SEV_COLOUR[a.severity]}[**{a.severity.upper()}**]")
            st.caption(f":material/lightbulb: {a.recommendation}")


with tab_all:
    _render(anomalies)
with tab_pay:
    _render([a for a in anomalies if a.domain == "paie"])
with tab_att:
    _render([a for a in anomalies if a.domain == "présence"])
with tab_evidence:
    st.markdown("**Registre de paie recalculé** (pile SNMG + CNAS + IRG)")
    st.dataframe(res["payroll_frame"], hide_index=True, width="stretch")
    st.markdown("**Statistiques de présence par employé**")
    st.dataframe(res["attendance_frame"], hide_index=True, width="stretch")

if anomalies:
    with st.expander("Exporter les anomalies", icon=":material/download:"):
        frame = anom_mod.anomalies_frame(anomalies)
        st.download_button("Télécharger (CSV)",
                           frame.to_csv(index=False).encode("utf-8"),
                           "anomalies.csv", "text/csv")

st.caption(":material/psychology: Le modèle est ajusté sur les données de "
           "l'entreprise : ce qui est « anormal » est relatif à votre propre "
           "norme, pas à un référentiel générique.")
appdata.data_badge()
