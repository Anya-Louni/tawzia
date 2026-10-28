"""Paie & conformité , bulletins, déclarations CNAS/IRG, et le gardien de la loi."""

import streamlit as st

import datetime as dt

from core import (appdata, compliance, demand as demand_mod, documents,
                  filings, payroll_dz)

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

tab_pay, tab_law = st.tabs(["Paie", "Gardien des risques légaux"])

# ---------------------------------------------------------------------------
with tab_pay:
    today = dt.date.today()
    # La paie se clôture sur le mois écoulé tant que le 25 n'est pas passé.
    y, m = (today.year, today.month) if today.day >= 25 else (
        (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12))
    g50 = filings.g50_draft(people, y, m)
    cnas = filings.cnas_draft(people, y, m)
    das = filings.das_draft(people, today.year)
    nets = [payroll_dz.pay_breakdown({"base": round(e.monthly_gross())})["net"] for e in people]

    with st.container(horizontal=True):
        st.metric("Bulletins du mois", f"{len(people)}", border=True)
        st.metric("Net total", appdata.dzd(sum(nets), compact=True), border=True)
        st.metric("Cotisations CNAS", appdata.dzd(cnas["total_due"], compact=True), border=True,
                  help=f"Part salariale {payroll_dz.CNAS_EMPLOYEE:.0%} + patronale "
                       f"{payroll_dz.CNAS_EMPLOYER:.1%}, barème par branche [à vérifier].")
        st.metric("IRG retenu (G50)", appdata.dzd(g50["irg_total"], compact=True), border=True)

    with st.container(border=True):
        st.subheader("Déclarations préparées")
        st.caption("Brouillons chiffrés. L'agent ne dépose rien : vous déposez sur le "
                   "portail officiel, il vous rappelle la date.")
        for draft, label, rows in (
            (g50, "G50, IRG salaires", g50["lines"]),
            (cnas, "Cotisations CNAS", [{"branche": k, **v} for k, v in cnas["by_branch"].items()]),
            (das, "DAS annuelle", das["lines"]),
        ):
            c1, c2, c3 = st.columns([2.2, 1.4, 1.2], vertical_alignment="center")
            c1.markdown(f"**{label}** · {draft['period']}  \n"
                        f":material/event: avant le {draft['due']:%d/%m/%Y} · "
                        f"[portail officiel]({draft['portal']})")
            c2.caption(f"{draft['employees']} salariés")
            c3.download_button("Brouillon CSV", filings.to_csv(rows).encode("utf-8"),
                               file_name=f"{draft['type']}_{draft['period'].replace('/', '-')}.csv",
                               mime="text/csv", icon=":material/download:",
                               key=f"dl_{draft['type']}", width="stretch")
        st.download_button("Fichier de virement des salaires (CSV)",
                           filings.bank_transfer_csv(people).encode("utf-8"),
                           file_name=f"virement_{y}-{m:02d}.csv", mime="text/csv",
                           icon=":material/account_balance:")

    with st.container(border=True):
        st.subheader("Bulletin d'un salarié")
        by_id = {e.emp_id: e for e in people}
        pick = st.selectbox("Salarié", list(by_id),
                            format_func=lambda k: f"{by_id[k].name} · {k}")
        emp = by_id[pick]
        slip = payroll_dz.pay_breakdown({"base": round(emp.monthly_gross())})
        st.dataframe([{"Brut": slip["gross"], "CNAS 9 %": slip["cnas_employee"],
                       "Imposable": round(slip["taxable"]), "IRG": slip["irg"],
                       "Net": slip["net"], "Coût employeur": slip["employer_cost"]}],
                     hide_index=True, width="stretch")
        if slip["irg_steps"]["exempt"]:
            st.caption(":material/info: Base imposable sous 30 000 DA : aucun IRG.")
        st.download_button("Bulletin bilingue FR/AR (à imprimer en PDF)",
                           documents.payslip_html(emp, slip, y, m,
                                                  st.session_state.get("guichet_company",
                                                                       "SARL Démonstration")),
                           file_name=f"bulletin_{emp.emp_id}_{y}-{m:02d}.html",
                           mime="text/html", icon=":material/description:")

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
