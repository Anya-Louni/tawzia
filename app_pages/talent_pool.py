"""
Candidates: every application ranked from best to worst fit.

The screen does one thing: get to a defensible shortlist. You see the ranking,
narrow it on what really matters for the job, and open a profile to understand
why it is there.
"""

import pandas as pd
import streamlit as st

from core import appdata, bias, brand, cv_screen, talent

appdata.sidebar_controls()

_POOL_KEY = "talent_extra_candidates"
st.session_state.setdefault(_POOL_KEY, [])

st.markdown(
    '<div class="tz-hero"><div>'
    '<h1 class="tz-hero-h">Candidates</h1>'
    '<div class="tz-hero-s">Applications ranked from best to worst fit for the job. '
    'Every ranking is explainable: you see what counts for and against each '
    'profile, and a fairness audit checks the outcome.</div></div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# The target job, then the ranking
# ---------------------------------------------------------------------------
# A post written in "Write a job post" arrives here as sorting criteria. It
# becomes an option of the selector, picked by default: it is what the manager
# just asked for.
drafted = st.session_state.get("talent_job_override")
options = list(cv_screen.JOBS)
labels = {k: cv_screen.JOBS[k].title for k in options}
if drafted is not None:
    options = ["__offre__"] + options
    labels["__offre__"] = f"Your post: {drafted.title}"

job_key = st.selectbox(
    "Job to fill", options=options,
    format_func=lambda k: labels[k], key="talent_job",
)
if job_key == "__offre__":
    job = drafted
    job_key = drafted.role_key
    st.caption(f":material/edit_note: Ranked on the post you just wrote. The "
               f"thresholds are those of the standard job "
               f"\"{cv_screen.JOBS[job_key].title}\".")
else:
    job = cv_screen.JOBS[job_key]

pool = talent.sample_pool(job_key, n=28) + list(st.session_state[_POOL_KEY])
ranked = talent.rank_pool(pool, job)
df = talent.pool_frame(ranked)

st.caption(
    f"This job needs: {job.min_education} minimum, "
    f"{job.min_experience_years:.0f} year(s) of experience, "
    f"{', '.join(cv_screen.LANG_LABEL.get(x, x) for x in job.required_languages)}"
    + (", a driving licence" if job.needs_driving_licence else "")
    + f". {talent.shortlist_note(ranked, job)}"
)

k1, k2, k3, k4 = st.columns(4)
strong = int((df["Verdict"] == talent.BANDS_FR["strong"]).sum())
possible = int((df["Verdict"] == talent.BANDS_FR["possible"]).sum())
weak = len(df) - strong - possible
with k1, st.container(border=True, height="stretch"):
    appdata.stat_card("Applications", f"{len(df)}", None, "flat",
                      f"for {job.title.lower()}")
with k2, st.container(border=True, height="stretch"):
    appdata.stat_card("Strong", f"{strong}",
                      f"{strong / max(len(df), 1) * 100:.0f}%", "up",
                      "tick what the job needs")
with k3, st.container(border=True, height="stretch"):
    appdata.stat_card("Worth a look", f"{possible}", None, "flat",
                      "one or two criteria missing")
with k4, st.container(border=True, height="stretch"):
    appdata.stat_card("Off target", f"{weak}", None, "flat",
                      "too far from the job")

audit = bias.four_fifths(ranked)
with st.expander(("Fairness audit: no gap" if audit["ok"] else
                  "Fairness audit: a gap to examine"),
                 icon=":material/balance:" if audit["ok"] else ":material/warning:"):
    st.dataframe([{"Group": r["label"], "Applications": r["candidates"],
                   "Shortlisted": r["selected"], "Rate": f"{r['rate']:.0%}",
                   "Ratio to highest": f"{r['ratio_to_top']:.0%}",
                   "Signal": ("below 80%" if r["flag"] else
                              "sample too small" if r["small_sample"] else "ok")}
                  for r in audit["rows"]], hide_index=True, width="stretch")
    st.caption(audit["rule"] + " The score reads neither name nor gender; the audit "
               "looks at the outcome. Benchmark: EEOC, New York Local Law 144.")

# ---------------------------------------------------------------------------
# The filters: everything a recruiter wants to narrow on
# ---------------------------------------------------------------------------
with st.container(border=True):
    appdata.card_head("Filter the pool", "to reach a shortlist")

    r1 = st.columns(4)
    min_score = r1[0].slider("Minimum score", 0, 100, 0, step=5,
                             key="talent_minscore")
    all_verdicts = list(talent.BANDS_FR.values())
    verdicts = r1[1].multiselect("Verdict", all_verdicts, default=all_verdicts,
                                 key="talent_verdicts")
    # Empty = all. Pre-ticking the twelve wilayas filled the filter with four
    # lines of chips.
    wilayas = sorted(df["Wilaya"].unique())
    keep_wilayas = r1[2].multiselect("Wilaya", wilayas, default=[],
                                     key="talent_wilayas",
                                     placeholder="All wilayas")
    min_years = r1[3].slider("Minimum experience (years)", 0.0,
                             float(max(df["Experience"].max(), 1)), 0.0,
                             step=0.5, key="talent_minyears")

    r2 = st.columns(4)
    levels = [k for k, _ in talent._EDUCATIONS]
    min_level = r2[0].selectbox(
        "Education at least", options=["indifférent"] + levels,
        format_func=lambda k: dict(talent._EDUCATIONS).get(k, "Any"),
        key="talent_minlevel",
    )
    need_langs = r2[1].multiselect("Must speak", cv_screen.LANGUAGES, format_func=lambda x: cv_screen.LANG_LABEL.get(x, x),
                                   key="talent_langs")
    licence_only = r2[2].toggle("Driving licence", key="talent_licence")
    sn_ok_only = r2[3].toggle("National service settled", key="talent_sn")

    search = st.text_input("Search a name", key="talent_search",
                           placeholder="e.g. Ferhat")

view = df[(df["Score"] >= min_score)
          & df["Verdict"].isin(verdicts)
          & (df["Wilaya"].isin(keep_wilayas) if keep_wilayas else True)
          & (df["Experience"] >= min_years)]

if min_level != "indifférent":
    need_rank = cv_screen.EDUCATION_RANK.get(min_level, 0)
    view = view[view["Level"].map(
        lambda k: cv_screen.EDUCATION_RANK.get(k, 0) >= need_rank)]
if need_langs:
    view = view[view["Languages"].map(
        lambda s: all(lang in s for lang in need_langs))]
if licence_only:
    view = view[view["Licence"]]
if sn_ok_only:
    view = view[view["National service"].isin(["degage", "exempte", "n/a"])]
if search.strip():
    view = view[view["Name"].str.contains(search.strip(), case=False, na=False)]

# ---------------------------------------------------------------------------
# The ranking, then the chosen candidate's profile
# ---------------------------------------------------------------------------
list_col, detail_col = st.columns([3, 2])

with list_col:
    with st.container(border=True):
        appdata.card_head("Ranking",
                          f"{len(view)} of {len(df)} applications")
        if view.empty:
            st.markdown('<div class="tz-empty">No candidate passes these '
                        'filters. Widen one criterion.</div>',
                        unsafe_allow_html=True)
        else:
            event = st.dataframe(
                view[["Rank", "Name", "Score", "Verdict", "Wilaya",
                      "Education", "Experience", "Licence"]],
                hide_index=True, width="stretch", height=430,
                on_select="rerun", selection_mode="single-row",
                key="talent_table",
                column_config={
                    "Score": st.column_config.ProgressColumn(
                        "Fit", min_value=0, max_value=100, format="%d%%"),
                    "Experience": st.column_config.NumberColumn(format="%.1f yrs"),
                    "Licence": st.column_config.CheckboxColumn(),
                },
            )
            st.download_button(
                "Export this list (CSV)",
                view.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"tawzia-candidates-{job_key}.csv", mime="text/csv",
                icon=":material/download:",
            )

with detail_col:
    with st.container(border=True):
        if view.empty:
            appdata.card_head("Profile", "no candidate")
            st.markdown('<div class="tz-empty">Select a candidate in the '
                        'ranking.</div>', unsafe_allow_html=True)
        else:
            # With no selection, show the best placed: the screen is never empty.
            rows = getattr(getattr(event, "selection", None), "rows", []) or []
            pos = rows[0] if rows else 0
            chosen_name = view.iloc[pos]["Name"]
            sc = next(s for s in ranked if s.candidate.name == chosen_name)
            c = sc.candidate

            appdata.card_head(c.name, f"{sc.score}% fit")
            st.markdown(
                f'<div class="tz-meter"><span style="width:{sc.score}%"></span></div>'
                f'<div class="tz-meter-l"><span>{c.wilaya} · {c.mobility}</span>'
                f'<span>{talent.BANDS_FR.get(sc.band, sc.band)}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            appdata.list_rows([
                {"name": c.education_raw or c.education, "sub": c.establishment,
                 "meta": "education"},
                {"name": f"{c.experience_years:.1f} years of experience",
                 "sub": ", ".join(c.positions) or "role not stated",
                 "meta": "career"},
                {"name": ", ".join(cv_screen.LANG_LABEL.get(x, x) for x in c.languages) or "not stated",
                 "sub": "declared languages", "meta": "languages"},
                {"name": "Driving licence" if c.driving_licence
                         else "No licence",
                 "sub": f"National service: {c.service_national}",
                 "meta": "admin",
                 "hot": job.needs_driving_licence and not c.driving_licence},
            ], avatars=False)

            if c.skills:
                st.markdown("**Skills found**")
                st.markdown(" · ".join(f"`{s}`" for s in c.skills))

            if sc.pluses:
                st.markdown("**What counts for**")
                for p in sc.pluses:
                    st.markdown(f":material/check: {p}")
            if sc.flags:
                st.markdown("**What counts against**")
                for f in sc.flags:
                    st.markdown(f":material/priority_high: {f}")

            with st.expander("Where the score comes from", icon=":material/calculate:"):
                st.dataframe(
                    talent.score_breakdown(sc), hide_index=True, width="stretch",
                    column_config={
                        "Achieved": st.column_config.NumberColumn(format="%d%%"),
                        "Weight": st.column_config.NumberColumn(format="%d%%"),
                        "Contribution": st.column_config.NumberColumn(format="%.1f pt"),
                    },
                )
                st.caption("\"Achieved\" is the candidate's mark on the criterion, "
                           "\"Weight\" the criterion's importance for this job, and "
                           "\"Contribution\" what it adds to the final score.")

# ---------------------------------------------------------------------------
# Add real applications to the pool
# ---------------------------------------------------------------------------
with st.container(border=True):
    appdata.card_head("Add an application", "paste the CV")
    st.caption(
        "Paste a CV's text: it is read, added to the pool and ranked with the "
        "others. The demo profiles are simulated; the ones you add are real."
    )
    cv_text = st.text_area("CV text", height=150, key="talent_cv",
                           placeholder="Name, education, experience, languages…")
    add_col = st.columns([1, 3])
    if add_col[0].button("Add to the pool", type="primary",
                         icon=":material/person_add:"):
        if len(cv_text.strip()) < 40:
            st.warning("Paste a slightly fuller CV.")
        else:
            hits = cv_screen.detect_injection(cv_text)
            cand, method = cv_screen.extract(cv_text, use_ai=True)
            st.session_state[_POOL_KEY].append(cand)
            if hits:
                st.warning(
                    "This CV contains text addressed to the screening tool "
                    "rather than the recruiter. It was ignored, but read this "
                    "file yourself.", icon=":material/report:")
            st.success(f"{cand.name or 'Candidate'} added to the pool.")
            st.rerun()
    if st.session_state[_POOL_KEY]:
        add_col[1].caption(
            f"{len(st.session_state[_POOL_KEY])} application(s) added in "
            f"this session.")
        if add_col[1].button("Remove my additions", icon=":material/delete:"):
            st.session_state[_POOL_KEY] = []
            st.rerun()

st.caption(
    ":material/info: The 28 demo profiles are simulated: no pool of Algerian CVs "
    "is public. The ranking scale is the same everywhere in the platform, so a "
    "candidate gets the same score on every screen."
)
appdata.data_badge()
