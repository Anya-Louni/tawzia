"""Simulateur d'inspection , un test de l'inspection du travail avant l'inspecteur."""

import streamlit as st

from core import appdata, inspector, ai

appdata.sidebar_controls()

st.title("Simulateur d'inspection")
st.caption("Passez l'inspection du travail sur vous-même d'abord. Chaque constat "
           "est une vraie vérification de règle, avec l'article, une fourchette "
           "d'amende indicative et la correction.")

# Les contrôles contrat / salaire / congés se font sur l'effectif : instantanés.
people = appdata.hr_people()

# Les contrôles heures sup / couverture ont besoin de la prévision (plus lourd),
# donc ils sont optionnels , la page reste instantanée par défaut.
deep = st.toggle(
    "Vérifier aussi les heures sup et la couverture (lance la prévision, ~1 min)",
    value=False,
    help="Ajoute les contrôles du plafond d'heures supplémentaires et du "
         "sous-effectif, qui nécessitent la prévision et le planning.",
)
roster, cons = None, None
if deep:
    with st.spinner("Construction du planning à partir de la prévision..."):
        plan = appdata.load_forward_plan(
            st.session_state["profile_key"], st.session_state["wilaya"],
            st.session_state["horizon"], st.session_state["regular_pool"],
            st.session_state["temp_ceiling"], st.session_state["service_level"],
            st.session_state["allow_network"],
        )
    roster = plan["roster"]
    cons = appdata.current_constraints()

res = inspector.audit(roster=roster, people=people, constraints=cons)

with st.container(horizontal=True):
    st.metric("Risque d'inspection", f"{res['score']}/100", border=True)
    st.metric("Constats", f"{len(res['findings'])}", border=True,
              help=f"{res['scorecard']['critical']} critiques, {res['scorecard']['warning']} avertissements")
    st.metric("Exposition estimée",
              f"{res['exposure_low']:,} - {res['exposure_high']:,} DZD", border=True,
              help="Fourchettes indicatives pour prioriser, ce n'est pas un avis juridique.")

_labels = {
    "ok": "Passerait probablement une inspection aujourd'hui",
    "warning": "Exposition modérée , à corriger",
    "critical": "Exposition élevée , à corriger avant toute inspection",
}
_msg = _labels.get(res["status"], res["label"])
if res["status"] == "ok":
    st.success(_msg, icon=":material/verified_user:")
elif res["status"] == "warning":
    st.warning(_msg, icon=":material/warning:")
else:
    st.error(_msg, icon=":material/gpp_bad:")

with st.container(border=True):
    st.subheader("Ce qu'un inspecteur relèverait")
    df = inspector.to_frame(res["findings"])
    df = df.rename(columns={
        "Severity": "Gravité", "Violation": "Infraction", "Legal basis": "Base légale",
        "Est. fine exposure": "Amende estimée", "Catch likelihood": "Probabilité de détection",
        "Fix": "Correction",
    })
    st.dataframe(
        df, hide_index=True, width="stretch",
        column_config={
            "Infraction": st.column_config.TextColumn(width="large"),
            "Correction": st.column_config.TextColumn(width="large"),
        },
    )

with st.container(border=True):
    st.subheader("Le rapport de l'inspecteur")
    st.caption(ai.status_line())
    if st.button("Rédiger le rapport", type="primary", icon=":material/gavel:"):
        with st.spinner("Simulation de l'inspection..."):
            st.session_state["insp_report"] = inspector.report(res, lang="fr")
    st.markdown(st.session_state.get("insp_report") or inspector._template_report(res, "fr"))

st.caption(":material/balance: Les fourchettes d'amende sont indicatives, pour "
           "prioriser les corrections. Les pénalités réelles suivent le code du "
           "travail algérien et l'appréciation de l'inspecteur. Vérifiez avec un "
           "conseil avant d'agir.")
appdata.data_badge()
