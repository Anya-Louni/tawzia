"""
core/nav.py
-----------
Navigation: five screens plus Settings, one click, sub-screens below.

The problem it solves
=====================
The old bar opened a modal for every section: two clicks and a list to read
before getting anywhere. Fewer choices mean less hesitation. One click on a
space opens its first screen directly, and the other screens of that space line
up as tabs under the bar. The first space, the decision inbox, makes most of the
others optional: people go there to sign, not to search.

Page titles (French) are the internal ids of the navigation; core/i18n.py
displays them in the chosen language.
"""

from __future__ import annotations

import streamlit as st

SECTION_ICONS = {
    "Décisions": ":material/inbox:",
    "Personnel": ":material/badge:",
    "Planning": ":material/calendar_view_week:",
    "Recrutement": ":material/person_search:",
    "Paie & déclarations": ":material/receipt_long:",
    "Réglages": ":material/settings:",
}

# What each space promises, in one line, written for an HR manager.
SECTION_NOTES = {
    "Décisions": "The work is done. What is left is to sign.",
    "Personnel": "Files, attendance, skills, retention.",
    "Planning": "How many people, which day, at what cost.",
    "Recrutement": "The job post, ANEM, ranked candidates, onboarding.",
    "Paie & déclarations": "Pay right, file on time, pass an inspection.",
    "Réglages": "Your data, privacy, the assistant, tools and evidence.",
}

# One sentence per screen: what it is for, never how it is built. Shown when
# hovering the tab. Key = page id.
PAGE_NOTES = {
    "Boîte de décisions": "The agents processed today's files: your decisions are left.",
    "Guichet salarié": "Certificates, balances, payslips and leave, answered without you.",
    "Tableau de bord": "Who is in, who is missing, and the load of the days ahead.",
    "Rédiger une offre": "One sentence is enough: the post is written, pay and law included.",
    "Canaux de sourcing": "Where to publish, what each channel costs and how fast it fills.",
    "Candidats": "Every application ranked, every rank explained.",
    "Intégration": "The new hire fills their file, the agent checks it, you sign one card.",
    "Employés": "Each employee's file and remaining leave days.",
    "Demandes & présence": "Leave, absences and lateness, judged on the law and the load.",
    "Compétences & mobilité": "Who inside can already do the job, and what training would cost.",
    "Rétention": "Who may leave, and the cheapest action to keep them.",
    "Planning de la semaine": "One button: the most stable, cheapest lawful schedule.",
    "Prévision de la demande": "The expected load day by day, Ramadan, holidays and weather included.",
    "Planning & coût": "The cheapest schedule that respects Algerian labour law.",
    "Analyse sectorielle": "The indicators specific to your trade.",
    "Aéroport": "Passenger flow hour by hour, and the effect of one late flight.",
    "Paie": "Payslips, CNAS and IRG computed on the current scale.",
    "Échéances & déclarations": "What to file with CNAS and the tax office, and by when.",
    "Détection d'anomalies": "The payroll and attendance errors an inspection would find.",
    "Simulateur d'inspection": "What a labour inspector would see today.",
    "Veille Journal Officiel": "The texts that change your obligations, and what they cost.",
    "Demander à Tawzia": "Ask anything about your company: it answers with your figures.",
    "Simulateur de scénarios": "What if: the costed effect of a decision before you make it.",
    "PDF vers texte IA": "Any PDF turned into clean text and chunks an AI can read.",
    "Données de l'entreprise": "Import your file: the whole platform switches to your figures.",
    "Preuves": "Proof that the method works, misses included.",
    "Calendrier algérien": "Ramadan, the two Eids and public holidays, computed and checked.",
    "Analyse économique": "What the platform earns, line by line.",
    "Sources & hypothèses": "Every figure: where it comes from, or why it is an assumption.",
    "Confidentialité": "What the platform does with your data, and for how long.",
}


def _context_controls() -> None:
    """
    The settings that used to fill a whole side rail, in three menus.

    They live in the band because they apply to every page: the sector and the
    wilaya change the roles, the figures and the real weather the model uses.
    """
    from . import demand as demand_mod, i18n, weather_dz

    profile_labels = {k: p.label for k, p in demand_mod.PROFILES.items()}
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.35])

    with c1.popover("Activity", icon=":material/storefront:", width="stretch",
                    help=f"{profile_labels[st.session_state['profile_key']]} "
                         f"· {st.session_state['wilaya']}"):
        st.selectbox(
            "Type of activity", options=list(profile_labels),
            format_func=lambda k: profile_labels[k], key="profile_key",
        )
        st.selectbox(
            "Wilaya", options=list(weather_dz.WILAYAS), key="wilaya",
            help="Sets the real weather series the model uses.",
        )

    with c2.popover("Forecast", icon=":material/tune:", width="stretch"):
        st.slider("Forecast horizon (days)", 7, 21, key="horizon")
        st.select_slider(
            "Service level", options=[0.50, 0.75, 0.80, 0.90],
            key="service_level", format_func=lambda v: f"p{v * 100:.0f}",
            help="Staff to this demand quantile. Higher means fewer service "
                 "failures, but more paid idle time.",
        )
        st.number_input("Permanent headcount", 20, 400, key="regular_pool")
        st.number_input("Temp ceiling per shift", 0, 200, key="temp_ceiling")

    with c4:
        st.segmented_control("Language", options=list(i18n.LANGS), key="lang",
                             format_func=i18n.LANGS.get, required=True,
                             label_visibility="collapsed")

    with c3.popover("Data", icon=":material/cloud:", width="stretch"):
        st.toggle(
            "Allow live API calls", key="allow_network",
            help="Turn off to run entirely from the local cache, useful when the "
                 "venue wifi is unreliable.",
        )
        st.caption("Open-Meteo and World Bank answers are cached on the first call: "
                   "the app then works offline.")
        st.divider()
        if st.button("Replay the guided tour", icon=":material/tour:", width="stretch"):
            st.session_state["_tour_replay"] = True
            st.rerun()
        # Only shows when a password protects access.
        from . import gate
        gate.sign_out_button()


def _ask(titles: list) -> None:
    """
    "Ask Tawzia": one sentence, and the platform acts.

    Three outcomes, in this order:
      1. it asks to redo the schedule (Ramadan, "redo the schedule"): done;
      2. it names an employee and a known request (certificate, balance,
         payslip, leave): the employee desk handles it, the card goes to the
         inbox;
      3. it names a screen: that screen opens;
      4. otherwise it is a question: it goes to the assistant, already asked.

    A widget callback runs before the script, the only moment clearing the field
    is allowed.
    """
    from . import company_data as cd, i18n, self_service as svc

    ss = st.session_state
    q = (ss.get("wf_ask") or "").strip()
    ss["wf_ask"] = ""
    if not q:
        return
    plain = svc._plain(q)

    # "Ramadan starts Thursday, redo the schedule": the schedule regenerates.
    if "ramadan" in plain or (any(w in plain for w in ("planning", "schedule", "roster")) and any(
            w in plain for w in ("refai", "refais", "genere", "redo", "regenerate",
                                 "regenere", "nouveau", "new", "rebuild"))):
        ss["sched_ramadan"] = "ramadan" in plain
        ss["sched_autorun"] = True
        ss["_nav_goto"] = "Planning de la semaine"
        return

    # A named employee wins over a screen name: "payslip for Amina" is a
    # request, not the Payroll screen.
    intent = svc.classify(q)
    if intent != "autre":
        for e in cd.people():
            if svc._plain(e.name) in plain:
                n = len(ss.setdefault("guichet_tickets", [])) + 100
                r = svc.answer(q, e, company=ss.get("guichet_company", "Your company"),
                               signatory=ss.get("guichet_signatory", "The HR manager"),
                               ticket_id=f"ask{n}")
                if r["ticket"]:
                    ss["guichet_tickets"].append(r["ticket"])
                if r["request"]:
                    ss.setdefault("guichet_requests", []).append(r["request"])
                ss["_ask_toast"] = f"{e.name}: {r['reply']}"
                ss["_nav_goto"] = "Boîte de décisions"
                return

    for t in titles:
        if svc._plain(t) in plain or svc._plain(i18n.t(t)) in plain:
            ss["_nav_goto"] = t
            return

    ss.setdefault("assistant_messages", []).append({"role": "user", "content": q})
    ss["assistant_pending"] = q
    ss["_nav_goto"] = "Demander à Tawzia"


def render(pages: dict, current) -> None:
    """
    The band: logo, the Ask Tawzia bar, settings, the six spaces, then the
    screens of the open space.

    Rendered once by `dashboard.py`, before the page runs, so it shows at the
    top of the workspace.
    """
    from . import brand as brand_mod, i18n, industry
    st.session_state.setdefault("lang", i18n.DEFAULT)

    path = getattr(current, "url_path", None)
    active = next(
        (sec for sec, pgs in pages.items()
         if any(getattr(p, "url_path", None) == path for p in pgs)),
        next(iter(pages)),
    )
    current_title = getattr(current, "title", "")

    # Title -> page object, so the command bar can open the target.
    by_title = {getattr(p, "title", ""): p
                for pgs in pages.values() for p in pgs}

    # The command bar may have fired on the previous rerun: open the page here,
    # while the script runs, the only place `switch_page` is allowed.
    target = st.session_state.pop("_nav_goto", None)
    if target and target in by_title:
        st.switch_page(by_title[target])
    rtl = i18n.rtl_css()
    if rtl:
        st.markdown(rtl, unsafe_allow_html=True)
    toast = st.session_state.pop("_ask_toast", None)
    if toast:
        st.toast(toast, icon=":material/smart_toy:")

    with st.container(key="wf_topbar"):
        logo, search, controls = st.columns([1.6, 3.4, 5.0], vertical_alignment="center")
        with logo:
            # A sector edition (?industry=hotel) is announced in a short line
            # under the logo; otherwise nothing sits under the brand.
            edition = (f'<span class="tz-topsub">{industry.label()}</span>'
                       if industry.is_tailored() else "")
            st.markdown(
                f'<div class="tz-topbrand">{brand_mod.lockup(24, ink="#FFFFFF", fill=brand_mod.SKY, text_only=True)}{edition}</div>',
                unsafe_allow_html=True,
            )
        with search:
            st.text_input(
                "Ask Tawzia", key="wf_ask", on_change=_ask,
                args=(list(by_title),), icon=":material/auto_awesome:",
                placeholder=i18n.t("ask_placeholder"),
                label_visibility="collapsed",
            )
        with controls:
            # Named container: the guided tour points at it.
            with st.container(key="wf_controls"):
                _context_controls()

        # The five screens and Settings: one click opens the first sub-screen.
        with st.container(key="wf_sections"):
            cols = st.columns(len(pages), gap="small")
            for i, (col, (sec, pgs)) in enumerate(zip(cols, pages.items())):
                if not pgs:
                    continue
                with col:
                    # Stable key (the index, not a hash): the open space carries
                    # `wf_sec_active`, which the guided tour points at too.
                    wrapper = "wf_sec_active" if sec == active else f"wf_sec_{i}"
                    with st.container(key=wrapper):
                        if st.button(i18n.t(sec), key=f"nav_{sec}", width="stretch",
                                     icon=SECTION_ICONS.get(sec),
                                     help=SECTION_NOTES.get(sec)):
                            st.session_state["_nav_goto"] = getattr(pgs[0], "title", "")
                            st.rerun()

        # The open space's screens, as tabs. The current screen is not a link:
        # there is nowhere to go.
        sub = pages.get(active, [])
        if len(sub) > 1:
            with st.container(key="wf_subnav", horizontal=True, gap="small"):
                for p in sub:
                    title = getattr(p, "title", "")
                    if title == current_title:
                        st.markdown(f'<span class="tz-sub-on">{i18n.t(title)}</span>',
                                    unsafe_allow_html=True, width="content")
                    else:
                        st.page_link(p, label=i18n.t(title), icon=getattr(p, "icon", None),
                                     help=PAGE_NOTES.get(title))
