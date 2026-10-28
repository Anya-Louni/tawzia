"""
Boîte de décisions , l'écran d'accueil : le travail RH est fait, il reste à signer.

Chaque agent est passé sur les données du jour (voir core/autopilot.py).
Ce qui est conforme et sans arbitrage est regroupé en une carte signée d'un
seul clic ; le reste arrive en cartes, la plus urgente d'abord. Chaque carte a quatre
parties et pas une de plus : ce que l'agent a fait, pourquoi, le texte appliqué,
et les trois boutons. Aucun agent n'envoie, ne dépose, ne paie ni ne refuse
sans un clic « Approuver ».
"""

import datetime as dt
import json

import streamlit as st

from core import (ai, appdata, attrition, autopilot as ap, company_data as cd,
                  cv_screen, db, deadlines_dz as dl, demand as demand_mod,
                  i18n, onboarding)

appdata.sidebar_controls()

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
except Exception:  # noqa: BLE001 , sans prévision, les demandes restent jugées sur la loi
    forecast = None

open_role = cv_screen.JOBS.get(profile.primary_role, next(iter(cv_screen.JOBS.values())))
with st.spinner("Les agents passent sur les dossiers du jour…"):
    run = ap.run(
        people=people, records=records,
        requests=list(appdata.hr_requests()) + list(ss["guichet_requests"]),
        attrition_df=attrition.score_workforce(people, records),
        forecast=forecast, headcount=len(people), role_key=profile.primary_role,
        tickets=ss["guichet_tickets"], open_role_title=open_role.title.lower(),
    )

decided = ss["ap_decided"]
pending = run.pending(decided)
handled = run.handled(decided)
batch = [a for a in pending if a.auto]
single = [a for a in pending if not a.auto]


def _decide(a: ap.Action, verdict: str) -> None:
    """Mémoriser la décision, la tracer, et livrer ce qui doit l'être."""
    decided[a.key] = verdict
    ss["ap_log"].insert(0, {"at": dt.datetime.now().strftime("%H:%M"),
                            "who": "Vous", "agent": a.agent, "what": a.title,
                            "verdict": verdict})
    # L'attestation approuvée revient au salarié, dans sa conversation.
    tid = a.payload.get("ticket")
    if tid is not None and verdict == "approved":
        t = next((t for t in ss["guichet_tickets"] if t["id"] == tid), None)
        if t and t.get("document"):
            ss["guichet_msgs"].append({
                "role": "assistant", "doc": t["document"], "intent": "attestation",
                "text": f"{t['emp_name'].split()[0]}, votre attestation est signée. "
                        f"La voici."})


# ---------------------------------------------------------------------------
# L'en-tête : ce qui reste, le temps rendu, la prochaine échéance légale
# ---------------------------------------------------------------------------
t = i18n.t
left_word = t("nothing_left") if not pending else t("n_waiting", n=len(pending))
st.markdown(
    '<div class="tz-hero"><div>'
    f'<h1 class="tz-hero-h">{t("inbox_title")}</h1>'
    f'<div class="tz-hero-s">{t("inbox_sub", n=len(people), k=len(run.actions), left=left_word)}'
    '</div></div></div>',
    unsafe_allow_html=True,
)

nxt = dl.next_critical(today, headcount=len(people))
c1, c2, c3 = st.columns(3)
with c1:
    urgent = sum(1 for a in pending if a.urgency == 0)
    appdata.stat_card(t("to_decide"), f"{len(pending)}",
                      f"{urgent} urgente{'s' if urgent > 1 else ''}" if urgent else None,
                      "down" if urgent else "flat")
with c2:
    appdata.stat_card(t("prepared"),
                      f"{ap.totals(run.actions)['minutes'] / 60:.1f} h",
                      caption=t("estimate"))
with c3:
    if nxt:
        d = nxt.days_left(today)
        appdata.stat_card(t("next_deadline"),
                          # Le nom court : la tuile porte un mot, pas une phrase.
                          next((k for k in ("G50", "CNAS", "DAS") if k in nxt.label),
                               nxt.label.split(" (")[0]),
                          caption=(f"le {nxt.due:%d/%m}, "
                                   + ("en retard" if d < 0 else f"dans {d} jour(s)")))
    else:
        appdata.stat_card("Prochaine échéance légale", "Aucune", caption="sur 45 jours")

# ---------------------------------------------------------------------------
# Les cartes, et à droite ce qui a été fait
# ---------------------------------------------------------------------------
_AGENT_BADGE = {
    "Présence": "blue", "Paie": "violet", "Conformité": "red",
    "Déclarations": "orange", "Rétention": "green", "Recrutement": "blue",
    "Guichet": "gray",
}

inbox, side = st.columns([1.9, 1], gap="large")

with inbox:
    head, bulk = st.columns([3, 1.3], vertical_alignment="center")
    head.subheader(t("to_validate"))
    if pending and bulk.button(t("approve_all", n=len(pending)),
                               icon=":material/done_all:", width="stretch"):
        for a in pending:
            _decide(a, "approved")
        st.rerun()

    if not pending:
        st.success("Boîte vide. Les agents vous écriront dès qu'une décision "
                   "vous revient.", icon=":material/check_circle:")

    if batch:
        with st.container(border=True):
            st.markdown(f":green-badge[Présence] :gray-badge[{len(batch)} réponses]  \n"
                        f"**{len(batch)} demandes conformes, réponses prêtes**")
            st.caption("**Pourquoi** · Solde suffisant, préavis respecté, aucun pic "
                       "de charge prévu sur les dates demandées.")
            st.caption(":material/gavel: Loi 90-11, art. 39 à 54 · loi 83-11")
            with st.expander("Voir les réponses"):
                for a in batch:
                    st.write(f"- {a.title}")
            b1, b2 = st.columns([1, 2])
            if b1.button(f"Approuver les {len(batch)}", key="ok_batch", type="primary",
                         icon=":material/done_all:", width="stretch"):
                for a in batch:
                    _decide(a, "approved")
                st.rerun()
            b2.page_link("app_pages/requests_view.py", label="Modifier une par une",
                         icon=":material/edit:")

    for a in single[:25]:
        with st.container(border=True):
            tag = f":{_AGENT_BADGE.get(a.agent, 'gray')}-badge[{a.agent}]"
            if a.urgency == 0:
                tag += " :red-badge[:material/priority_high: Urgent]"
            if a.stakes_dzd > 0:
                tag += f" :green-badge[+{appdata.dzd(a.stakes_dzd, compact=True)}]"
            st.markdown(f"{tag}  \n**{a.title}**")
            st.caption(f"**{t('why')}** · {a.detail}")
            if a.law:
                st.caption(f":material/gavel: {a.law}")
            with st.expander(t("what_approval_does")):
                st.write(a.decision)
                for issue in a.payload.get("issues", []):
                    st.write(f"- {issue}")
            b1, b2, b3 = st.columns(3)
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
    # Cartes venues de la base : intégration, outils MCP de brouillon.
    con = db.seed(db.connect())
    for c in db.pending_cards(con):
        with st.container(border=True):
            st.markdown(f":blue-badge[{c['agent']}] :gray-badge[{c['source']}]  \n**{c['title']}**")
            st.caption(f"**Pourquoi** · {c['detail']}")
            if c["law"]:
                st.caption(f":material/gavel: {c['law']}")
            with st.expander("Voir ce que l'approbation déclenche"):
                st.write(c["decision"])
            b1, b2, b3 = st.columns(3)
            if b1.button("Approuver", key=f"okdb_{c['id']}", type="primary",
                         icon=":material/check:", width="stretch"):
                db.decide_card(con, c["id"], "approved", "Vous")
                payload = json.loads(c["payload"] or "{}")
                if payload.get("kind") == "hire" and ss.get("ob_reg"):
                    n = onboarding.launch(con, ss["ob_reg"], f"NEW-{c['id']}")
                    st.toast(f"Embauche approuvée : {n} tâches lancées.", icon=":material/rocket_launch:")
                ss["ap_log"].insert(0, {"at": dt.datetime.now().strftime("%H:%M"), "who": "Vous",
                                        "agent": c["agent"], "what": c["title"], "verdict": "approved"})
                st.rerun()
            if c["source"] == "onboarding":
                b2.page_link("app_pages/onboarding_view.py", label="Voir le dossier",
                             icon=":material/folder_open:")
            if b3.button("Rejeter", key=f"nodb_{c['id']}", icon=":material/close:",
                         width="stretch"):
                db.decide_card(con, c["id"], "rejected", "Vous")
                ss["ap_log"].insert(0, {"at": dt.datetime.now().strftime("%H:%M"), "who": "Vous",
                                        "agent": c["agent"], "what": c["title"], "verdict": "rejected"})
                st.rerun()

    if len(single) > 25:
        st.caption(f"{len(single) - 25} autres décisions, moins urgentes, suivent.")

with side:
    with st.container(border=True):
        appdata.card_head(t("brief"))
        if st.button("Rédiger le résumé", icon=":material/auto_awesome:",
                     width="stretch"):
            facts = "\n".join(f"- {a.agent}: {a.title}" for a in run.actions[:20])
            r = ai.chat(
                "Tu es le directeur RH d'une entreprise algérienne. Rédige en "
                "français un résumé de 5 lignes pour la direction, à partir des "
                "faits fournis uniquement. N'invente aucun chiffre. Pas de tiret long.",
                f"Faits du jour :\n{facts}", max_tokens=350,
            )
            ss["ap_brief"] = r.text if r.ok else (
                "Aucune clé IA configurée : voici les faits bruts.\n\n" + facts)
        if ss.get("ap_brief"):
            st.markdown(ss["ap_brief"])
        else:
            st.caption("Cinq lignes écrites à partir des seuls faits relevés.")

    with st.container(border=True):
        appdata.card_head(t("agents_did"))
        appdata.list_rows(
            [{"name": agent, "sub": note, "meta": ""} for agent, note in run.log],
            avatars=False, wrap=True,
        )

    with st.container(border=True):
        appdata.card_head(t("action_log"), f"{len(ss['ap_log'])}")
        rows = [{"name": e["what"], "sub": f"{e['at']} · {e['who']} · "
                 + ("approuvé" if e["verdict"] == "approved" else "rejeté"),
                 "meta": e["agent"]} for e in ss["ap_log"][:8]]
        appdata.list_rows(rows, empty="Rien encore.", avatars=False, wrap=True)
        st.caption("Chaque décision est tracée : qui, quoi, quand. Rien ne part "
                   "sans un clic humain.")
        if decided and st.button("Annuler mes décisions", icon=":material/undo:",
                                 width="stretch"):
            decided.clear()
            ss["ap_log"].clear()
            st.rerun()

appdata.data_badge()
