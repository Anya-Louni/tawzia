"""Appariement CV/poste , classez un lot de CV par embeddings locaux."""

import io

import streamlit as st

from core import ai, appdata, cv_screen, matching

appdata.sidebar_controls()

st.title("Appariement CV / poste")
st.caption(
    "Décrivez un poste, déposez plusieurs CV, et laissez les **embeddings "
    "locaux** classer les candidats par proximité au poste , sans clé, hors "
    "ligne, reproductible. Le classement combine la similarité sémantique et la "
    "grille structurée algérienne (formation, langues, permis, service national)."
)

st.caption(":material/memory: Moteur : embeddings TF-IDF (mots + n-grammes de "
           "caractères) calculés sur votre appareil. Aucune donnée candidat "
           "n'est envoyée à un service externe.")


def _read_upload(up) -> str:
    data = up.read()
    if up.name.lower().endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            return "\n".join((pg.extract_text() or "") for pg in reader.pages).strip()
        except Exception:
            return ""
    return data.decode("utf-8", errors="ignore")


# --- le poste --------------------------------------------------------------
if "match_job" not in st.session_state:
    st.session_state["match_job"] = cv_screen.JOB_TEMPLATES_TEXT["sorter"]

jc1, jc2 = st.columns([3, 1])
with jc1:
    st.text_area("Description du poste (vos propres mots)", key="match_job",
                 height=140)
with jc2:
    tmpl = st.selectbox("Modèle", list(cv_screen.JOB_TEMPLATES_TEXT),
                        format_func=lambda k: cv_screen.JOBS[k].title
                        if k in cv_screen.JOBS else k.title())
    if st.button("Charger", icon=":material/download:", width="stretch"):
        st.session_state["match_job"] = cv_screen.JOB_TEMPLATES_TEXT[tmpl]
        st.rerun()
    sim_weight = st.slider("Poids sémantique", 0.0, 1.0, 0.5, 0.1,
                           help="Part de la similarité par embeddings dans le "
                                "score global ; le reste vient de la grille "
                                "structurée.")

# --- les CV ----------------------------------------------------------------
st.subheader("Les candidats")
ups = st.file_uploader("Déposer un lot de CV (.pdf / .txt)", type=["pdf", "txt"],
                       accept_multiple_files=True)

cvs = {}
if ups:
    for up in ups:
        txt = _read_upload(up)
        if txt:
            cvs[up.name.rsplit(".", 1)[0]] = txt

use_samples = st.checkbox("Utiliser les CV exemples (démonstration)",
                          value=not cvs)
if use_samples:
    cvs = {**cv_screen.SAMPLE_CVS, **cvs}

st.caption(f"{len(cvs)} CV prêts à classer.")

st.divider()

if st.button("Classer les candidats", type="primary", icon=":material/sort:"):
    job_text = st.session_state["match_job"].strip()
    if not job_text or not cvs:
        st.warning("Ajoutez une description de poste et au moins un CV.")
        st.stop()
    with st.spinner("Calcul des embeddings et classement..."):
        job_key = matching.match_job_key(job_text)
        job = cv_screen.JOBS.get(job_key)
        ranked = matching.rank_cvs(job_text, cvs, job=job,
                                   use_ai=False, sim_weight=sim_weight)
        st.session_state["match_ranked"] = ranked
        st.session_state["match_jobkey"] = job_key
        st.session_state["match_cvs"] = cvs
        st.session_state["match_jobtext"] = job_text

ranked = st.session_state.get("match_ranked")
if ranked:
    jk = st.session_state.get("match_jobkey")
    if jk in cv_screen.JOBS:
        st.caption(f":material/auto_awesome: Grille structurée appliquée : "
                   f"**{cv_screen.JOBS[jk].title}** (détectée par embeddings).")

    top = ranked[0]
    band_colour = {"fort": "green", "possible": "orange", "faible": "red"}
    with st.container(border=True):
        cols = st.columns([1, 3])
        cols[0].metric("Meilleur candidat", f"{top.blended}%")
        with cols[1]:
            st.markdown(f"### {top.label} , "
                        f":{band_colour[top.band]}[{top.band.upper()}]")
            st.caption(f"Similarité au poste {top.similarity*100:.0f}% · "
                       f"score structuré {top.structured}% · "
                       f"termes communs : {', '.join(top.shared_terms) or '-'}")

    st.dataframe(
        matching.rank_frame(ranked), hide_index=True, width="stretch",
        column_config={
            "Score global": st.column_config.ProgressColumn(
                "Score global", min_value=0, max_value=100, format="%d%%"),
            "Similarité poste": st.column_config.NumberColumn(format="%d%%"),
            "Score structuré": st.column_config.NumberColumn(format="%d%%"),
        },
    )

    # Optional AI written verdict for the top candidate
    if any(ai.providers_available().values()):
        if st.button("Verdict IA détaillé sur le 1er candidat",
                     icon=":material/psychology:"):
            with st.spinner("Évaluation IA..."):
                res = cv_screen.evaluate_freeform(
                    st.session_state["match_cvs"][top.label],
                    st.session_state["match_jobtext"], use_ai=True)
            with st.container(border=True):
                st.markdown(f"**{top.label}** , {res['score']}% "
                            f"({res['verdict']})")
                if res["summary"]:
                    st.write(res["summary"])
                cc = st.columns(2)
                with cc[0]:
                    st.markdown("**Points forts**")
                    for p in res["strengths"] or ["-"]:
                        st.markdown(f":material/check_circle: {p}")
                with cc[1]:
                    st.markdown("**Lacunes**")
                    for g in res["gaps"] or ["-"]:
                        st.markdown(f":material/error: {g}")
                if res["interview_questions"]:
                    st.markdown("**Questions d'entretien**")
                    for i, q in enumerate(res["interview_questions"], 1):
                        st.markdown(f"{i}. {q}")
    else:
        st.caption(":material/rule: Classement par embeddings locaux (sans clé). "
                   "Ajoutez GROQ_API_KEY pour un verdict rédigé par candidat.")

appdata.data_badge()
