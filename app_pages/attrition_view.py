"""Attrition-seer, who is likely to quit, and what it would cost."""

import altair as alt
import pandas as pd
import streamlit as st

from core import appdata, attrition

appdata.sidebar_controls()

st.title("Attrition risk")
st.caption("Who is likely to leave in the next six months, why, and what replacing them costs.")

df = appdata.hr_attrition()
s = attrition.summary(df)

with st.container(horizontal=True):
    st.metric("High risk", f"{s['high']}", border=True)
    st.metric("Medium risk", f"{s['medium']}", border=True)
    st.metric("Expected leavers (6mo)", f"{s['expected_leavers']}", border=True,
              help="Sum of individual risk probabilities.")
    st.metric("Cost at risk", appdata.dzd(s["cost_at_risk"], compact=True), border=True,
              help="Expected replacement cost across the workforce.")

st.info(
    "This is a transparent expected-risk model built on real attendance, tenure, "
    "pay and contract data, weighted by the drivers HR research links to turnover. "
    "It is not trained on real quit history (none is public) - a pilot re-fits the "
    "weights to the customer's own leavers.",
    icon=":material/psychology:",
)

col_a, col_b = st.columns([3, 2])
with col_a:
    with st.container(border=True):
        st.subheader("Risk ranking")
        def _row_color(row):
            return None
        st.dataframe(
            df, hide_index=True, width="stretch", height=420,
            column_config={
                "Risk %": st.column_config.ProgressColumn(
                    "Risk %", min_value=0, max_value=100, format="%.0f%%"),
                "Replacement cost (DZD)": st.column_config.NumberColumn(format="%d"),
                "Expected cost (DZD)": st.column_config.NumberColumn(format="%d"),
            },
        )

with col_b:
    with st.container(border=True):
        st.subheader("Risk by band")
        band = df["Band"].value_counts().rename_axis("Band").reset_index(name="Count")
        chart = (
            alt.Chart(band).mark_arc(innerRadius=50).encode(
                theta="Count:Q",
                color=alt.Color("Band:N", scale=alt.Scale(
                    domain=["high", "medium", "low"],
                    range=["#DB4A31", "#EAB24C", "#8FB65A"])),
                tooltip=["Band:N", "Count:Q"],
            ).properties(height=220)
        )
        st.altair_chart(chart, width="stretch")

    with st.container(border=True):
        st.subheader("Do this first")
        actions = attrition.retention_actions(df)
        if actions:
            for a in actions:
                st.markdown(f":material/arrow_right: {a}")
        else:
            st.caption("No high-risk staff right now.")

appdata.data_badge()
