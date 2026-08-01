"""Business case — sizing, pricing and unit economics, all derived and shown working."""

import pandas as pd
import streamlit as st

from core import appdata, macro_dz, market, sources

appdata.sidebar_controls()

st.title("Business case")
st.caption("Bottom-up, derived from the measured saving. No top-down TAM arithmetic.")

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
st.subheader("1. Price derived from measured value")

col_ctl, col_out = st.columns([1, 2])
with col_ctl:
    # Slider works in whole percent so the labels read correctly; converted to
    # a fraction below.
    value_share_pct = st.slider(
        "Share of customer saving we capture",
        5, 40, 20, 5,
        format="%d%%",
        help="Lower leaves the customer more upside and shortens the sales "
             "cycle — which matters in a market with little history of "
             "buying software.",
    )
    value_share = value_share_pct / 100.0

pricing = market.price_from_value(saving, days_scored, value_share=value_share)

with col_out:
    with st.container(horizontal=True):
        st.metric(
            "Saving per site / month",
            appdata.dzd(pricing.saving_per_site_month_dzd, compact=True),
            border=True,
        )
        st.metric(
            "Our price / site / month",
            appdata.dzd(pricing.monthly_price_dzd, compact=True),
            border=True,
        )
        st.metric(
            "Customer return",
            f"{1 / value_share:.0f}×",
            border=True,
            help="What the customer keeps for every dinar spent with us.",
        )

st.caption(pricing.note)
st.info(
    "The price moves when the evidence moves. If a pilot shows a smaller "
    "saving, this number and everything below it come down with it. That is "
    "deliberate — it stops the pitch drifting away from what the software "
    "actually does.",
    icon=":material/link:",
)

st.divider()

# ---------------------------------------------------------------------------
st.subheader("2. Market size, counted bottom-up")

sizing = market.sizing(pricing.monthly_price_dzd)

with st.container(horizontal=True):
    st.metric("TAM", appdata.dzd(sizing["tam_dzd"], compact=True),
              f"{sizing['total_sites']} sites", border=True)
    st.metric("SAM", appdata.dzd(sizing["sam_dzd"], compact=True),
              "privately-owned only", border=True)
    st.metric("SOM (3 yr)", appdata.dzd(sizing["som_dzd"], compact=True),
              f"{sizing['som_sites']} sites", border=True)
    st.metric("Beachhead", f"{sizing['beachhead_sites']} sites",
              "parcel & delivery branches", border=True)

with st.container(border=True):
    st.markdown("**Segments**")
    st.dataframe(
        sizing["table"], hide_index=True, width="stretch",
        column_config={
            "Sites": st.column_config.NumberColumn("Sites", format="%d"),
            "Avg shift workers": st.column_config.NumberColumn("Avg crew", format="%d"),
            "Annual value (DZD)": st.column_config.NumberColumn("Annual value", format="%.0f"),
            "Basis": st.column_config.TextColumn("How we counted", width="large"),
        },
    )

for n in sizing["notes"]:
    st.caption(f"· {n}")

st.warning(
    "**Be straight about this in the room.** Algeria alone is a "
    f"{sizing['sam_dzd'] / 135e6:.1f}-million-dollar-a-year serviceable "
    "market. That is a good, profitable business — it is not, on its own, a "
    "venture-scale one. Anyone who tells an investor otherwise loses the room "
    "at diligence. The regional case below is what justifies a second cheque.",
    icon=":material/warning:",
)

st.divider()

# ---------------------------------------------------------------------------
st.subheader("3. Why this travels beyond Algeria")

expansion = market.regional_expansion(sizing["sam_dzd"])

with st.container(border=True):
    st.dataframe(
        expansion["table"], hide_index=True, width="stretch",
        column_config={
            "Population (M)": st.column_config.NumberColumn("Pop. (M)", format="%.1f"),
            "Scaled SAM (DZD/yr)": st.column_config.NumberColumn("Scaled SAM", format="%.0f"),
        },
    )
    st.metric(
        "Regional serviceable market",
        appdata.dzd(expansion["total_dzd"], compact=True),
        f"≈ ${expansion['total_dzd'] / 135:,.0f}/year",
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
        st.markdown("**What to believe and what not to**")
        for a in ue.assumptions():
            st.markdown(f"- {a}")
        st.caption(
            "The LTV:CAC figure looks strong mainly because the churn "
            "assumption is generous and unevidenced. Treat it as a placeholder "
            "until there is cohort data — and say so before an investor says "
            "it for you."
        )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("5. Funding context in Algeria")

with st.container(border=True):
    for line in market.funding_context():
        st.markdown(f"- {line}")

macro = appdata.load_macro(st.session_state["allow_network"])
if not macro.empty:
    with st.expander("Algerian macro backdrop (World Bank, live)", icon=":material/public:"):
        st.dataframe(
            macro, hide_index=True, width="stretch",
            column_config={"Value": st.column_config.NumberColumn("Value", format="%.1f")},
        )

appdata.data_badge()
