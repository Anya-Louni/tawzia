"""Sourcing and employer brand: where candidates come from, and at what cost."""

import altair as alt
import streamlit as st

from core import ai, appdata, demand as demand_mod, labour_dz, sourcing

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]

st.title("Sourcing channels")
st.caption("The rest of the suite handles a candidate once they have applied. "
           "This page answers the question before all the others: where do "
           "candidates come from, through which channel, at what cost and how fast.")

options = [k for k in labour_dz.ROLES if k in sourcing.ROLE_FAMILY]
default_role = profile.primary_role if profile.primary_role in options else options[0]

with st.container(border=True):
    st.subheader("The need to cover")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    role_key = c1.selectbox("Role to fill", options, index=options.index(default_role),
                            format_func=lambda k: labour_dz.ROLES[k].label)
    headcount = c2.number_input("People to hire", 1, 500, 25)
    urgency = c3.number_input("Target lead time (d)", 7, 180, 45)
    budget = c4.number_input("Budget per channel (DZD)", 0, 500_000, 60_000, step=5_000)

    family = sourcing.ROLE_FAMILY[role_key]
    st.caption(f":material/category: Job family: **{sourcing.FAMILIES[family]}** · "
               f"Site: **{wilaya}** ({sourcing.REGION_LABEL[sourcing.region_of(wilaya)]})")

ranked = sourcing.rank_channels(role_key, wilaya, headcount, urgency_days=urgency,
                                budget_dzd=budget or None)
plan = sourcing.build_plan(ranked, headcount)

st.info(
    "The channel directory is real: universities, national schools, the "
    "CFPA/INSFP network, ANEM and existing, verifiable Algerian job sites. "
    "**Volumes, costs and lead times are framing assumptions**: no Algerian "
    "operator publishes cost per hire. A pilot replaces them with the client's "
    "real figures after the first measured campaign.",
    icon=":material/fact_check:",
)

with st.container(horizontal=True):
    st.metric("Channels picked", len(plan["channels"]), border=True)
    st.metric("Need covered", f"{plan['coverage_pct']}%", border=True,
              help="Expected hires against the stated need.")
    st.metric("Plan cost", appdata.dzd(plan["total_cost"], compact=True), border=True)
    st.metric("Cost per hire",
              appdata.dzd(plan["cost_per_hire"], compact=True) if plan["cost_per_hire"] else "-",
              border=True)
    st.metric("Lead time", f"{plan['lead_days']} d", border=True,
              help="The slowest channel in the plan sets the lead time.")

if plan["gap"] > 0:
    st.warning(f"The available channels only cover {plan['coverage_pct']}% of the "
               f"need: about **{plan['gap']:.0f} hires** are missing. Widen the "
               f"wilaya, extend the lead time, or raise the budget per channel.",
               icon=":material/warning:")

left, right = st.columns([3, 2])

with left, st.container(border=True):
    st.subheader("Channel ranking")
    df = sourcing.rank_frame(ranked)
    st.dataframe(df, hide_index=True, width="stretch", height=430, column_config={
        "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
        "Campaign cost (DZD)": st.column_config.NumberColumn(format="%d"),
        "Cost per hire (DZD)": st.column_config.NumberColumn(format="%d"),
    })
    st.download_button("Export the ranking (CSV)", df.to_csv(index=False).encode("utf-8"),
                       file_name=f"sourcing_{role_key}_{wilaya}.csv", mime="text/csv",
                       icon=":material/download:")

with right:
    with st.container(border=True):
        st.subheader("Cost per hire")
        top = sourcing.rank_frame(ranked).head(8)
        top = top[top["Cost per hire (DZD)"] > 0]
        if top.empty:
            st.caption("No paid channel in the ranking.")
        else:
            chart = alt.Chart(top).mark_bar(cornerRadiusEnd=2, color="#0B57A8").encode(
                x=alt.X("Cost per hire (DZD):Q", title="DZD per hire"),
                y=alt.Y("Channel:N", sort="x", title=None),
                tooltip=["Channel:N", "Cost per hire (DZD):Q", "Lead time (d):Q"],
            ).properties(height=260)
            st.altair_chart(chart, width="stretch")

    with st.container(border=True):
        st.subheader("The chosen plan")
        if not plan["channels"]:
            st.caption("No channel converts for this need.")
        for s in plan["channels"]:
            st.markdown(f"**{s.channel.name}**")
            st.caption(f"{s.expected_hires:.1f} expected hires · "
                       f"{appdata.dzd(s.channel.cost_dzd, compact=True)} · "
                       f"{s.channel.lead_days} d")

with st.expander("Why these channels and not others", icon=":material/help:"):
    for s in ranked[:8]:
        st.markdown(f"**{s.channel.name}**, score {s.score}")
        if s.channel.note:
            st.caption(s.channel.note)
        for r in s.reasons:
            st.markdown(f":material/arrow_right: {r}")
        if s.channel.url:
            st.markdown(f"[{s.channel.url}]({s.channel.url})")
        st.divider()

st.subheader("Partners and relays to activate")
st.caption("Profiles to look for and verifiable criteria, not a list of names. A "
           "language model that \"finds influencers\" invents plausible, false "
           "names. Verification stays human.")

partners = sourcing.partner_profiles_for(role_key)
cols = st.columns(min(len(partners), 3) or 1)
for i, p in enumerate(partners):
    with cols[i % len(cols)], st.container(border=True):
        st.markdown(f"**{p.label}**")
        st.caption(f":material/travel_explore: {p.where}")
        st.markdown("**Criteria**")
        for c in p.criteria:
            st.markdown(f":material/check_circle: {c}")
        st.markdown("**What we ask**")
        st.markdown(p.ask)

st.subheader("Outreach message")
use_ai = any(ai.providers_available().values())
st.caption((":material/smart_toy: AI writing on (" + ai.status_line() + ")") if use_ai else
           ":material/rule: No AI key: deterministic template. Add GROQ_API_KEY for "
           "a tailored message.")

c1, c2 = st.columns([2, 1])
channel_keys = [s.channel.key for s in ranked[:12]]
pick = c1.selectbox("Channel to contact", channel_keys,
                    format_func=lambda k: sourcing.CHANNELS[k].name) if channel_keys else None
company = c2.text_input("Company name", "Your company")

if pick and st.button("Write the message", type="primary", icon=":material/edit_note:"):
    with st.spinner("Writing…"):
        st.session_state["sourcing_msg"] = sourcing.draft_outreach(
            sourcing.CHANNELS[pick], role_key, company, int(headcount), wilaya,
            use_ai=use_ai)

msg = st.session_state.get("sourcing_msg")
if msg:
    with st.container(border=True):
        st.text_area("Message", msg["text"], height=300, label_visibility="collapsed")
        st.caption(f"Writing method: {msg['method']}")

appdata.data_badge()
