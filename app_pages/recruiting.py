"""Recruiting, AI CV screening for the Algerian CV format."""

import streamlit as st

from core import ai, appdata, cv_screen, demand as demand_mod, labour_dz

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]

st.title("Recruiting")
st.caption("Screen Algerian CVs against the role, in seconds. Formation LMD, service national, langues, permis.")

# Choose a job: default to the current site's primary role if we have a template.
job_keys = list(cv_screen.JOBS)
default_key = profile.primary_role if profile.primary_role in cv_screen.JOBS else job_keys[0]
job_key = st.selectbox(
    "Poste a pourvoir",
    job_keys,
    index=job_keys.index(default_key),
    format_func=lambda k: cv_screen.JOBS[k].title,
)
job = cv_screen.JOBS[job_key]

with st.container(border=True):
    st.markdown(
        f"**{job.title}** needs: formation **{job.min_education}+**, "
        f"**{job.min_experience_years:.0f}y** experience, langues "
        f"**{', '.join(job.required_languages)}**"
        + (", **permis**" if job.needs_driving_licence else "")
        + (", **service national** cleared" if job.needs_service_national_cleared else "")
    )

use_ai = any(ai.providers_available().values())
st.caption(
    (":material/smart_toy: AI extraction on (" + ai.status_line() + ")") if use_ai
    else ":material/rule: No AI key - using the rule-based reader. Add a key for messy CVs."
)

tab_batch, tab_one = st.tabs(["Sample shortlist", "Screen one CV"])

# ---------------------------------------------------------------------------
with tab_batch:
    st.caption("Four sample Algerian CVs, screened and ranked against the role.")
    if st.button("Screen the shortlist", type="primary", icon=":material/rule:"):
        with st.spinner("Reading CVs..."):
            ranked = cv_screen.rank(cv_screen.SAMPLE_CVS, job, use_ai=use_ai)
        for s in ranked:
            c = s.candidate
            colour = {"strong": "green", "possible": "orange", "weak": "red"}[s.band]
            with st.container(border=True):
                head = st.columns([3, 1])
                with head[0]:
                    st.markdown(f"**{c.name}** &nbsp; :{colour}[{s.band.upper()}]")
                    st.caption(f"{c.wilaya} · {c.education} · {c.experience_years:.0f}y · "
                               f"langues: {', '.join(c.languages) or '-'} · "
                               f"service national: {c.service_national}")
                with head[1]:
                    st.metric("Fit", f"{s.score}%", label_visibility="collapsed")
                if s.pluses:
                    st.markdown(" ".join(f":green-badge[{p}]" for p in s.pluses))
                if s.flags:
                    st.markdown(" ".join(f":red-badge[{f}]" for f in s.flags))

# ---------------------------------------------------------------------------
with tab_one:
    st.caption("Paste a CV (French, Algerian format) and screen it.")
    example = cv_screen.SAMPLE_CVS["Yacine Meziane"]
    cv_text = st.text_area("CV text", value=example, height=280)
    if st.button("Screen this CV", icon=":material/person_search:"):
        with st.spinner("Reading..."):
            s = cv_screen.screen(cv_text, job, use_ai=use_ai)
        c = s.candidate
        st.metric("Fit score", f"{s.score}%", s.band)
        st.markdown(
            f"**{c.name}** — {c.wilaya} — formation **{c.education}** — "
            f"**{c.experience_years:.0f}y** — service national **{c.service_national}** — "
            f"permis **{'oui' if c.driving_licence else 'non'}**"
        )
        if c.positions:
            st.caption("Postes: " + "; ".join(c.positions))
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**Points forts**")
            for p in s.pluses:
                st.markdown(f":material/check: {p}")
        with cols[1]:
            st.markdown("**A verifier**")
            for f in s.flags:
                st.markdown(f":material/flag: {f}")
        st.caption(f"Extraction: {s.method}")

appdata.data_badge()
