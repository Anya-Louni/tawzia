"""
Proof: the page that decides whether you believe the rest of the app.

Shows the walk-forward backtest, the comparison against an HR tool that does
not understand Algeria, and the out-of-sample money comparison where both
schedules were built blind and scored on the same realised demand.
"""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from core import appdata, demand as demand_mod, sources

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]
horizon = st.session_state["horizon"]

C_DZ, C_GEN, C_BASE, C_GREY = "#0B57A8", "#6CBEF5", "#0A2540", "#7C8494"

st.title("Proof")
st.caption("Everything here is out of sample. No model on this page has ever "
           "seen the data it is scored on.")

st.info(
    "**The honest caveat, up front.** We do not have a real Algerian operator's "
    "volume register; nobody outside those companies does. The *demand volumes* "
    "on this page are simulated. What is real is the **Algerian calendar** the "
    "demand responds to (real Ramadan and Eid dates, the real Friday-Saturday "
    "weekend, real public holidays) and the **observed weather** from the ERA5 "
    "archive for this wilaya. These results validate the method and the "
    "mechanics, not the market. The size needs a pilot.",
    icon=":material/info:",
)

with st.spinner("Running the backtest and scoring the schedules…"):
    ev = appdata.load_evidence(
        st.session_state["profile_key"], wilaya, horizon,
        st.session_state["regular_pool"], st.session_state["temp_ceiling"],
        st.session_state["service_level"], st.session_state["allow_network"],
    )

bt = ev.backtest
metrics = bt.metrics
delta = ev.delta

dz = float(metrics.loc[metrics["Model"] == "Tawzia", "MAPE_%"].iloc[0])
gen = float(metrics.loc[metrics["Model"] == "Generic international model", "MAPE_%"].iloc[0])
sn = float(metrics.loc[metrics["Model"] == "Seasonal naive", "MAPE_%"].iloc[0])

st.subheader("1. Does the forecast beat the alternatives?")

with st.container(horizontal=True):
    st.metric("Our forecast error (MAPE)", f"{dz:.1f}%", border=True)
    st.metric("vs a generic international tool", f"{gen:.1f}%",
              f"-{(gen - dz) / gen * 100:.0f}% error", border=True,
              help="Same algorithm, same data, same tuning, but with the feature "
                   "set an HR tool built for Europe would have: Saturday-Sunday "
                   "weekend, no Hijri calendar, no diaspora season.")
    st.metric("vs seasonal naive", f"{sn:.1f}%",
              f"-{(sn - dz) / sn * 100:.0f}% error", border=True,
              help="Same shift, same weekday, last week. What a good operations "
                   "manager does in their head, and a genuinely hard baseline.")
    st.metric("Forecast origins", f"{bt.n_origins}", border=True)

with st.container(border=True):
    st.markdown("**Full backtest metrics**")
    st.dataframe(metrics, hide_index=True, width="stretch", column_config={
        "Model": "Model",
        "MAE": st.column_config.NumberColumn("MAE", format="%.0f"),
        "RMSE": st.column_config.NumberColumn("RMSE", format="%.0f"),
        "MAPE_%": st.column_config.NumberColumn("MAPE %", format="%.2f"),
        "Bias_%": st.column_config.NumberColumn("Bias %", format="%+.2f"),
        "Under_%": st.column_config.NumberColumn("Under-forecast %", format="%.1f"),
    })
    st.caption(
        "**Bias** matters more than MAPE for a schedule. A forecast biased low "
        "understaffs, and being short costs about "
        f"{sources.value('understaffing_penalty_multiple')}x what the saved wages "
        "were worth. Ours is deliberately left slightly positive: over-forecasting "
        "is the cheaper direction."
    )

with st.container(border=True):
    st.markdown("**Error by forecast horizon**")
    st.caption("How fast each approach degrades as you plan further out.")
    pivot = bt.by_horizon.pivot(index="horizon", columns="Model", values="MAPE_%")
    st.line_chart(pivot, height=280, color=[C_GEN, C_GREY, C_DZ, C_BASE][:pivot.shape[1]])

st.divider()

st.subheader("2. Does the better forecast turn into money?")
st.caption("Both schedules were built only from information available at the "
           "forecast origin; neither saw the demand it would face. Both pay "
           "identical wage rates, identical legal premiums and an identical "
           "penalty for demand they failed to cover. The only difference is "
           "forecast quality.")

with st.container(horizontal=True):
    st.metric("Cost saving", f"{delta['saving_pct']:.1f}%",
              appdata.dzd(delta["saving_dzd"], compact=True), border=True)
    st.metric("Service level gain", f"+{delta['service_gain_pp']:.1f} pts", border=True,
              help="Share of demand actually served.")
    st.metric("Win rate", f"{delta['win_rate']:.0f}%",
              f"over {delta['origins']} origins", border=True)
    st.metric("Worst origin", f"{delta['worst_origin_pct']:+.1f}%", border=True,
              help="We lose money on some windows. A comparison that never loses "
                   "is a rigged comparison.")

with st.container(border=True):
    st.markdown("**Cost comparison, summed over every scored window**")
    st.dataframe(ev.comparison, hide_index=True, width="stretch", column_config={
        "Strategy": "Strategy",
        "Labour cost (DZD)": st.column_config.NumberColumn("Labour", format="%.0f"),
        "Shortfall cost (DZD)": st.column_config.NumberColumn("Shortfall", format="%.0f"),
        "Total cost (DZD)": st.column_config.NumberColumn("Total", format="%.0f"),
        "Unserved units": st.column_config.NumberColumn("Unserved", format="%.0f"),
        "Service level": st.column_config.NumberColumn("Service", format="%.1%%"),
        "Idle units": st.column_config.NumberColumn("Idle", format="%.0f"),
        "Worker-shifts": st.column_config.NumberColumn("Staff shifts", format="%d"),
        "Cost per unit (DZD)": st.column_config.NumberColumn("Cost/unit", format="%.2f"),
    })
    st.caption("Note the optimised plan spends **more** on labour and still comes "
               "out ahead. That is the real lesson: in Algerian shift operations, "
               "the expensive failure is understaffing, not generosity.")

with st.container(border=True):
    st.markdown("**Saving by forecast window**")
    st.caption("Each bar is an independent window. The negatives are real: windows "
               "where a fixed schedule happened to fit demand better.")
    po = ev.per_origin.copy()
    po["origin"] = pd.to_datetime(po["origin"])
    po = po.sort_values("origin")
    po["label"] = po["origin"].dt.strftime("%d %b %y")
    po["sign"] = np.where(po["saving_pct"] >= 0, "Saving", "Loss")
    # Altair with sort=None keeps the timeline order.
    savings_chart = (
        alt.Chart(po).mark_bar().encode(
            x=alt.X("label:N", sort=None, title=None,
                    axis=alt.Axis(labelAngle=-45, labelFontSize=10)),
            y=alt.Y("saving_pct:Q", title="Saving vs fixed schedule (%)"),
            color=alt.Color("sign:N", scale=alt.Scale(domain=["Saving", "Loss"],
                                                      range=[C_DZ, C_GREY]),
                            legend=alt.Legend(title=None, orient="top")),
            tooltip=[alt.Tooltip("label:N", title="Window starting"),
                     alt.Tooltip("saving_pct:Q", title="Saving %", format="+.1f"),
                     alt.Tooltip("saving:Q", title="Saving DZD", format=",.0f")],
        ).properties(height=260)
    )
    st.altair_chart(savings_chart, width="stretch")

st.divider()

st.subheader("3. Which Algerian signals actually earn their place?")

fi = appdata.load_feature_importance(
    st.session_state["profile_key"], wilaya, st.session_state["allow_network"])

label_map = {
    "is_weekend_int": "Friday-Saturday weekend",
    "is_holiday_int": "Algerian public holidays",
    "is_ramadan_int": "Ramadan",
    "ramadan_progress": "Position within Ramadan",
    "eid_fitr_runup": "Run-up to Eid al-Fitr",
    "eid_adha_runup": "Run-up to Eid al-Adha",
    "diaspora_intensity": "Summer diaspora season",
    "is_rentree_int": "Back to school",
    "payday_boost": "Month-end pay cycle",
    "shift_idx": "Shift of the day",
    "weekday": "Day of week",
    "log_recent_level": "Recent activity level",
    "horizon": "Forecast horizon",
    "temp_max": "Max temperature (real)",
    "precip_mm": "Rainfall (real)",
    "heat_stress": "Heat stress (real)",
    "weather_demand": "Weather effect on demand",
}
_DZ_FEATURES = ["is_weekend_int", "is_holiday_int", "is_ramadan_int",
                "ramadan_progress", "eid_fitr_runup", "eid_adha_runup",
                "diaspora_intensity", "is_rentree_int", "payday_boost"]
fi_show = fi.copy()
fi_show["Signal"] = fi_show["Feature"].map(label_map).fillna(fi_show["Feature"])
fi_show = fi_show[fi_show["Importance"] > 0].head(12).copy()
fi_show["Signal type"] = np.where(fi_show["Feature"].isin(_DZ_FEATURES),
                                  "Algeria-specific", "Generic")

col_a, col_b = st.columns([3, 2])
with col_a, st.container(border=True):
    st.markdown("**Permutation importance**")
    imp_chart = (
        alt.Chart(fi_show).mark_bar().encode(
            y=alt.Y("Signal:N", sort="-x", title=None),
            x=alt.X("Importance:Q", title="Permutation importance"),
            color=alt.Color("Signal type:N",
                            scale=alt.Scale(domain=["Algeria-specific", "Generic"],
                                            range=[C_DZ, C_GREY]),
                            legend=alt.Legend(title=None, orient="top")),
            tooltip=[alt.Tooltip("Signal:N"), alt.Tooltip("Importance:Q", format=".4f"),
                     alt.Tooltip("Signal type:N")],
        ).properties(height=340)
    )
    st.altair_chart(imp_chart, width="stretch")
with col_b, st.container(border=True):
    st.markdown("**Why this is the moat**")
    st.markdown(
        "Algeria-specific signals (the Friday-Saturday weekend, official public "
        "holidays, Ramadan and the Eid run-ups) carry real predictive weight.\n\n"
        "An HR tool built for a Gregorian, Saturday-Sunday market cannot represent "
        "any of them. It is not badly built; it is built for somewhere else.\n\n"
        "The gap is measurable, and it is on this page: "
        f"**{(gen - dz) / gen * 100:.0f}% less error** than the same algorithm "
        "without the Algerian feature set."
    )
    st.caption("Weather ranks lower than calendar features here. Its effect "
               "concentrates in the Saharan wilayas and humid coastal winters: "
               "switch the wilaya to Ouargla to see it count more.")

st.divider()

with st.expander("Method and its limits", icon=":material/science:"):
    for n in bt.notes:
        st.markdown(f"- {n}")
    st.markdown("---")
    for n in ev.notes:
        st.markdown(f"- {n}")

appdata.data_badge()
