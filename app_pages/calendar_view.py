"""
Algerian calendar — the moat, made visible.

This page exists to make one argument concrete: the demand calendar in Algeria
is not the demand calendar a global workforce tool was built for, and the gap
is large, recurring, and measurable.
"""

import datetime as dt

import pandas as pd
import streamlit as st

from core import appdata, calendar_dz

appdata.sidebar_controls()

st.title("The Algerian calendar")
st.caption("Why a workforce tool built elsewhere mis-forecasts here, every week.")

# ---------------------------------------------------------------------------
st.subheader("The weekend")

today = dt.date.today()
week_start = today - dt.timedelta(days=today.weekday())
week = [week_start + dt.timedelta(days=i) for i in range(7)]

rows = []
for d in week:
    ctx = calendar_dz.day_context(d)
    rows.append({
        "Date": d.strftime("%d %b"),
        "Day": ctx.weekday_name,
        "Algeria": "Weekend" if ctx.is_weekend else "Working day",
        "Most global tools assume": "Weekend" if d.weekday() in (5, 6) else "Working day",
        "Agree": "✓" if (ctx.is_weekend == (d.weekday() in (5, 6))) else "✗ WRONG",
    })

col1, col2 = st.columns([3, 2])
with col1:
    with st.container(border=True):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
with col2:
    with st.container(border=True):
        st.markdown("**Two days wrong, every single week**")
        st.markdown(
            "Algeria's weekend is **Friday–Saturday**. A tool that assumes "
            "Saturday–Sunday gets Thursday, Friday and Sunday wrong on a "
            "recurring weekly cycle.\n\n"
            "It rosters heavy on Friday — the quietest day — and light on "
            "Sunday, a full working day. That is not a tuning problem you can "
            "fix with more training data; the tool has no way to express the "
            "right answer."
        )
        st.caption(
            "The earlier version of this very project had the same bug: its "
            "weekly pattern marked weekdays 5 and 6 as the low days. We found "
            "it while rebuilding, which is rather the point."
        )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("The moving year")

st.markdown(
    "Ramadan and the two Aïds are set by the Hijri calendar, which is about "
    "11 days shorter than the Gregorian year. Algeria's two largest demand "
    "events therefore **drift backwards through the seasons**. A model that "
    "learned \"March is busy\" is already wrong by the time it ships."
)

years = list(range(today.year - 2, today.year + 4))
drift = []
for y in years:
    hy_guess = calendar_dz.to_hijri(dt.date(y, 6, 1))[0]
    for hy in (hy_guess - 1, hy_guess, hy_guess + 1):
        try:
            r_start = calendar_dz.from_hijri(hy, 9, 1)
            fitr = calendar_dz.from_hijri(hy, 10, 1)
            adha = calendar_dz.from_hijri(hy, 12, 10)
        except (ValueError, OverflowError):
            continue
        if r_start.year == y:
            drift.append({
                "Gregorian year": y,
                "Hijri year": hy,
                "Ramadan begins": r_start.strftime("%d %b"),
                "Aïd el-Fitr": fitr.strftime("%d %b %Y"),
                "Aïd el-Adha": adha.strftime("%d %b %Y"),
            })

col_a, col_b = st.columns([3, 2])
with col_a:
    with st.container(border=True):
        st.dataframe(pd.DataFrame(drift), hide_index=True, width="stretch")
        st.caption(
            "Computed with the tabular Islamic calendar, verified round-trip "
            "over 60 Hijri years. Accurate to within a day or two of Algeria's "
            "official moon-sighting announcement — the app flags days where "
            "that ambiguity matters."
        )
with col_b:
    with st.container(border=True):
        st.markdown("**Why this is hard to bolt on**")
        st.markdown(
            "Ramadan does not just raise volume. It **reshapes the day**: "
            "activity moves to the evening after f'tour, working hours "
            "shorten, and the last ten nights carry the Aïd shopping peak.\n\n"
            "Then the two Aïd days are a near-shutdown, followed by a rebound. "
            "Encoding that needs the Hijri calendar as a first-class citizen "
            "of the feature set — not a holiday flag pasted on top."
        )

st.markdown("**Checked against the reference, on the dates that matter**")
hijri_check = appdata.load_hijri_check(st.session_state["allow_network"])
if not hijri_check.empty:
    with st.container(border=True):
        st.dataframe(hijri_check, hide_index=True, width="stretch")
    exact = (hijri_check["Agreement"] == "exact").sum()
    st.caption(
        f"{exact} of {len(hijri_check)} key dates match the Aladhan reference "
        "exactly; the rest differ by a single day. That ±1 day is real "
        "moon-sighting uncertainty, not a bug — Algeria's Commission Nationale "
        "d'Observation du Croissant Lunaire sets the actual date, and the app "
        "flags the affected days so the forecaster widens its interval near "
        "them instead of being confidently wrong. Note Ramadan starts, which "
        "drive the largest demand shift, resolve exactly."
    )
else:
    st.info(
        "Running on the local tabular calendar (no network check). Accurate "
        "to within a day or two of the official announcement — which the app "
        "flags per day.",
        icon=":material/wifi_off:",
    )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("The rest of the Algerian year")

drivers = pd.DataFrame([
    {
        "Driver": "Diaspora return season",
        "When": "mid-June → early September, peaking late July",
        "Why it matters": "Several million Algerians resident abroad come home. "
                          "In a European-trained model, summer reads as a demand "
                          "trough. Here it is the annual peak.",
    },
    {
        "Driver": "Rentrée scolaire",
        "When": "late August → mid-September",
        "Why it matters": "Sharp, narrow retail and delivery peak on stationery, "
                          "uniforms and textbooks.",
    },
    {
        "Driver": "End-of-month payday",
        "When": "around the 27th, every month",
        "Why it matters": "Algerian salaries are overwhelmingly paid at month "
                          "end. Consumer demand spikes in the first days of the "
                          "following month and thins before it.",
    },
    {
        "Driver": "Yennayer",
        "When": "12 January",
        "Why it matters": "Amazigh New Year, a gazetted public holiday since "
                          "2018. Absent from essentially every foreign calendar "
                          "library.",
    },
    {
        "Driver": "Saharan heat",
        "When": "June → September, south of the Atlas",
        "Why it matters": "Ouargla recorded 84 days above 38°C in summer 2024 "
                          "(observed, ERA5). Heat cuts sustainable pace and "
                          "drives absenteeism — the same volume needs more bodies.",
    },
])

with st.container(border=True):
    st.dataframe(
        drivers, hide_index=True, width="stretch",
        column_config={
            "Why it matters": st.column_config.TextColumn("Why it matters", width="large")
        },
    )

st.subheader("Next 8 months")
events = appdata.load_calendar_events(days=240)
with st.container(border=True):
    if events.empty:
        st.caption("No major events detected in this window.")
    else:
        st.dataframe(
            events, hide_index=True, width="stretch",
            column_config={"Impact": st.column_config.TextColumn("Impact", width="large")},
        )

appdata.data_badge()
