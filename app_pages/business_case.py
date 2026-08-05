"""Analyse économique , dimensionnement, prix et unit economics, tout dérivé et montré."""

import pandas as pd
import streamlit as st

from core import appdata, macro_dz, market, sources

appdata.sidebar_controls()

st.title("Analyse économique")
st.caption("Bottom-up, dérivé de l'économie mesurée. Aucune arithmétique de TAM top-down.")

ev = appdata.load_evidence(
    st.session_state["profile_key"],
    st.session_state["wilaya"],
    st.session_state["horizon"],
    st.session_state["regular_pool"],
    st.session_state["temp_ceiling"],
    st.session_state["service_level"],
    st.session_state["allow_network"],
)

days_scored = int(ev.delta["days_scored"])
saving = float(ev.delta["saving_dzd"])

# ---------------------------------------------------------------------------
st.subheader("1. Prix dérivé de la valeur mesurée")

col_ctl, col_out = st.columns([1, 2])
with col_ctl:
    # Le curseur travaille en pourcentage entier pour un affichage correct ;
    # converti en fraction plus bas.
    value_share_pct = st.slider(
        "Part de l'économie client que nous capturons",
        5, 40, 20, 5,
        format="%d%%",
        help="Plus bas laisse plus de gain au client et raccourcit le cycle de "
             "vente , ce qui compte dans un marché peu habitué à acheter du "
             "logiciel.",
    )
    value_share = value_share_pct / 100.0

pricing = market.price_from_value(saving, days_scored, value_share=value_share)

with col_out:
    with st.container(horizontal=True):
        st.metric(
            "Économie par site / mois",
            appdata.dzd(pricing.saving_per_site_month_dzd, compact=True),
            border=True,
        )
        st.metric(
            "Notre prix / site / mois",
            appdata.dzd(pricing.monthly_price_dzd, compact=True),
            border=True,
        )
        st.metric(
            "Retour client",
            f"{1 / value_share:.0f}×",
            border=True,
            help="Ce que le client conserve pour chaque dinar dépensé chez nous.",
        )

st.caption(pricing.note)
st.info(
    "Le prix bouge quand la preuve bouge. Si un pilote montre une économie plus "
    "faible, ce chiffre et tout ce qui suit baissent avec lui. C'est délibéré , "
    "cela empêche le discours commercial de dériver loin de ce que le logiciel "
    "fait réellement.",
    icon=":material/link:",
)

st.divider()

# ---------------------------------------------------------------------------
st.subheader("2. Taille du marché, comptée bottom-up")

sizing = market.sizing(pricing.monthly_price_dzd)

with st.container(horizontal=True):
    st.metric("TAM", appdata.dzd(sizing["tam_dzd"], compact=True),
              f"{sizing['total_sites']} sites", border=True)
    st.metric("SAM", appdata.dzd(sizing["sam_dzd"], compact=True),
              "privé uniquement", border=True)
    st.metric("SOM (3 ans)", appdata.dzd(sizing["som_dzd"], compact=True),
              f"{sizing['som_sites']} sites", border=True)
    st.metric("Tête de pont", f"{sizing['beachhead_sites']} sites",
              "agences colis & livraison", border=True)

with st.container(border=True):
    st.markdown("**Segments**")
    st.dataframe(
        sizing["table"], hide_index=True, width="stretch",
        column_config={
            "Segment": "Segment",
            "Sites": st.column_config.NumberColumn("Sites", format="%d"),
            "Avg shift workers": st.column_config.NumberColumn("Équipe moy.", format="%d"),
            "Annual value (DZD)": st.column_config.NumberColumn("Valeur annuelle", format="%.0f"),
            "Confidence": "Confiance",
            "Basis": st.column_config.TextColumn("Comment nous avons compté", width="large"),
        },
    )

for n in sizing["notes"]:
    st.caption(f"· {n}")

st.warning(
    "**Soyez franc là-dessus dans la salle.** L'Algérie seule est un marché "
    f"adressable de {sizing['sam_dzd'] / 135e6:.1f} millions de dollars par an. "
    "C'est une bonne affaire rentable , ce n'est pas, à elle seule, une affaire "
    "à l'échelle du capital-risque. Quiconque dit le contraire à un investisseur "
    "perd la salle en due diligence. C'est le dossier régional ci-dessous qui "
    "justifie un second chèque.",
    icon=":material/warning:",
)

st.divider()

# ---------------------------------------------------------------------------
st.subheader("3. Pourquoi cela dépasse l'Algérie")

expansion = market.regional_expansion(sizing["sam_dzd"])

with st.container(border=True):
    st.dataframe(
        expansion["table"], hide_index=True, width="stretch",
        column_config={
            "Population (M)": st.column_config.NumberColumn("Pop. (M)", format="%.1f"),
            "SAM proportionnel (DZD/an)": st.column_config.NumberColumn("SAM proportionnel", format="%.0f"),
        },
    )
    st.metric(
        "Marché adressable régional",
        appdata.dzd(expansion["total_dzd"], compact=True),
        f"≈ {expansion['total_dzd'] / 135:,.0f} $/an",
        border=True,
    )

for n in expansion["notes"]:
    st.caption(f"· {n}")

st.divider()

# ---------------------------------------------------------------------------
st.subheader("4. Unit economics")

ue = market.UnitEconomics(pricing.monthly_price_dzd)

col_l, col_r = st.columns([2, 3])
with col_l:
    with st.container(border=True):
        st.dataframe(ue.table(), hide_index=True, width="stretch")
with col_r:
    with st.container(border=True):
        st.markdown("**Ce qu'il faut croire et ce qu'il ne faut pas**")
        for a in ue.assumptions():
            st.markdown(f"- {a}")
        st.caption(
            "Le ratio LTV:CAC paraît solide surtout parce que l'hypothèse "
            "d'attrition est généreuse et non prouvée. Traitez-le comme un "
            "provisoire tant qu'il n'y a pas de données de cohorte , et dites-le "
            "avant qu'un investisseur ne le dise pour vous."
        )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("5. Contexte de financement en Algérie")

with st.container(border=True):
    for line in market.funding_context():
        st.markdown(f"- {line}")

macro = appdata.load_macro(st.session_state["allow_network"])
if not macro.empty:
    with st.expander("Toile de fond macroéconomique algérienne (Banque mondiale, en direct)", icon=":material/public:"):
        st.dataframe(
            macro, hide_index=True, width="stretch",
            column_config={"Value": st.column_config.NumberColumn("Valeur", format="%.1f")},
        )

appdata.data_badge()
