"""
Intégration , le nouvel embauché remplit son dossier, l'agent vérifie, le RH signe.

À gauche, le téléphone du nouvel embauché (le lien à usage unique). À droite, ce
que voit le RH : la vérification, puis la carte d'approbation qui part dans la
boîte de décisions. La lecture des pièces est simulée en démonstration.
"""

import datetime as dt

import streamlit as st

from core import appdata, db, labour_dz, onboarding as ob, seed_company as sc

appdata.sidebar_controls()
ss = st.session_state
con = db.seed(db.connect())

st.markdown(
    '<div class="tz-hero"><div><h1 class="tz-hero-h">Intégration</h1>'
    '<div class="tz-hero-s">Le nouvel embauché remplit son dossier depuis son '
    'téléphone. L\'agent vérifie chaque pièce et renvoie ce qui ne va pas. '
    '<b>Le RH approuve une seule carte</b>, et tout part en même temps.</div></div></div>',
    unsafe_allow_html=True,
)

with st.expander("Nouvelle embauche", expanded="ob_reg" not in ss, icon=":material/person_add:"):
    c1, c2, c3 = st.columns(3)
    name = c1.text_input("Nom", "Amina Belkacem")
    role = c2.selectbox("Poste", list(sc.STAFFING["ALG"]),
                        format_func=lambda k: labour_dz.ROLES[k].label
                        + (" · sensible" if k in sc.SENSITIVE_ROLES else ""))
    site = c3.selectbox("Site", list(sc.SITES), format_func=lambda k: sc.SITES[k]["name"])
    c4, c5, c6 = st.columns(3)
    gender = c4.selectbox("Genre", ["F", "M"])
    start = c5.date_input("Prise de poste", dt.date.today() + dt.timedelta(days=12))
    contract = c6.selectbox("Contrat", ["CDI", "CDD"])
    if st.button("Envoyer le lien d'inscription", type="primary", icon=":material/send:"):
        reg = ob.Registration(name, role, site, start, contract=contract,
                              cdd_reason="surcroit_temporaire" if contract == "CDD" else "",
                              gender=gender)
        ss["ob_reg"] = reg
        ss["ob_sent"] = False
        ss.pop("ob_template", None)
        db.log(con, "hr", "hr", "lien_inscription", name, "lien unique, 7 jours, code SMS")
        st.rerun()

reg = ss.get("ob_reg")
if reg is None:
    st.caption("L'agent attend une offre acceptée pour envoyer le lien d'inscription.")
    appdata.data_badge()
    st.stop()

phone, hr_side = st.columns([1, 1.5], gap="large")

with phone:
    with st.container(key="tz_phone", border=True):
        st.caption(f":material/smartphone: Lien sécurisé · valable {ob._C['link_valid_days']} jours")
        st.markdown(f"**Bienvenue {reg.candidate.split()[0]}**  \nVotre dossier, pièce par pièce.")
        for code in ob.checklist(reg.role_key, reg.gender):
            if code in ob._C["sensitive_extra"]:
                continue
            doc = reg.docs.get(code)
            label = ob.DOC_LABELS[code]
            if doc is None:
                if st.button(f"Photographier : {label}", key=f"up_{code}",
                             icon=":material/photo_camera:", width="stretch"):
                    # Démo : ce que l'OCR lirait sur cette pièce. La première photo
                    # du diplôme arrive floue, pour montrer le renvoi automatique.
                    if "ob_template" not in ss:
                        tpl = ob.Registration(reg.candidate, reg.role_key, reg.site,
                                              reg.start, gender=reg.gender)
                        ss["ob_template"] = ob.simulate_upload(
                            tpl, birth=dt.date(2000, 3, 4),
                            id_expiry=dt.date.today() + dt.timedelta(days=120)).docs
                    reg.docs[code] = dict(ss["ob_template"][code])
                    st.rerun()
            elif doc["status"] == "blurry":
                st.warning(f"{label} : la photo est floue.", icon=":material/blur_on:")
                if st.button("Reprendre la photo", key=f"re_{code}", width="stretch"):
                    doc["status"] = "ok"
                    st.rerun()
            else:
                st.caption(f":material/check_circle: {label}")
        st.caption("Démonstration : la lecture des pièces est simulée.")

with hr_side:
    v = ob.verify(reg)
    with st.container(border=True):
        appdata.card_head("Vérification par l'agent",
                          f"{v['documents_ok']}/{v['documents_needed']} pièces")
        for b in v["bounce"]:
            st.caption(f":material/reply: Renvoyé au salarié : {b}")
        for n in v["notes"]:
            st.caption(f":material/info: {n}")
        if v["complete"] and not ss.get("ob_sent"):
            card = ob.approval_card(reg, v)
            if st.button("Envoyer la carte au RH", type="primary", icon=":material/inbox:"):
                db.add_card(con, source="onboarding", payload={"kind": "hire"}, **card)
                ss["ob_sent"] = True
                st.rerun()
        elif ss.get("ob_sent"):
            st.success("Carte envoyée dans la boîte de décisions.", icon=":material/inbox:")
            st.page_link("app_pages/autopilot.py", label="Ouvrir la boîte de décisions",
                         icon=":material/arrow_forward:")
        else:
            st.caption("L'agent attend les pièces manquantes. Le RH n'a rien à relancer.")

    with st.container(border=True):
        appdata.card_head("Ce qui part à l'approbation", f"{len(ob.plan(reg))} tâches")
        st.dataframe(ob.plan(reg), hide_index=True, width="stretch",
                     column_config={"task": "Tâche", "owner": "Responsable", "due": "Échéance"})

appdata.data_badge()
