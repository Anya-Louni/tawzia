"""
This week's schedule: one button, "Generate". The rest is explained.

The CP-SAT solver (core/scheduler.py) places every employee with labour law as
hard constraints, starts from last week to stay stable, and reads the load from
the forecast. The schedule then goes to the decision inbox as a card: nothing
is published to the teams without approval.
"""

import datetime as dt

import streamlit as st

from core import appdata, db, scheduler as sch, seed_company as sc

appdata.sidebar_controls()
ss = st.session_state

st.markdown(
    '<div class="tz-hero"><div><h1 class="tz-hero-h">This week\'s schedule</h1>'
    '<div class="tz-hero-s">The most stable, cheapest schedule that respects the law: '
    '48 h at most, one rest day, no forbidden night shift. <b>You approve, it goes '
    'to the teams.</b></div></div></div>',
    unsafe_allow_html=True,
)

ws = sch.next_week_start()
c1, c2, c3 = st.columns([1.4, 1, 1])
site = c1.selectbox("Site", list(sc.SITES), format_func=lambda k: sc.SITES[k]["name"],
                    key="sched_site")
ramadan = c2.toggle("Ramadan hours", key="sched_ramadan",
                    help="6.5-hour shifts, adjustable in the configuration.")
derog = c3.toggle("Night waiver (art. 29)", key=f"sched_derog_{site}",
                  value=sc.SITES[site]["women_night_derogation"],
                  help="Granted by the labour inspector. It opens equal access to "
                       "night roles for women.")

try:
    fc = appdata.expected_demand(ss["profile_key"], ss["wilaya"], 21, ss["allow_network"])
except Exception:  # noqa: BLE001 , without a forecast, average load
    fc = None
load = sch.load_from_forecast(fc, ws)
peak = max(range(7), key=lambda d: load[d])
pday = ws + dt.timedelta(days=peak)
st.caption(f":material/trending_up: Expected load {(load[peak] - 1) * 100:+.0f}% on "
           f"{pday:%A} {pday.day}, from the forecast (Algerian calendar and real "
           f"weather){', Ramadan' if ramadan else ''}.")


@st.cache_data(show_spinner=False)
def _last_week(site: str, week: dt.date, derog: bool) -> dict:
    # Last week, solved once: the stability reference.
    r = sch.solve(site, week - dt.timedelta(days=7), women_derogation=derog)
    return {f"{k[0]}|{k[1]}": v for k, v in r.assign.items()}


if st.button("Generate", type="primary", icon=":material/auto_awesome:") or ss.pop("sched_autorun", False):
    with st.spinner("The solver is finding the best lawful schedule…"):
        last = {tuple([k.split("|")[0], int(k.split("|")[1])]): v
                for k, v in _last_week(site, ws, derog).items()}
        ss["sched_result"] = sch.solve(site, ws, load, ramadan=ramadan,
                                       women_derogation=derog, last_week=last)

res = ss.get("sched_result")
if res is None or res.site != site:
    st.caption("The agent is waiting for your click. It reads the forecast, approved "
               "leave and last week's schedule.")
    appdata.data_badge()
    st.stop()

if res.status not in ("OPTIMAL", "FEASIBLE"):
    st.error("No lawful schedule covers this week. Add reinforcements or lower the need.",
             icon=":material/error:")
    st.stop()

short = sum(res.shortfall.values())
with st.container(border=True):
    st.markdown(f"**Schedule for the week of {ws:%d/%m} ready.** {len(res.violations)} legal "
                f"violation · overtime {res.overtime_hours:.0f} h ({appdata.dzd(res.overtime_cost)}) · "
                f"{res.stability:.0%} unchanged from last week"
                + (f" · {short} slot(s) not covered" if short else " · demand covered"))
    st.caption(":material/gavel: Ord. 97-03 (40 h) · Law 90-11 art. 27, 28, 29, 31, 33")
    if st.button("Send for approval", icon=":material/inbox:"):
        con = db.seed(db.connect())
        db.add_card(con, source="planning", agent="Planning",
                    title=f"Schedule for {ws:%d/%m}, {sc.SITES[site]['name']}: ready",
                    detail=(f"0 violation. Overtime {res.overtime_hours:.0f} h. "
                            f"{res.stability:.0%} unchanged from last week. "
                            f"{short} slot(s) not covered."
                            + (" Ramadan hours." if res.ramadan else "")),
                    law="Ord. 97-03 · Law 90-11 art. 27 to 33",
                    decision="Schedule published to the teams in the employee desk.")
        st.toast("Card sent to the decision inbox.", icon=":material/inbox:")

art29 = [n for n, a in res.blocked_nights if a == "art. 29"]
art28 = [n for n, a in res.blocked_nights if a == "art. 28"]
if art29 or art28:
    with st.expander(f"Why {len(res.blocked_nights)} person(s) are not on nights"):
        if art29:
            st.markdown(f"**Art. 29** · {len(art29)} woman/women. The site has no labour "
                        f"inspector waiver for night work by women. Requesting it opens "
                        f"equal access to night roles: switch the setting above to see "
                        f"the effect.")
        if art28:
            st.markdown(f"**Art. 28** · {', '.join(art28)}: under 19, no night shifts.")

st.dataframe(sch.grid(res), hide_index=True, width="stretch", height=420)
st.caption("M morning · A afternoon · N night · \"·\" rest day")
appdata.data_badge()
