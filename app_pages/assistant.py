"""
Assistant opérations , questions en langage naturel sur le plan actuel.

Ancré strictement dans les chiffres déjà générés par les autres pages. Il
explique les résultats, il ne les produit pas. Le prompt système précise que les
volumes sont simulés, pour que l'assistant ne puisse pas surestimer.
"""

import os

import streamlit as st

from core import appdata, demand as demand_mod, labour_dz

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]

st.title("Assistant opérations")
st.caption(
    "Posez des questions sur la prévision, le planning ou le détail des coûts. "
    "L'assistant lit ce que l'app a déjà calculé , il ne relance pas le modèle."
)

api_key = os.environ.get("GROQ_API_KEY", "")

if not api_key:
    st.info(
        "**Aucune `GROQ_API_KEY` configurée.** Toutes les autres pages "
        "fonctionnent sans. Pour activer celle-ci, obtenez une clé gratuite sur "
        "console.groq.com et ajoutez-la dans les Secrets :\n\n"
        "```\nGROQ_API_KEY=gsk_votre_cle\n```",
        icon=":material/key:",
    )
    st.stop()

try:
    from groq import Groq
except ImportError:
    st.error("Exécutez `pip install groq` pour activer l'assistant.", icon=":material/error:")
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

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

with st.expander("Questions suggérées", icon=":material/lightbulb:"):
    st.markdown(
        "- Pourquoi faut-il du personnel en plus le jour le plus chargé ?\n"
        "- Quels jours dépend-on le plus des intérimaires, et à quel coût ?\n"
        "- Qu'advient-il du planning pendant le Ramadan ?\n"
        "- Où la météo nuit-elle à la productivité cette quinzaine ?\n"
        "- Expliquez la différence entre salaire brut et coût chargé."
    )

for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input("Posez une question sur le plan actuel…")

if question:
    st.session_state["chat_history"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    roster_summary = roster[[
        "date", "shift", "required_workers", "regular", "overtime",
        "temp", "total_staff", "planned_cost",
    ]].to_string(index=False)

    fc_cols = [c for c in ("date", "shift", "forecast", "p10", "p90",
                           "holiday_name", "is_ramadan_int", "ramadan_day",
                           "temp_max", "precip_mm", "weather_productivity")
               if c in fc.columns]
    fc_summary = fc[fc_cols].to_string(index=False)

    role = labour_dz.ROLES[profile.primary_role]
    cost_context = (
        f"Role: {role.label}. Gross hourly {role.gross_hourly:.2f} DZD; "
        f"loaded hourly (incl. {labour_dz.CNAS_EMPLOYER:.0%} CNAS employer "
        f"charges) {role.loaded_hourly:.2f} DZD. Overtime +"
        f"{labour_dz.OVERTIME_PREMIUM:.0%}, night +{labour_dz.NIGHT_PREMIUM:.0%}, "
        f"Friday/Saturday rest day +{labour_dz.RESTDAY_PREMIUM:.0%}, public "
        f"holiday +{labour_dz.HOLIDAY_PREMIUM:.0%}. Agency temps carry a "
        f"further {labour_dz.TEMP_AGENCY_MARKUP:.0%} markup. SNMG is "
        f"{labour_dz.SNMG_MONTHLY:,.0f} DZD/month over "
        f"{labour_dz.LEGAL_MONTHLY_HOURS} legal hours."
    )

    system_prompt = (
        "You are the operations assistant inside WorkForce.dz, a shift-labour "
        "planning tool for Algerian operations. Answer the manager's question "
        "using ONLY the data below. Be concise and concrete, and cite actual "
        "dates, shifts and figures.\n\n"
        "Important context you must respect:\n"
        "- Algeria's weekend is FRIDAY and SATURDAY, not Saturday-Sunday.\n"
        "- Costs quoted are LOADED costs including CNAS employer charges.\n"
        "- The operational VOLUMES in this data are simulated for a prototype. "
        "The calendar and weather driving them are real. If the user asks how "
        "accurate or how real this is, say so plainly and do not overstate it.\n"
        "- If the data below does not answer the question, say so rather than "
        "guessing.\n"
        "- ALWAYS answer in French.\n\n"
        f"SITE: {profile.label} in {st.session_state['wilaya']}. "
        f"Demand unit: {profile.demand_unit}.\n\n"
        f"COST STRUCTURE:\n{cost_context}\n\n"
        f"FORECAST:\n{fc_summary}\n\n"
        f"ROSTER:\n{roster_summary}"
    )

    client = Groq(api_key=api_key)
    with st.chat_message("assistant"):
        with st.spinner("Réflexion…"):
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    max_tokens=700,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question},
                    ],
                )
                answer = response.choices[0].message.content
            except Exception as exc:  # noqa: BLE001
                answer = f"Erreur lors de l'appel à l'API Groq : {exc}"
            st.markdown(answer)

    st.session_state["chat_history"].append({"role": "assistant", "content": answer})

if st.session_state["chat_history"]:
    if st.button("Effacer la conversation", icon=":material/delete:"):
        st.session_state["chat_history"] = []
        st.rerun()
