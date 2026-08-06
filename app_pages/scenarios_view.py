"""Simulateur de scénarios , le « et si ? » chiffré sur les données réelles."""

import streamlit as st

from core import appdata, company_data as cd, labour_dz, scenarios as scen_mod

appdata.sidebar_controls()

st.title("Simulateur de scénarios")
st.caption(
    "Testez une décision avant de la prendre : hausse de salaire, embauche, "
    "SNMG, absentéisme, heures sup. contre intérim. Tout est recalculé sur la "
    "vraie pile de coûts algérienne et sur les données de l'entreprise , "
    "référence et scénario côte à côte, avec l'écart sur chaque ligne."
)

people = cd.people()
records = cd.attendance_records()
st.caption(f":material/database: Source : **{cd.source_label()}** , "
           f"{len(people)} employés.")

# --- levers ----------------------------------------------------------------
preset = st.selectbox("Partir d'un scénario type (optionnel)",
                      [", aucun ,"] + list(scen_mod.PRESETS))
base_lev = scen_mod.PRESETS.get(preset, scen_mod.Levers())

with st.container(border=True):
    st.markdown("**Les leviers**")
    c1, c2, c3 = st.columns(3)
    wage = c1.slider("Hausse de salaire (%)", -10.0, 30.0,
                     float(base_lev.wage_increase_pct), 1.0)
    snmg = c2.slider("Variation du SNMG (%)", 0.0, 30.0,
                     float(base_lev.snmg_change_pct), 1.0)
    head = c3.slider("Variation d'effectif", -20, 50,
                     int(base_lev.headcount_change), 1)
    c4, c5, c6 = st.columns(3)
    abs_on = c4.checkbox("Cibler un absentéisme",
                         value=base_lev.absenteeism_target_pct is not None)
    abs_target = c4.slider("Cible d'absentéisme (%)", 0.0, 15.0,
                           float(base_lev.absenteeism_target_pct or 4.0), 0.5,
                           disabled=not abs_on)
    ot_share = c5.slider("Part couverte en heures sup. (vs intérim)", 0.0, 1.0,
                         float(base_lev.overtime_share), 0.1)
    role = c6.selectbox("Poste pour l'embauche",
                        list(labour_dz.ROLES),
                        format_func=lambda k: labour_dz.ROLES[k].label,
                        index=list(labour_dz.ROLES).index(base_lev.new_role_key)
                        if base_lev.new_role_key in labour_dz.ROLES else 0)

levers = scen_mod.Levers(
    wage_increase_pct=wage, snmg_change_pct=snmg, headcount_change=head,
    absenteeism_target_pct=abs_target if abs_on else None,
    overtime_share=ot_share, new_role_key=role,
)

result = scen_mod.simulate(people, records, levers)
base, scen = result["baseline"], result["scenario"]
d = result["deltas"]

st.divider()

# --- headline deltas -------------------------------------------------------
def _fmt(n):
    return appdata.dzd(n, compact=True)


st.subheader("Impact du scénario")
mc = st.columns(4)
mc[0].metric("Coût employeur / mois", _fmt(scen.employer_cost),
             _fmt(d["employer_cost"]), delta_color="inverse")
mc[1].metric("Coût absentéisme / mois", _fmt(scen.absence_cost),
             _fmt(d["absence_cost"]), delta_color="inverse")
mc[2].metric("Risque de départ moyen", f"{scen.attrition_risk:.0f}%",
             f"{d['attrition_risk']:+.1f} pts", delta_color="inverse")
mc[3].metric("Coût total / mois", _fmt(scen.total_monthly),
             _fmt(d["total_monthly"]), delta_color="inverse")

net_annual = d["total_monthly"] * 12
if net_annual < 0:
    st.success(f"Ce scénario **économise ~{appdata.dzd(-net_annual, compact=True)} "
               f"par an** (coût total).", icon=":material/savings:")
elif net_annual > 0:
    st.info(f"Ce scénario **coûte ~{appdata.dzd(net_annual, compact=True)} de plus "
            f"par an** , à mettre en regard du service et de la rétention gagnés.",
            icon=":material/payments:")

# --- side by side ----------------------------------------------------------
st.subheader("Référence vs scénario")
frame = scen_mod.compare_frame(result)
money_cols = ["Masse salariale", "Coût employeur", "CNAS (35%)", "IRG (G50)",
              "Coût absentéisme", "Coût total/mois"]
st.dataframe(
    frame, hide_index=True, width="stretch",
    column_config={c: st.column_config.NumberColumn(c, format="%.0f DZD")
                   for c in money_cols},
)

st.caption(":material/functions: Chaque levier agit sur un mécanisme réel : "
           "re-tarification sur la pile SNMG/CNAS/IRG, majoration intérim vs "
           "heures sup., et re-scoring du risque de départ selon la paie et "
           "l'absentéisme.")
appdata.data_badge()
