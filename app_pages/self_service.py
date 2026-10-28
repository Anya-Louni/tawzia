"""
Guichet salarié , le salarié demande, la plateforme répond, le RH n'est plus dérangé.

À gauche, la conversation telle que la voit le salarié. À droite, ce que le
guichet a traité seul et ce qu'il a transmis à l'autopilote. Le moteur est
core/self_service.py : classification par règles, réponses tirées du dossier,
demandes de congé passées au même contrôle légal que le reste de la plateforme.
"""

import streamlit as st

from core import appdata, company_data as cd, self_service as svc

appdata.sidebar_controls()

ss = st.session_state
ss.setdefault("guichet_msgs", [])
ss.setdefault("guichet_tickets", [])
ss.setdefault("guichet_requests", [])
ss.setdefault("guichet_company", "SARL Démonstration")
ss.setdefault("guichet_signatory", "Le responsable des ressources humaines")

people = cd.people()
by_id = {e.emp_id: e for e in people}

st.markdown(
    '<div class="tz-hero"><div>'
    '<h1 class="tz-hero-h">Guichet salarié</h1>'
    '<div class="tz-hero-s">Attestation de travail, solde de congés, bulletin, '
    'demande de congé : le salarié écrit comme il parle, en français, en arabe '
    'ou en darija, et reçoit sa réponse <b>sans passer par le bureau RH</b>.'
    '</div></div></div>',
    unsafe_allow_html=True,
)

chat, side = st.columns([1.6, 1], gap="large")

with chat:
    emp_id = st.selectbox("Connecté en tant que", options=list(by_id),
                          format_func=lambda k: f"{by_id[k].name} · {k}",
                          key="guichet_emp")
    emp = by_id[emp_id]

    examples = [
        "nheb attestation de travail lel bank",
        "chhal bqali men youm congé ?",
        "Je veux prendre un congé du 14 au 20 décembre",
        "أريد كشف الراتب",
    ]
    def _take_pick() -> None:
        # Une suggestion ne sert qu'une fois : vidée dans le rappel (seul
        # endroit où modifier un widget est permis), sinon elle se renverrait
        # à chaque rerun.
        ss["_guichet_pending"] = ss.get("guichet_pick")
        ss["guichet_pick"] = None

    st.pills("Essayez", examples, key="guichet_pick", on_change=_take_pick,
             label_visibility="collapsed")

    box = st.container(height=460, border=True)
    typed = st.chat_input("Écrivez votre demande…")
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
            # Réponse donnée seule : elle compte dans le journal du guichet.
            ss["guichet_tickets"].append({"id": tid, "label": svc.LABELS[r["intent"]],
                                          "emp_name": emp.name, "text": message,
                                          "needs_signature": False})

    with box:
        if not ss["guichet_msgs"]:
            st.caption("Aucune demande pour l'instant. Choisissez un exemple ou "
                       "écrivez la vôtre.")
        for i, m in enumerate(ss["guichet_msgs"]):
            with st.chat_message(m["role"], avatar=":material/person:" if m["role"] == "user"
                                 else ":material/support_agent:"):
                st.markdown(m["text"])
                if m.get("doc"):
                    with st.expander("Voir l'attestation", icon=":material/description:"):
                        st.text(m["doc"])
                    st.download_button("Télécharger", m["doc"], key=f"dl_{i}",
                                       file_name="attestation_de_travail.txt",
                                       icon=":material/download:")

with side:
    tickets = ss["guichet_tickets"]
    alone = sum(1 for t in tickets if not t.get("needs_signature"))
    signed = len(tickets) - alone
    c1, c2 = st.columns(2)
    with c1:
        appdata.stat_card("Réglé seul", f"{alone}", caption="réponse immédiate")
    with c2:
        appdata.stat_card("Vers vos décisions", f"{signed + len(ss['guichet_requests'])}",
                          caption="signature ou décision")

    with st.container(border=True):
        appdata.card_head("Demandes reçues", f"{len(tickets) + len(ss['guichet_requests'])}")
        signed_keys = {k for k, v in ss.get("ap_decided", {}).items() if v == "approved"}
        rows = [{"name": t["label"], "sub": t["emp_name"],
                 "meta": ("signée" if f"tk:{t['id']}" in signed_keys else "à signer")
                 if t.get("needs_signature") else "répondu"}
                for t in tickets[::-1]]
        rows += [{"name": r.kind_label, "sub": r.emp_name, "meta": "à décider"}
                 for r in ss["guichet_requests"][::-1]]
        appdata.list_rows(rows[:10], empty="Rien encore.", avatars=False)
        st.page_link("app_pages/autopilot.py", label="Ouvrir la boîte de décisions",
                     icon=":material/arrow_forward:")

    with st.expander("Réglages du guichet", icon=":material/tune:"):
        st.text_input("Raison sociale", key="guichet_company")
        st.text_input("Signataire des attestations", key="guichet_signatory")

    st.caption(":material/info: Le guichet s'ouvre sur un lien, depuis n'importe "
               "quel téléphone. Un canal WhatsApp Business est prévu, il n'est pas "
               "encore branché. La reconnaissance des messages est faite par "
               "règles, sans envoi à un service extérieur.")

appdata.data_badge()
