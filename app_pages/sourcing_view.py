"""Sourcing & marque employeur , d'où viennent les candidats, et à quel coût."""

import altair as alt
import streamlit as st

from core import ai, appdata, demand as demand_mod, labour_dz, sourcing

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]

st.title("Sourcing & marque employeur")
st.caption("Le reste de la suite traite le candidat une fois qu'il a postulé. "
           "Cette page répond à la question posée avant toutes les autres : "
           "d'où viennent les candidats, par quel canal, à quel coût et en "
           "combien de temps.")

# --- le besoin -------------------------------------------------------------

role_labels = sourcing.ROLE_FAMILY
options = [k for k in labour_dz.ROLES if k in role_labels]
default_role = profile.primary_role if profile.primary_role in options else options[0]

with st.container(border=True):
    st.subheader("Le besoin à couvrir")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    role_key = c1.selectbox(
        "Poste à pourvoir", options,
        index=options.index(default_role),
        format_func=lambda k: labour_dz.ROLES[k].label,
    )
    headcount = c2.number_input("Personnes à recruter", 1, 500, 25)
    urgency = c3.number_input("Délai souhaité (j)", 7, 180, 45)
    budget = c4.number_input("Budget par canal (DZD)", 0, 500_000, 60_000, step=5_000)

    family = sourcing.ROLE_FAMILY[role_key]
    st.caption(f":material/category: Famille de métiers : **{sourcing.FAMILIES[family]}** · "
               f"Site : **{wilaya}** ({sourcing.region_of(wilaya)})")

ranked = sourcing.rank_channels(role_key, wilaya, headcount,
                                urgency_days=urgency,
                                budget_dzd=budget or None)
plan = sourcing.build_plan(ranked, headcount)

st.info(
    "Le répertoire de canaux est réel : universités, écoles nationales, réseau "
    "CFPA/INSFP, ANEM et sites d'emploi algériens existants et vérifiables. "
    "**Les volumes, coûts et délais sont des hypothèses de cadrage** , aucun "
    "opérateur algérien ne publie son coût par embauche. Un pilote les remplace "
    "par les chiffres réels du client dès la première campagne mesurée.",
    icon=":material/fact_check:",
)

# --- le plan ---------------------------------------------------------------

with st.container(horizontal=True):
    st.metric("Canaux retenus", len(plan["channels"]), border=True)
    st.metric("Couverture du besoin", f"{plan['coverage_pct']} %", border=True,
              help="Embauches attendues rapportées au besoin exprimé.")
    st.metric("Coût du plan", appdata.dzd(plan["total_cost"], compact=True), border=True)
    st.metric("Coût par embauche",
              appdata.dzd(plan["cost_per_hire"], compact=True) if plan["cost_per_hire"] else "-",
              border=True)
    st.metric("Délai", f"{plan['lead_days']} j", border=True,
              help="Le canal le plus lent du plan détermine le délai.")

if plan["gap"] > 0:
    st.warning(
        f"Les canaux disponibles ne couvrent que {plan['coverage_pct']} % du "
        f"besoin : il manque environ **{plan['gap']:.0f} embauches**. Élargir la "
        f"wilaya, allonger le délai, ou relever le budget par canal.",
        icon=":material/warning:",
    )

left, right = st.columns([3, 2])

with left:
    with st.container(border=True):
        st.subheader("Classement des canaux")
        df = sourcing.rank_frame(ranked)
        st.dataframe(
            df, hide_index=True, width="stretch", height=430,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=100, format="%d"),
                "Coût campagne (DZD)": st.column_config.NumberColumn(format="%d"),
                "Coût par embauche (DZD)": st.column_config.NumberColumn(format="%d"),
            },
        )
        st.download_button(
            "Exporter le classement (CSV)", df.to_csv(index=False).encode("utf-8"),
            file_name=f"sourcing_{role_key}_{wilaya}.csv", mime="text/csv",
            icon=":material/download:",
        )

with right:
    with st.container(border=True):
        st.subheader("Coût par embauche")
        top = sourcing.rank_frame(ranked).head(8)
        top = top[top["Coût par embauche (DZD)"] > 0]
        if top.empty:
            st.caption("Aucun canal payant dans le classement.")
        else:
            chart = (
                alt.Chart(top).mark_bar(cornerRadiusEnd=4).encode(
                    x=alt.X("Coût par embauche (DZD):Q", title="DZD par embauche"),
                    y=alt.Y("Canal:N", sort="x", title=None),
                    tooltip=["Canal:N", "Coût par embauche (DZD):Q", "Délai (j):Q"],
                ).properties(height=260)
            )
            st.altair_chart(chart, width="stretch")

    with st.container(border=True):
        st.subheader("Le plan retenu")
        if not plan["channels"]:
            st.caption("Aucun canal ne convertit sur ce besoin.")
        for s in plan["channels"]:
            st.markdown(f"**{s.channel.name}**")
            st.caption(f"{s.expected_hires:.1f} embauches attendues · "
                       f"{appdata.dzd(s.channel.cost_dzd, compact=True)} · "
                       f"{s.channel.lead_days} j")

# --- pourquoi ce classement ------------------------------------------------

with st.expander("Pourquoi ces canaux, et pas les autres", icon=":material/help:"):
    for s in ranked[:8]:
        st.markdown(f"**{s.channel.name}** , score {s.score}")
        if s.channel.note:
            st.caption(s.channel.note)
        for r in s.reasons:
            st.markdown(f":material/arrow_right: {r}")
        if s.channel.url:
            st.markdown(f"[{s.channel.url}]({s.channel.url})")
        st.divider()

# --- partenaires -----------------------------------------------------------

st.subheader("Partenaires et relais à activer")
st.caption("Des profils à rechercher et des critères vérifiables, pas une liste "
           "de noms. Un modèle de langage qui « trouve des influenceurs » invente "
           "des noms plausibles et faux : c'est le pire résultat possible face à "
           "quelqu'un qui connaît son écosystème. La vérification reste humaine.")

partners = sourcing.partner_profiles_for(role_key)
cols = st.columns(min(len(partners), 3) or 1)
for i, p in enumerate(partners):
    with cols[i % len(cols)]:
        with st.container(border=True):
            st.markdown(f"**{p.label}**")
            st.caption(f":material/travel_explore: {p.where}")
            st.markdown("**Critères**")
            for c in p.criteria:
                st.markdown(f":material/check_circle: {c}")
            st.markdown("**Ce qu'on demande**")
            st.markdown(p.ask)

# --- prise de contact ------------------------------------------------------

st.subheader("Message de prise de contact")

use_ai = any(ai.providers_available().values())
st.caption((":material/smart_toy: Rédaction par IA active (" + ai.status_line() + ")")
           if use_ai else
           ":material/rule: Aucune clé IA , modèle de message déterministe. "
           "Ajoutez GROQ_API_KEY pour une rédaction sur mesure.")

c1, c2 = st.columns([2, 1])
channel_keys = [s.channel.key for s in ranked[:12]]
pick = c1.selectbox(
    "Canal à contacter", channel_keys,
    format_func=lambda k: sourcing.CHANNELS[k].name,
) if channel_keys else None
company = c2.text_input("Nom de l'entreprise", "Votre entreprise")

if pick and st.button("Rédiger le message", type="primary", icon=":material/edit_note:"):
    with st.spinner("Rédaction…"):
        st.session_state["sourcing_msg"] = sourcing.draft_outreach(
            sourcing.CHANNELS[pick], role_key, company, int(headcount), wilaya,
            use_ai=use_ai,
        )

msg = st.session_state.get("sourcing_msg")
if msg:
    with st.container(border=True):
        st.text_area("Message", msg["text"], height=300, label_visibility="collapsed")
        st.caption(f"Méthode de rédaction : {msg['method']}")

appdata.data_badge()
