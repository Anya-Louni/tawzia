"""
Sources and assumptions: every figure in the product, and where it comes from.

This page is part of the pitch. It says: we know which of our numbers are
measured and which are assumed, and we do not hope you will not ask.
"""

import pandas as pd
import streamlit as st

from core import appdata, sources

appdata.sidebar_controls()

st.title("Sources and assumptions")
st.caption("Every externally sourced figure and every modelling choice, in one place.")

measured = sources.measured()
live = sources.live_sources()
assumptions = sources.assumptions()

with st.container(horizontal=True):
    st.metric("Cited measurements", len(measured), border=True)
    st.metric("Live data feeds", len(live), border=True)
    st.metric("Stated assumptions", len(assumptions), border=True)

st.divider()

st.subheader("What is real in this app")
with st.container(border=True):
    st.markdown(
        """
| Layer | Status |
|---|---|
| **Algerian calendar**: Ramadan, both Eids, Yennayer, official public holidays, Friday-Saturday weekend | **Real.** Computed from the tabular Islamic calendar, round-trip checked over 60 Hijri years and cross-checked with the Aladhan reference service. |
| **Weather**: daily temperature, rainfall and heat stress per wilaya | **Real.** ERA5 reanalysis (observed history) and operational forecast, via Open-Meteo. |
| **Macroeconomics**: population, labour force, CPI, unemployment | **Real.** World Bank Open Data, fetched live. |
| **Labour costs**: SNMG, CNAS employer contributions, legal premiums and caps | **Real.** Derived from published Algerian rates and the labour code. |
| **Payroll and filings**: IRG scale, CNAS, G50, DAS | **Real rules, dated config.** Every rate lives in `config/dz_payroll_2026.toml`, with test vectors. |
| **Employees and operational volumes** | **Simulated.** A fictional 140-person company on two sites. The calendar and weather they respond to are not. |
| **Savings figure** | **Out of sample, on simulated volumes.** The method transfers unchanged to real data. The size needs a pilot. |
"""
    )

st.divider()

st.subheader("Cited measurements")
st.caption("Published figures. Each links to its source.")
rows = [{
    "What": f.label,
    "Value": f"{f.value:,}" if isinstance(f.value, (int, float)) else str(f.value),
    "Unit": f.unit,
    "Source": f.source,
    "As of": f.as_of,
    "Link": f.url,
} for f in measured]
with st.container(border=True):
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
        "Source": st.column_config.TextColumn("Source", width="medium"),
        "Link": st.column_config.LinkColumn("Link", display_text="open"),
    })

with st.expander("Why each one matters", icon=":material/help:"):
    for f in measured:
        st.markdown(f"**{f.label}**: {f.note}")

st.divider()

st.subheader("Live data feeds")
with st.container(border=True):
    for f in live:
        st.markdown(f"**{f.label}**: {f.source}")
        st.caption(f"{f.note}  \n{f.url}")

st.divider()

st.subheader("Assumptions")
st.warning("These are our modelling choices, not findings. They are the figures a "
           "pilot client replaces with its own on day one, and the ones an investor "
           "should push on hardest.", icon=":material/warning:")
for f in assumptions:
    with st.container(border=True):
        st.markdown(f"**{f.label}** = `{f.value}` {f.unit}")
        st.caption(f.note)

st.divider()

st.subheader("What we removed from the earlier prototype")
with st.container(border=True):
    st.markdown(
        """
Being explicit about this beats hiding it: it shows the work is held to a standard.

- **A rigged baseline.** The old cost comparison charged the "naive" strategy a
  1.3x rush surcharge the optimised plan never paid. Both strategies now face
  identical cost and penalty structures.
- **Circular validation.** The old forecaster was trained and tested on the same
  fixed-seed formula. It is now walk-forward backtested on held-out periods,
  with deliberately unpredictable shocks left in.
- **The wrong weekend.** The original weekly pattern treated Saturday and Sunday
  as quiet days. The Algerian weekend is Friday-Saturday.
- **Invented labour costs.** "3,000 DZD per employee per shift" appeared with no
  derivation. Costs are now built from the SNMG and the CNAS scale.
- **A decorative flight board.** A fake live-looking flight feed drove nothing
  and proved nothing. It was removed rather than dressed up.
"""
    )

appdata.data_badge()
