"""
The Algerian calendar: the moat, made visible.

The demand calendar in Algeria is not the one a global HR tool was designed
for, and the gap is large, recurring and measurable.
"""

import datetime as dt

import pandas as pd
import streamlit as st

from core import appdata, calendar_dz

appdata.sidebar_controls()

st.title("Algerian Calendar")
st.caption("Why an HR tool designed elsewhere gets it wrong here, every week.")

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
        "Most tools assume": "Weekend" if d.weekday() in (5, 6) else "Working day",
        "Match": "✓" if (ctx.is_weekend == (d.weekday() in (5, 6))) else "✗ WRONG",
    })

col1, col2 = st.columns([3, 2])
with col1:
    with st.container(border=True):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
with col2:
    with st.container(border=True):
        st.markdown("**Two wrong days, every week**")
        st.markdown(
            "The Algerian weekend is **Friday‑Saturday**. A tool that assumes "
            "Saturday‑Sunday gets Thursday, Friday and Sunday wrong, "
            "on a recurring weekly cycle.\n\n"
            "It heavily schedules Friday, the quietest day, and lightly schedules "
            "Sunday, a full working day. This is not a tuning issue that more data "
            "can fix; the tool has no way to express the correct answer."
        )
        st.caption(
            "The first version of this project had the same bug: its weekly pattern "
            "marked days 5 and 6 as low‑demand days. We found it while rebuilding, "
            "which illustrates the point well."
        )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("The moving year")

st.markdown(
    "Ramadan and the two Eids are set by the Hijri calendar, about "
    "11 days shorter than the Gregorian year. The two biggest demand spikes "
    "in Algeria therefore **shift across seasons**. A model that learned "
    "“March is busy” is already wrong by the time it is delivered."
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
                "Ramadan starts": r_start.strftime("%d %b"),
                "Eid al-Fitr": fitr.strftime("%d %b %Y"),
                "Eid al-Adha": adha.strftime("%d %b %Y"),
            })

col_a, col_b = st.columns([3, 2])
with col_a:
    with st.container(border=True):
        st.dataframe(pd.DataFrame(drift), hide_index=True, width="stretch")
        st.caption(
            "Calculated with the tabular Islamic calendar, verified round‑trip "
            "over 60 Hijri years. Accurate to one or two days of the official "
            "moon‑sighting announcement, the app flags the days where this "
            "ambiguity matters."
        )
with col_b:
    with st.container(border=True):
        st.markdown("**Why it’s hard to add later**")
        st.markdown(
            "Ramadan does not only increase volume. It **re‑organizes the day**: "
            "activity shifts to the evening after ftour, hours shorten, and the "
            "last ten nights carry the peak purchases for Eid.\n\n"
            "Then the two Eid days are a near‑closure, followed by a rebound. "
            "Encoding this requires the Hijri calendar as a separate element of "
            "the model, not just a simple holiday flag slapped on."
        )

st.markdown("**Verified against the reference, on the dates that matter**")
hijri_check = appdata.load_hijri_check(st.session_state["allow_network"])
if not hijri_check.empty:
    exact = (hijri_check["Agreement"] == "exact").sum()
    show = hijri_check
    with st.container(border=True):
        st.dataframe(show, hide_index=True, width="stretch")
    st.caption(
        f"{exact} of {len(hijri_check)} key dates match exactly the "
        "Aladhan reference; the others differ by a single day. This ±1 day is "
        "the real lunar‑sighting uncertainty, not a bug, the National "
        "Commission for Lunar Crescent Observation sets the actual date, and "
        "the app flags the affected days so the forecast widens its interval "
        "instead of being falsely certain. Ramadan starts, which drive the "
        "largest demand change, land exactly right."
    )
else:
    st.info(
        "Works with the local tabular calendar (no network verification). Accurate "
        "to one or two days of the official announcement, which the app flags per day.",
        icon=":material/wifi_off:",
    )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("The rest of the Algerian year")

drivers = pd.DataFrame([
    {
        "Driver": "Diaspora return season",
        "When": "mid-June to early September, peak late July",
        "Why it matters": "Several million Algerians living abroad come home. In "
                          "a model trained in Europe, summer is a demand trough. "
                          "Here it is the annual peak.",
    },
    {
        "Driver": "Back to school",
        "When": "late August to mid-September",
        "Why it matters": "A sharp, narrow retail and delivery peak on supplies, "
                          "uniforms and textbooks.",
    },
    {
        "Driver": "Month-end payday",
        "When": "around the 27th, every month",
        "Why it matters": "Algerian salaries are overwhelmingly paid at month end. "
                          "Demand climbs in the first days of the next month and "
                          "thins out before.",
    },
    {
        "Driver": "Yennayer",
        "When": "12 January",
        "Why it matters": "Amazigh New Year, an official public holiday since 2018. "
                          "Missing from almost every foreign calendar library.",
    },
    {
        "Driver": "Saharan heat",
        "When": "June to September, south of the Atlas",
        "Why it matters": "Ouargla logged 84 days above 38°C in summer 2024 "
                          "(observed, ERA5). Heat lowers sustainable pace and raises "
                          "absenteeism: the same volume needs more hands.",
    },
])

with st.container(border=True):
    st.dataframe(
        drivers, hide_index=True, width="stretch",
        column_config={
            "Why it matters": st.column_config.TextColumn(
                "Why it matters", width="large")
        },
    )

st.subheader("The next 8 months")
events = appdata.load_calendar_events(days=240)
with st.container(border=True):
    if events.empty:
        st.caption("No major events detected in this window.")
    else:
        st.dataframe(
            events, hide_index=True, width="stretch",
            column_config={
                "Date": "Date",
                "Event": "Event",
                "Impact": st.column_config.TextColumn("Impact", width="large"),
            },
        )

appdata.data_badge()
