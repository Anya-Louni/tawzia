"""Tableau de KPI , les indicateurs RH & paie de l'entreprise."""

import pandas as pd
import streamlit as st

from core import appdata, company_data as cd, kpis as kpi_mod

appdata.sidebar_controls()

st.title("Tableau de KPI")
st.caption("Les indicateurs clés RH, présence, coût et risque , calculés sur la "
           "vraie pile SNMG + CNAS + IRG et sur les données de l'entreprise.")

people = cd.people()
records = cd.attendance_records()
st.caption(f":material/database: Source : **{cd.source_label()}** , "
           f"{len(people)} employés.")
if not cd.is_real():
    st.caption(":material/science: Chiffres de démonstration. Importez votre "
               "fichier dans « Données de l'entreprise » pour vos vrais KPI.")

res = kpi_mod.compute(people, records)
kpis = res["kpis"]

_BAND_COLOUR = {"bon": "green", "surveiller": "orange", "critique": "red",
                "neutre": "gray"}
_BAND_ICON = {"bon": ":material/check_circle:", "surveiller": ":material/warning:",
              "critique": ":material/error:", "neutre": ":material/remove:"}


def _kpi_group(group: str):
    items = [k for k in kpis if k.group == group]
    with st.container():
        cols = st.columns(len(items)) if items else [st]
        for col, k in zip(cols, items):
            with col:
                st.metric(k.label, k.display, border=True, help=k.help)
                if k.band != "neutre":
                    st.markdown(f":{_BAND_COLOUR[k.band]}[{_BAND_ICON[k.band]} "
                                f"{k.band}]")


for group in ["Effectif", "Coût", "Présence", "Risque"]:
    st.subheader(group)
    _kpi_group(group)
    st.write("")

st.divider()

# Health summary
crit = [k for k in kpis if k.band == "critique"]
warn = [k for k in kpis if k.band == "surveiller"]
c1, c2, c3 = st.columns(3)
c1.metric("Indicateurs critiques", len(crit))
c2.metric("À surveiller", len(warn))
c3.metric("Total suivis", len(kpis))

if crit:
    st.error("**À traiter en priorité :** " +
             " · ".join(f"{k.label} ({k.display})" for k in crit),
             icon=":material/priority_high:")
elif warn:
    st.warning("**À surveiller :** " +
               " · ".join(f"{k.label} ({k.display})" for k in warn),
               icon=":material/visibility:")
else:
    st.success("Tous les indicateurs sont dans les normes.",
               icon=":material/check_circle:")

with st.expander("Exporter le tableau de KPI", icon=":material/download:"):
    frame = kpi_mod.kpi_frame(kpis)
    st.dataframe(frame, hide_index=True, width="stretch")
    st.download_button("Télécharger (CSV)",
                       frame.to_csv(index=False).encode("utf-8"),
                       "kpi_workforce.csv", "text/csv")

appdata.data_badge()
