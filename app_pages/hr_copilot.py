"""AI HR copilot, plain-language answers grounded in the real HR data."""

import datetime as dt

import streamlit as st

from core import (
    appdata, ai, attendance, compliance, demand as demand_mod, hr,
    labour_dz, payroll_dz,
)

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]

st.title("Copilote RH")
st.caption("Posez vos questions sur le personnel, les congés, la paie, la présence "
           "ou la loi. Les réponses viennent uniquement des données de ce site.")

# Provider status: Provider for the jury, Groq free fallback.
status = ai.status_line()
avail = ai.providers_available()
if avail["provider"]:
    st.success(f":material/smart_toy: {status}", icon=":material/verified:")
elif avail["groq"]:
    st.info(f":material/smart_toy: {status}")
else:
    st.warning(
        "Aucune clé IA configurée. Ajoutez **PROVIDER_API_KEY** (idéale pour le "
        "jury) ou **GROQ_API_KEY** (gratuite) dans les Secrets. Toutes les autres "
        "pages RH fonctionnent sans.",
        icon=":material/key:",
    )

# ---------------------------------------------------------------------------
# Build a compact, real data snapshot for the model to reason over.
# ---------------------------------------------------------------------------

@st.cache_data(ttl="30m", show_spinner=False)
def _context(profile_key, wilaya, headcount, allow_network):
    people = appdata.hr_people()
    today = dt.date.today()
    wf = hr.workforce_frame(people, today)
    records = appdata.hr_attendance()
    summary = attendance.lateness_summary(records)
    requests = appdata.hr_requests()

    plan = appdata.load_forward_plan(
        profile_key, wilaya, st.session_state["horizon"], headcount,
        st.session_state["temp_ceiling"], st.session_state["service_level"], allow_network)
    roster = plan["roster"]
    register = payroll_dz.payroll_register(roster, profile.primary_role)
    alerts = compliance.scan(roster=roster, people=people, constraints=appdata.current_constraints())

    parts = []
    parts.append(f"SITE: {profile.label} in {wilaya}. Headcount {len(people)}.")
    parts.append("WORKFORCE (sample):\n" + wf.head(20).to_string(index=False))
    parts.append("ATTENDANCE (14d, worst first):\n" + summary.head(10).to_string(index=False))
    parts.append("PENDING REQUESTS:\n" + "\n".join(
        f"- {r.emp_name}: {r.kind_label} {r.start:%d %b}"
        f"{('-' + format(r.end, '%d %b')) if r.end != r.start else ''} ({r.reason})"
        for r in requests) or "none")
    dl = payroll_dz.declaration_lines(register)
    parts.append("MONTHLY PAYROLL DECLARATIONS:\n" + dl.to_string(index=False))
    parts.append("COMPLIANCE ALERTS:\n" + ("\n".join(
        f"- [{a.severity}] {a.category}: {a.message}" for a in alerts) or "none"))
    parts.append(
        "ALGERIAN LAW REFERENCE: annual leave 30 days (40 in southern wilayas), "
        f"accrued 2.5/month; maternity 14 weeks; sick pay 50% first 15 days then "
        f"100%; SNMG {labour_dz.SNMG_MONTHLY:,.0f} DZD; CNAS employee 9% + employer "
        f"26%; IRG exempt at/below 30,000 DZD; overtime capped at 20%; weekend is "
        f"Friday-Saturday.")
    return "\n\n".join(parts)

context = _context(st.session_state["profile_key"], st.session_state["wilaya"],
                   appdata.workforce_headcount(), st.session_state["allow_network"])

SYSTEM = (
    "You are the HR copilot inside WorkForce.dz, an HR platform for Algerian "
    "operations. Answer the manager's question using ONLY the data below. Be "
    "concise and concrete, cite real names, dates and figures. Respect Algerian "
    "labour law (Friday-Saturday weekend; leave and pay rules as given). Costs "
    "are loaded costs including CNAS. If the data does not answer the question, "
    "say so. Never invent employees, numbers or rules not present. "
    "ALWAYS answer in French.\n\n"
    + context
)

with st.expander("Exemples de questions", icon=":material/lightbulb:"):
    st.markdown(
        "- Qui risque de partir, et pourquoi ?\n"
        "- Combien de jours de congé reste-t-il à l'équipe au total ?\n"
        "- Sommes-nous en infraction avec le droit du travail en ce moment ?\n"
        "- Rédige une réponse approuvant la demande de sortie la plus proche.\n"
        "- Quelle sera la facture CNAS de ce mois, et pourquoi 26% ?"
    )

if "hr_chat" not in st.session_state:
    st.session_state["hr_chat"] = []

for m in st.session_state["hr_chat"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

q = st.chat_input("Posez votre question au copilote RH...")
if q:
    if not (avail["provider"] or avail["groq"]):
        st.warning("Configurez d'abord une clé IA (voir ci-dessus).", icon=":material/key:")
    else:
        st.session_state["hr_chat"].append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            with st.spinner("Réflexion..."):
                res = ai.chat(SYSTEM, q, max_tokens=700)
            if res.ok:
                st.markdown(res.text)
                cap = f"via {res.provider} ({res.model})"
                if res.error:
                    cap += f" {res.error}"
                st.caption(cap)
                st.session_state["hr_chat"].append({"role": "assistant", "content": res.text})
            else:
                st.error(res.error or "Le fournisseur d'IA n'a pas pu répondre.")

if st.session_state["hr_chat"]:
    if st.button("Effacer la conversation", icon=":material/delete:"):
        st.session_state["hr_chat"] = []
        st.rerun()

appdata.data_badge()
