"""Recrutement , décrivez un poste, déposez un CV, l'IA juge l'adéquation."""

import io

import streamlit as st

from core import ai, appdata, cv_screen, demand as demand_mod

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]

st.title("Recrutement")
st.caption("Décrivez le poste avec vos propres mots, déposez n'importe quel CV, "
           "et laissez l'IA juger l'adéquation dans le contexte algérien : "
           "formation, service national, langues, permis, mobilité.")

use_ai = any(ai.providers_available().values())
st.caption((":material/smart_toy: Évaluation par IA active (" + ai.status_line() + ")") if use_ai
           else ":material/rule: Aucune clé IA pour l'instant , lecture par règles. "
                "Ajoutez GROQ_API_KEY (gratuit) pour le verdict IA complet et des "
                "questions sur mesure.")


def _read_upload(up) -> str:
    data = up.read()
    if up.name.lower().endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            return "\n".join((pg.extract_text() or "") for pg in reader.pages).strip()
        except Exception:
            st.warning("Impossible de lire ce PDF. Collez le texte à la place.")
            return ""
    return data.decode("utf-8", errors="ignore")


# --- valeurs par défaut ----------------------------------------------------
if "rec_job" not in st.session_state:
    st.session_state["rec_job"] = cv_screen.JOB_TEMPLATES_TEXT.get(
        profile.primary_role, next(iter(cv_screen.JOB_TEMPLATES_TEXT.values())))
if "rec_cv" not in st.session_state:
    st.session_state["rec_cv"] = cv_screen.SAMPLE_CVS["Yacine Meziane"]

left, right = st.columns(2)

with left:
    st.subheader("Le poste")
    tcol1, tcol2 = st.columns([2, 1])
    tmpl = tcol1.selectbox(
        "Charger un modèle", list(cv_screen.JOB_TEMPLATES_TEXT),
        format_func=lambda k: cv_screen.JOBS[k].title if k in cv_screen.JOBS else k.title(),
        label_visibility="collapsed",
    )
    if tcol2.button("Charger", icon=":material/download:", width="stretch"):
        st.session_state["rec_job"] = cv_screen.JOB_TEMPLATES_TEXT[tmpl]
        st.rerun()
    st.text_area("Description du poste (vos propres mots)", key="rec_job", height=200,
                 label_visibility="collapsed",
                 placeholder="ex. Réceptionniste d'hôtel, licence, arabe/français/anglais, "
                             "accueil et réservation, disponible en shifts...")

with right:
    st.subheader("Le candidat")
    up = st.file_uploader("Déposer un CV (.pdf / .txt)", type=["pdf", "txt"])
    if up is not None:
        parsed = _read_upload(up)
        if parsed:
            st.session_state["rec_cv"] = parsed
    if st.button("Utiliser un CV exemple", icon=":material/description:"):
        st.session_state["rec_cv"] = cv_screen.SAMPLE_CVS["Imene Cherif"]
        st.rerun()
    st.text_area("Texte du CV", key="rec_cv", height=224, label_visibility="collapsed")

st.divider()

if st.button("Évaluer l'adéquation", type="primary", icon=":material/psychology:"):
    job_text = st.session_state["rec_job"].strip()
    cv_text = st.session_state["rec_cv"].strip()
    if not job_text or not cv_text:
        st.warning("Ajoutez à la fois une description de poste et un CV.")
        st.stop()
    with st.spinner("Lecture du CV et évaluation de l'adéquation..."):
        st.session_state["rec_result"] = cv_screen.evaluate_freeform(cv_text, job_text, use_ai=use_ai)

res = st.session_state.get("rec_result")
if res:
    cand = res["candidate"]
    colour = {"strong": "green", "possible": "orange", "weak": "red"}[res["verdict"]]
    verdict_fr = {"strong": "FORT", "possible": "POSSIBLE", "weak": "FAIBLE"}[res["verdict"]]

    with st.container(border=True):
        top = st.columns([1, 3])
        top[0].metric("Score d'adéquation", f"{res['score']}%")
        with top[1]:
            st.markdown(f"### :{colour}[{verdict_fr}]")
            if res["summary"]:
                st.write(res["summary"])
        if res["recommendation"]:
            st.success(res["recommendation"], icon=":material/recommend:")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Points forts**")
        for p in res["strengths"] or ["-"]:
            st.markdown(f":material/check_circle: {p}")
    with c2:
        st.markdown("**Lacunes**")
        for g in res["gaps"] or ["-"]:
            st.markdown(f":material/error: {g}")
    with c3:
        st.markdown("**Signaux d'alerte**")
        for r in res["red_flags"] or ["Aucun"]:
            st.markdown(f":material/flag: {r}")

    if res["interview_questions"]:
        with st.container(border=True):
            st.subheader("Questions d'entretien à poser")
            for i, q in enumerate(res["interview_questions"], 1):
                st.markdown(f"**{i}.** {q}")

    with st.expander("Profil extrait", icon=":material/badge:"):
        st.write({
            "Nom": cand.name, "Wilaya": cand.wilaya, "Formation": cand.education,
            "Expérience (ans)": cand.experience_years,
            "Langues": ", ".join(cand.languages) or "-",
            "Permis de conduire": "oui" if cand.driving_licence else "non",
            "Service national": cand.service_national,
            "Postes": "; ".join(cand.positions) or "-",
        })
    st.caption(f"Méthode d'évaluation : {res['method']}")

appdata.data_badge()
