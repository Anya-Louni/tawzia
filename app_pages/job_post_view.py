"""
Rédiger une offre , dites ce que vous cherchez, l'offre est écrite.

L'écran prend une phrase du responsable et rend une annonce publiable. Il la cale
sur l'équipe qui existe déjà : le salaire indicatif est celui que l'entreprise
pratique sur ce poste, les congés et le repos hebdomadaire viennent du droit
algérien, et si quelqu'un en interne couvre déjà le poste, il le dit avant que
l'annonce ne parte.
"""

import streamlit as st

from core import (appdata, company_data as cd, job_post as jp, labour_dz,
                  skills)

appdata.sidebar_controls()

wilaya = st.session_state["wilaya"]
people = cd.people()

st.markdown(
    '<div class="tz-hero"><div>'
    '<h1 class="tz-hero-h">Rédiger une offre</h1>'
    '<div class="tz-hero-s">Dites en une phrase ce que vous cherchez. L\'offre '
    'est rédigée, puis confrontée à votre équipe : ce que vous payez déjà sur ce '
    'poste, ce que dit la loi, et qui en interne pourrait le tenir.'
    '</div></div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Ce que le responsable demande
# ---------------------------------------------------------------------------
role_options = skills.role_options()

# Un formulaire, et non des widgets libres : hors formulaire, `st.text_area` ne
# transmet sa valeur qu'au moment où il perd le focus, si bien qu'un utilisateur
# qui écrit puis clique aussitôt sur le bouton envoie une demande vide et reçoit
# « écrivez une phrase de plus » alors qu'il vient d'en écrire une. Dans un
# formulaire, le texte et le clic partent ensemble.
with st.form("jp_form", border=True):
    appdata.card_head("Votre demande", "en vos mots")

    brief = st.text_area(
        "Ce que vous cherchez", height=120, key="jp_brief",
        placeholder="ex. Il me faut 3 agents de tri pour le hub, sérieux et "
                    "disponibles en shifts, en CDD de 12 mois, capables de "
                    "travailler le vendredi.",
        label_visibility="collapsed",
    )

    # Rien n'est présélectionné : le poste n'est pas deviné à la place du
    # responsable. Laissé vide, il est déduit de ce qu'il a écrit, et le titre
    # libre permet un intitulé que le référentiel ne connaît pas.
    role_key = st.selectbox(
        "Poste concerné", options=list(role_options), index=None,
        format_func=lambda k: role_options[k], key="jp_role",
        placeholder="Déduit de votre demande, ou choisissez le poste",
        help="Sert à récupérer le salaire pratiqué et les compétences "
             "attendues. Laissez vide et il sera déduit de votre phrase.",
    )
    free_title = st.text_input(
        "Intitulé à publier (facultatif)", key="jp_title",
        placeholder="ex. Agent de tri , équipe de nuit",
        help="Si votre intitulé ne figure pas dans la liste, écrivez-le ici : "
             "il est repris tel quel dans l'annonce.",
    )
    use_ai = st.toggle("Rédaction par IA", value=True, key="jp_ai",
                       help="Décochez pour utiliser le gabarit hors ligne. "
                            "Dans les deux cas, salaire, congés et repos "
                            "hebdomadaire sont calculés et non rédigés.")

    go = st.form_submit_button("Rédiger l'offre", type="primary",
                               icon=":material/edit_note:")

# Poste non choisi : on le devine à partir des mots du responsable, et on le dit.
guessed = None
if role_key is None:
    guessed = jp.guess_role(brief, role_options)
    role_key = guessed or "sorter"

facts = jp.pool_facts(people, role_key, wilaya)

if guessed:
    st.caption(f":material/auto_awesome: Poste déduit de votre demande : "
               f"**{role_options[guessed]}**. Changez-le ci-dessus si ce n'est "
               f"pas celui-là.")
elif brief.strip() and st.session_state.get("jp_role") is None:
    st.caption(":material/help: Poste non reconnu dans votre phrase : "
               f"les conditions reprennent le barème de "
               f"**{role_options.get(role_key, role_key)}**. Précisez le poste "
               f"pour un salaire indicatif juste.")

if go:
    if len(brief.strip()) < 15:
        st.warning("Écrivez une phrase de plus : le poste, le nombre de "
                   "personnes, le type de contrat si vous l'avez en tête.")
    else:
        with st.spinner("Rédaction de l'offre…"):
            post = jp.draft(brief, facts, use_ai=use_ai)
            if free_title.strip():
                post.title = free_title.strip()
            st.session_state["jp_post"] = post

# ---------------------------------------------------------------------------
# Ce que dit l'équipe en place : les faits qui cadrent l'offre
# ---------------------------------------------------------------------------
f1, f2, f3, f4 = st.columns(4)
with f1, st.container(border=True, height="stretch"):
    appdata.stat_card("Sur ce poste", f"{facts.headcount_role}",
                      f"{facts.headcount_total} au total", "flat",
                      f"à {facts.wilaya}")
with f2, st.container(border=True, height="stretch"):
    appdata.stat_card("Salaire pratiqué",
                      appdata.dzd(facts.gross_monthly, compact=True),
                      "brut / mois", "flat",
                      f"coût chargé {appdata.dzd(facts.loaded_monthly, compact=True)}")
with f3, st.container(border=True, height="stretch"):
    appdata.stat_card("Part de CDI", f"{facts.cdi_share * 100:.0f}%",
                      f"{facts.avg_tenure_years:.1f} ans", "flat",
                      "ancienneté moyenne de l'équipe")
with f4, st.container(border=True, height="stretch"):
    appdata.stat_card("Congé annuel", f"{facts.leave_days} j", None, "flat",
                      f"repos {facts.weekend}")

post = st.session_state.get("jp_post")

if post is None:
    with st.container(border=True):
        appdata.card_head("L'offre", "pas encore rédigée")
        st.markdown(
            '<div class="tz-empty">Écrivez votre demande ci-dessus, puis '
            'cliquez sur « Rédiger l\'offre ».</div>',
            unsafe_allow_html=True,
        )
else:
    # --- Les alertes d'abord : elles peuvent annuler la publication ---------
    blocking = [m for lvl, m in post.warnings if lvl == "bloquant"]
    attention = [m for lvl, m in post.warnings if lvl == "attention"]

    for m in blocking:
        st.error(m, icon=":material/gavel:")
    for m in attention:
        st.warning(m, icon=":material/info:")

    left, right = st.columns([3, 2])

    with left:
        with st.container(border=True):
            appdata.card_head(post.title, "prêt à publier")
            st.markdown(post.summary)

            if post.missions:
                st.markdown("**Missions**")
                for m in post.missions:
                    st.markdown(f"- {m}")
            if post.required:
                st.markdown("**Profil recherché**")
                for m in post.required:
                    st.markdown(f"- {m}")
            if post.nice:
                st.markdown("**Atouts appréciés**")
                for m in post.nice:
                    st.markdown(f"- {m}")

            st.markdown("**Conditions**")
            for m in post.conditions:
                st.markdown(f"- {m}")
            st.caption(post.apply_line)

            st.divider()
            dl = st.columns(2)
            dl[0].download_button(
                "Télécharger l'offre (.md)",
                post.as_markdown().encode("utf-8"),
                file_name=f"offre-{facts.role_key}.md", mime="text/markdown",
                width="stretch", icon=":material/download:",
            )
            dl[1].download_button(
                "Version texte (.txt)",
                post.as_markdown().replace("**", "").replace("# ", "")
                    .encode("utf-8"),
                file_name=f"offre-{facts.role_key}.txt", mime="text/plain",
                width="stretch", icon=":material/content_copy:",
            )
            st.caption(f":material/smart_toy: {post.method}. Le salaire, les "
                       f"congés et le repos hebdomadaire sont calculés à partir "
                       f"du SNMG et du droit algérien, pas rédigés.")

    with right:
        with st.container(border=True):
            appdata.card_head("Avant de publier", "regardez en interne")
            if facts.internal_ready or facts.internal_trainable:
                appdata.list_rows([
                    {"name": f.name,
                     "sub": f"{f.coverage}% du poste couvert · {f.verdict}",
                     "meta": (f"{f.training_days} j" if f.training_days
                              else "prêt"),
                     "hot": f.verdict == "prêt"}
                    for f in (facts.internal_ready + facts.internal_trainable)[:5]
                ])
                st.page_link("app_pages/skills_view.py",
                             label="Comparer former ou recruter",
                             icon=":material/school:")
            elif facts.headcount_role:
                # La mobilité interne compare des postes différents. Si toute
                # l'équipe tient déjà ce poste, il n'y a rien à comparer : la
                # demande est un renfort, pas une reconversion.
                st.markdown(
                    f'<div class="tz-empty">Vos {facts.headcount_role} salariés '
                    f'sur ce poste le tiennent déjà : il s\'agit d\'un renfort, '
                    f'pas d\'une mobilité interne. L\'offre reprend le salaire '
                    f'et les conditions qu\'ils ont.</div>',
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div class="tz-empty">Personne en interne ne couvre ce '
                    'poste aujourd\'hui : le recrutement externe est justifié.'
                    '</div>', unsafe_allow_html=True)

        with st.container(border=True):
            appdata.card_head("Trier les candidatures", "sur cette offre")
            st.caption(
                "L'offre est convertie en critères de tri. Le vivier classe "
                "alors les candidatures sur ce poste, avec les mêmes seuils que "
                "le reste de la plateforme."
            )
            if st.button("Classer le vivier sur cette offre",
                         icon=":material/groups_2:", width="stretch"):
                st.session_state["talent_job_override"] = jp.to_screening_job(
                    post, facts)
                st.switch_page("app_pages/talent_pool.py")

        with st.container(border=True):
            appdata.card_head("Où la publier", "canaux réels")
            st.caption(
                "Le sourcing liste les canaux algériens qui existent vraiment, "
                "leur coût et le délai constaté."
            )
            st.page_link("app_pages/sourcing_view.py",
                         label="Choisir les canaux",
                         icon=":material/travel_explore:")

st.caption(
    ":material/info: L'annonce est un brouillon : relisez-la avant publication. "
    "La plateforme garantit la cohérence des conditions (SNMG, congés, repos, "
    "CNAS) et signale les écarts avec votre équipe, elle ne se substitue pas à "
    "votre décision."
)
appdata.data_badge()
