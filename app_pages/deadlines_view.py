"""
Deadlines & filings: what the accountant must file, and by when.

The screen answers one question: what has to go out this week, and where. It
shows the nearest deadline large, with the button that opens the official
portal, then the full list below.
"""

import datetime as _dt

import streamlit as st

from core import appdata, company_data as cd, deadlines_dz as dl, filings

appdata.sidebar_controls()

people = cd.people()
headcount = len(people)
today = _dt.date.today()

st.markdown(
    f'<div class="tz-hero"><div>'
    f'<h1 class="tz-hero-h">Deadlines & filings</h1>'
    f'<div class="tz-hero-s">What has to go to CNAS and the tax office, and by when. '
    f'Tracked headcount: <b>{headcount}</b> employees, so CNAS contributions are '
    f'<b>{"monthly" if headcount >= dl.CNAS_MONTHLY_THRESHOLD else "quarterly"}</b>.'
    f'</div></div></div>',
    unsafe_allow_html=True,
)

horizon = st.segmented_control(
    "Window", options=[60, 120, 365],
    format_func=lambda d: f"{d} days" if d < 365 else "1 year",
    default=120, key="dl_horizon", label_visibility="collapsed",
) or 120

items = dl.upcoming(today, headcount=headcount, horizon_days=horizon)
counts = dl.counts(today, headcount=headcount, horizon_days=horizon)

# ---------------------------------------------------------------------------
# The alert: the next deadline, large, with the portal link
# ---------------------------------------------------------------------------
nxt = dl.next_critical(today, headcount=headcount)
if nxt:
    left = nxt.days_left(today)
    if left < 0:
        st.error(
            f"**{nxt.label}: {abs(left)} days overdue.** It was due on "
            f"{nxt.due:%d/%m/%Y} for {nxt.period}. {nxt.penalty}",
            icon=":material/priority_high:",
        )
    elif left <= 7:
        st.warning(f"**{nxt.label}: in {left} days** ({nxt.due:%d/%m/%Y}). {nxt.what}",
                   icon=":material/schedule:")
    else:
        st.info(f"**Next deadline: {nxt.label}**, on {nxt.due:%d/%m/%Y} "
                f"(in {left} days). {nxt.what}", icon=":material/event_upcoming:")

k1, k2, k3, k4 = st.columns(4)
with k1:
    appdata.stat_card("Overdue", f"{counts['en_retard']}",
                      "to settle" if counts["en_retard"] else "none",
                      "down" if counts["en_retard"] else "up",
                      "a late contribution is still due, with a surcharge")
with k2:
    appdata.stat_card("Within 7 days", f"{counts['urgent']}", None, "flat", "to file this week")
with k3:
    appdata.stat_card("Within 30 days", f"{counts['a_venir']}", None, "flat", "to prepare")
with k4:
    appdata.stat_card("In the window", f"{len(items)}", f"{horizon} d", "flat", "all obligations")

# ---------------------------------------------------------------------------
# The amounts going out: what a delay would put at stake
# ---------------------------------------------------------------------------
y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
g50 = filings.g50_draft(people, y, m)
cnas = filings.cnas_draft(people, y, m)

left_col, right_col = st.columns([3, 2])

with left_col:
    with st.container(border=True):
        appdata.card_head("What goes out this period", f"payroll of {m:02d}/{y}")
        st.dataframe([
            {"Filing": "CNAS contributions", "Amount (DZD)": cnas["total_due"],
             "Due": cnas["due"].strftime("%d/%m/%Y")},
            {"Filing": "G50, IRG on salaries", "Amount (DZD)": g50["irg_total"],
             "Due": g50["due"].strftime("%d/%m/%Y")},
        ], hide_index=True, width="stretch",
            column_config={"Amount (DZD)": st.column_config.NumberColumn(format="%d")})
        st.caption("This is the base a late surcharge would apply to. Filing on time "
                   "does not earn money: it avoids losing it on a sum already owed.")
        st.page_link("app_pages/payroll_view.py", label="Open the prepared drafts",
                     icon=":material/arrow_forward:")

with right_col:
    with st.container(border=True):
        appdata.card_head("Where to file", "official portals")
        st.link_button("CNAS tele-declaration (DAS and contributions)",
                       dl.PORTAL_CNAS, width="stretch", type="primary",
                       icon=":material/open_in_new:")
        st.link_button("DGI Jibaya'tic (G50)", dl.PORTAL_DGI,
                       width="stretch", icon=":material/open_in_new:")
        st.link_button("CNAS main site", dl.PORTAL_CNAS_MAIN,
                       width="stretch", icon=":material/open_in_new:")
        st.link_button("CASNOS, self-employed", dl.PORTAL_CASNOS,
                       width="stretch", icon=":material/open_in_new:")
        st.divider()
        st.download_button(
            "Add to calendar (.ics)",
            data=dl.to_ics(items).encode("utf-8"),
            file_name="tawzia-deadlines.ics", mime="text/calendar",
            width="stretch", icon=":material/calendar_add_on:",
            help="Import the file into Outlook, Google Calendar or any calendar: "
                 "every deadline arrives with a reminder 7 days before.",
        )

# ---------------------------------------------------------------------------
# The full list, filterable
# ---------------------------------------------------------------------------
with st.container(border=True):
    appdata.card_head("All deadlines", f"{len(items)} over {horizon} days")

    f1, f2 = st.columns(2)
    bodies = sorted({o.body for o in items})
    keep_bodies = f1.multiselect("Body", bodies, default=bodies, key="dl_bodies")
    statuses = [dl.STATUS_FR[k] for k in ("en_retard", "urgent", "a_venir", "plus_tard")]
    keep_status = f2.multiselect("Status", statuses, default=statuses, key="dl_status")

    df = dl.frame(today, headcount=headcount, horizon_days=horizon)
    if not df.empty:
        df = df[df["Body"].isin(keep_bodies) & df["Status"].isin(keep_status)]

    if df.empty:
        st.markdown('<div class="tz-empty">No deadline with these filters.</div>',
                    unsafe_allow_html=True)
    else:
        st.dataframe(
            df[["Due", "Days left", "Status", "Obligation", "Body", "Period", "Reliability"]],
            hide_index=True, width="stretch",
            column_config={
                "Due": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Days left": st.column_config.NumberColumn(format="%d d"),
            },
        )
        st.download_button(
            "Export as CSV", df.to_csv(index=False).encode("utf-8-sig"),
            file_name="tawzia-deadlines.csv", mime="text/csv",
            icon=":material/download:",
        )

    for o in items[:4]:
        with st.expander(f"{o.due:%d/%m/%Y}: {o.label} ({o.body})",
                         icon=":material/description:"):
            st.markdown(f"**To do.** {o.what}")
            st.markdown(f"**Period.** {o.period}")
            st.markdown(f"**If late.** {o.penalty}")
            st.link_button("Open the portal", o.portal, icon=":material/open_in_new:")
            if o.confidence == "sourcee":
                st.caption(f":material/verified: Source: {o.source}")
            else:
                st.caption(f":material/help: {o.source}. This rule exists, but its date "
                           f"or amount varies with finance laws: have your accountant "
                           f"or agency confirm it.")

# ---------------------------------------------------------------------------
# Obligations triggered by an event, not the calendar
# ---------------------------------------------------------------------------
with st.container(border=True):
    appdata.card_head("Triggered by an event", "not by the calendar")
    for e in dl.EVENT_DRIVEN:
        st.markdown(f"**{e['label']}**: {e['trigger']} · {e['body']}")
        st.caption(f"{e['what']} {e['note']}")

st.caption(
    ":material/gavel: This screen reminds you of deadlines; it does not replace your "
    "accountant. Dates marked \"Sourced\" come from a named source; those marked \"To "
    "confirm\" exist but vary, and the platform would rather say so."
)
appdata.data_badge()
