"""Copilote décisionnel , répond à partir des vrais chiffres de l'entreprise."""

import streamlit as st

from core import ai, appdata, company_data as cd, copilot

appdata.sidebar_controls()

st.title("Copilote décisionnel")
st.caption(
    "Posez une question de gestion : le copilote répond à partir des **vrais "
    "chiffres de l'entreprise** (KPI, anomalies, risque de départ, coûts), "
    "recommande une action, et propose le scénario à simuler pour la chiffrer. "
    "Il ne raisonne que sur ces données , il n'invente aucun chiffre."
)

people = cd.people()
records = cd.attendance_records()
brief = copilot.build_brief(people, records, source_label=cd.source_label())

st.caption(f":material/database: Apprend de : **{cd.source_label()}** , "
           f"{brief['effectif']} employés. " +
           (ai.status_line() if any(ai.providers_available().values())
            else "Sans clé IA : recommandations par règles."))

# --- the brief the copilot is grounded in ----------------------------------
with st.expander("Ce que le copilote sait (brief chiffré)", icon=":material/fact_check:"):
    k = brief["kpis"]
    cols = st.columns(4)
    for i, key in enumerate(["headcount", "employer_cost", "absenteeism",
                             "attrition_risk"]):
        if key in k:
            cols[i].metric(k[key]["label"], k[key]["display"])
    st.code(copilot.brief_as_text(brief), language="text")

st.divider()

# --- always-on rule recommendations ----------------------------------------
st.subheader("Recommandations prioritaires")
for r in copilot.rule_recommendation(brief):
    st.markdown(r)

st.divider()

# --- the question box ------------------------------------------------------
st.subheader("Posez votre question")
qcols = st.columns(3)
for i, q in enumerate(copilot.SUGGESTED_QUESTIONS[:3]):
    if qcols[i].button(q, width="stretch", key=f"sq{i}"):
        st.session_state["copilot_q"] = q

question = st.text_input("Votre question", key="copilot_q",
                         placeholder="ex. Faut-il embaucher ce trimestre ?")

if st.button("Demander au copilote", type="primary", icon=":material/smart_toy:"):
    if not question.strip():
        st.warning("Écrivez une question.")
        st.stop()
    with st.spinner("Le copilote analyse les chiffres de l'entreprise..."):
        ans = copilot.ask(question.strip(), brief)
    st.session_state["copilot_ans"] = ans

ans = st.session_state.get("copilot_ans")
if ans:
    with st.container(border=True):
        if ans.get("used_ai") and ans.get("text"):
            st.markdown(ans["text"])
            st.caption(f":material/verified: Réponse fondée sur le brief chiffré "
                       f"· modèle {ans.get('model', 'Groq')}")
        else:
            st.info(ans.get("note", "Recommandations par règles ci-dessus."),
                    icon=":material/rule:")
            for r in ans.get("recommendations", []):
                st.markdown(r)

st.caption(":material/lightbulb: Sur un fichier importé, le copilote apprend de "
           "vos vrais chiffres. La couche langage (Groq) ne fait que rédiger la "
           "décision ; les modèles maison produisent les chiffres.")
appdata.data_badge()
