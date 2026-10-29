"""Scenario simulator: the costed "what if?" on the company's real data."""

import streamlit as st

from core import appdata, company_data as cd, labour_dz, scenarios as scen_mod

appdata.sidebar_controls()

st.title("Scenario simulator")
st.caption("Test a decision before you make it: pay rise, hiring, SNMG, "
           "absenteeism, overtime against temps. Everything is recalculated on the "
           "real Algerian cost stack and the company's data, baseline and scenario "
           "side by side, with the delta on every line.")

people = cd.people()
records = cd.attendance_records()
st.caption(f":material/database: Source: **{cd.source_label()}**, {len(people)} employees.")

preset = st.selectbox("Start from a typical scenario (optional)",
                      ["None"] + list(scen_mod.PRESETS))
base_lev = scen_mod.PRESETS.get(preset, scen_mod.Levers())

with st.container(border=True):
    st.markdown("**The levers**")
    c1, c2, c3 = st.columns(3)
    wage = c1.slider("Pay rise (%)", -10.0, 30.0, float(base_lev.wage_increase_pct), 1.0)
    snmg = c2.slider("SNMG change (%)", 0.0, 30.0, float(base_lev.snmg_change_pct), 1.0)
    head = c3.slider("Headcount change", -20, 50, int(base_lev.headcount_change), 1)
    c4, c5, c6 = st.columns(3)
    abs_on = c4.checkbox("Target an absenteeism rate",
                         value=base_lev.absenteeism_target_pct is not None)
    abs_target = c4.slider("Absenteeism target (%)", 0.0, 15.0,
                           float(base_lev.absenteeism_target_pct or 4.0), 0.5,
                           disabled=not abs_on)
    ot_share = c5.slider("Share covered by overtime (vs temps)", 0.0, 1.0,
                         float(base_lev.overtime_share), 0.1)
    role = c6.selectbox("Role for new hires", list(labour_dz.ROLES),
                        format_func=lambda k: labour_dz.ROLES[k].label,
                        index=list(labour_dz.ROLES).index(base_lev.new_role_key)
                        if base_lev.new_role_key in labour_dz.ROLES else 0)

levers = scen_mod.Levers(
    wage_increase_pct=wage, snmg_change_pct=snmg, headcount_change=head,
    absenteeism_target_pct=abs_target if abs_on else None,
    overtime_share=ot_share, new_role_key=role,
)

result = scen_mod.simulate(people, records, levers)
scen = result["scenario"]
d = result["deltas"]

st.divider()


def _fmt(n):
    return appdata.dzd(n, compact=True)


st.subheader("Scenario impact")
mc = st.columns(4)
mc[0].metric("Employer cost / month", _fmt(scen.employer_cost),
             _fmt(d["employer_cost"]), delta_color="inverse")
mc[1].metric("Absence cost / month", _fmt(scen.absence_cost),
             _fmt(d["absence_cost"]), delta_color="inverse")
mc[2].metric("Average leaving risk", f"{scen.attrition_risk:.0f}%",
             f"{d['attrition_risk']:+.1f} pts", delta_color="inverse")
mc[3].metric("Total cost / month", _fmt(scen.total_monthly),
             _fmt(d["total_monthly"]), delta_color="inverse")

net_annual = d["total_monthly"] * 12
if net_annual < 0:
    st.success(f"This scenario **saves about {appdata.dzd(-net_annual, compact=True)} "
               f"a year** (total cost).", icon=":material/savings:")
elif net_annual > 0:
    st.info(f"This scenario **costs about {appdata.dzd(net_annual, compact=True)} more "
            f"a year**, to weigh against the service and retention gained.",
            icon=":material/payments:")

st.subheader("Baseline vs scenario")
frame = scen_mod.compare_frame(result)
money_cols = ["Wage bill", "Employer cost", "CNAS", "IRG (G50)", "Absence cost",
              "Total cost/month"]
st.dataframe(frame, hide_index=True, width="stretch",
             column_config={c: st.column_config.NumberColumn(c, format="%.0f DZD")
                            for c in money_cols})

st.caption(":material/functions: Each lever acts on a real mechanism: repricing on "
           "the SNMG/CNAS/IRG stack, temp markup against overtime, and re-scoring "
           "leaving risk from pay and absenteeism.")
appdata.data_badge()
