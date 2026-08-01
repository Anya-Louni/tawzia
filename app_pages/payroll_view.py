"""Payroll & compliance, payslips, CNAS/IRG declarations, and the law guardian."""

import streamlit as st

from core import appdata, compliance, demand as demand_mod, payroll_dz

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]

st.title("Payroll & compliance")
st.caption("The legal paperwork an Algerian employer must file every month, generated from the roster.")

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

tab_pay, tab_law = st.tabs(["Payroll", "Law-risk guardian"])

# ---------------------------------------------------------------------------
with tab_pay:
    with st.container(horizontal=True):
        st.metric("Headcount", f"{register['headcount']}", border=True)
        st.metric("Total gross", appdata.dzd(tot["gross"], compact=True), border=True)
        st.metric("Net paid", appdata.dzd(tot["net"], compact=True), border=True)
        st.metric("Employer cost", appdata.dzd(tot["employer_cost"], compact=True), border=True,
                  help="Gross + 26% CNAS employer charge.")

    with st.container(border=True):
        st.subheader("Monthly declarations to file")
        st.caption("What the employer remits to CNAS and the tax office (G50) each month.")
        st.dataframe(
            payroll_dz.declaration_lines(register), hide_index=True, width="stretch",
            column_config={"Amount (DZD)": st.column_config.NumberColumn(format="%d")},
        )
        st.download_button(
            "Download declaration (CSV)",
            payroll_dz.declaration_lines(register).to_csv(index=False).encode("utf-8"),
            file_name=f"cnas_irg_declaration_{st.session_state['profile_key']}.csv",
            mime="text/csv", icon=":material/download:",
        )

    with st.container(border=True):
        st.subheader("Sample payslip")
        st.caption(f"One {register['role']} at {register['gross_per_head']:,.0f} DZD gross/month.")
        slip = register["slips"][0]
        st.dataframe(
            [slip.as_dict()], hide_index=True, width="stretch",
        )
        if slip.exempt:
            st.info("This worker is below the 30,000 DZD IRG threshold, so pays zero income tax.",
                    icon=":material/info:")
        if register["dgi_check_flags"]:
            st.warning(
                f"{register['dgi_check_flags']} salaries fall in the 30,000-35,000 DZD "
                "smoothing band. Validate those against the official DGI calculator.",
                icon=":material/rule:",
            )

# ---------------------------------------------------------------------------
with tab_law:
    st.subheader("Labour-law risk guardian")
    st.caption("Scans the roster and workforce for violations before an inspector does.")

    alerts = compliance.scan(roster=roster, people=people, constraints=cons)
    sc = compliance.scorecard(alerts)

    status_icon = {"critical": ":material/error:", "warning": ":material/warning:",
                   "ok": ":material/verified:"}[sc["status"]]
    with st.container(horizontal=True):
        st.metric("Status", sc["label"], border=True)
        st.metric("Critical", f"{sc['critical']}", border=True)
        st.metric("Warnings", f"{sc['warning']}", border=True)

    if not alerts:
        st.success("No labour-law issues found in the current plan.", icon=":material/verified:")
    else:
        for a in alerts:
            box = st.error if a.severity == "critical" else (
                st.warning if a.severity == "warning" else st.info)
            box(f"**{a.category}** - {a.message}\n\n"
                f":material/gavel: {a.rule}\n\n:material/build: {a.action}")

appdata.data_badge()
