"""
Privacy: what the platform does with data, and what it does not.

An HR director who hands over a staff register has the right to know where the
data goes. This page answers precisely, including when the answer is awkward:
text sent to the AI layer goes to a model provider unless the local model is on.
"""

import streamlit as st

from core import ai, appdata, company_data as cd, db, deadlines_dz as dl

appdata.sidebar_controls()

st.markdown(
    '<div class="tz-hero"><div>'
    '<h1 class="tz-hero-h">Privacy and data</h1>'
    '<div class="tz-hero-s">What is processed, where, by whom, and for how long. '
    'Written to be read before you hand over a staff file.'
    '</div></div></div>',
    unsafe_allow_html=True,
)

_con = db.seed(db.connect())
with st.container(border=True):
    appdata.card_head("Trust settings", "law 25-11")
    t1, t2 = st.columns(2)
    t1.toggle("Mask personal data before any AI call", value=True,
              key="pii_redaction",
              help="Names, phone numbers, NIN, RIB and emails are replaced by tokens, "
                   "then put back in the answer.")
    t2.toggle("Local model (nothing leaves the machine)", key="llm_local",
              disabled=not ai.local_model(),
              help="An open model served by Ollama. Set TAWZIA_LOCAL_MODEL to turn "
                   "it on: this is the sovereign hosting option.")
    st.caption(f":material/smart_toy: {ai.status_line()}")
    st.caption(":material/how_to_reg: Every hire, rejection, payroll run and filing goes "
               "through a human click. No agent sends or files on its own.")

with st.expander("Action log", icon=":material/history:"):
    st.dataframe(db.recent_log(_con, 40), hide_index=True, width="stretch",
                 column_config={"at": "When", "actor": "Who", "role": "Role",
                                "action": "What", "target": "On", "why": "Why"})
    st.caption("Collection, access, change and erasure are logged, as law 25-11 "
               "expects. Sensitive fields are encrypted with AES-256-GCM.")

with st.expander("Incident register", icon=":material/report:"):
    st.caption("A data breach must be notified to the ANPDP within a short delay "
               "(5 days per the brief, to verify against the Official Journal text).")
    with st.form("incident"):
        what = st.text_area("What happened")
        if st.form_submit_button("Record the incident") and what.strip():
            db.log(_con, "hr", "hr", "incident", "ANPDP", what.strip()[:300])
            st.success("Incident recorded in the log. An ANPDP notification card "
                       "should be prepared.", icon=":material/check:")
    st.caption("Backups: encrypted, restore tested, to be documented at deployment.")


providers = ai.providers_available()
ai_on = any(providers.values())
_ai_note = ("The AI layer is active on this instance." if ai_on else
            "No AI key is configured here, so nothing leaves.")

k1, k2, k3 = st.columns(3)
with k1, st.container(border=True, height="stretch"):
    appdata.stat_card("Data in this session", cd.source_label(), None, "flat",
                      "shown on every screen, next to the figures")
with k2, st.container(border=True, height="stretch"):
    appdata.stat_card("Storage", "Encrypted", None, "flat",
                      "local SQLite, sensitive fields AES-256-GCM")
with k3, st.container(border=True, height="stretch"):
    appdata.stat_card("AI layer", "Active" if ai_on else "Inactive",
                      "Groq" if providers.get("groq") else "none",
                      "up" if ai_on else "flat",
                      "used only to write, never to calculate")

with st.container(border=True):
    appdata.card_head("What the platform processes", "and why")
    st.markdown(
        "- **Staff records**: name, staff number, role, wilaya, hire date, "
        "contract, dependants, salary. Used for leave entitlement, payroll, "
        "contributions and scheduling.\n"
        "- **Attendance**: clock-ins, lateness, absences. Used for attendance "
        "tracking and leaving-risk estimates.\n"
        "- **Requests**: leave, short absences, sick notes. Used for approvals.\n"
        "- **Uploaded CVs**: the CV text, for screening and ranking.\n\n"
        "Bank details and national ID numbers are stored encrypted and only "
        "decrypted for the payroll role. If your file holds health data, remove "
        "those columns before import: no calculation here uses them."
    )

with st.container(border=True):
    appdata.card_head("Where the data goes", "the full list")
    st.markdown(
        "**Stays on the application server:**\n"
        "- every staff record, attendance, request, payroll run, schedule and "
        "the calculations derived from them.\n\n"
        "**Goes to a third-party service:**\n"
        f"- **Text you send to the assistant, CV screening or job-post drafting** "
        f"goes to **Groq** (the language-model provider), after names and "
        f"identifiers are masked. Turn on the local model and nothing leaves. {_ai_note}\n"
        "- **Open-Meteo** receives a wilaya and a date range for weather. "
        "No personal data.\n"
        "- **World Bank** receives a country code for macro indicators. "
        "No personal data.\n"
        "- **Aladhan** receives a date to verify the Hijri calendar. "
        "No personal data.\n\n"
        "Nothing is sent to CNAS, the tax office or any agency: you file on "
        "their portals yourself."
    )
    st.info(
        "To work with no network calls at all, open the **Data** menu in the "
        "header and turn off \"Allow live API calls\". Screens keep working on "
        "the local cache; only the AI conversation becomes unavailable.",
        icon=":material/wifi_off:",
    )

with st.container(border=True):
    appdata.card_head("Retention and deletion", "your control")
    st.markdown(
        "- Imported files live **in the session**: closing the tab clears them.\n"
        "- The **\"Back to demo data\"** button on the *Company data* screen "
        "removes your file immediately.\n"
        "- Technical caches (weather, calendar, backtest) are kept on disk for "
        "speed and **hold no personal data**."
    )
    st.page_link("app_pages/company_data_view.py",
                 label="Manage or remove your data",
                 icon=":material/database:")

with st.container(border=True):
    appdata.card_head("Algerian legal framework", "to be validated by counsel")
    st.markdown(
        "Personal-data processing in Algeria is governed by **Law 18-07 of "
        "10 June 2018**, as amended by **Law 25-11**, on the protection of "
        "individuals in the processing of personal data. For an employer using "
        "this platform it means:\n"
        "- inform employees of the processing and its purpose;\n"
        "- collect only what serves that purpose;\n"
        "- allow access and correction;\n"
        "- secure access and limit retention.\n\n"
        "Social and tax filing obligations remain those of the official portals."
    )
    st.warning(
        "This page describes how the platform works technically. It is not legal "
        "advice: have your privacy policy and employee notices validated by "
        "counsel before a real deployment.",
        icon=":material/gavel:",
    )
    cols = st.columns(2)
    cols[0].link_button("CNAS portal", dl.PORTAL_CNAS_MAIN, width="stretch",
                        icon=":material/open_in_new:")
    cols[1].link_button("DGI portal", dl.PORTAL_DGI, width="stretch",
                        icon=":material/open_in_new:")

with st.container(border=True):
    appdata.card_head("What the platform never invents", "our rule")
    st.markdown(
        "Figures on screen come from the calculation engines, never from the "
        "language model: it writes, it does not calculate. Operational volumes in "
        "the demo are simulated and labelled as such on every screen; the "
        "calendar, weather, SNMG, CNAS rates and IRG scale are real and sourced."
    )
    st.page_link("app_pages/sources_view.py",
                 label="See every figure and its source",
                 icon=":material/menu_book:")

appdata.data_badge()
