"""
Evidence — the page that decides whether anyone believes the rest of the app.

Shows the walk-forward backtest, the comparison against a workforce tool that
does not understand Algeria, and the out-of-sample money comparison where both
rosters were built blind and scored against the same realised demand.
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

st.title("Evidence")
st.caption(
    "Everything here is out-of-sample. No model on this page ever saw the "
    "data it is scored on."
)

st.info(
    "**The honest caveat, up front.** We do not have a real Algerian "
    "operator's volume ledger — nobody outside those companies does. The "
    "*demand volumes* on this page are simulated. What is real is the "
    "**Algerian calendar** the demand responds to (actual Ramadan and Aïd "
    "dates, actual Friday–Saturday weekend, actual gazetted holidays) and the "
    "**observed weather** from the ERA5 archive for this wilaya. So these "
    "results validate the method and the machinery — not the market. The "
    "magnitude needs a pilot to confirm, and we say that to every investor "
    "who asks.",
    icon=":material/info:",
)

with st.spinner("Running backtest and scoring rosters…"):
    ev = appdata.load_evidence(
        st.session_state["profile_key"],
        wilaya,
        horizon,
        st.session_state["regular_pool"],
        st.session_state["temp_ceiling"],
        st.session_state["service_level"],
        st.session_state["allow_network"],
    )

bt = ev.backtest
metrics = bt.metrics
delta = ev.delta

dz = float(metrics.loc[metrics["Model"] == "WorkForce.dz", "MAPE_%"].iloc[0])
gen = float(metrics.loc[metrics["Model"] == "Generic international model", "MAPE_%"].iloc[0])
sn = float(metrics.loc[metrics["Model"] == "Seasonal naive", "MAPE_%"].iloc[0])

# ---------------------------------------------------------------------------
st.subheader("1. Does the forecast beat the alternatives?")

with st.container(horizontal=True):
    st.metric("Our forecast error (MAPE)", f"{dz:.1f}%", border=True)
    st.metric(
        "vs generic international tool",
        f"{gen:.1f}%",
        f"-{(gen - dz) / gen * 100:.0f}% error",
        border=True,
        help="Same algorithm, same data, same tuning — but with the feature "
             "set a workforce tool built for Europe would have: Saturday–"
             "Sunday weekend, no Hijri calendar, no diaspora season.",
    )
    st.metric(
        "vs seasonal naive",
        f"{sn:.1f}%",
        f"-{(sn - dz) / sn * 100:.0f}% error",
        border=True,
        help="Same shift, same weekday, last week. What a good ops manager "
             "does in their head — and a genuinely hard baseline.",
    )
    st.metric("Forecast origins", f"{bt.n_origins}", border=True)

with st.container(border=True):
    st.markdown("**Full backtest metrics**")
    st.dataframe(
        metrics,
        hide_index=True,
        width="stretch",
        column_config={
            "Model": "Model",
            "MAE": st.column_config.NumberColumn("MAE", format="%.0f"),
            "RMSE": st.column_config.NumberColumn("RMSE", format="%.0f"),
            "MAPE_%": st.column_config.NumberColumn("MAPE %", format="%.2f"),
            "Bias_%": st.column_config.NumberColumn("Bias %", format="%+.2f"),
            "Under_%": st.column_config.NumberColumn("Under-forecast %", format="%.1f"),
        },
    )
    st.caption(
        "**Bias** matters more than MAPE for a roster. A forecast biased low "
        "rosters short, and being short costs roughly "
        f"{sources.value('understaffing_penalty_multiple')}× what the saved "
        "wages were worth. Ours is deliberately left slightly positive — "
        "erring high is the cheap direction."
    )

with st.container(border=True):
    st.markdown("**Error by forecast horizon**")
    st.caption("How fast each approach degrades as you plan further ahead.")
    pivot = bt.by_horizon.pivot(index="horizon", columns="Model", values="MAPE_%")
    st.line_chart(
        pivot,
        height=280,
        color=["#C8102E", "#B78B4A", "#16233A", "#7C8494"],
    )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("2. Does the better forecast turn into money?")
st.caption(
    "Both rosters were built from information available at the forecast "
    "origin — neither saw the demand it would face. Both pay identical wage "
    "rates, identical statutory premiums, and an identical penalty for demand "
    "they failed to cover. The only difference is forecast quality."
)

with st.container(horizontal=True):
    st.metric(
        "Cost saving",
        f"{delta['saving_pct']:.1f}%",
        appdata.dzd(delta["saving_dzd"], compact=True),
        border=True,
    )
    st.metric(
        "Service level gain",
        f"+{delta['service_gain_pp']:.1f} pp",
        border=True,
        help="Share of demand actually served.",
    )
    st.metric(
        "Win rate",
        f"{delta['win_rate']:.0f}%",
        f"of {delta['origins']} origins",
        border=True,
    )
    st.metric(
        "Worst origin",
        f"{delta['worst_origin_pct']:+.1f}%",
        border=True,
        help="We lose money on some windows. A comparison that never loses "
             "is a comparison that has been rigged.",
    )

with st.container(border=True):
    st.markdown("**Cost comparison, aggregated over every scored window**")
    comp = ev.comparison.copy()
    st.dataframe(
        comp,
        hide_index=True,
        width="stretch",
        column_config={
            "Strategy": "Strategy",
            "Labour cost (DZD)": st.column_config.NumberColumn("Labour", format="%.0f"),
            "Shortfall cost (DZD)": st.column_config.NumberColumn("Shortfall", format="%.0f"),
            "Total cost (DZD)": st.column_config.NumberColumn("Total", format="%.0f"),
            "Unserved units": st.column_config.NumberColumn("Unserved", format="%.0f"),
            "Service level": st.column_config.NumberColumn("Service", format="%.1%%"),
            "Idle units": st.column_config.NumberColumn("Idle", format="%.0f"),
            "Worker-shifts": st.column_config.NumberColumn("Worker-shifts", format="%d"),
            "Cost per unit (DZD)": st.column_config.NumberColumn("Cost/unit", format="%.2f"),
        },
    )
    st.caption(
        "Note the optimised plan spends **more** on labour and still comes out "
        "ahead. That is the actual insight: the expensive failure in Algerian "
        "shift operations is being short, not being generous."
    )

with st.container(border=True):
    st.markdown("**Saving per forecast window**")
    st.caption(
        "Each bar is one independent window. The negative ones are real — "
        "windows where a fixed roster happened to fit the demand better."
    )
    po = ev.per_origin.copy()
    po["origin"] = pd.to_datetime(po["origin"])
    po = po.sort_values("origin")
    po["label"] = po["origin"].dt.strftime("%d %b %y")
    po["sign"] = np.where(po["saving_pct"] >= 0, "Saved", "Lost")

    # Altair rather than st.bar_chart: a categorical axis would be sorted
    # alphabetically by label ("01 Apr 24" before "02 Feb 26"), which scrambles
    # the chronology. `sort=None` keeps the frame's own order.
    savings_chart = (
        alt.Chart(po)
        .mark_bar()
        .encode(
            x=alt.X("label:N", sort=None, title=None,
                    axis=alt.Axis(labelAngle=-45, labelFontSize=10)),
            y=alt.Y("saving_pct:Q", title="Saving vs fixed roster (%)"),
            color=alt.Color(
                "sign:N",
                scale=alt.Scale(domain=["Saved", "Lost"],
                                range=["#C8102E", "#7C8494"]),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("label:N", title="Window starting"),
                alt.Tooltip("saving_pct:Q", title="Saving %", format="+.1f"),
                alt.Tooltip("saving:Q", title="Saving DZD", format=",.0f"),
            ],
        )
        .properties(height=260)
    )
    st.altair_chart(savings_chart, width="stretch")

st.divider()

# ---------------------------------------------------------------------------
st.subheader("3. Which Algerian signals are actually earning their keep?")

fi = appdata.load_feature_importance(
    st.session_state["profile_key"], wilaya, st.session_state["allow_network"]
)

label_map = {
    "is_weekend_int": "Friday–Saturday weekend",
    "is_holiday_int": "Algerian public holidays",
    "is_ramadan_int": "Ramadan",
    "ramadan_progress": "Position within Ramadan",
    "eid_fitr_runup": "Aïd el-Fitr run-up",
    "eid_adha_runup": "Aïd el-Adha run-up",
    "diaspora_intensity": "Diaspora summer season",
    "is_rentree_int": "Rentrée scolaire",
    "payday_boost": "End-of-month payday cycle",
    "shift_idx": "Shift of day",
    "weekday": "Day of week",
    "log_recent_level": "Recent operating level",
    "horizon": "Forecast horizon",
    "temp_max": "Max temperature (real)",
    "precip_mm": "Rainfall (real)",
    "heat_stress": "Heat stress (real)",
    "weather_demand": "Weather demand effect",
}
fi_show = fi.copy()
fi_show["Signal"] = fi_show["Feature"].map(label_map).fillna(fi_show["Feature"])
fi_show = fi_show[fi_show["Importance"] > 0].head(12)

col_a, col_b = st.columns([3, 2])
with col_a:
    with st.container(border=True):
        st.markdown("**Permutation importance**")
        # Explicit descending sort - a plain bar chart would order the
        # categories alphabetically, which buries the point this chart exists
        # to make.
        fi_show = fi_show.copy()
        fi_show["is_dz"] = fi_show["Feature"].isin([
            "is_weekend_int", "is_holiday_int", "is_ramadan_int",
            "ramadan_progress", "eid_fitr_runup", "eid_adha_runup",
            "diaspora_intensity", "is_rentree_int", "payday_boost",
        ])
        fi_show["Signal type"] = np.where(
            fi_show["is_dz"], "Algeria-specific", "Generic"
        )
        imp_chart = (
            alt.Chart(fi_show)
            .mark_bar()
            .encode(
                y=alt.Y("Signal:N", sort="-x", title=None),
                x=alt.X("Importance:Q", title="Permutation importance"),
                color=alt.Color(
                    "Signal type:N",
                    scale=alt.Scale(domain=["Algeria-specific", "Generic"],
                                    range=["#C8102E", "#7C8494"]),
                    legend=alt.Legend(title=None, orient="top"),
                ),
                tooltip=[
                    alt.Tooltip("Signal:N"),
                    alt.Tooltip("Importance:Q", format=".4f"),
                    alt.Tooltip("Signal type:N"),
                ],
            )
            .properties(height=340)
        )
        st.altair_chart(imp_chart, width="stretch")
with col_b:
    with st.container(border=True):
        st.markdown("**Why this is the moat**")
        st.markdown(
            "The Algeria-specific signals — the Friday–Saturday weekend, the "
            "gazetted holidays, Ramadan and the Aïd run-ups — carry real "
            "predictive weight.\n\n"
            "A workforce tool built for a Gregorian, Saturday–Sunday market "
            "cannot represent any of them. It is not that such a tool is "
            "badly built; it is that it is built for somewhere else.\n\n"
            "That gap is measurable, and it is on this page: "
            f"**{(gen - dz) / gen * 100:.0f}% lower error** than the same "
            "algorithm without the Algerian feature set."
        )
        st.caption(
            "Weather features rank lower here than the calendar ones. Their "
            "effect concentrates in Saharan wilayas and wet coastal winters — "
            "switch the wilaya to Ouargla to see them matter more."
        )

st.divider()

with st.expander("Method and its limits", icon=":material/science:"):
    for n in bt.notes:
        st.markdown(f"- {n}")
    st.markdown("---")
    for n in ev.notes:
        st.markdown(f"- {n}")

appdata.data_badge()
