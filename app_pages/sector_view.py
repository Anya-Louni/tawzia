"""Analyse sectorielle , la fonctionnalité propre au « Type d'activité » choisi."""

import streamlit as st

from core import (appdata, company_data as cd, demand as demand_mod,
                  sector_features as sf)

appdata.sidebar_controls()

profile_key = st.session_state["profile_key"]
profile = demand_mod.PROFILES[profile_key]
sig = sf.SIGNATURES.get(profile_key, {})

st.title(f"{sig.get('icon', ':material/insights:')} {sig.get('title', 'Analyse sectorielle')}")
st.caption(f"**{profile.label}** · l'outil propre à ce secteur. Changez le "
           f"**Type d'activité** dans la barre latérale pour une autre analyse.")

# Sector features need expected forward demand, not a calibrated forecast with
# intervals. We use the fast expected-demand path (no walk-forward backtest), so
# switching "Type d'activité" recomputes this page instantly.
plan = None
try:
    fc = appdata.expected_demand(
        profile_key, st.session_state["wilaya"], st.session_state["horizon"],
        st.session_state["allow_network"],
    )
    plan = {"forecast": fc}
except Exception:
    plan = None

people = cd.people()
feat = sf.compute(profile_key, plan, people)

if feat is None:
    st.info("Aucune analyse sectorielle définie pour cette activité.")
    st.stop()

st.caption(f":material/database: Effectif : **{cd.source_label()}** · "
           f"demande attendue en {profile.demand_unit} "
           f"(heuristique sectorielle, non calibrée , voir Prévision pour le "
           f"modèle complet)")
st.write(feat.intro)

# --- headline metrics ------------------------------------------------------
if feat.metrics:
    cols = st.columns(len(feat.metrics))
    for col, (label, display, help_txt) in zip(cols, feat.metrics):
        col.metric(label, display, help=help_txt or None, border=True)

# --- the actionable insight ------------------------------------------------
if feat.insight:
    st.success(feat.insight, icon=":material/lightbulb:")

# --- chart + table ---------------------------------------------------------
has_chart = feat.chart is not None and not feat.chart.empty
has_table = feat.table is not None and not feat.table.empty


def _render_chart():
    with st.container(border=True):
        st.subheader("Sur l'horizon")
        if feat.chart_kind == "area":
            st.area_chart(feat.chart, height=280)
        elif feat.chart_kind == "line":
            st.line_chart(feat.chart, height=280)
        else:
            st.bar_chart(feat.chart, height=280)


def _render_table():
    with st.container(border=True):
        st.subheader("Détail")
        st.dataframe(feat.table, hide_index=True, width="stretch")
        if feat.table_caption:
            st.caption(feat.table_caption)


if has_chart and has_table:
    left, right = st.columns([3, 2])
    with left:
        _render_chart()
    with right:
        _render_table()
elif has_chart:
    _render_chart()
elif has_table:
    _render_table()

# --- provenance ------------------------------------------------------------
if feat.notes:
    with st.expander("Sources & hypothèses de cette analyse", icon=":material/menu_book:"):
        for n in feat.notes:
            st.markdown(f"- {n}")

appdata.data_badge()
