"""
Assistant: one conversation for the whole platform.

A single thread; for each question a router picks the domain and gives the
model only that domain's figures. The user never has to know which screen to
ask on, and the model gets a short context, so a sharper answer.

The chat UI is the `tawzia_chat` component (assistant-ui, Custom Components
v2). Python owns the conversation and produces the answers: **no API key ever
reaches the browser**.

Figures always come from the in-house engines. The language layer only writes:
it may not invent a number, and the prompt forbids it explicitly.
"""

import datetime as dt

import streamlit as st
from tawzia_chat import tawzia_chat

from core import (ai, appdata, attendance, company_data as cd, compliance,
                  copilot, demand as demand_mod, hr, labour_dz, payroll_dz)

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]

_HISTORY = "assistant_messages"
_PENDING = "assistant_pending"
_LAST_TOPIC = "assistant_last_topic"

st.session_state.setdefault(_HISTORY, [])
st.session_state.setdefault(_PENDING, None)
st.session_state.setdefault(_LAST_TOPIC, None)

st.markdown(
    '<div class="tz-hero"><div>'
    '<h1 class="tz-hero-h">Ask Tawzia</h1>'
    '<div class="tz-hero-s">Ask anything about your company: scheduling and '
    'costs, people and payroll, or a decision to make. The assistant fetches '
    'the figures the platform has already calculated.</div></div></div>',
    unsafe_allow_html=True,
)


# The three contexts. Only one is sent to the model, depending on the question.

def _header() -> str:
    return (f"COMPANY: {profile.label} in {wilaya}. "
            f"Load unit: {profile.demand_unit}. "
            f"Today: {dt.date.today():%d/%m/%Y}.")


def _planning_context() -> str:
    """Forecast load, recommended schedule and cost structure."""
    plan = appdata.load_forward_plan(
        st.session_state["profile_key"], wilaya, st.session_state["horizon"],
        st.session_state["regular_pool"], st.session_state["temp_ceiling"],
        st.session_state["service_level"], st.session_state["allow_network"],
    )
    roster, fc = plan["roster"], plan["forecast"]
    roster_cols = [c for c in ("date", "shift", "required_workers", "regular",
                               "overtime", "temp", "total_staff", "planned_cost")
                   if c in roster.columns]
    fc_cols = [c for c in ("date", "shift", "forecast", "p10", "p90",
                           "holiday_name", "is_ramadan_int", "ramadan_day",
                           "temp_max", "precip_mm", "weather_productivity")
               if c in fc.columns]

    role = labour_dz.ROLES[profile.primary_role]
    cost = (
        f"Role: {role.label}. Gross hourly {role.gross_hourly:.2f} DZD; loaded "
        f"cost (with {labour_dz.CNAS_EMPLOYER:.0%} CNAS employer share) "
        f"{role.loaded_hourly:.2f} DZD. Overtime +{labour_dz.OVERTIME_PREMIUM:.0%}, "
        f"night +{labour_dz.NIGHT_PREMIUM:.0%}, Friday/Saturday rest day "
        f"+{labour_dz.RESTDAY_PREMIUM:.0%}, public holiday "
        f"+{labour_dz.HOLIDAY_PREMIUM:.0%}. Agency temps carry an extra "
        f"{labour_dz.TEMP_AGENCY_MARKUP:.0%} markup. The SNMG is "
        f"{labour_dz.SNMG_MONTHLY:,.0f} DZD/month for "
        f"{labour_dz.LEGAL_MONTHLY_HOURS} legal hours."
    )
    return (f"COST STRUCTURE:\n{cost}\n\n"
            f"FORECAST LOAD:\n{fc[fc_cols].to_string(index=False)}\n\n"
            f"RECOMMENDED SCHEDULE:\n{roster[roster_cols].to_string(index=False)}")


@st.cache_data(ttl="30m", show_spinner=False)
def _hr_context(profile_key, wilaya_key, headcount, allow_network, horizon,
                temp_ceiling, service_level) -> str:
    """Headcount, attendance, requests, payroll filings and legal alerts."""
    people = appdata.hr_people()
    wf = hr.workforce_frame(people, dt.date.today())
    records = appdata.hr_attendance()
    summary = attendance.lateness_summary(records)
    requests = appdata.hr_requests()

    plan = appdata.load_forward_plan(profile_key, wilaya_key, horizon, headcount,
                                     temp_ceiling, service_level, allow_network)
    register = payroll_dz.payroll_register(plan["roster"], profile.primary_role)
    alerts = compliance.scan(roster=plan["roster"], people=people,
                             constraints=appdata.current_constraints())

    parts = [
        f"HEADCOUNT: {len(people)} employees.",
        "STAFF REGISTER (extract):\n" + wf.head(20).to_string(index=False),
        "ATTENDANCE (14 days, worst first):\n"
        + summary.head(10).to_string(index=False),
        "PENDING REQUESTS:\n" + ("\n".join(
            f"- {r.emp_name}: {r.kind_label} {r.start:%d/%m}"
            f"{('-' + format(r.end, '%d/%m')) if r.end != r.start else ''} "
            f"({r.reason})" for r in requests) or "none"),
        "THIS MONTH'S PAYROLL FILINGS:\n"
        + payroll_dz.declaration_lines(register).to_string(index=False),
        "COMPLIANCE ALERTS:\n" + ("\n".join(
            f"- [{a.severity}] {a.category}: {a.message}" for a in alerts)
            or "none"),
        ("ALGERIAN LEGAL REFERENCE: annual leave 30 days (40 in the southern "
         "wilayas), earned 2.5 days a month; maternity 14 weeks; sick leave "
         "50% for the first 15 days then 100%; SNMG "
         f"{labour_dz.SNMG_MONTHLY:,.0f} DZD; CNAS {labour_dz.CNAS_EMPLOYEE:.0%} "
         f"employee + {labour_dz.CNAS_EMPLOYER:.1%} employer; no IRG at 30,000 DZD "
         "and below; overtime capped at 20%; weekend Friday-Saturday."),
    ]
    return "\n\n".join(parts)


def _decision_context() -> tuple:
    """The company's costed brief: indicators, risks, costs."""
    people = cd.people()
    records = cd.attendance_records()
    brief = copilot.build_brief(people, records, source_label=cd.source_label())
    return copilot.brief_as_text(brief), brief


_SYSTEM_BASE = (
    "You are the assistant of Tawzia, the HR and workforce-planning platform "
    "for Algerian companies. Answer the manager's question using ONLY the data "
    "below.\n\n"
    "Rules you must follow:\n"
    "- The Algerian weekend is FRIDAY and SATURDAY, not Saturday-Sunday.\n"
    "- Costs quoted are LOADED costs, employer contributions included.\n"
    "- Never invent a figure, name or rule that is not in the data. If the data "
    "does not answer the question, say so plainly.\n"
    "- Operational volumes in the demo are simulated; the calendar, weather and "
    "labour law driving them are real. If asked what is real, answer honestly.\n"
    "- Be concise and concrete. Quote real dates, names and amounts.\n"
    "- Answer in the language of the question, without technical jargon.\n"
)


def _prompt_for(topic: str) -> str:
    """The full system prompt, with only the context the question needs."""
    if topic == "planning":
        body = _planning_context()
    elif topic == "rh":
        body = _hr_context(
            st.session_state["profile_key"], wilaya,
            appdata.workforce_headcount(), st.session_state["allow_network"],
            st.session_state["horizon"], st.session_state["temp_ceiling"],
            st.session_state["service_level"],
        )
    else:
        body, _ = _decision_context()
        body = ("COMPANY BRIEF WITH FIGURES (source of truth):\n" + body
                + "\n\nStructure your answer: (1) direct answer, (2) what the "
                  "figures say, (3) a concrete recommendation.")
    return f"{_SYSTEM_BASE}\n{_header()}\n\n{body}"


# What the assistant knows, and what it recommends unprompted
_brief_text, brief = _decision_context()

with st.container(border=True):
    appdata.card_head("What the assistant knows", cd.source_label())
    cols = st.columns(4)
    for i, key in enumerate(["headcount", "employer_cost", "absenteeism",
                             "attrition_risk"]):
        if key in brief["kpis"]:
            cols[i].metric(brief["kpis"][key]["label"],
                           brief["kpis"][key]["display"])
    st.caption("It reads three domains: **scheduling and costs**, **people, "
               "payroll and labour law**, and **decision indicators**. Ask in "
               "your own words: it looks in the right place.")

with st.expander("What to deal with first", icon=":material/priority_high:"):
    for r in copilot.rule_recommendation(brief):
        st.markdown(r)
    st.caption("These recommendations come from the platform's rules and show "
               "even without an AI key.")

if not any(ai.providers_available().values()):
    st.info(
        "**No AI key configured.** The conversation is off, but the "
        "recommendations above and every other screen work. To turn it on, get "
        "a free key at console.groq.com and add `GROQ_API_KEY` to the app secrets.",
        icon=":material/key:",
    )
    appdata.data_badge()
    st.stop()

SUGGESTIONS = [
    "Should we hire this quarter, and for which role?",
    "Which days depend most on temps, and at what cost?",
    "What will this month's CNAS bill be, and how is it calculated?",
    "Who might leave in the next six months, and why?",
]

result = tawzia_chat(
    st.session_state[_HISTORY],
    busy=st.session_state[_PENDING] is not None,
    placeholder="Ask about your company…",
    suggestions=SUGGESTIONS,
    empty_title="What do you want to know?",
    empty_text=f"Scheduling, people, payroll, decisions: the assistant reads the "
               f"figures already calculated for {profile.label} in {wilaya}.",
    key="assistant_thread",
)

sent = getattr(result, "sent", None)

# Two steps: show the question and the typing indicator first, then call the
# model on the next rerun, so the screen never freezes on the network call.
if sent and st.session_state[_PENDING] is None:
    st.session_state[_HISTORY].append({"role": "user", "content": sent})
    st.session_state[_PENDING] = sent
    st.rerun()

if st.session_state[_PENDING] is not None:
    question = st.session_state[_PENDING]
    topic = copilot.route(question)
    st.session_state[_LAST_TOPIC] = topic
    res = ai.chat(_prompt_for(topic), question, max_tokens=800, temperature=0.2)
    answer = res.text if res.ok else f"I could not answer: {res.error}"
    st.session_state[_HISTORY].append({"role": "assistant", "content": answer})
    st.session_state[_PENDING] = None
    st.rerun()

controls = st.container(horizontal=True)
with controls:
    if st.session_state[_HISTORY]:
        if st.button("Clear the conversation", icon=":material/delete:"):
            st.session_state[_HISTORY] = []
            st.session_state[_PENDING] = None
            st.session_state[_LAST_TOPIC] = None
            st.rerun()
    topic = st.session_state[_LAST_TOPIC]
    if topic:
        st.caption(f":material/database: Last answer based on: "
                   f"**{copilot.TOPICS[topic]}** · {ai.status_line()}")
    else:
        st.caption(f":material/smart_toy: {ai.status_line()}")

appdata.data_badge()
