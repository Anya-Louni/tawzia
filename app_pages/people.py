"""
Employees: the staff files and profiles.

The page also adds an employee. The form arrives **prefilled** with what the
platform already knows (site, activity, majority contract, today's date), and
everything stays editable: filling a file should not mean retyping what is
known, but nobody should be forced into a guessed value.
"""

import datetime as dt

import streamlit as st

from core import appdata, company_data as cd, demand as demand_mod, hr, labour_dz

appdata.sidebar_controls()

st.title("Employees")
st.caption("The people behind the schedule, with Algerian entitlements built in.")

people = cd.people()
today = dt.date.today()
frame = hr.workforce_frame(people, today)

south = sum(1 for e in people if e.is_southern)
avg_bal = frame["Leave balance (days)"].mean()
avg_sen = frame["Seniority (years)"].mean()

with st.container(horizontal=True):
    st.metric("Headcount", f"{len(people)}", border=True)
    st.metric("Average seniority", f"{avg_sen:.1f} years", border=True)
    st.metric("Average leave balance", f"{avg_bal:.1f} days", border=True)
    st.metric("South (40 days)", f"{south}", border=True,
              help="Employees in the Saharan wilayas get 40 days of annual leave, not 30.")

st.caption(
    f":material/info: Source: **{cd.source_label()}**. Entitlements, accrual and "
    f"seniority are computed under Algerian labour law."
)

# ---------------------------------------------------------------------------
# Add an employee: prefilled, fully editable
# ---------------------------------------------------------------------------
_profile = demand_mod.PROFILES[st.session_state["profile_key"]]
_site_wilaya = st.session_state["wilaya"]
_majority_contract = ("CDI" if sum(
    1 for e in people if str(e.contract).upper() == "CDI") >= len(people) / 2
    else "CDD")
_digits = [int("".join(c for c in str(e.emp_id) if c.isdigit()))
           for e in people if any(c.isdigit() for c in str(e.emp_id))]
_prefix = "".join(c for c in str(people[0].emp_id) if c.isalpha()) if people else "E"
_next_id = f"{_prefix}{max(_digits or [999]) + 1}"

with st.expander("Add an employee", icon=":material/person_add:"):
    st.caption(
        f"Prefilled from what the platform already knows: site "
        f"**{_site_wilaya}**, activity **{_profile.label}**, most common contract "
        f"in the team **{_majority_contract}**, next staff number "
        f"**{_next_id}**. Correct whatever does not fit."
    )
    with st.form("add_employee"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("First and last name", placeholder="e.g. Amine Benali")
        emp_id = c2.text_input("Staff number", value=_next_id)
        role_labels = {k: labour_dz.ROLES[k].label for k in labour_dz.ROLES}
        role_key = c3.selectbox(
            "Role", options=list(role_labels),
            format_func=lambda k: role_labels[k],
            index=list(role_labels).index(_profile.primary_role),
        )

        c4, c5, c6 = st.columns(3)
        wilaya_in = c4.selectbox(
            "Wilaya", options=sorted(hr.SOUTHERN_WILAYAS
                                     | {_site_wilaya, "Alger", "Oran",
                                        "Constantine", "Blida", "Annaba"}),
            index=None, placeholder=_site_wilaya,
            help="Empty = the current site. A southern wilaya gives 40 days of "
                 "leave instead of 30.",
        )
        hire = c5.date_input("Hire date", value=dt.date.today(), format="DD/MM/YYYY")
        contract = c6.selectbox("Contract", options=["CDI", "CDD"],
                                index=0 if _majority_contract == "CDI" else 1)

        c7, c8, c9 = st.columns(3)
        dependants = c7.number_input("Dependants", 0, 12, 0)
        spouse = c8.toggle("Dependent spouse")
        gross = c9.number_input(
            "Monthly gross (DZD)", 0, 1_000_000,
            int(labour_dz.ROLES[_profile.primary_role].gross_monthly), step=1000,
            help="Prefilled with the role's scale. 0 = let the platform apply the scale.")

        submitted = st.form_submit_button("Add to the register", type="primary",
                                          icon=":material/save:")

    if submitted:
        if len(name.strip().split()) < 2:
            st.warning("Write the first and last name.")
        elif any(str(e.emp_id) == emp_id.strip() for e in people):
            st.error(f"Staff number {emp_id} already exists in the register.")
        else:
            new = hr.Employee(
                emp_id=emp_id.strip() or _next_id,
                name=name.strip(),
                role_key=role_key,
                wilaya=wilaya_in or _site_wilaya,
                hire_date=hire,
                dependants=int(dependants),
                spouse=bool(spouse),
                contract=contract,
                leave_taken_ytd=0.0,
                gross_override=float(gross) if gross else None,
            )
            cd.set_company_data(
                list(people) + [new], cd.attendance_records(),
                label=(cd.source_label() if cd.is_uploaded()
                       else "Demo + files entered by hand"),
            )
            st.success(
                f"{new.name} added. Annual entitlement: "
                f"{new.annual_entitlement()} days; gross "
                f"{new.monthly_gross():,.0f} DZD. The whole platform uses it straight away.")
            st.rerun()

    st.divider()
    st.caption(
        "Many files to enter? Import your staff file: columns are recognised "
        "automatically in French and English, and an empty template can be downloaded."
    )
    st.page_link("app_pages/company_data_view.py", label="Import a staff file",
                 icon=":material/upload_file:")

col_list, col_detail = st.columns([3, 2])

with col_list:
    with st.container(border=True):
        st.subheader("Employee list")
        st.dataframe(
            frame, hide_index=True, width="stretch", height=460,
            column_config={
                "Monthly gross (DZD)": st.column_config.NumberColumn(format="%d"),
                "Leave balance (days)": st.column_config.NumberColumn(format="%.1f"),
            },
        )

with col_detail:
    with st.container(border=True):
        st.subheader("Profile")
        names = {f"{e.name} ({e.emp_id})": e for e in people}
        pick = st.selectbox("Employee", list(names), label_visibility="collapsed")
        e = names[pick]
        role = labour_dz.ROLES[e.role_key]
        st.markdown(f"### {e.name}")
        st.caption(f"{role.label} · {e.wilaya} · {e.contract}")

        st.markdown(
            f"""
| | |
|---|---|
| **Staff number** | {e.emp_id} |
| **Hired on** | {e.hire_date:%d %b %Y} |
| **Seniority** | {e.seniority_years(today)} years (premium {e.seniority_premium(today):.0%}) |
| **Annual entitlement** | {e.annual_entitlement()} days |
| **Leave balance** | {e.accrued_leave(today):.1f} days |
| **Dependants** | {e.dependants}{' + spouse' if e.spouse else ''} |
| **Monthly gross** | {e.monthly_gross():,.0f} DZD |
"""
        )
        if e.is_southern:
            st.info("Southern wilaya: 40 days of annual leave (30 + 10).", icon=":material/wb_sunny:")

appdata.data_badge()
