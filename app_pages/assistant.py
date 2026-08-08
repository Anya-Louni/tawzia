"""
Assistant opérations , questions en langage naturel sur le plan actuel.

L'interface de conversation est le composant `workforce_chat` (assistant-ui,
Custom Components v2). Python détient la conversation et produit les réponses :
**aucune clé d'API ne descend dans le navigateur**.

L'assistant est ancré strictement dans les chiffres déjà calculés par les autres
pages. Il explique les résultats, il ne les produit pas, et le prompt système lui
interdit de présenter des volumes simulés comme des mesures.
"""

import streamlit as st
from workforce_chat import workforce_chat

from core import ai, appdata, demand as demand_mod, labour_dz

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]

st.title("Assistant opérations")
st.caption(
    "Posez vos questions sur la prévision, le planning ou le détail des coûts. "
    "L'assistant lit ce que l'application a déjà calculé , il ne relance pas "
    "le modèle et n'invente aucun chiffre."
)

_HISTORY = "assistant_messages"
_PENDING = "assistant_pending"

st.session_state.setdefault(_HISTORY, [])
st.session_state.setdefault(_PENDING, None)

if not any(ai.providers_available().values()):
    st.info(
        "**Aucune clé IA configurée.** Toutes les autres pages fonctionnent "
        "sans. Pour activer la conversation, obtenez une clé gratuite sur "
        "console.groq.com et ajoutez `GROQ_API_KEY` aux secrets de "
        "l'application.",
        icon=":material/key:",
    )
    st.stop()

plan = appdata.load_forward_plan(
    st.session_state["profile_key"],
    st.session_state["wilaya"],
    st.session_state["horizon"],
    st.session_state["regular_pool"],
    st.session_state["temp_ceiling"],
    st.session_state["service_level"],
    st.session_state["allow_network"],
)
roster = plan["roster"]
fc = plan["forecast"]


def _system_prompt() -> str:
    """Le contexte figé que l'assistant a le droit d'utiliser, et rien d'autre."""
    roster_cols = [c for c in ("date", "shift", "required_workers", "regular",
                               "overtime", "temp", "total_staff", "planned_cost")
                   if c in roster.columns]
    fc_cols = [c for c in ("date", "shift", "forecast", "p10", "p90",
                           "holiday_name", "is_ramadan_int", "ramadan_day",
                           "temp_max", "precip_mm", "weather_productivity")
               if c in fc.columns]

    role = labour_dz.ROLES[profile.primary_role]
    cost_context = (
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

    return (
        "Tu es l'assistant opérations de WorkForce.dz, un outil de planification "
        "de main-d'œuvre pour les entreprises algériennes. Réponds à la question "
        "du responsable en utilisant UNIQUEMENT les données ci-dessous. Sois "
        "concis et concret, et cite les dates, les shifts et les chiffres réels.\n\n"
        "Règles que tu dois respecter :\n"
        "- Le week-end algérien est VENDREDI et SAMEDI, pas samedi-dimanche.\n"
        "- Les coûts cités sont des coûts CHARGÉS, charges patronales comprises.\n"
        "- Les VOLUMES opérationnels de ces données sont simulés pour un "
        "prototype ; le calendrier et la météo qui les pilotent sont réels. Si "
        "on te demande à quel point c'est réel, dis-le franchement et "
        "n'exagère rien.\n"
        "- Si les données ci-dessous ne répondent pas à la question, dis-le "
        "plutôt que de deviner.\n"
        "- Réponds TOUJOURS en français.\n\n"
        f"SITE : {profile.label} à {st.session_state['wilaya']}. "
        f"Unité de demande : {profile.demand_unit}.\n\n"
        f"STRUCTURE DE COÛT :\n{cost_context}\n\n"
        f"PRÉVISION :\n{fc[fc_cols].to_string(index=False)}\n\n"
        f"PLANNING :\n{roster[roster_cols].to_string(index=False)}"
    )


SUGGESTIONS = [
    "Pourquoi faut-il du personnel en plus le jour le plus chargé ?",
    "Quels jours dépend-on le plus des intérimaires, et à quel coût ?",
    "Qu'advient-il du planning pendant le Ramadan ?",
    "Expliquez la différence entre salaire brut et coût chargé.",
]

# Le composant affiche la conversation ; `sent` porte le message envoyé.
result = workforce_chat(
    st.session_state[_HISTORY],
    busy=st.session_state[_PENDING] is not None,
    placeholder="Posez une question sur le plan actuel…",
    suggestions=SUGGESTIONS,
    empty_title="Que voulez-vous savoir sur ce plan ?",
    empty_text="L'assistant lit la prévision et le planning déjà calculés pour "
               f"{profile.label} à {st.session_state['wilaya']}, et répond avec "
               "les chiffres réels de cet écran.",
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
    res = ai.chat(_system_prompt(), question, max_tokens=700, temperature=0.2)
    answer = res.text if res.ok else (
        f"Je n'ai pas pu répondre : {res.error}"
    )
    st.session_state[_HISTORY].append({"role": "assistant", "content": answer})
    st.session_state[_PENDING] = None
    st.rerun()

controls = st.container(horizontal=True)
with controls:
    if st.session_state[_HISTORY]:
        if st.button("Effacer la conversation", icon=":material/delete:"):
            st.session_state[_HISTORY] = []
            st.session_state[_PENDING] = None
            st.rerun()
    st.caption(f":material/smart_toy: {ai.status_line()}")

appdata.data_badge()
