"""Payroll: payslips, CNAS / G50 / DAS drafts, and the labour-law guard."""

import datetime as dt

import streamlit as st

from core import (appdata, company_data as cd, compliance, documents, filings,
                  payroll_dz)

appdata.sidebar_controls()

st.title("Payroll")
st.caption("The month's payslips and the filings an Algerian employer must make, "
           "prepared and checked. You file; the agent never does.")

people = cd.people()

tab_pay, tab_law = st.tabs(["Payroll run", "Labour-law guard"])

# ---------------------------------------------------------------------------
with tab_pay:
    today = dt.date.today()
    # Payroll closes on the past month until the 25th.
    y, m = (today.year, today.month) if today.day >= 25 else (
        (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12))
    g50 = filings.g50_draft(people, y, m)
    cnas = filings.cnas_draft(people, y, m)
    das = filings.das_draft(people, today.year)
    nets = [payroll_dz.pay_breakdown({"base": round(e.monthly_gross())})["net"] for e in people]

    with st.container(horizontal=True):
        st.metric("Payslips this month", f"{len(people)}", border=True)
        st.metric("Total net", appdata.dzd(sum(nets), compact=True), border=True)
        st.metric("CNAS contributions", appdata.dzd(cnas["total_due"], compact=True), border=True,
                  help=f"Employee share {payroll_dz.CNAS_EMPLOYEE:.0%} + employer "
                       f"{payroll_dz.CNAS_EMPLOYER:.1%}, branch table [verify].")
        st.metric("IRG withheld (G50)", appdata.dzd(g50["irg_total"], compact=True), border=True)

    with st.container(border=True):
        st.subheader("Prepared filings")
        st.caption("Costed drafts. The agent files nothing: you file on the official "
                   "portal, it reminds you of the date.")
        for draft, label, rows in (
            (g50, "G50, salary IRG", g50["lines"]),
            (cnas, "CNAS contributions", [{"branch": k, **v} for k, v in cnas["by_branch"].items()]),
            (das, "Annual DAS", das["lines"]),
        ):
            c1, c2, c3 = st.columns([2.2, 1.4, 1.2], vertical_alignment="center")
            c1.markdown(f"**{label}** · {draft['period']}  \n"
                        f":material/event: by {draft['due']:%d/%m/%Y} · "
                        f"[official portal]({draft['portal']})")
            c2.caption(f"{draft['employees']} employees")
            c3.download_button("Draft CSV", filings.to_csv(rows).encode("utf-8"),
                               file_name=f"{draft['type']}_{draft['period'].replace('/', '-')}.csv",
                               mime="text/csv", icon=":material/download:",
                               key=f"dl_{draft['type']}", width="stretch")
        st.download_button("Salary bank transfer file (CSV)",
                           filings.bank_transfer_csv(people).encode("utf-8"),
                           file_name=f"transfer_{y}-{m:02d}.csv", mime="text/csv",
                           icon=":material/account_balance:")

    with st.container(border=True):
        st.subheader("One employee's payslip")
        by_id = {e.emp_id: e for e in people}
        pick = st.selectbox("Employee", list(by_id),
                            format_func=lambda k: f"{by_id[k].name} · {k}")
        emp = by_id[pick]
        slip = payroll_dz.pay_breakdown({"base": round(emp.monthly_gross())})
        st.dataframe([{"Gross": slip["gross"], "CNAS 9%": slip["cnas_employee"],
                       "Taxable": round(slip["taxable"]), "IRG": slip["irg"],
                       "Net": slip["net"], "Employer cost": slip["employer_cost"]}],
                     hide_index=True, width="stretch")
        if slip["irg_steps"]["exempt"]:
            st.caption(":material/info: Taxable base under 30,000 DA: no IRG.")
        st.download_button("Bilingual French/Arabic payslip (print to PDF)",
                           documents.payslip_html(emp, slip, y, m,
                                                  st.session_state.get("guichet_company",
                                                                       "Démo Handling & Logistique")),
                           file_name=f"payslip_{emp.emp_id}_{y}-{m:02d}.html",
                           mime="text/html", icon=":material/description:")

# ---------------------------------------------------------------------------
with tab_law:
    st.subheader("Labour-law guard")
    st.caption("Checks the workforce, and optionally the schedule, for violations "
               "before an inspector does.")

    deep = st.toggle("Also check the schedule (overtime cap and coverage; runs the "
                     "forecast, slower on first use)", value=False)
    roster = None
    if deep:
        plan = appdata.load_forward_plan(
            st.session_state["profile_key"], st.session_state["wilaya"],
            st.session_state["horizon"], st.session_state["regular_pool"],
            st.session_state["temp_ceiling"], st.session_state["service_level"],
            st.session_state["allow_network"],
        )
        roster = plan["roster"]

    alerts = compliance.scan(roster=roster, people=people,
                             constraints=appdata.current_constraints())
    sc = compliance.scorecard(alerts)

    with st.container(horizontal=True):
        st.metric("Status", sc["label"], border=True)
        st.metric("Critical", f"{sc['critical']}", border=True)
        st.metric("Warnings", f"{sc['warning']}", border=True)

    if not alerts:
        st.success("No labour-law issue found.", icon=":material/verified:")
    else:
        for a in alerts:
            box = st.error if a.severity == "critical" else (
                st.warning if a.severity == "warning" else st.info)
            box(f"**{a.category}**: {a.message}\n\n"
                f":material/gavel: {a.rule}\n\n:material/build: {a.action}")

appdata.data_badge()
