"""
Write a job post: say what you are looking for, the post is written.

The screen takes one sentence from the manager and returns a publishable ad,
fitted to the existing team: the indicative salary is what the company pays for
the role, leave and weekly rest come from Algerian law, and if someone in house
already covers the role, it says so before the ad goes out.
"""

import streamlit as st

from core import appdata, company_data as cd, job_post as jp, skills

appdata.sidebar_controls()

wilaya = st.session_state["wilaya"]
people = cd.people()

st.markdown(
    '<div class="tz-hero"><div>'
    '<h1 class="tz-hero-h">Write a job post</h1>'
    '<div class="tz-hero-s">Say in one sentence what you are looking for. The '
    'post is written, then checked against your team: what you already pay for '
    'the role, what the law says, and who in house could hold it.'
    '</div></div></div>',
    unsafe_allow_html=True,
)

role_options = skills.role_options()

# A form, so the text and the click are sent together (a bare text_area only
# commits its value on blur).
with st.form("jp_form", border=True):
    appdata.card_head("Your request", "in your own words")

    brief = st.text_area(
        "What you are looking for", height=120, key="jp_brief",
        placeholder="e.g. I need 3 sorters for the hub, reliable and available "
                    "for shifts, on a 12-month CDD, able to work Fridays.",
        label_visibility="collapsed",
    )
    role_key = st.selectbox(
        "Role", options=list(role_options), index=None,
        format_func=lambda k: role_options[k], key="jp_role",
        placeholder="Inferred from your request, or pick the role",
        help="Used to fetch the salary you pay and the expected skills. Leave "
             "empty and it is inferred from your sentence.",
    )
    free_title = st.text_input(
        "Title to publish (optional)", key="jp_title",
        placeholder="e.g. Sorter, night team",
        help="If your title is not in the list, write it here: it is used as is.",
    )
    use_ai = st.toggle("AI writing", value=True, key="jp_ai",
                       help="Turn off to use the offline template. Either way, "
                            "salary, leave and weekly rest are calculated, not written.")

    go = st.form_submit_button("Write the post", type="primary",
                               icon=":material/edit_note:")

guessed = None
if role_key is None:
    guessed = jp.guess_role(brief, role_options)
    role_key = guessed or "sorter"

facts = jp.pool_facts(people, role_key, wilaya)

if guessed:
    st.caption(f":material/auto_awesome: Role inferred from your request: "
               f"**{role_options[guessed]}**. Change it above if that is wrong.")
elif brief.strip() and st.session_state.get("jp_role") is None:
    st.caption(f":material/help: Role not recognised in your sentence: conditions "
               f"use the scale of **{role_options.get(role_key, role_key)}**. Name "
               f"the role for an accurate indicative salary.")

if go:
    if len(brief.strip()) < 15:
        st.warning("Write one more sentence: the role, the number of people, the "
                   "contract type if you have it in mind.")
    else:
        with st.spinner("Writing the post…"):
            post = jp.draft(brief, facts, use_ai=use_ai)
            if free_title.strip():
                post.title = free_title.strip()
            st.session_state["jp_post"] = post

f1, f2, f3, f4 = st.columns(4)
with f1, st.container(border=True, height="stretch"):
    appdata.stat_card("In this role", f"{facts.headcount_role}",
                      f"{facts.headcount_total} in total", "flat", f"in {facts.wilaya}")
with f2, st.container(border=True, height="stretch"):
    appdata.stat_card("Salary paid", appdata.dzd(facts.gross_monthly, compact=True),
                      "gross / month", "flat",
                      f"loaded cost {appdata.dzd(facts.loaded_monthly, compact=True)}")
with f3, st.container(border=True, height="stretch"):
    appdata.stat_card("CDI share", f"{facts.cdi_share * 100:.0f}%",
                      f"{facts.avg_tenure_years:.1f} yrs", "flat", "average team tenure")
with f4, st.container(border=True, height="stretch"):
    appdata.stat_card("Annual leave", f"{facts.leave_days} d", None, "flat",
                      f"rest {facts.weekend}")

post = st.session_state.get("jp_post")

if post is None:
    with st.container(border=True):
        appdata.card_head("The post", "not written yet")
        st.markdown('<div class="tz-empty">Write your request above, then click '
                    '"Write the post".</div>', unsafe_allow_html=True)
else:
    # Warnings first: they can stop the publication.
    for m in [m for lvl, m in post.warnings if lvl == "bloquant"]:
        st.error(m, icon=":material/gavel:")
    for m in [m for lvl, m in post.warnings if lvl == "attention"]:
        st.warning(m, icon=":material/info:")

    left, right = st.columns([3, 2])

    with left, st.container(border=True):
        appdata.card_head(post.title, "ready to publish")
        st.markdown(post.summary)
        for head, items in (("Responsibilities", post.missions),
                            ("Profile", post.required),
                            ("Nice to have", post.nice),
                            ("Conditions", post.conditions)):
            if items:
                st.markdown(f"**{head}**")
                for m in items:
                    st.markdown(f"- {m}")
        st.caption(post.apply_line)

        st.divider()
        dl = st.columns(2)
        dl[0].download_button("Download the post (.md)", post.as_markdown().encode("utf-8"),
                              file_name=f"job-{facts.role_key}.md", mime="text/markdown",
                              width="stretch", icon=":material/download:")
        dl[1].download_button("Text version (.txt)",
                              post.as_markdown().replace("**", "").replace("# ", "").encode("utf-8"),
                              file_name=f"job-{facts.role_key}.txt", mime="text/plain",
                              width="stretch", icon=":material/content_copy:")
        st.caption(f":material/smart_toy: {post.method}. Salary, leave and weekly "
                   f"rest are calculated from the SNMG and Algerian law, not written.")

    with right:
        with st.container(border=True):
            appdata.card_head("Before you publish", "look in house")
            if facts.internal_ready or facts.internal_trainable:
                appdata.list_rows([
                    {"name": f.name,
                     "sub": f"{f.coverage}% of the role covered · {f.verdict}",
                     "meta": (f"{f.training_days} d" if f.training_days else "ready"),
                     "hot": f.verdict == "ready"}
                    for f in (facts.internal_ready + facts.internal_trainable)[:5]
                ])
                st.page_link("app_pages/skills_view.py", label="Compare train or hire",
                             icon=":material/school:")
            elif facts.headcount_role:
                st.markdown(
                    f'<div class="tz-empty">Your {facts.headcount_role} employees in '
                    f'this role already hold it: this is reinforcement, not '
                    f'internal mobility. The post uses their salary and conditions.</div>',
                    unsafe_allow_html=True)
            else:
                st.markdown('<div class="tz-empty">Nobody in house covers this role '
                            'today: external hiring is justified.</div>',
                            unsafe_allow_html=True)

        with st.container(border=True):
            appdata.card_head("Screen applicants", "against this post")
            st.caption("The post becomes screening criteria. The pool then ranks "
                       "applicants for this role, with the same thresholds as the "
                       "rest of the platform.")
            if st.button("Rank the pool against this post", icon=":material/groups_2:",
                         width="stretch"):
                st.session_state["talent_job_override"] = jp.to_screening_job(post, facts)
                st.switch_page("app_pages/talent_pool.py")

        with st.container(border=True):
            appdata.card_head("Where to publish", "real channels")
            st.caption("Sourcing lists the Algerian channels that actually exist, "
                       "their cost and the observed lead time.")
            st.page_link("app_pages/sourcing_view.py", label="Pick the channels",
                         icon=":material/travel_explore:")

st.caption(":material/info: The post is a draft: reread it before publishing. The "
           "platform guarantees consistent conditions (SNMG, leave, rest, CNAS) and "
           "flags gaps with your team; it does not replace your decision.")
appdata.data_badge()
