"""Skills and mobility: the team gap, and who can already hold the role."""

import altair as alt
import streamlit as st

from core import appdata, labour_dz, skills

appdata.sidebar_controls()

st.title("Skills and internal mobility")
st.caption("A vacancy goes to external hiring by default: the most expensive "
           "and slowest option. This page first shows who on staff is already "
           "two skills away from the role.")

people = appdata.hr_people()

st.info(
    "The skills framework per role is an explicit modelling choice, and the "
    "first thing a client replaces with its own grid. Demo profiles are "
    "**derived from the synthetic workforce**; in production they come from the "
    "annual review or the imported HR file. The derivation is deterministic: "
    "same employee, same profile on every view.",
    icon=":material/psychology:",
)

tab_gap, tab_mob, tab_matrix = st.tabs(["Team gap", "Internal mobility", "Skills matrix"])

with tab_gap:
    gaps = skills.team_gaps(people)
    plan = skills.training_plan(people)
    behind = gaps[gaps["Gap"] > 0]

    with st.container(horizontal=True):
        st.metric("Skills with a gap", len(behind), border=True,
                  help="Skills where the average employee is below the level "
                       "their own role requires.")
        st.metric("Training days", plan["total_days"], border=True)
        st.metric("Plan cost", appdata.dzd(plan["total_cost"], compact=True), border=True)
        st.metric("Staff analysed", len(people), border=True)

    col_a, col_b = st.columns([3, 2])

    with col_a:
        with st.container(border=True):
            st.subheader("Required level against actual level")
            if gaps.empty:
                st.caption("No skills data for this workforce.")
            else:
                melted = gaps.head(10).melt(
                    id_vars="Skill", value_vars=["Required level", "Average level"],
                    var_name="Measure", value_name="Level")
                chart = (
                    alt.Chart(melted).mark_bar(cornerRadiusEnd=2).encode(
                        x=alt.X("Level:Q", title="Level (0-5)"),
                        y=alt.Y("Skill:N", sort="-x", title=None),
                        yOffset="Measure:N",
                        color=alt.Color("Measure:N", title=None, scale=alt.Scale(
                            domain=["Required level", "Average level"],
                            range=["#0B57A8", "#6CBEF5"])),
                        tooltip=["Skill:N", "Measure:N", "Level:Q"],
                    ).properties(height=340)
                )
                st.altair_chart(chart, width="stretch")

    with col_b:
        with st.container(border=True):
            st.subheader("Costed training plan")
            if not plan["lines"]:
                st.success("Staff are at the required level on every skill of "
                           "their role.", icon=":material/check_circle:")
            else:
                st.dataframe(plan["lines"], hide_index=True, width="stretch",
                             column_config={"Cost (DZD)": st.column_config.NumberColumn(format="%d")})
                st.caption(f"Assumptions: {skills.TRAINING_DAYS_PER_LEVEL} days per "
                           f"level gained, {skills.TRAINING_COST_PER_DAY:,} DZD per day "
                           f"per person (direct cost, salary excluded).")

    with st.container(border=True):
        st.subheader("Detail by skill")
        st.dataframe(gaps, hide_index=True, width="stretch",
                     column_config={"Gap": st.column_config.NumberColumn(
                         "Gap", format="%.2f",
                         help="Positive = the team is below the required level.")})

with tab_mob:
    role_opts = skills.role_options()
    c1, c2 = st.columns([2, 1])
    target = c1.selectbox(
        "Role to fill", list(role_opts), format_func=lambda k: role_opts[k],
        index=list(role_opts).index("supervisor") if "supervisor" in role_opts else 0,
    )
    top_n = c2.number_input("Candidates to show", 3, 25, 8)

    fits = skills.mobility_candidates(people, target, top=int(top_n))

    if not fits:
        st.warning("No one to assess: the whole workforce already holds this role.",
                   icon=":material/info:")
    else:
        ready = [f for f in fits if not f.blocked and f.coverage >= skills.READY_THRESHOLD]
        trainable = [f for f in fits if not f.blocked and f.coverage < skills.READY_THRESHOLD]

        with st.container(horizontal=True):
            st.metric("Ready or nearly", len(ready), border=True,
                      help=f"Coverage at least {skills.READY_THRESHOLD}% of the role's requirements.")
            st.metric("Trainable", len(trainable), border=True)
            st.metric("Best coverage", f"{fits[0].coverage}%", border=True)
            st.metric("Training for #1", f"{fits[0].training_days} d", border=True)

        with st.container(border=True):
            st.subheader(f"Who can hold \"{role_opts[target]}\"")
            mf = skills.mobility_frame(fits)
            st.dataframe(mf, hide_index=True, width="stretch", column_config={
                "Coverage %": st.column_config.ProgressColumn(
                    "Coverage %", min_value=0, max_value=100, format="%d%%"),
                "Training cost (DZD)": st.column_config.NumberColumn(format="%d"),
            })
            st.download_button("Export (CSV)", mf.to_csv(index=False).encode("utf-8"),
                               file_name=f"mobility_{target}.csv", mime="text/csv",
                               icon=":material/download:")

        st.subheader("Train internally, or hire externally")
        pick = st.selectbox("Employee to assess", range(len(fits)),
                            format_func=lambda i: f"{fits[i].name}, coverage {fits[i].coverage}%")
        f = fits[pick]
        arb = skills.reskill_vs_recruit(f, target)

        c_int, c_ext = st.columns(2)
        with c_int, st.container(border=True):
            st.markdown("**Train internally**")
            st.metric("Cost", appdata.dzd(arb["internal_cost"], compact=True))
            st.metric("Lead time", f"{arb['internal_days']} d")
            st.caption(f"{f.name}, currently {f.current_role}.")
        with c_ext, st.container(border=True):
            st.markdown("**Hire externally**")
            st.metric("Cost", appdata.dzd(arb["external_cost"], compact=True))
            st.metric("Lead time", f"{arb['external_days']} d")
            st.caption("Sourcing and selection, plus the ramp-up when the role is "
                       "paid but not yet held.")

        if arb["recommendation"] == "Train internally":
            st.success(f"**{arb['recommendation']}**: saves "
                       f"{appdata.dzd(arb['saving'], compact=True)} and "
                       f"{arb['days_saved']} days.", icon=":material/recommend:")
        else:
            st.warning(f"**{arb['recommendation']}**: training would cost "
                       f"{appdata.dzd(-arb['saving'], compact=True)} more than hiring. "
                       f"The engine does not push mobility on principle: when the "
                       f"skills gap is too wide, it says so.", icon=":material/info:")

        with st.container(border=True):
            st.subheader(f"What {f.name} is missing")
            if not f.missing:
                st.success("No missing skill for this role.", icon=":material/check_circle:")
            for label, have, req in f.missing:
                st.markdown(f":material/arrow_right: **{label}**: level {have} of {req} required")
            if f.blocked:
                st.error(f"At least one skill is more than {skills.MAX_TRAINABLE_GAP} "
                         f"levels short: this is a change of trade, not upskilling.",
                         icon=":material/block:")

with tab_matrix:
    with st.container(border=True):
        st.subheader("Staff x skills matrix")
        st.caption("Levels from 0 (none) to 5 (mastery, can train others).")
        matrix = skills.skill_matrix(people)
        st.dataframe(matrix, hide_index=True, width="stretch", height=460)
        st.download_button("Export the matrix (CSV)", matrix.to_csv(index=False).encode("utf-8"),
                           file_name="skills_matrix.csv", mime="text/csv",
                           icon=":material/download:")

    with st.expander("The framework: what each role requires", icon=":material/menu_book:"):
        for role_key, req in skills.ROLE_SKILLS.items():
            if role_key not in labour_dz.ROLES:
                continue
            st.markdown(f"**{labour_dz.ROLES[role_key].label}**")
            st.caption(" · ".join(f"{skills.SKILLS[s]} ({lvl})"
                                  for s, lvl in sorted(req.items(), key=lambda x: -x[1])))

appdata.data_badge()
