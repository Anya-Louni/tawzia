"""
Sources & assumptions — every number in the product, and where it came from.

Having this page at all is part of the pitch. It says: we know which of our
numbers are measured and which are assumed, and we are not hoping you won't ask.
"""

import pandas as pd
import streamlit as st

from core import appdata, sources

appdata.sidebar_controls()

st.title("Sources & assumptions")
st.caption("Every externally-sourced figure, every modelling choice, in one place.")

measured = sources.measured()
live = sources.live_sources()
assumptions = sources.assumptions()

with st.container(horizontal=True):
    st.metric("Cited measurements", len(measured), border=True)
    st.metric("Live data feeds", len(live), border=True)
    st.metric("Stated assumptions", len(assumptions), border=True)

st.divider()

# ---------------------------------------------------------------------------
st.subheader("What is real in this app")

with st.container(border=True):
    st.markdown(
        """
| Layer | Status |
|---|---|
| **Algerian calendar** — Ramadan, the two Aïds, Yennayer, gazetted holidays, Friday–Saturday weekend | **Real.** Computed from the tabular Islamic calendar, verified round-trip over 60 Hijri years and cross-checked against the Aladhan reference service. |
| **Weather** — daily temperature, rainfall, heat stress per wilaya | **Real.** ERA5 reanalysis (observed history) and the operational forecast, via Open-Meteo. |
| **Macroeconomics** — population, labour force, CPI, unemployment | **Real.** World Bank Open Data, fetched live. |
| **Labour costs** — SNMG, CNAS employer charges, statutory premiums and caps | **Real.** Derived from published Algerian rates and the labour code. Our derived hourly floor of 138.46 DZD reproduces the officially published figure exactly. |
| **Operational volumes** — parcels, passengers, cases per shift | **Simulated.** No real Algerian operator's ledger is public. The volumes are synthetic; the calendar and weather they respond to are not. |
| **Savings figure** | **Out-of-sample, on simulated volumes.** The method is sound and would transfer unchanged to real data. The magnitude needs a pilot. |
"""
    )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("Cited measurements")
st.caption("Published figures. Each links to its source.")

rows = []
for f in measured:
    rows.append({
        "What": f.label,
        "Value": f"{f.value:,}" if isinstance(f.value, (int, float)) else str(f.value),
        "Unit": f.unit,
        "Source": f.source,
        "As of": f.as_of,
        "Link": f.url,
    })
with st.container(border=True):
    st.dataframe(
        pd.DataFrame(rows), hide_index=True, width="stretch",
        column_config={
            "Source": st.column_config.TextColumn("Source", width="medium"),
            "Link": st.column_config.LinkColumn("Link", display_text="open"),
        },
    )

with st.expander("Why each of these matters", icon=":material/help:"):
    for f in measured:
        st.markdown(f"**{f.label}** — {f.note}")

st.divider()

# ---------------------------------------------------------------------------
st.subheader("Live data feeds")

with st.container(border=True):
    for f in live:
        st.markdown(f"**{f.label}** — {f.source}")
        st.caption(f"{f.note}  \n{f.url}")

st.divider()

# ---------------------------------------------------------------------------
st.subheader("Assumptions")
st.warning(
    "These are our modelling choices, not findings. They are the numbers a "
    "pilot customer replaces with their own on day one, and the ones an "
    "investor should push hardest on.",
    icon=":material/warning:",
)

for f in assumptions:
    with st.container(border=True):
        st.markdown(f"**{f.label}** = `{f.value}` {f.unit}")
        st.caption(f.note)

st.divider()

# ---------------------------------------------------------------------------
st.subheader("What we removed from the earlier prototype")

with st.container(border=True):
    st.markdown(
        """
Being explicit about this is worth more than hiding it — it shows the work is
being held to a standard.

- **A rigged baseline.** The previous cost comparison charged the "naive"
  strategy a 1.3× rush surcharge that the optimised plan never paid. The
  saving was an artefact of that choice. Both strategies now face identical
  cost and penalty structures.

- **Circular validation.** The old forecaster was trained on a fixed-seed
  formula and then scored on that same formula, so its accuracy was guaranteed.
  It is now scored by walk-forward backtest against held-out periods, with
  deliberately unforecastable shocks left in.

- **The wrong weekend.** The original weekly pattern treated Saturday and
  Sunday as the low-demand days. Algeria's weekend is Friday–Saturday.

- **Invented labour costs.** "3,000 DZD per worker per shift" appeared with no
  derivation. Costs now build up from the SNMG and the CNAS schedule.

- **A decorative flight board.** A synthetic live-looking flight feed drove
  nothing and proved nothing. It has been removed rather than dressed up.
"""
    )

appdata.data_badge()
