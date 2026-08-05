"""Paie & conformité , bulletins, déclarations CNAS/IRG, et le gardien de la loi."""

import streamlit as st

from core import appdata, compliance, demand as demand_mod, payroll_dz

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]

st.title("Paie & conformité")
st.caption("Les documents légaux qu'un employeur algérien doit déposer chaque "
           "mois, générés à partir du planning.")

plan = appdata.load_forward_plan(
    st.session_state["profile_key"], st.session_state["wilaya"],
    st.session_state["horizon"], st.session_state["regular_pool"],
    st.session_state["temp_ceiling"], st.session_state["service_level"],
    st.session_state["allow_network"],
)
roster = plan["roster"]
people = appdata.hr_people()
cons = appdata.current_constraints()

register = payroll_dz.payroll_register(roster, profile.primary_role)
tot = register["totals"]

tab_pay, tab_law = st.tabs(["Paie", "Gardien des risques légaux"])

# ---------------------------------------------------------------------------
with tab_pay:
    with st.container(horizontal=True):
        st.metric("Effectif", f"{register['headcount']}", border=True)
        st.metric("Brut total", appdata.dzd(tot["gross"], compact=True), border=True)
        st.metric("Net versé", appdata.dzd(tot["net"], compact=True), border=True)
        st.metric("Coût employeur", appdata.dzd(tot["employer_cost"], compact=True), border=True,
                  help="Brut + charge patronale CNAS de 26%.")

    with st.container(border=True):
        st.subheader("Déclarations mensuelles à déposer")
        st.caption("Ce que l'employeur verse à la CNAS et au fisc (G50) chaque mois.")
        st.dataframe(
            payroll_dz.declaration_lines(register), hide_index=True, width="stretch",
            column_config={"Montant (DZD)": st.column_config.NumberColumn(format="%d")},
        )
        st.download_button(
            "Télécharger la déclaration (CSV)",
            payroll_dz.declaration_lines(register).to_csv(index=False).encode("utf-8"),
            file_name=f"declaration_cnas_irg_{st.session_state['profile_key']}.csv",
            mime="text/csv", icon=":material/download:",
        )

    with st.container(border=True):
        st.subheader("Exemple de bulletin de paie")
        st.caption(f"Un(e) {register['role']} à {register['gross_per_head']:,.0f} DZD brut/mois.")
        slip = register["slips"][0]
        st.dataframe(
            [slip.as_dict()], hide_index=True, width="stretch",
        )
        if slip.exempt:
            st.info("Cet employé est sous le seuil IRG de 30 000 DZD, il ne paie donc aucun impôt sur le revenu.",
                    icon=":material/info:")
        if register["dgi_check_flags"]:
            st.warning(
                f"{register['dgi_check_flags']} salaires tombent dans la bande de "
                "lissage 30 000-35 000 DZD. À valider avec la calculette officielle de la DGI.",
                icon=":material/rule:",
            )

# ---------------------------------------------------------------------------
with tab_law:
    st.subheader("Gardien des risques du droit du travail")
    st.caption("Analyse le planning et l'effectif pour détecter les infractions avant l'inspecteur.")

    _CAT_FR = {"Overtime": "Heures supplémentaires", "Coverage": "Couverture",
               "Contracts": "Contrats", "Leave": "Congés", "Minimum wage": "Salaire minimum"}

    alerts = compliance.scan(roster=roster, people=people, constraints=cons)
    sc = compliance.scorecard(alerts)

    with st.container(horizontal=True):
        st.metric("Statut", sc["label"], border=True)
        st.metric("Critiques", f"{sc['critical']}", border=True)
        st.metric("Avertissements", f"{sc['warning']}", border=True)

    if not alerts:
        st.success("Aucun problème de droit du travail dans le plan actuel.", icon=":material/verified:")
    else:
        for a in alerts:
            box = st.error if a.severity == "critical" else (
                st.warning if a.severity == "warning" else st.info)
            box(f"**{_CAT_FR.get(a.category, a.category)}** , {a.message}\n\n"
                f":material/gavel: {a.rule}\n\n:material/build: {a.action}")

appdata.data_badge()
