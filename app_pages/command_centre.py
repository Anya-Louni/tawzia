"""
Dashboard: the screen a manager opens every morning.

Reading order is deliberate: first what is happening today (attendance,
absences, requests waiting for a decision), then what is coming (Algerian
calendar, forecast load), then the recommended schedule and its cost.

Every change shown is compared with a real, named baseline (the mean of the
loaded clock window), never with a "last month" that is not in the data.
"""

import datetime as _dt

import altair as alt
import pandas as pd
import streamlit as st

from core import (appdata, attendance as att_mod, brand, calendar_dz,
                  company_data as cd, deadlines_dz as dl, demand as demand_mod,
                  industry, sector_features as sf)

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]
horizon = st.session_state["horizon"]

_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")

# Brand blue for what is fine, two warm tones for the two problems.
C_OK, C_LATE, C_ABS = brand.BLUE, "#E4A13B", "#DE5B4F"


def _date_en(d: _dt.date) -> str:
    return (f"{calendar_dz.WEEKDAY_NAMES_FR[d.weekday()]} {d.day} "
            f"{_MONTHS[d.month - 1]} {d.year}")


def _hijri(d: _dt.date) -> str:
    hy, hm, hd = calendar_dz.to_hijri(d)
    return f"{hd} {calendar_dz.HIJRI_MONTHS[hm]} {hy}"


# Today: headcount, clock-ins, requests, leaving risk
people = appdata.hr_people()
records = appdata.hr_attendance()
requests = appdata.hr_requests()
risk = appdata.hr_attrition()

adf = pd.DataFrame([{"date": r.date, "flag": r.flag} for r in records])
# The clock log stops the day before, so the last clocked day is not "today".
now = _dt.date.today()
last_clocked = adf["date"].max() if not adf.empty else now
day = adf[adf["date"] == last_clocked] if not adf.empty else adf
clocked_label = f"{last_clocked.day} {_MONTHS[last_clocked.month - 1]}"
is_today = last_clocked == now

planned_today = len(day)
absent_today = int((day["flag"] == "absent").sum()) if planned_today else 0
late_today = int((day["flag"] == "late").sum()) if planned_today else 0
present_today = planned_today - absent_today

n_days = adf["date"].nunique() if not adf.empty else 0
mean_absent = (adf["flag"] == "absent").sum() / n_days if n_days else 0.0
present_rate = present_today / planned_today * 100 if planned_today else 0.0
mean_present_rate = (
    (adf["flag"] != "absent").sum() / len(adf) * 100 if len(adf) else 0.0
)

pending = [r for r in requests if r.status == "pending"]
leave_pending = [r for r in pending if r.kind in ("annual", "unpaid", "family")]

cdd = sum(1 for e in people if str(e.contract).upper() == "CDD")
cdd_share = cdd / len(people) * 100 if people else 0.0

high_risk = int((risk["Band"] == "high").sum()) if not risk.empty else 0

# Schedule: forecast load and recommended roster
plan = appdata.load_forward_plan(
    st.session_state["profile_key"],
    wilaya,
    horizon,
    st.session_state["regular_pool"],
    st.session_state["temp_ceiling"],
    st.session_state["service_level"],
    st.session_state["allow_network"],
)
fc, roster = plan["forecast"], plan["roster"]

daily = fc.groupby("date", as_index=False).agg(
    forecast=("forecast", "sum"), p10=("p10", "sum"), p90=("p90", "sum")
)
daily_staff = roster.groupby("date", as_index=False).agg(
    staff=("total_staff", "sum"), cost=("planned_cost", "sum")
)
peak_row = daily.loc[daily["forecast"].idxmax()]
# Name the window by its real dates: history stops where ERA5 weather does.
win_start = pd.to_datetime(daily["date"].min()).date()
win_end = pd.to_datetime(daily["date"].max()).date()
win_label = (f"{win_start.day} {_MONTHS[win_start.month - 1]} "
             f"to {win_end.day} {_MONTHS[win_end.month - 1]}")
win_stale = win_end < now
total_cost = float(daily_staff["cost"].sum())
peak_staff = int(roster.groupby("date")["total_staff"].sum().max())
temp_share = (
    roster["temp"].sum() / roster["total_staff"].sum() * 100
    if roster["total_staff"].sum() else 0
)

st.markdown(
    f'<div class="tz-hero"><div>'
    f'<h1 class="tz-hero-h">Dashboard</h1>'
    f'<div class="tz-hero-s">{_date_en(now)} · {_hijri(now)} · '
    f'<b>{profile.label}</b> · {wilaya} · load measured in '
    f'{profile.demand_unit}</div></div></div>',
    unsafe_allow_html=True,
)
industry.banner()

if plan["infeasible"]:
    st.error(
        "**This site cannot legally cover the forecast.** Permanent staff plus "
        "the temp ceiling is not enough, within the overtime cap and weekly rest, "
        "to serve forecast demand. This is a finding, not an error: the site needs "
        "more people. Raise permanent staff or the temp ceiling in Settings to "
        "see what it would take.",
        icon=":material/warning:",
    )

# First band: the four numbers of the day
k1, k2, k3, k4 = st.columns(4)

with k1, st.container(border=True, height="stretch"):
    appdata.stat_card(
        "Headcount", f"{len(people)}",
        f"{cdd_share:.0f}% CDD", "flat",
        f"{len(people) - cdd} CDI · {cdd} CDD · {wilaya}",
    )
with k2, st.container(border=True, height="stretch"):
    appdata.stat_card(
        "Present" + ("" if is_today else " (last clock day)"),
        f"{present_today}",
        f"{present_rate - mean_present_rate:+.1f} pt",
        "up" if present_rate >= mean_present_rate else "down",
        f"{clocked_label} · of {planned_today} shifts · mean "
        f"{mean_present_rate:.0f}% over {n_days} days",
    )
with k3, st.container(border=True, height="stretch"):
    appdata.stat_card(
        "Absent" + ("" if is_today else " (last clock day)"),
        f"{absent_today}",
        (f"{(absent_today - mean_absent) / mean_absent * 100:+.0f}%"
         if mean_absent else "first day"),
        "down" if absent_today > mean_absent else "up",
        f"{clocked_label} · mean {mean_absent:.1f} a day · "
        f"{late_today} late",
    )
with k4, st.container(border=True, height="stretch"):
    appdata.stat_card(
        "Pending requests", f"{len(pending)}",
        f"{len(leave_pending)} leave", "flat",
        "to weigh against this week's load",
    )

# Second band: attendance over time, and what is coming
left, right = st.columns([3, 2])

with left:
    with st.container(border=True):
        appdata.card_head("Attendance by day", f"last {n_days} working days")
        appdata.legend([("On time", C_OK), ("Late", C_LATE), ("Absent", C_ABS)])
        if adf.empty:
            st.markdown('<div class="tz-empty">No clock data loaded.</div>',
                        unsafe_allow_html=True)
        else:
            _LBL = {"on_time": "On time", "late": "Late", "absent": "Absent"}
            per_day = (adf.assign(statut=adf["flag"].map(_LBL))
                       .groupby(["date", "statut"]).size()
                       .rename("agents").reset_index())
            per_day["jour"] = pd.to_datetime(per_day["date"]).dt.strftime("%d/%m")
            order = ["On time", "Late", "Absent"]
            chart = (
                alt.Chart(per_day)
                .mark_bar(cornerRadius=2, size=26)
                .encode(
                    x=alt.X("jour:N", title=None, sort=None,
                            axis=alt.Axis(labelAngle=0, labelColor=brand.MUTED,
                                          labelFontSize=11, domain=False,
                                          ticks=False)),
                    y=alt.Y("agents:Q", title=None, stack=True,
                            axis=alt.Axis(labelColor=brand.MUTED,
                                          labelFontSize=11, domain=False,
                                          ticks=False, gridOpacity=.5,
                                          tickCount=4)),
                    color=alt.Color("statut:N", sort=order, legend=None,
                                    scale=alt.Scale(domain=order,
                                                    range=[C_OK, C_LATE, C_ABS])),
                    # On time sits at the base; the two problems stack above it.
                    order=alt.Order("color_statut_sort_index:Q",
                                    sort="ascending"),
                    tooltip=[alt.Tooltip("jour:N", title="Day"),
                             alt.Tooltip("statut:N", title="Status"),
                             alt.Tooltip("agents:Q", title="Staff")],
                )
                .properties(height=268)
                .configure_view(strokeWidth=0, fill=None)
                .configure_axis(grid=False)
                .configure_axisY(grid=True, gridColor="#DDE4EE",
                                 gridDash=[3, 4])
            )
            st.altair_chart(chart, width="stretch")
            st.caption("Clock-ins simulated for the demo; in production the "
                       "platform reads the time clock or the attendance file.")

with right:
    with st.container(border=True):
        appdata.card_head("Coming up", "Algerian calendar")
        events = appdata.load_calendar_events(days=max(horizon + 60, 120))
        if events.empty:
            st.markdown('<div class="tz-empty">No major Algerian calendar '
                        'event in this window.</div>',
                        unsafe_allow_html=True)
        else:
            rows = []
            for _, e in events.head(6).iterrows():
                d = pd.to_datetime(e["Date"]).date()
                delta = (d - now).days
                rows.append({
                    "name": f"{d.day} {_MONTHS[d.month - 1]} · {e['Event']}",
                    "sub": e["Impact"],
                    "meta": f"D+{delta}" if delta > 0 else "today",
                    "hot": 0 <= delta <= 7,
                })
            appdata.list_rows(rows, avatars=False, wrap=True)
        st.page_link("app_pages/calendar_view.py",
                     label="Full calendar and verification",
                     icon=":material/calendar_month:")

# Third band: what needs a decision today
c1, c2, c3, c4 = st.columns(4)

with c1, st.container(border=True, height="stretch"):
    appdata.card_head("Requests to handle", f"{len(pending)} pending")
    appdata.list_rows([
        {"name": r.emp_name,
         "sub": f"{r.kind_label} · {r.start:%d/%m}"
                + (f" to {r.end:%d/%m}" if r.end != r.start else ""),
         "meta": (f"{(r.end - r.start).days + 1} d" if not r.is_sortie
                  else f"{r.hours:.0f} h" if r.hours else "short leave"),
         "hot": (r.start - now).days <= 3}
        for r in pending[:4]
    ], empty="No pending request.")
    st.page_link("app_pages/requests_view.py", label="Decide on requests",
                 icon=":material/how_to_reg:")

with c2, st.container(border=True, height="stretch"):
    appdata.card_head("Leaving risk", f"{high_risk} at high risk")
    appdata.list_rows([
        {"name": r["Name"], "sub": r["Top driver"],
         "meta": f"{r['Risk %']:.0f} %", "hot": r["Band"] == "high"}
        for _, r in risk.head(4).iterrows()
    ], empty="No scored profile.")
    st.page_link("app_pages/retention_negotiator.py",
                 label="See causes and cost", icon=":material/trending_down:")

with c3, st.container(border=True, height="stretch"):
    appdata.card_head("To file", "CNAS and tax")
    _dls = dl.upcoming(now, headcount=len(people), horizon_days=60)
    appdata.list_rows([
        {"name": o.label,
         "sub": f"{o.body} · {o.period}",
         "meta": ("overdue" if o.days_left(now) < 0
                  else f"D+{o.days_left(now)}"),
         "hot": o.status(now) in ("en_retard", "urgent")}
        for o in _dls[:3]
    ], empty="Nothing to file in the next 60 days.",
        avatars=False, wrap=True)
    st.page_link("app_pages/deadlines_view.py",
                 label="All deadlines and portals",
                 icon=":material/event_available:")

with c4, st.container(border=True, height="stretch"):
    appdata.card_head("Lateness and absence",
                      f"{late_today + absent_today} flags")
    flags = att_mod.todays_flags(records)
    appdata.list_rows([
        {"name": r["Name"], "sub": f"{r['Status']} · due {r['Scheduled']}",
         "meta": (f"+{r['Late (min)']} min" if r["Late (min)"] != ""
                  else "absent"),
         "hot": r["Status"].startswith("Absent")}
        for _, r in flags.head(4).iterrows()
    ], empty="Everyone on time today.")
    st.page_link("app_pages/requests_view.py", label="Attendance register",
                 icon=":material/schedule:")

# Fourth band: forecast load and the schedule it drives
st.markdown("### Forecast load and schedule")
st.caption(f"Forecast window: **{win_label}** ({horizon} days), computed from "
           f"the last day of available history.")
if win_stale:
    st.warning(
        "This window is already past: the cached run predates today. Rerun to "
        "forecast from today (Data menu, then toggle live calls off and on to "
        "force a recompute).",
        icon=":material/history:",
    )

# Named container so the four tiles share a height (two carry sparklines).
with st.container(key="tz_planrow"):
    m1, m2, m3, m4 = st.columns(4)
m1.metric(
    f"Load ({profile.demand_unit})", f"{daily['forecast'].sum():,.0f}",
    border=True, chart_data=daily["forecast"].tolist(), chart_type="line",
    help=f"Total over {win_label}.",
)
m2.metric(
    "Peak day", pd.to_datetime(peak_row["date"]).strftime("%d/%m"),
    f"{peak_row['forecast']:,.0f}", border=True,
    help="The day with the highest forecast load.",
)
m3.metric(
    "Peak staff", f"{peak_staff}", border=True,
    chart_data=daily_staff["staff"].tolist(), chart_type="bar",
    help="Busiest day, all shifts combined.",
)
m4.metric(
    "Planned cost", appdata.dzd(total_cost, compact=True), border=True,
    help="Loaded cost, CNAS employer share and legal premiums included.",
)

pl, pr = st.columns([3, 2])

with pl:
    with st.container(border=True):
        appdata.card_head("Forecast demand",
                          f"quantile p{st.session_state['service_level'] * 100:.0f}")
        st.caption("The band is the p10-p90 interval, derived from the real "
                   "backtest error at each horizon. It is not an assumed "
                   "distribution.")
        chart_df = daily.set_index("date")[["p10", "forecast", "p90"]]
        chart_df.columns = ["Low (p10)", "Forecast", "High (p90)"]
        st.line_chart(chart_df, height=272,
                      color=["#C6D2E2", brand.BLUE, "#C6D2E2"])

with pr:
    with st.container(border=True):
        appdata.card_head("Schedule mix", "over the horizon")
        st.markdown(
            f'<div class="tz-meter"><span style="width:'
            f'{min(temp_share, 100):.1f}%"></span></div>'
            f'<div class="tz-meter-l"><span>Temps {temp_share:.0f}%</span>'
            f'<span>Permanent {100 - temp_share:.0f}%</span></div>',
            unsafe_allow_html=True,
        )
        st.caption("A temp carries a 35% premium. Above a quarter of the "
                   "schedule, the question is no longer scheduling but "
                   "permanent headcount.")
        ot = float(roster["overtime"].sum())
        st.markdown(
            f'<div class="tz-row"><div class="tz-av">OT</div>'
            f'<div class="tz-row-txt"><div class="tz-row-t">'
            f'{ot:,.0f} overtime hours</div>'
            f'<div class="tz-row-s">within the legal cap</div></div></div>'
            f'<div class="tz-row"><div class="tz-av">SV</div>'
            f'<div class="tz-row-txt"><div class="tz-row-t">'
            f'{int(roster["supervisors"].sum())} supervisor shifts</div>'
            f'<div class="tz-row-s">supervision ratio met</div></div></div>',
            unsafe_allow_html=True,
        )
        st.page_link("app_pages/roster_view.py",
                     label="Detailed schedule and cost", icon=":material/groups:")

# Sector spotlight
try:
    _sfc = appdata.expected_demand(
        st.session_state["profile_key"], wilaya, horizon,
        st.session_state["allow_network"])
    _sec_plan = {"forecast": _sfc}
except Exception:
    _sec_plan = plan
_feat = sf.compute(st.session_state["profile_key"], _sec_plan, cd.people())
if _feat is not None:
    with st.container(border=True):
        appdata.card_head(f"{_feat.icon} {_feat.title}", "specific to your activity")
        cols = st.columns(len(_feat.metrics)) if _feat.metrics else []
        for col, (label, display, help_txt) in zip(cols, _feat.metrics):
            col.metric(label, display, help=help_txt or None)
        if _feat.insight:
            st.caption(f":material/lightbulb: {_feat.insight}")
        st.page_link("app_pages/sector_view.py", label="Sector analysis",
                     icon=":material/insights:")

with st.container(border=True):
    appdata.card_head("Recommended schedule", win_label)
    st.caption(f"Built at demand quantile "
               f"p{st.session_state['service_level'] * 100:.0f}, within the "
               f"overtime cap and weekly rest.")
    show = roster[[
        "date", "shift", "forecast_for_roster", "required_workers",
        "regular", "overtime", "temp", "total_staff", "supervisors", "planned_cost",
    ]].copy()
    show["date"] = pd.to_datetime(show["date"]).dt.strftime("%a %d %b")
    st.dataframe(
        show, hide_index=True, width="stretch",
        column_config={
            "date": "Date",
            "shift": "Shift",
            "forecast_for_roster": st.column_config.NumberColumn(
                f"Forecast ({profile.demand_unit})", format="%d"),
            "required_workers": st.column_config.NumberColumn("Required", format="%d"),
            "regular": st.column_config.NumberColumn("Permanent", format="%d"),
            "overtime": st.column_config.NumberColumn("Overtime", format="%d"),
            "temp": st.column_config.NumberColumn("Temps", format="%d"),
            "total_staff": st.column_config.NumberColumn("Total", format="%d"),
            "supervisors": st.column_config.NumberColumn("Supervisors", format="%d"),
            "planned_cost": st.column_config.NumberColumn("Cost (DZD)", format="%.0f"),
        },
    )

st.caption(f":material/cloud: Forecast weather: {plan['weather_provenance']}")
appdata.data_badge()
