"""
Onboarding: the new hire fills their file, the agent checks it, HR signs.

On the left, the new hire's phone (the one-time link). On the right, what HR
sees: the verification, then the approval card that goes to the decision inbox.
Document reading is simulated in the demo.
"""

import datetime as dt

import streamlit as st

from core import appdata, db, labour_dz, onboarding as ob, seed_company as sc

appdata.sidebar_controls()
ss = st.session_state
con = db.seed(db.connect())

st.markdown(
    '<div class="tz-hero"><div><h1 class="tz-hero-h">Onboarding</h1>'
    '<div class="tz-hero-s">The new hire fills their file from their phone. The '
    'agent checks every document and sends back what is wrong. '
    '<b>HR approves one card</b>, and everything launches at once.</div></div></div>',
    unsafe_allow_html=True,
)

with st.expander("New hire", expanded="ob_reg" not in ss, icon=":material/person_add:"):
    c1, c2, c3 = st.columns(3)
    name = c1.text_input("Name", "Amina Belkacem")
    role = c2.selectbox("Role", list(sc.STAFFING["ALG"]),
                        format_func=lambda k: labour_dz.ROLES[k].label
                        + (" · sensitive" if k in sc.SENSITIVE_ROLES else ""))
    site = c3.selectbox("Site", list(sc.SITES), format_func=lambda k: sc.SITES[k]["name"])
    c4, c5, c6 = st.columns(3)
    gender = c4.selectbox("Gender", ["F", "M"])
    start = c5.date_input("Start date", dt.date.today() + dt.timedelta(days=12))
    contract = c6.selectbox("Contract", ["CDI", "CDD"])
    if st.button("Send the registration link", type="primary", icon=":material/send:"):
        reg = ob.Registration(name, role, site, start, contract=contract,
                              cdd_reason="surcroit_temporaire" if contract == "CDD" else "",
                              gender=gender)
        ss["ob_reg"] = reg
        ss["ob_sent"] = False
        ss.pop("ob_template", None)
        db.log(con, "hr", "hr", "registration_link", name, "one-time link, 7 days, SMS code")
        st.rerun()

reg = ss.get("ob_reg")
if reg is None:
    st.caption("The agent is waiting for an accepted offer to send the registration link.")
    appdata.data_badge()
    st.stop()

phone, hr_side = st.columns([1, 1.5], gap="large")

with phone:
    with st.container(key="tz_phone", border=True):
        st.caption(f":material/smartphone: Secure link · valid {ob._C['link_valid_days']} days")
        st.markdown(f"**Welcome {reg.candidate.split()[0]}**  \nYour file, one document at a time.")
        for code in ob.checklist(reg.role_key, reg.gender):
            if code in ob._C["sensitive_extra"]:
                continue
            doc = reg.docs.get(code)
            label = ob.DOC_LABELS[code]
            if doc is None:
                if st.button(f"Take a photo: {label}", key=f"up_{code}",
                             icon=":material/photo_camera:", width="stretch"):
                    # Demo: what OCR would read on this document. The first photo
                    # of the diploma arrives blurry, to show the automatic bounce.
                    if "ob_template" not in ss:
                        tpl = ob.Registration(reg.candidate, reg.role_key, reg.site,
                                              reg.start, gender=reg.gender)
                        ss["ob_template"] = ob.simulate_upload(
                            tpl, birth=dt.date(2000, 3, 4),
                            id_expiry=dt.date.today() + dt.timedelta(days=120)).docs
                    reg.docs[code] = dict(ss["ob_template"][code])
                    st.rerun()
            elif doc["status"] == "blurry":
                st.warning(f"{label}: the photo is blurry.", icon=":material/blur_on:")
                if st.button("Retake the photo", key=f"re_{code}", width="stretch"):
                    doc["status"] = "ok"
                    st.rerun()
            else:
                st.caption(f":material/check_circle: {label}")
        st.caption("Demo: document reading is simulated.")

with hr_side:
    v = ob.verify(reg)
    with st.container(border=True):
        appdata.card_head("Agent verification",
                          f"{v['documents_ok']}/{v['documents_needed']} documents")
        for b in v["bounce"]:
            st.caption(f":material/reply: Sent back to the new hire: {b}")
        for n in v["notes"]:
            st.caption(f":material/info: {n}")
        if v["complete"] and not ss.get("ob_sent"):
            card = ob.approval_card(reg, v)
            if st.button("Send the card to HR", type="primary", icon=":material/inbox:"):
                db.add_card(con, source="onboarding", payload={"kind": "hire"}, **card)
                ss["ob_sent"] = True
                st.rerun()
        elif ss.get("ob_sent"):
            st.success("Card sent to the decision inbox.", icon=":material/inbox:")
            st.page_link("app_pages/autopilot.py", label="Open the decision inbox",
                         icon=":material/arrow_forward:")
        else:
            st.caption("The agent is waiting for the missing documents. HR has nothing to chase.")

    with st.container(border=True):
        appdata.card_head("What launches on approval", f"{len(ob.plan(reg))} tasks")
        st.dataframe(ob.plan(reg), hide_index=True, width="stretch",
                     column_config={"task": "Task", "owner": "Owner", "due": "Due"})

appdata.data_badge()
