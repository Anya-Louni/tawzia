"""Recruiting - describe any role, drop in any CV, let the AI judge the fit."""

import io

import streamlit as st

from core import ai, appdata, cv_screen, demand as demand_mod

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]

st.title("Recruiting")
st.caption("Describe the role in your own words, drop in any CV, and let the AI "
           "judge the fit in Algerian context: formation, service national, "
           "langues, permis, mobilite.")

use_ai = any(ai.providers_available().values())
st.caption((":material/smart_toy: AI evaluation on (" + ai.status_line() + ")") if use_ai
           else ":material/rule: No AI key yet - using the rule-based reader. "
                "Add GROQ_API_KEY (free) for the full AI verdict and tailored questions.")


def _read_upload(up) -> str:
    data = up.read()
    if up.name.lower().endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            return "\n".join((pg.extract_text() or "") for pg in reader.pages).strip()
        except Exception:
            st.warning("Could not read that PDF. Paste the text instead.")
            return ""
    return data.decode("utf-8", errors="ignore")


# --- seed defaults once ---------------------------------------------------
if "rec_job" not in st.session_state:
    st.session_state["rec_job"] = cv_screen.JOB_TEMPLATES_TEXT.get(
        profile.primary_role, next(iter(cv_screen.JOB_TEMPLATES_TEXT.values())))
if "rec_cv" not in st.session_state:
    st.session_state["rec_cv"] = cv_screen.SAMPLE_CVS["Yacine Meziane"]

left, right = st.columns(2)

with left:
    st.subheader("The role")
    tcol1, tcol2 = st.columns([2, 1])
    tmpl = tcol1.selectbox(
        "Quick-fill a template", list(cv_screen.JOB_TEMPLATES_TEXT),
        format_func=lambda k: cv_screen.JOBS[k].title if k in cv_screen.JOBS else k.title(),
        label_visibility="collapsed",
    )
    if tcol2.button("Load", icon=":material/download:", width="stretch"):
        st.session_state["rec_job"] = cv_screen.JOB_TEMPLATES_TEXT[tmpl]
        st.rerun()
    st.text_area("Job description (your own words)", key="rec_job", height=200,
                 label_visibility="collapsed",
                 placeholder="e.g. Receptionniste d'hotel, licence, arabe/francais/anglais, "
                             "accueil et reservation, disponible en shifts...")

with right:
    st.subheader("The candidate")
    up = st.file_uploader("Upload a CV (.pdf / .txt)", type=["pdf", "txt"])
    if up is not None:
        parsed = _read_upload(up)
        if parsed:
            st.session_state["rec_cv"] = parsed
    if st.button("Use a sample CV", icon=":material/description:"):
        st.session_state["rec_cv"] = cv_screen.SAMPLE_CVS["Imene Cherif"]
        st.rerun()
    st.text_area("CV text", key="rec_cv", height=224, label_visibility="collapsed")

st.divider()

if st.button("Evaluate the fit", type="primary", icon=":material/psychology:"):
    job_text = st.session_state["rec_job"].strip()
    cv_text = st.session_state["rec_cv"].strip()
    if not job_text or not cv_text:
        st.warning("Add both a job description and a CV.")
        st.stop()
    with st.spinner("Reading the CV and judging the fit..."):
        st.session_state["rec_result"] = cv_screen.evaluate_freeform(cv_text, job_text, use_ai=use_ai)

res = st.session_state.get("rec_result")
if res:
    cand = res["candidate"]
    colour = {"strong": "green", "possible": "orange", "weak": "red"}[res["verdict"]]

    with st.container(border=True):
        top = st.columns([1, 3])
        top[0].metric("Fit score", f"{res['score']}%")
        with top[1]:
            st.markdown(f"### :{colour}[{res['verdict'].upper()}]")
            if res["summary"]:
                st.write(res["summary"])
        if res["recommendation"]:
            st.success(res["recommendation"], icon=":material/recommend:")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Strengths**")
        for p in res["strengths"] or ["-"]:
            st.markdown(f":material/check_circle: {p}")
    with c2:
        st.markdown("**Gaps**")
        for g in res["gaps"] or ["-"]:
            st.markdown(f":material/error: {g}")
    with c3:
        st.markdown("**Red flags**")
        for r in res["red_flags"] or ["None"]:
            st.markdown(f":material/flag: {r}")

    if res["interview_questions"]:
        with st.container(border=True):
            st.subheader("Interview questions to ask")
            for i, q in enumerate(res["interview_questions"], 1):
                st.markdown(f"**{i}.** {q}")

    with st.expander("Extracted profile", icon=":material/badge:"):
        st.write({
            "Name": cand.name, "Wilaya": cand.wilaya, "Education": cand.education,
            "Experience (yrs)": cand.experience_years,
            "Languages": ", ".join(cand.languages) or "-",
            "Driving licence": "yes" if cand.driving_licence else "no",
            "Service national": cand.service_national,
            "Positions": "; ".join(cand.positions) or "-",
        })
    st.caption(f"Evaluation method: {res['method']}")

appdata.data_badge()
