"""
Vivier de candidats , toutes les candidatures classées du plus au moins adapté.

L'écran sert à une seule chose : arriver à une liste courte défendable. On voit
le classement, on restreint sur ce qui compte vraiment pour le poste, et on ouvre
un profil pour comprendre pourquoi il est là.
"""

import pandas as pd
import streamlit as st

from core import appdata, bias, brand, cv_screen, talent

appdata.sidebar_controls()

_POOL_KEY = "talent_extra_candidates"
st.session_state.setdefault(_POOL_KEY, [])

st.markdown(
    '<div class="tz-hero"><div>'
    '<h1 class="tz-hero-h">Vivier de candidats</h1>'
    '<div class="tz-hero-s">Les candidatures classées du plus au moins adapté '
    'au poste. Chaque classement est explicable : on voit ce qui joue pour et '
    'contre chaque profil.</div></div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Le poste visé, puis le classement
# ---------------------------------------------------------------------------
# Une offre rédigée dans « Rédiger une offre » arrive ici sous forme de critères
# de tri. Elle devient une option du sélecteur, choisie d'office : c'est ce que
# le responsable vient de demander.
drafted = st.session_state.get("talent_job_override")
options = list(cv_screen.JOBS)
labels = {k: cv_screen.JOBS[k].title for k in options}
if drafted is not None:
    options = ["__offre__"] + options
    labels["__offre__"] = f"Votre offre : {drafted.title}"

job_key = st.selectbox(
    "Poste à pourvoir", options=options,
    format_func=lambda k: labels[k], key="talent_job",
)
if job_key == "__offre__":
    job = drafted
    job_key = drafted.role_key
    st.caption(f":material/edit_note: Classement sur l'offre que vous venez de "
               f"rédiger. Les seuils sont ceux du poste type "
               f"« {cv_screen.JOBS[job_key].title} ».")
else:
    job = cv_screen.JOBS[job_key]

pool = talent.sample_pool(job_key, n=28) + list(st.session_state[_POOL_KEY])
ranked = talent.rank_pool(pool, job)
df = talent.pool_frame(ranked)

st.caption(
    f"Ce poste demande : {job.min_education} minimum, "
    f"{job.min_experience_years:.0f} an(s) d'expérience, "
    f"{', '.join(job.required_languages)}"
    + (", permis de conduire" if job.needs_driving_licence else "")
    + f". {talent.shortlist_note(ranked, job)}"
)

k1, k2, k3, k4 = st.columns(4)
strong = int((df["Verdict"] == talent.BANDS_FR["strong"]).sum())
possible = int((df["Verdict"] == talent.BANDS_FR["possible"]).sum())
weak = len(df) - strong - possible
with k1, st.container(border=True, height="stretch"):
    appdata.stat_card("Candidatures", f"{len(df)}", None, "flat",
                      f"pour {job.title.lower()}")
with k2, st.container(border=True, height="stretch"):
    appdata.stat_card("Dossiers solides", f"{strong}",
                      f"{strong / max(len(df), 1) * 100:.0f}%", "up",
                      "cochent l'essentiel du poste")
with k3, st.container(border=True, height="stretch"):
    appdata.stat_card("À voir", f"{possible}", None, "flat",
                      "il manque un ou deux critères")
with k4, st.container(border=True, height="stretch"):
    appdata.stat_card("Hors cible", f"{weak}", None, "flat",
                      "trop loin du poste demandé")

audit = bias.four_fifths(ranked)
with st.expander(("Audit d'équité : aucun écart" if audit["ok"] else
                  "Audit d'équité : un écart à examiner"),
                 icon=":material/balance:" if audit["ok"] else ":material/warning:"):
    st.dataframe([{"Groupe": r["label"], "Candidatures": r["candidates"],
                   "Retenues": r["selected"], "Taux": f"{r['rate']:.0%}",
                   "Rapport au plus haut": f"{r['ratio_to_top']:.0%}",
                   "Signal": ("sous 80 %" if r["flag"] else
                              "échantillon trop petit" if r["small_sample"] else "ok")}
                  for r in audit["rows"]], hide_index=True, width="stretch")
    st.caption(audit["rule"] + " Le score ne lit ni le nom ni le genre ; l'audit "
               "regarde le résultat. Référence : EEOC, loi locale 144 de New York.")

# ---------------------------------------------------------------------------
# Les filtres : tout ce sur quoi un recruteur veut restreindre
# ---------------------------------------------------------------------------
with st.container(border=True):
    appdata.card_head("Filtrer le vivier", "pour arriver à une liste courte")

    r1 = st.columns(4)
    min_score = r1[0].slider("Score minimum", 0, 100, 0, step=5,
                             key="talent_minscore")
    all_verdicts = list(talent.BANDS_FR.values())
    verdicts = r1[1].multiselect("Verdict", all_verdicts, default=all_verdicts,
                                 key="talent_verdicts")
    # Vide = toutes. Pré-cocher les douze wilayas remplissait le filtre de
    # pastilles sur quatre lignes, et la molette restait prise dedans.
    wilayas = sorted(df["Wilaya"].unique())
    keep_wilayas = r1[2].multiselect("Wilaya", wilayas, default=[],
                                     key="talent_wilayas",
                                     placeholder="Toutes les wilayas")
    min_years = r1[3].slider("Expérience minimum (années)", 0.0,
                             float(max(df["Expérience"].max(), 1)), 0.0,
                             step=0.5, key="talent_minyears")

    r2 = st.columns(4)
    levels = [k for k, _ in talent._EDUCATIONS]
    min_level = r2[0].selectbox(
        "Formation au moins", options=["indifférent"] + levels,
        format_func=lambda k: dict(talent._EDUCATIONS).get(k, "Indifférent"),
        key="talent_minlevel",
    )
    need_langs = r2[1].multiselect("Doit parler", cv_screen.LANGUAGES,
                                   key="talent_langs")
    licence_only = r2[2].toggle("Permis de conduire", key="talent_licence")
    sn_ok_only = r2[3].toggle("Service national réglé", key="talent_sn")

    search = st.text_input("Rechercher un nom", key="talent_search",
                           placeholder="ex. Ferhat")

view = df[(df["Score"] >= min_score)
          & df["Verdict"].isin(verdicts)
          & (df["Wilaya"].isin(keep_wilayas) if keep_wilayas else True)
          & (df["Expérience"] >= min_years)]

if min_level != "indifférent":
    need_rank = cv_screen.EDUCATION_RANK.get(min_level, 0)
    view = view[view["Niveau"].map(
        lambda k: cv_screen.EDUCATION_RANK.get(k, 0) >= need_rank)]
if need_langs:
    view = view[view["Langues"].map(
        lambda s: all(lang in s for lang in need_langs))]
if licence_only:
    view = view[view["Permis"]]
if sn_ok_only:
    view = view[view["Service national"].isin(["degage", "exempte", "n/a"])]
if search.strip():
    view = view[view["Nom"].str.contains(search.strip(), case=False, na=False)]

# ---------------------------------------------------------------------------
# Le classement, puis le profil du candidat choisi
# ---------------------------------------------------------------------------
list_col, detail_col = st.columns([3, 2])

with list_col:
    with st.container(border=True):
        appdata.card_head("Classement",
                          f"{len(view)} sur {len(df)} candidatures")
        if view.empty:
            st.markdown('<div class="tz-empty">Aucun candidat ne passe ces '
                        'filtres. Élargissez un critère.</div>',
                        unsafe_allow_html=True)
        else:
            event = st.dataframe(
                view[["Rang", "Nom", "Score", "Verdict", "Wilaya",
                      "Formation", "Expérience", "Permis"]],
                hide_index=True, width="stretch", height=430,
                on_select="rerun", selection_mode="single-row",
                key="talent_table",
                column_config={
                    "Score": st.column_config.ProgressColumn(
                        "Adéquation", min_value=0, max_value=100, format="%d%%"),
                    "Expérience": st.column_config.NumberColumn(format="%.1f ans"),
                    "Permis": st.column_config.CheckboxColumn(),
                },
            )
            st.download_button(
                "Exporter cette liste (CSV)",
                view.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"tawzia-vivier-{job_key}.csv", mime="text/csv",
                icon=":material/download:",
            )

with detail_col:
    with st.container(border=True):
        if view.empty:
            appdata.card_head("Profil", "aucun candidat")
            st.markdown('<div class="tz-empty">Sélectionnez un candidat dans '
                        'le classement.</div>', unsafe_allow_html=True)
        else:
            # Sans sélection, on montre le mieux placé : l'écran n'est jamais vide.
            rows = getattr(getattr(event, "selection", None), "rows", []) or []
            pos = rows[0] if rows else 0
            chosen_name = view.iloc[pos]["Nom"]
            sc = next(s for s in ranked if s.candidate.name == chosen_name)
            c = sc.candidate

            appdata.card_head(c.name, f"{sc.score}% d'adéquation")
            st.markdown(
                f'<div class="tz-meter"><span style="width:{sc.score}%"></span></div>'
                f'<div class="tz-meter-l"><span>{c.wilaya} · {c.mobility}</span>'
                f'<span>{talent.BANDS_FR.get(sc.band, sc.band)}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            appdata.list_rows([
                {"name": c.education_raw or c.education, "sub": c.establishment,
                 "meta": "formation"},
                {"name": f"{c.experience_years:.1f} ans d'expérience",
                 "sub": ", ".join(c.positions) or "poste non précisé",
                 "meta": "parcours"},
                {"name": ", ".join(c.languages) or "non précisé",
                 "sub": "langues déclarées", "meta": "langues"},
                {"name": "Permis de conduire" if c.driving_licence
                         else "Pas de permis",
                 "sub": f"Service national : {c.service_national}",
                 "meta": "administratif",
                 "hot": job.needs_driving_licence and not c.driving_licence},
            ], avatars=False)

            if c.skills:
                st.markdown("**Compétences repérées**")
                st.markdown(" · ".join(f"`{s}`" for s in c.skills))

            if sc.pluses:
                st.markdown("**Ce qui joue pour**")
                for p in sc.pluses:
                    st.markdown(f":material/check: {p}")
            if sc.flags:
                st.markdown("**Ce qui joue contre**")
                for f in sc.flags:
                    st.markdown(f":material/priority_high: {f}")

            with st.expander("D'où vient le score", icon=":material/calculate:"):
                st.dataframe(
                    talent.score_breakdown(sc), hide_index=True, width="stretch",
                    column_config={
                        "Atteint": st.column_config.NumberColumn(format="%d%%"),
                        "Poids": st.column_config.NumberColumn(format="%d%%"),
                        "Apport": st.column_config.NumberColumn(format="%.1f pt"),
                    },
                )
                st.caption("« Atteint » est la note du candidat sur le critère, "
                           "« Poids » l'importance du critère pour ce poste, et "
                           "« Apport » ce que cela donne dans le score final.")

# ---------------------------------------------------------------------------
# Ajouter de vraies candidatures au vivier
# ---------------------------------------------------------------------------
with st.container(border=True):
    appdata.card_head("Ajouter une candidature", "collez le CV")
    st.caption(
        "Collez le texte d'un CV : il est lu, ajouté au vivier et classé avec "
        "les autres. Les profils de démonstration sont simulés ; ceux que vous "
        "ajoutez sont les vrais."
    )
    cv_text = st.text_area("Texte du CV", height=150, key="talent_cv",
                           placeholder="Nom, formation, expérience, langues…")
    add_col = st.columns([1, 3])
    if add_col[0].button("Ajouter au vivier", type="primary",
                         icon=":material/person_add:"):
        if len(cv_text.strip()) < 40:
            st.warning("Collez un CV un peu plus complet.")
        else:
            hits = cv_screen.detect_injection(cv_text)
            cand, method = cv_screen.extract(cv_text, use_ai=True)
            st.session_state[_POOL_KEY].append(cand)
            if hits:
                st.warning(
                    "Ce CV contient du texte qui s'adresse à l'outil de tri "
                    "plutôt qu'au recruteur. Il a été ignoré, mais lisez ce "
                    "dossier vous-même.", icon=":material/report:")
            st.success(f"{cand.name or 'Candidat'} ajouté au vivier.")
            st.rerun()
    if st.session_state[_POOL_KEY]:
        add_col[1].caption(
            f"{len(st.session_state[_POOL_KEY])} candidature(s) ajoutée(s) à "
            f"cette session.")
        if add_col[1].button("Retirer mes ajouts", icon=":material/delete:"):
            st.session_state[_POOL_KEY] = []
            st.rerun()

st.caption(
    ":material/info: Les 28 profils du vivier de démonstration sont simulés : "
    "aucun vivier de CV algériens n'est public. Le barème de classement, lui, "
    "est le même que celui de l'évaluation de CV, donc un candidat obtient le "
    "même score partout dans la plateforme."
)
appdata.data_badge()
