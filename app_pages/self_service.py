"""
Employee desk: the employee asks, the platform answers, HR is not interrupted.

On the left, the conversation as the employee sees it. On the right, what the
desk handled alone and what it sent to the decision inbox. The engine is
core/self_service.py: rule-based classification, answers from the file, leave
requests through the same legal check as the rest of the platform.
"""

import streamlit as st

from core import appdata, company_data as cd, i18n, self_service as svc

appdata.sidebar_controls()

ss = st.session_state
ss.setdefault("guichet_msgs", [])
ss.setdefault("guichet_tickets", [])
ss.setdefault("guichet_requests", [])
ss.setdefault("guichet_company", "Démo Handling & Logistique")
ss.setdefault("guichet_signatory", "Le responsable des ressources humaines")

people = cd.people()
by_id = {e.emp_id: e for e in people}

st.markdown(
    '<div class="tz-hero"><div>'
    f'<h1 class="tz-hero-h">{i18n.t("desk_title")}</h1>'
    f'<div class="tz-hero-s">{i18n.t("desk_sub")}</div></div></div>',
    unsafe_allow_html=True,
)

chat, side = st.columns([1.6, 1], gap="large")

with chat:
    emp_id = st.selectbox(i18n.t("logged_as"), options=list(by_id),
                          format_func=lambda k: f"{by_id[k].name} · {k}",
                          key="guichet_emp")
    emp = by_id[emp_id]

    examples = [
        "nheb attestation de travail lel bank",
        "How many leave days do I have left?",
        "I'd like time off from 14 to 20 December",
        "أريد كشف الراتب",
    ]
    def _take_pick() -> None:
        # A suggestion is used once: cleared in the callback (the only place a
        # widget may be changed), otherwise it would resend on every rerun.
        ss["_guichet_pending"] = ss.get("guichet_pick")
        ss["guichet_pick"] = None

    st.pills("Essayez", examples, key="guichet_pick", on_change=_take_pick,
             label_visibility="collapsed")

    box = st.container(height=460, border=True)
    typed = st.chat_input(i18n.t("type_request"))
    message = typed or ss.pop("_guichet_pending", None)

    if message:
        try:
            forecast = appdata.expected_demand(ss["profile_key"], ss["wilaya"],
                                               ss["horizon"], ss["allow_network"])
        except Exception:  # noqa: BLE001
            forecast = None
        tid = f"{len(ss['guichet_tickets']) + len(ss['guichet_msgs'])}"
        r = svc.answer(message, emp, forecast=forecast, company=ss["guichet_company"],
                       signatory=ss["guichet_signatory"], ticket_id=tid)
        ss["guichet_msgs"] += [
            {"role": "user", "text": message, "who": emp.name},
            {"role": "assistant", "text": r["reply"], "doc": r["document"],
             "intent": r["intent"]},
        ]
        if r["ticket"]:
            ss["guichet_tickets"].append(r["ticket"])
        if r["request"]:
            ss["guichet_requests"].append(r["request"])
        if not r["ticket"] and not r["request"]:
            # Answered on its own: it counts in the desk log.
            ss["guichet_tickets"].append({"id": tid, "label": svc.LABELS[r["intent"]],
                                          "emp_name": emp.name, "text": message,
                                          "needs_signature": False})

    with box:
        if not ss["guichet_msgs"]:
            st.caption("No request yet. Pick an example or write your own.")
        for i, m in enumerate(ss["guichet_msgs"]):
            with st.chat_message(m["role"], avatar=":material/person:" if m["role"] == "user"
                                 else ":material/support_agent:"):
                st.markdown(m["text"])
                if m.get("doc"):
                    with st.expander("Voir l'attestation", icon=":material/description:"):
                        st.text(m["doc"])
                    st.download_button("Download", m["doc"], key=f"dl_{i}",
                                       file_name="attestation_de_travail.txt",
                                       icon=":material/download:")

with side:
    tickets = ss["guichet_tickets"]
    alone = sum(1 for t in tickets if not t.get("needs_signature"))
    signed = len(tickets) - alone
    c1, c2 = st.columns(2)
    with c1:
        appdata.stat_card("Answered alone", f"{alone}", caption="instant reply")
    with c2:
        appdata.stat_card("Sent to your inbox", f"{signed + len(ss['guichet_requests'])}",
                          caption="signature or decision")

    with st.container(border=True):
        appdata.card_head("Requests received", f"{len(tickets) + len(ss['guichet_requests'])}")
        signed_keys = {k for k, v in ss.get("ap_decided", {}).items() if v == "approved"}
        rows = [{"name": t["label"], "sub": t["emp_name"],
                 "meta": ("signed" if f"tk:{t['id']}" in signed_keys else "to sign")
                 if t.get("needs_signature") else "answered"}
                for t in tickets[::-1]]
        rows += [{"name": r.kind_label, "sub": r.emp_name, "meta": "to decide"}
                 for r in ss["guichet_requests"][::-1]]
        appdata.list_rows(rows[:10], empty="Rien encore.", avatars=False)
        st.page_link("app_pages/autopilot.py", label="Open the decision inbox",
                     icon=":material/arrow_forward:")

    with st.expander("Desk settings", icon=":material/tune:"):
        st.text_input("Company name", key="guichet_company")
        st.text_input("Certificate signatory (as printed)", key="guichet_signatory")

    st.caption(":material/info: The desk opens from a link on any phone. A WhatsApp "
               "Business channel is planned, not yet connected. Messages are "
               "recognised by rules, with nothing sent to an outside service.")

appdata.data_badge()
