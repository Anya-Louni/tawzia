"""Requests & attendance: short absences, leave, and who is late."""

import streamlit as st

from core import appdata, attendance

appdata.sidebar_controls()

st.title("Requests & attendance")
st.caption("Employee requests decided on the law and the forecast load, plus the "
           "lateness and absence board.")

people = appdata.hr_people()
lookup = {e.emp_id: e for e in people}
requests = appdata.hr_requests()
records = appdata.hr_attendance()

# Forecast context, to know whether a day is a peak. The fast expected demand is
# enough here; the calibrated forecast with its backtest is not needed.
try:
    forecast = appdata.expected_demand(
        st.session_state["profile_key"], st.session_state["wilaya"],
        st.session_state["horizon"], st.session_state["allow_network"])
except Exception:  # noqa: BLE001 , without a forecast, requests are judged on the law alone
    forecast = None

flags_today = attendance.todays_flags(records)
summary = attendance.lateness_summary(records)

with st.container(horizontal=True):
    st.metric("Pending requests", f"{len(requests)}", border=True)
    st.metric("Late or absent today", f"{len(flags_today)}", border=True)
    chronic = int((summary["Absent %"] >= 15).sum()) if not summary.empty else 0
    st.metric("Leaving watch", f"{chronic}", border=True,
              help="Employees with 15%+ absence, the strongest signal of leaving.")

_REC = {
    "approve": "approve",
    "approve_with_cover": "approve with cover",
    "approve_with_note": "approve with a note",
    "reject": "decline",
    "record": "record",
    "review": "review",
}

tab_req, tab_att = st.tabs(["Request inbox", "Attendance & lateness"])

# ---------------------------------------------------------------------------
with tab_req:
    st.subheader("Request inbox")
    st.caption(
        "Every request gets a recommendation: a legal check (leave balance, notice) "
        "plus a load check, so approving during a forecast peak is flagged."
    )
    for r in requests:
        emp = lookup.get(r.emp_id)
        if emp is None:
            continue
        d = attendance.decide_request(r, emp, forecast=forecast)
        rec = d["recommend"]
        icon = {"approve": ":material/check_circle:", "approve_with_cover": ":material/warning:",
                "approve_with_note": ":material/warning:", "reject": ":material/cancel:",
                "record": ":material/description:", "review": ":material/help:"}.get(rec, ":material/help:")
        with st.container(border=True):
            top = st.columns([3, 2, 2])
            with top[0]:
                st.markdown(f"**{r.emp_name}** · {r.kind_label}")
                span = f"{r.start:%d %b}" if r.is_sortie else f"{r.start:%d %b} to {r.end:%d %b}"
                extra = f" ({r.hours:.0f} h)" if r.is_sortie and r.hours else ""
                st.caption(f"{span}{extra} · “{r.reason}”")
            with top[1]:
                st.markdown(f"{icon} **{_REC.get(rec, rec)}**")
                if d.get("load") == "peak":
                    st.caption(":material/trending_up: demand peak")
            with top[2]:
                st.caption(f"Balance after: {d['balance_after']:.1f} days")
            for w in d["warnings"]:
                st.caption(f":material/warning: {w}")
            for rn in d["reasons"][:1]:
                st.caption(rn)

# ---------------------------------------------------------------------------
with tab_att:
    st.subheader("Late or absent today")
    if flags_today.empty:
        st.success("Everyone on time today.", icon=":material/check_circle:")
    else:
        st.dataframe(flags_today, hide_index=True, width="stretch")

    st.subheader("Attendance record (14 days)")
    st.caption("Chronic lateness and absence are the raw signal of leaving risk.")
    if not summary.empty:
        def _risk(row):
            if row["Absent %"] >= 20 or row["Late %"] >= 35:
                return "High"
            if row["Absent %"] >= 10 or row["Late %"] >= 20:
                return "Watch"
            return "OK"
        summary = summary.copy()
        summary["Leaving risk"] = summary.apply(_risk, axis=1)
        st.dataframe(
            summary, hide_index=True, width="stretch", height=380,
            column_config={
                "Late %": st.column_config.NumberColumn(format="%.1f"),
                "Absent %": st.column_config.NumberColumn(format="%.1f"),
            },
        )

appdata.data_badge()
