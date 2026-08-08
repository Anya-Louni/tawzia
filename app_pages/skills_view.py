"""Compétences & mobilité , l'écart de l'équipe, et qui peut déjà tenir le poste."""

import altair as alt
import streamlit as st

from core import appdata, labour_dz, skills

appdata.sidebar_controls()

st.title("Compétences & mobilité interne")
st.caption("Le poste vacant part par défaut au recrutement externe : le plus "
           "cher et le plus lent. Cette page montre d'abord qui, dans l'effectif, "
           "est déjà à deux compétences du poste.")

people = appdata.hr_people()

st.info(
    "Le référentiel de compétences par poste est un choix de modélisation "
    "explicite, et la première chose qu'un client remplace par sa propre grille. "
    "Les profils individuels de la démo sont **dérivés de l'effectif synthétique** ; "
    "en déploiement ils viennent de l'évaluation annuelle ou du fichier RH importé. "
    "La déduction est déterministe : même salarié, même profil à chaque affichage.",
    icon=":material/psychology:",
)

tab_gap, tab_mob, tab_matrix = st.tabs(
    ["Écart d'équipe", "Mobilité interne", "Matrice des compétences"])

# ---------------------------------------------------------------------------
# Écart d'équipe , le plan de formation
# ---------------------------------------------------------------------------

with tab_gap:
    gaps = skills.team_gaps(people)
    plan = skills.training_plan(people)
    behind = gaps[gaps["Écart"] > 0]

    with st.container(horizontal=True):
        st.metric("Compétences en écart", len(behind), border=True,
                  help="Compétences où l'effectif moyen est sous le niveau "
                       "requis par son propre poste.")
        st.metric("Jours de formation", plan["total_days"], border=True)
        st.metric("Coût du plan", appdata.dzd(plan["total_cost"], compact=True),
                  border=True)
        st.metric("Effectif analysé", len(people), border=True)

    col_a, col_b = st.columns([3, 2])

    with col_a:
        with st.container(border=True):
            st.subheader("Niveau requis contre niveau réel")
            if gaps.empty:
                st.caption("Aucune donnée de compétence sur cet effectif.")
            else:
                melted = gaps.head(10).melt(
                    id_vars="Compétence",
                    value_vars=["Niveau requis", "Niveau moyen"],
                    var_name="Mesure", value_name="Niveau")
                chart = (
                    alt.Chart(melted).mark_bar(cornerRadiusEnd=3).encode(
                        x=alt.X("Niveau:Q", title="Niveau (0-5)"),
                        y=alt.Y("Compétence:N", sort="-x", title=None),
                        yOffset="Mesure:N",
                        color=alt.Color("Mesure:N", title=None, scale=alt.Scale(
                            domain=["Niveau requis", "Niveau moyen"],
                            range=["#1D4ED8", "#93C5FD"])),
                        tooltip=["Compétence:N", "Mesure:N", "Niveau:Q"],
                    ).properties(height=340)
                )
                st.altair_chart(chart, width="stretch")

    with col_b:
        with st.container(border=True):
            st.subheader("Plan de formation chiffré")
            if not plan["lines"]:
                st.success("L'effectif est au niveau requis sur toutes les "
                           "compétences de son poste.", icon=":material/check_circle:")
            else:
                st.dataframe(
                    plan["lines"], hide_index=True, width="stretch",
                    column_config={
                        "Coût (DZD)": st.column_config.NumberColumn(format="%d"),
                    },
                )
                st.caption(
                    f"Hypothèses : {skills.TRAINING_DAYS_PER_LEVEL} jours par "
                    f"niveau gagné, {skills.TRAINING_COST_PER_DAY:,} DZD par jour "
                    f"et par personne (coût direct, hors salaire)."
                )

    with st.container(border=True):
        st.subheader("Détail par compétence")
        st.dataframe(
            gaps, hide_index=True, width="stretch",
            column_config={
                "Écart": st.column_config.NumberColumn(
                    "Écart", format="%.2f",
                    help="Positif = l'équipe est sous le niveau requis."),
            },
        )

# ---------------------------------------------------------------------------
# Mobilité interne
# ---------------------------------------------------------------------------

with tab_mob:
    role_opts = skills.role_options()
    c1, c2 = st.columns([2, 1])
    target = c1.selectbox(
        "Poste à pourvoir", list(role_opts),
        format_func=lambda k: role_opts[k],
        index=list(role_opts).index("supervisor") if "supervisor" in role_opts else 0,
    )
    top_n = c2.number_input("Candidats à afficher", 3, 25, 8)

    fits = skills.mobility_candidates(people, target, top=int(top_n))

    if not fits:
        st.warning("Aucun salarié à évaluer : tout l'effectif tient déjà ce poste.",
                   icon=":material/info:")
    else:
        ready = [f for f in fits if not f.blocked and f.coverage >= skills.READY_THRESHOLD]
        trainable = [f for f in fits if not f.blocked and f.coverage < skills.READY_THRESHOLD]

        with st.container(horizontal=True):
            st.metric("Prêts ou presque", len(ready), border=True,
                      help=f"Couverture ≥ {skills.READY_THRESHOLD} % des exigences du poste.")
            st.metric("Formables", len(trainable), border=True)
            st.metric("Meilleure couverture", f"{fits[0].coverage} %", border=True)
            st.metric("Formation du 1er", f"{fits[0].training_days} j", border=True)

        with st.container(border=True):
            st.subheader(f"Qui peut tenir « {role_opts[target]} »")
            mf = skills.mobility_frame(fits)
            st.dataframe(
                mf, hide_index=True, width="stretch",
                column_config={
                    "Couverture %": st.column_config.ProgressColumn(
                        "Couverture %", min_value=0, max_value=100, format="%d%%"),
                    "Coût formation (DZD)": st.column_config.NumberColumn(format="%d"),
                },
            )
            st.download_button(
                "Exporter (CSV)", mf.to_csv(index=False).encode("utf-8"),
                file_name=f"mobilite_{target}.csv", mime="text/csv",
                icon=":material/download:",
            )

        # --- former ou recruter --------------------------------------------
        st.subheader("Former en interne, ou recruter en externe")

        pick = st.selectbox(
            "Salarié à évaluer", range(len(fits)),
            format_func=lambda i: f"{fits[i].name} , couverture {fits[i].coverage} %",
        )
        f = fits[pick]
        arb = skills.reskill_vs_recruit(f, target)

        c_int, c_ext = st.columns(2)
        with c_int:
            with st.container(border=True):
                st.markdown("**Former en interne**")
                st.metric("Coût", appdata.dzd(arb["internal_cost"], compact=True))
                st.metric("Délai", f"{arb['internal_days']} j")
                st.caption(f"{f.name}, aujourd'hui {f.current_role}.")
        with c_ext:
            with st.container(border=True):
                st.markdown("**Recruter en externe**")
                st.metric("Coût", appdata.dzd(arb["external_cost"], compact=True))
                st.metric("Délai", f"{arb['external_days']} j")
                st.caption("Sourcing et sélection, plus la montée en compétence "
                           "pendant laquelle le poste est payé sans être tenu.")

        if arb["recommendation"] == "Former en interne":
            st.success(
                f"**{arb['recommendation']}** , économie de "
                f"{appdata.dzd(arb['saving'], compact=True)} et "
                f"{arb['days_saved']} jours gagnés.",
                icon=":material/recommend:",
            )
        else:
            st.warning(
                f"**{arb['recommendation']}** , la formation coûterait "
                f"{appdata.dzd(-arb['saving'], compact=True)} de plus que le "
                f"recrutement. Le moteur ne pousse pas la mobilité par principe : "
                f"quand l'écart de compétences est trop large, il le dit.",
                icon=":material/info:",
            )

        with st.container(border=True):
            st.subheader(f"Ce qui manque à {f.name}")
            if not f.missing:
                st.success("Aucune compétence manquante pour ce poste.",
                           icon=":material/check_circle:")
            for label, have, req in f.missing:
                st.markdown(f":material/arrow_right: **{label}** , niveau {have} "
                            f"sur {req} requis")
            if f.blocked:
                st.error(
                    f"Au moins une compétence manque de plus de "
                    f"{skills.MAX_TRAINABLE_GAP} niveaux : ce n'est plus une mise à "
                    f"niveau, c'est un changement de métier.",
                    icon=":material/block:",
                )

# ---------------------------------------------------------------------------
# Matrice
# ---------------------------------------------------------------------------

with tab_matrix:
    with st.container(border=True):
        st.subheader("Matrice effectif x compétences")
        st.caption("Niveaux de 0 (aucune notion) à 5 (maîtrise, peut former les autres).")
        matrix = skills.skill_matrix(people)
        st.dataframe(matrix, hide_index=True, width="stretch", height=460)
        st.download_button(
            "Exporter la matrice (CSV)", matrix.to_csv(index=False).encode("utf-8"),
            file_name="matrice_competences.csv", mime="text/csv",
            icon=":material/download:",
        )

    with st.expander("Le référentiel : ce que chaque poste exige",
                     icon=":material/menu_book:"):
        for role_key, req in skills.ROLE_SKILLS.items():
            if role_key not in labour_dz.ROLES:
                continue
            st.markdown(f"**{labour_dz.ROLES[role_key].label}**")
            st.caption(" · ".join(f"{skills.SKILLS[s]} ({lvl})"
                                  for s, lvl in sorted(req.items(), key=lambda x: -x[1])))

appdata.data_badge()
