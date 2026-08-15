"""
Assistant , une seule conversation pour toute la plateforme.

Cet écran remplace les trois qui posaient la même question à trois endroits
(planning, RH, décision). Le fil de discussion est unique ; à chaque question,
un routeur choisit le domaine concerné et ne donne au modèle que les chiffres de
ce domaine. L'utilisateur n'a plus à savoir dans quel écran poser sa question, et
le modèle reçoit un contexte court, donc une réponse plus précise.

L'interface de conversation est le composant `tawzia_chat` (assistant-ui, Custom
Components v2). Python détient la conversation et produit les réponses :
**aucune clé d'API ne descend dans le navigateur**.

Les chiffres viennent toujours des moteurs maison. La couche langage ne fait que
rédiger : elle n'a pas le droit d'inventer un chiffre, et le prompt le lui
interdit explicitement.
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
    f'<div class="tz-hero"><div>'
    f'<h1 class="tz-hero-h">Assistant</h1>'
    f'<div class="tz-hero-s">Posez n\'importe quelle question sur votre '
    f'entreprise : le planning et les coûts, le personnel et la paie, ou une '
    f'décision à prendre. L\'assistant va chercher les chiffres déjà calculés '
    f'par la plateforme.</div></div></div>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Les trois contextes. Un seul est envoyé au modèle, selon la question.
# ---------------------------------------------------------------------------

def _header() -> str:
    return (f"ENTREPRISE : {profile.label} à {wilaya}. "
            f"Unité de charge : {profile.demand_unit}. "
            f"Date du jour : {dt.date.today():%d/%m/%Y}.")


def _planning_context() -> str:
    """Prévision de charge, planning recommandé et structure de coût."""
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
        f"Poste : {role.label}. Brut horaire {role.gross_hourly:.2f} DZD ; "
        f"coût chargé (avec {labour_dz.CNAS_EMPLOYER:.0%} de charges patronales "
        f"CNAS) {role.loaded_hourly:.2f} DZD. Heures supplémentaires +"
        f"{labour_dz.OVERTIME_PREMIUM:.0%}, nuit +{labour_dz.NIGHT_PREMIUM:.0%}, "
        f"jour de repos vendredi/samedi +{labour_dz.RESTDAY_PREMIUM:.0%}, jour "
        f"férié +{labour_dz.HOLIDAY_PREMIUM:.0%}. Les intérimaires d'agence "
        f"portent en plus {labour_dz.TEMP_AGENCY_MARKUP:.0%} de majoration. Le "
        f"SNMG est de {labour_dz.SNMG_MONTHLY:,.0f} DZD/mois pour "
        f"{labour_dz.LEGAL_MONTHLY_HOURS} heures légales."
    )
    return (f"STRUCTURE DE COÛT :\n{cost}\n\n"
            f"PRÉVISION DE CHARGE :\n{fc[fc_cols].to_string(index=False)}\n\n"
            f"PLANNING RECOMMANDÉ :\n{roster[roster_cols].to_string(index=False)}")


@st.cache_data(ttl="30m", show_spinner=False)
def _hr_context(profile_key, wilaya_key, headcount, allow_network, horizon,
                temp_ceiling, service_level) -> str:
    """Effectif, présence, demandes, déclarations de paie et alertes légales."""
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
        f"EFFECTIF : {len(people)} salariés.",
        "REGISTRE DU PERSONNEL (extrait) :\n" + wf.head(20).to_string(index=False),
        "PRÉSENCE (14 jours, les plus problématiques d'abord) :\n"
        + summary.head(10).to_string(index=False),
        "DEMANDES EN ATTENTE :\n" + ("\n".join(
            f"- {r.emp_name} : {r.kind_label} {r.start:%d/%m}"
            f"{('-' + format(r.end, '%d/%m')) if r.end != r.start else ''} "
            f"({r.reason})" for r in requests) or "aucune"),
        "DÉCLARATIONS DE PAIE DU MOIS :\n"
        + payroll_dz.declaration_lines(register).to_string(index=False),
        "ALERTES DE CONFORMITÉ :\n" + ("\n".join(
            f"- [{a.severity}] {a.category} : {a.message}" for a in alerts)
            or "aucune"),
        ("RÉFÉRENCE LÉGALE ALGÉRIENNE : congé annuel 30 jours (40 dans les "
         "wilayas du Sud), acquis 2,5 jours par mois ; maternité 14 semaines ; "
         "maladie 50% les 15 premiers jours puis 100% ; SNMG "
         f"{labour_dz.SNMG_MONTHLY:,.0f} DZD ; CNAS 9% salarié + 26% employeur ; "
         "IRG exonéré à 30 000 DZD et en dessous ; heures supplémentaires "
         "plafonnées à 20% ; week-end vendredi-samedi."),
    ]
    return "\n\n".join(parts)


def _decision_context() -> tuple:
    """Le brief chiffré de l'entreprise : indicateurs, risques, coûts."""
    people = cd.people()
    records = cd.attendance_records()
    brief = copilot.build_brief(people, records, source_label=cd.source_label())
    return copilot.brief_as_text(brief), brief


_SYSTEM_BASE = (
    "Tu es l'assistant de Tawzia, la plateforme RH et de planification des "
    "entreprises algériennes. Réponds à la question du responsable en utilisant "
    "UNIQUEMENT les données fournies ci-dessous.\n\n"
    "Règles que tu dois respecter :\n"
    "- Le week-end algérien est VENDREDI et SAMEDI, pas samedi-dimanche.\n"
    "- Les coûts cités sont des coûts CHARGÉS, charges patronales comprises.\n"
    "- N'invente jamais un chiffre, un nom ou une règle qui ne figure pas dans "
    "les données. Si elles ne répondent pas à la question, dis-le simplement.\n"
    "- Les volumes opérationnels de la démonstration sont simulés ; le "
    "calendrier, la météo et le droit du travail qui les pilotent sont réels. "
    "Si on te demande ce qui est réel, réponds franchement.\n"
    "- Sois concis et concret. Cite les dates, les noms et les montants réels.\n"
    "- Réponds TOUJOURS en français, sans jargon technique.\n"
)


def _prompt_for(topic: str) -> str:
    """Le prompt système complet, avec le seul contexte utile à la question."""
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
        body = ("BRIEF CHIFFRÉ DE L'ENTREPRISE (source de vérité) :\n" + body
                + "\n\nStructure ta réponse : (1) réponse directe, (2) ce que "
                  "disent les chiffres, (3) recommandation concrète.")
    return f"{_SYSTEM_BASE}\n{_header()}\n\n{body}"


# ---------------------------------------------------------------------------
# Ce que l'assistant sait, et ce qu'il recommande sans qu'on lui demande
# ---------------------------------------------------------------------------
_brief_text, brief = _decision_context()

with st.container(border=True):
    appdata.card_head("Ce que l'assistant sait", cd.source_label())
    cols = st.columns(4)
    for i, key in enumerate(["headcount", "employer_cost", "absenteeism",
                             "attrition_risk"]):
        if key in brief["kpis"]:
            cols[i].metric(brief["kpis"][key]["label"],
                           brief["kpis"][key]["display"])
    st.caption(
        "Il lit trois domaines : **le planning et les coûts**, **le personnel, "
        "la paie et le droit du travail**, et **les indicateurs de décision**. "
        "Posez la question dans vos mots : il va chercher au bon endroit."
    )

with st.expander("Ce qu'il faudrait traiter en priorité",
                 icon=":material/priority_high:"):
    for r in copilot.rule_recommendation(brief):
        st.markdown(r)
    st.caption("Ces recommandations viennent des règles de la plateforme et "
               "s'affichent même sans clé IA.")

if not any(ai.providers_available().values()):
    st.info(
        "**Aucune clé IA configurée.** La conversation est désactivée, mais les "
        "recommandations ci-dessus et tous les autres écrans fonctionnent. Pour "
        "activer la conversation, obtenez une clé gratuite sur console.groq.com "
        "et ajoutez `GROQ_API_KEY` aux secrets de l'application.",
        icon=":material/key:",
    )
    appdata.data_badge()
    st.stop()

# ---------------------------------------------------------------------------
# La conversation
# ---------------------------------------------------------------------------
SUGGESTIONS = [
    "Faut-il embaucher ce trimestre, et à quel poste ?",
    "Quels jours dépend-on le plus des intérimaires, et à quel coût ?",
    "Quelle sera la facture CNAS de ce mois, et pourquoi 26% ?",
    "Qui risque de partir dans les six mois, et pourquoi ?",
]

result = tawzia_chat(
    st.session_state[_HISTORY],
    busy=st.session_state[_PENDING] is not None,
    placeholder="Posez votre question sur l'entreprise…",
    suggestions=SUGGESTIONS,
    empty_title="Que voulez-vous savoir ?",
    empty_text=f"Planning, personnel, paie, décisions : l'assistant lit les "
               f"chiffres déjà calculés pour {profile.label} à {wilaya}.",
    key="assistant_thread",
)

sent = getattr(result, "sent", None)

# Deux temps : on affiche d'abord la question et l'indicateur de saisie, puis on
# appelle le modèle au rerun suivant. Sans cela l'écran resterait figé pendant
# tout l'appel réseau, sans que l'utilisateur voie son propre message.
if sent and st.session_state[_PENDING] is None:
    st.session_state[_HISTORY].append({"role": "user", "content": sent})
    st.session_state[_PENDING] = sent
    st.rerun()

if st.session_state[_PENDING] is not None:
    question = st.session_state[_PENDING]
    topic = copilot.route(question)
    st.session_state[_LAST_TOPIC] = topic
    res = ai.chat(_prompt_for(topic), question, max_tokens=800, temperature=0.2)
    answer = res.text if res.ok else f"Je n'ai pas pu répondre : {res.error}"
    st.session_state[_HISTORY].append({"role": "assistant", "content": answer})
    st.session_state[_PENDING] = None
    st.rerun()

controls = st.container(horizontal=True)
with controls:
    if st.session_state[_HISTORY]:
        if st.button("Effacer la conversation", icon=":material/delete:"):
            st.session_state[_HISTORY] = []
            st.session_state[_PENDING] = None
            st.session_state[_LAST_TOPIC] = None
            st.rerun()
    topic = st.session_state[_LAST_TOPIC]
    if topic:
        st.caption(f":material/database: Dernière réponse fondée sur : "
                   f"**{copilot.TOPICS[topic]}** · {ai.status_line()}")
    else:
        st.caption(f":material/smart_toy: {ai.status_line()}")

appdata.data_badge()
