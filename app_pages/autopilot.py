"""
Decision inbox: the home screen. The HR work is done; what is left is to sign.

Every agent has gone over today's data (see core/autopilot.py). Compliant items
that need no judgement are grouped into one card signed with a single click;
everything else gets its own card, most urgent first. Each card has four parts
and no more: what the agent did, why, the rule applied, and the buttons. No
agent sends, files, pays or rejects anything without a human "Approve".

The layout is built to invite action: the day's count is the headline, a
progress bar fills as cards are cleared, the one safe batch sits first, and a
filter lets HR work one agent at a time.
"""

import datetime as dt
import html
import json

import streamlit as st

from core import (ai, appdata, attrition, autopilot as ap, company_data as cd,
                  cv_screen, db, deadlines_dz as dl, demand as demand_mod,
                  i18n, onboarding)

appdata.sidebar_controls()
t = i18n.t

ss = st.session_state
ss.setdefault("ap_decided", {})
ss.setdefault("ap_log", [])
ss.setdefault("guichet_tickets", [])
ss.setdefault("guichet_requests", [])
ss.setdefault("guichet_msgs", [])

profile = demand_mod.PROFILES[ss["profile_key"]]
people = cd.people()
records = cd.attendance_records()
today = dt.date.today()

try:
    forecast = appdata.expected_demand(ss["profile_key"], ss["wilaya"],
                                       ss["horizon"], ss["allow_network"])
except Exception:  # noqa: BLE001 , without a forecast, requests are judged on the law alone
    forecast = None

open_role = cv_screen.JOBS.get(profile.primary_role, next(iter(cv_screen.JOBS.values())))
with st.spinner(t("agents_running")):
    run = ap.run(
        people=people, records=records,
        requests=list(appdata.hr_requests()) + list(ss["guichet_requests"]),
        attrition_df=attrition.score_workforce(people, records),
        forecast=forecast, headcount=len(people), role_key=profile.primary_role,
        tickets=ss["guichet_tickets"], open_role_title=open_role.title.lower(),
    )

con = db.seed(db.connect())
db_cards = db.pending_cards(con)
decided = ss["ap_decided"]
pending = run.pending(decided)
batch = [a for a in pending if a.auto]
single = [a for a in pending if not a.auto]
total = len(run.actions) + len(db_cards)
left = len(pending) + len(db_cards)
cleared = total - left
urgent = sum(1 for a in pending if a.urgency == 0)

# One colour and one drawn icon per agent (stroke icons, 24px grid).
AGENT = {
    "Présence": ("--tz-a-presence", '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>'),
    "Paie": ("--tz-a-paie", '<rect x="3" y="6" width="18" height="12" rx="1"/><circle cx="12" cy="12" r="2.5"/>'),
    "Déclarations": ("--tz-a-decl", '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M10 12h5M10 16h5"/>'),
    "Conformité": ("--tz-a-conf", '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z"/><path d="M9 12l2 2 4-4"/>'),
    "Rétention": ("--tz-a-ret", '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>'),
    "Recrutement": ("--tz-a-rec", '<circle cx="10" cy="8" r="3.5"/><path d="M3 20c0-4 3-6 7-6s7 2 7 6M18 8v6M15 11h6"/>'),
    "Guichet": ("--tz-a-guichet", '<path d="M4 5h16v11H9l-5 4z"/>'),
    "Intégration": ("--tz-a-onb", '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>'),
    "Planning": ("--tz-a-plan", '<rect x="3" y="5" width="18" height="16" rx="1"/><path d="M3 10h18M8 3v4M16 3v4"/>'),
}


def _icon(agent: str) -> str:
    var, paths = AGENT.get(agent, ("--tz-a-guichet", '<circle cx="12" cy="12" r="7"/>'))
    return (f'<span class="tz-agent" style="background:var({var})" aria-hidden="true">'
            f'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{paths}</svg></span>')


def _decide(a: ap.Action, verdict: str) -> None:
    """Record the decision, log it, and deliver what has to be delivered."""
    decided[a.key] = verdict
    ss["ap_log"].insert(0, {"at": dt.datetime.now().strftime("%H:%M"),
                            "who": t("you"), "agent": a.agent, "what": a.title,
                            "verdict": verdict})
    # An approved certificate goes back to the employee, in their own chat.
    tid = a.payload.get("ticket")
    if tid is not None and verdict == "approved":
        tk = next((x for x in ss["guichet_tickets"] if x["id"] == tid), None)
        if tk and tk.get("document"):
            ss["guichet_msgs"].append({
                "role": "assistant", "doc": tk["document"], "intent": "attestation",
                "text": t("cert_signed", name=tk["emp_name"].split()[0])})


# ---------------------------------------------------------------------------
# Today: the count, the progress, and what each agent prepared
# ---------------------------------------------------------------------------
per_agent = {}
for a in run.actions:
    per_agent[a.agent] = per_agent.get(a.agent, 0) + 1
for c in db_cards:
    per_agent[c["agent"]] = per_agent.get(c["agent"], 0) + 1
top = max(per_agent.values()) if per_agent else 1

done_by_agent, open_by_agent = {}, {}
for a in run.actions:
    bucket = done_by_agent if a.key in decided else open_by_agent
    bucket[a.agent] = bucket.get(a.agent, 0) + 1
segments = "".join(
    f'<span style="width:{n / max(total, 1) * 100:.2f}%;'
    f'background:var({AGENT.get(ag, ("--tz-a-guichet",))[0]})" title="{html.escape(ag)}"></span>'
    for ag, n in done_by_agent.items())
bars = "".join(
    f'<div class="tz-agent-bar"><span>{html.escape(t("agent:" + ag))}</span>'
    f'<i style="width:{n / top * 100:.0f}%;background:var({AGENT.get(ag, ("--tz-a-guichet",))[0]})"></i>'
    f'<b>{n}</b></div>' for ag, n in sorted(per_agent.items(), key=lambda kv: -kv[1]))
hours = ap.totals(run.actions)["minutes"] / 60
headline = (t("today_none") if not left else
            t("today_h", n=left, u=urgent) if urgent else t("today_h0", n=left))
st.markdown(
    f'<div class="tz-today"><div class="tz-today-main">'
    f'<div class="tz-today-h">{headline}</div>'
    f'<div class="tz-today-s">{t("today_s", d=today.strftime("%d/%m/%Y"), n=len(people), h=f"{hours:.1f}")}</div>'
    f'<div class="tz-prog"><div class="tz-prog-bar" role="progressbar" '
    f'aria-valuenow="{cleared}" aria-valuemin="0" aria-valuemax="{total}">{segments}</div>'
    f'<div class="tz-prog-l"><span>{t("cleared", c=cleared, n=total)}</span>'
    f'<span>{t("hours_est")}</span></div></div></div>'
    f'<div class="tz-today-viz"><h4>{t("agents_prepared")}</h4>{bars}</div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# The work column and the side column
# ---------------------------------------------------------------------------
inbox, side = st.columns([1.9, 1], gap="large")

with inbox:
    agents_present = sorted({a.agent for a in single} | {c["agent"] for c in db_cards})
    options = ["all", "urgent"] + agents_present
    pick = st.segmented_control(
        t("filter"), options=options, default="all", key="ap_filter",
        format_func=lambda o: (t("f_all", n=len(single) + len(db_cards)) if o == "all"
                               else t("f_urgent", n=urgent) if o == "urgent"
                               else t("agent:" + o)),
        label_visibility="collapsed") or "all"

    if not left:
        st.success(t("inbox_empty"), icon=":material/check_circle:")

    if batch and pick in ("all", "Présence"):
        with st.container(border=True):
            st.markdown(
                f'<div class="tz-card-top">{_icon("Présence")}<div>'
                f'<div class="tz-card-m"><span class="tz-tag agent">{t("agent:Présence")}</span>'
                f'<span class="tz-tag money">{t("n_replies", n=len(batch))}</span></div>'
                f'<div class="tz-card-t">{t("batch_t", n=len(batch))}</div></div></div>'
                f'<div class="tz-why"><b>{t("why")}</b> · {t("batch_why")}</div>'
                f'<div class="tz-law">Law 90-11, art. 39 to 54 · law 83-11</div>',
                unsafe_allow_html=True)
            with st.expander(t("see_replies")):
                for a in batch:
                    st.write(f"- {a.title}")
            b1, b2 = st.columns([1.2, 1.4])
            if b1.button(t("approve_n", n=len(batch)), key="ok_batch", type="primary",
                         icon=":material/done_all:", width="stretch"):
                for a in batch:
                    _decide(a, "approved")
                st.rerun()
            b2.page_link("app_pages/requests_view.py", label=t("edit_one_by_one"),
                         icon=":material/edit:")

    shown = [a for a in single
             if pick == "all" or (pick == "urgent" and a.urgency == 0) or a.agent == pick]
    for a in shown[:25]:
        with st.container(border=True):
            tags = f'<span class="tz-tag agent">{html.escape(t("agent:" + a.agent))}</span>'
            if a.urgency == 0:
                tags += f'<span class="tz-tag urgent">{t("urgent")}</span>'
            if a.stakes_dzd > 0:
                tags += f'<span class="tz-tag money">+{appdata.dzd(a.stakes_dzd, compact=True)}</span>'
            st.markdown(
                f'<div class="tz-card-top">{_icon(a.agent)}<div>'
                f'<div class="tz-card-m">{tags}</div>'
                f'<div class="tz-card-t">{html.escape(a.title)}</div></div></div>'
                f'<div class="tz-why"><b>{t("why")}</b> · {html.escape(a.detail)}</div>'
                + (f'<div class="tz-law">{html.escape(a.law)}</div>' if a.law else ""),
                unsafe_allow_html=True)
            with st.expander(t("what_approval_does")):
                st.write(a.decision)
                for issue in a.payload.get("issues", []):
                    st.write(f"- {issue}")
            b1, b2, b3 = st.columns([1.2, 1, 1])
            if b1.button(t("approve"), key=f"ok_{a.key}", type="primary",
                         icon=":material/check:", width="stretch"):
                _decide(a, "approved")
                st.rerun()
            if a.page:
                b2.page_link(a.page, label=t("edit"), icon=":material/edit:")
            if b3.button(t("reject"), key=f"no_{a.key}", icon=":material/close:",
                         width="stretch"):
                _decide(a, "rejected")
                st.rerun()

    # Cards from the database: onboarding and MCP draft tools.
    for c in db_cards:
        if pick not in ("all", c["agent"]):
            continue
        with st.container(border=True):
            st.markdown(
                f'<div class="tz-card-top">{_icon(c["agent"])}<div>'
                f'<div class="tz-card-m"><span class="tz-tag agent">{html.escape(t("agent:" + c["agent"]))}</span>'
                f'<span class="tz-tag agent">{html.escape(c["source"])}</span></div>'
                f'<div class="tz-card-t">{html.escape(c["title"])}</div></div></div>'
                f'<div class="tz-why"><b>{t("why")}</b> · {html.escape(c["detail"])}</div>'
                + (f'<div class="tz-law">{html.escape(c["law"])}</div>' if c["law"] else ""),
                unsafe_allow_html=True)
            with st.expander(t("what_approval_does")):
                st.write(c["decision"])
            b1, b2, b3 = st.columns([1.2, 1, 1])
            if b1.button(t("approve"), key=f"okdb_{c['id']}", type="primary",
                         icon=":material/check:", width="stretch"):
                db.decide_card(con, c["id"], "approved", t("you"))
                payload = json.loads(c["payload"] or "{}")
                if payload.get("kind") == "hire" and ss.get("ob_reg"):
                    n = onboarding.launch(con, ss["ob_reg"], f"NEW-{c['id']}")
                    st.toast(t("hire_launched", n=n), icon=":material/rocket_launch:")
                ss["ap_log"].insert(0, {"at": dt.datetime.now().strftime("%H:%M"), "who": t("you"),
                                        "agent": c["agent"], "what": c["title"], "verdict": "approved"})
                st.rerun()
            if c["source"] == "onboarding":
                b2.page_link("app_pages/onboarding_view.py", label=t("see_file"),
                             icon=":material/folder_open:")
            if b3.button(t("reject"), key=f"nodb_{c['id']}", icon=":material/close:",
                         width="stretch"):
                db.decide_card(con, c["id"], "rejected", t("you"))
                ss["ap_log"].insert(0, {"at": dt.datetime.now().strftime("%H:%M"), "who": t("you"),
                                        "agent": c["agent"], "what": c["title"], "verdict": "rejected"})
                st.rerun()

    if len(shown) > 25:
        st.caption(t("more_cards", n=len(shown) - 25))
    if pending and pick == "all":
        if st.button(t("approve_all", n=len(pending)), icon=":material/done_all:"):
            for a in pending:
                _decide(a, "approved")
            st.rerun()

with side:
    nxt = dl.next_critical(today, headcount=len(people))
    if nxt:
        d = nxt.days_left(today)
        short = next((k for k in ("G50", "CNAS", "DAS") if k in nxt.label), nxt.label.split(" (")[0])
        st.markdown(
            f'<div class="tz-deadline{" late" if d < 0 else ""}">'
            f'<span>{t("next_deadline")}</span><b>{short} · {nxt.due:%d/%m/%Y}</b>'
            f'<span>{t("overdue") if d < 0 else t("in_days", n=d)}</span></div>',
            unsafe_allow_html=True)
        st.page_link("app_pages/deadlines_view.py", label=t("open_filing"),
                     icon=":material/arrow_forward:")

    with st.container(border=True):
        appdata.card_head(t("brief"))
        if st.button(t("write_brief"), icon=":material/auto_awesome:", width="stretch"):
            facts = "\n".join(f"- {a.agent}: {a.title}" for a in run.actions[:20])
            r = ai.chat(
                "You are the HR director of an Algerian company. Write a five-line "
                f"summary for management in {i18n.lang_name()}, from the facts provided only. "
                "Invent no figures. No em dashes.",
                f"Today's facts:\n{facts}", max_tokens=600,
            )
            ss["ap_brief"] = r.text if r.ok else (t("no_ai_key") + "\n\n" + facts)
        if ss.get("ap_brief"):
            st.markdown(ss["ap_brief"])
        else:
            st.caption(t("brief_hint"))

    with st.container(border=True):
        appdata.card_head(t("action_log"), f"{len(ss['ap_log'])}")
        rows = [{"name": e["what"], "sub": f"{e['at']} · {e['who']} · "
                 + (t("approved") if e["verdict"] == "approved" else t("rejected")),
                 "meta": t("agent:" + e["agent"])} for e in ss["ap_log"][:8]]
        appdata.list_rows(rows, empty=t("log_empty"), avatars=False, wrap=True)
        st.caption(t("log_note"))
        if decided and st.button(t("undo"), icon=":material/undo:", width="stretch"):
            decided.clear()
            ss["ap_log"].clear()
            st.rerun()

appdata.data_badge()
