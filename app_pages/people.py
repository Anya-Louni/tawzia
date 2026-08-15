"""
Employés , les fiches et profils du personnel.

La page porte aussi l'ajout d'un salarié. Le formulaire arrive **prérempli** avec
ce que la plateforme sait déjà (site, activité, contrat majoritaire, date du
jour), et tout reste modifiable : remplir une fiche ne doit pas demander de
retaper ce qui est déjà connu, mais personne ne doit se voir imposer une valeur
devinée.
"""

import datetime as dt

import streamlit as st

from core import appdata, company_data as cd, demand as demand_mod, hr, labour_dz

appdata.sidebar_controls()

st.title("Employés")
st.caption("Les personnes derrière le planning, avec les droits algériens intégrés.")

people = cd.people()
today = dt.date.today()
frame = hr.workforce_frame(people, today)

south = sum(1 for e in people if e.is_southern)
avg_bal = frame["Solde acquis (j)"].mean()
avg_sen = frame["Ancienneté (ans)"].mean()

with st.container(horizontal=True):
    st.metric("Effectif", f"{len(people)}", border=True)
    st.metric("Ancienneté moyenne", f"{avg_sen:.1f} ans", border=True)
    st.metric("Solde de congés moyen", f"{avg_bal:.1f} j", border=True)
    st.metric("Sud (40 jours)", f"{south}", border=True,
              help="Les employés des wilayas sahariennes ont 40 jours de congé annuel, pas 30.")

st.caption(
    f":material/info: Source : **{cd.source_label()}**. Droits, acquisition et "
    f"ancienneté sont calculés selon le droit du travail algérien."
)

# ---------------------------------------------------------------------------
# Ajouter un salarié : prérempli, entièrement modifiable
# ---------------------------------------------------------------------------
_profile = demand_mod.PROFILES[st.session_state["profile_key"]]
_site_wilaya = st.session_state["wilaya"]
_majority_contract = ("CDI" if sum(
    1 for e in people if str(e.contract).upper() == "CDI") >= len(people) / 2
    else "CDD")
_next_id = f"E{max([int(str(e.emp_id)[1:]) for e in people if str(e.emp_id)[1:].isdigit()] or [999]) + 1}"

with st.expander("Ajouter un salarié", icon=":material/person_add:"):
    st.caption(
        f"Prérempli à partir de ce que la plateforme sait déjà : site "
        f"**{_site_wilaya}**, activité **{_profile.label}**, contrat le plus "
        f"courant dans l'équipe **{_majority_contract}**, matricule suivant "
        f"**{_next_id}**. Corrigez ce qui ne correspond pas."
    )
    with st.form("add_employee"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Nom et prénom", placeholder="ex. Amine Benali")
        emp_id = c2.text_input("Matricule", value=_next_id)
        role_labels = {k: labour_dz.ROLES[k].label for k in labour_dz.ROLES}
        role_key = c3.selectbox(
            "Poste", options=list(role_labels),
            format_func=lambda k: role_labels[k],
            index=list(role_labels).index(_profile.primary_role),
        )

        c4, c5, c6 = st.columns(3)
        wilaya_in = c4.selectbox(
            "Wilaya", options=sorted(hr.SOUTHERN_WILAYAS
                                     | {_site_wilaya, "Alger", "Oran",
                                        "Constantine", "Blida", "Annaba"}),
            index=None, placeholder=_site_wilaya,
            help="Vide = le site en cours. Une wilaya du Sud ouvre droit à 40 "
                 "jours de congé au lieu de 30.",
        )
        hire = c5.date_input("Date d'embauche", value=dt.date.today(),
                             format="DD/MM/YYYY")
        contract = c6.selectbox("Contrat", options=["CDI", "CDD"],
                                index=0 if _majority_contract == "CDI" else 1)

        c7, c8, c9 = st.columns(3)
        dependants = c7.number_input("Personnes à charge", 0, 12, 0)
        spouse = c8.toggle("Conjoint à charge")
        gross = c9.number_input(
            "Brut mensuel (DZD)", 0, 1_000_000,
            int(labour_dz.ROLES[_profile.primary_role].gross_monthly), step=1000,
            help="Prérempli au barème du poste. 0 = laisser la plateforme "
                 "appliquer le barème.")

        submitted = st.form_submit_button("Ajouter au registre", type="primary",
                                          icon=":material/save:")

    if submitted:
        if len(name.strip().split()) < 2:
            st.warning("Écrivez le nom et le prénom.")
        elif any(str(e.emp_id) == emp_id.strip() for e in people):
            st.error(f"Le matricule {emp_id} existe déjà dans le registre.")
        else:
            new = hr.Employee(
                emp_id=emp_id.strip() or _next_id,
                name=name.strip(),
                role_key=role_key,
                wilaya=wilaya_in or _site_wilaya,
                hire_date=hire,
                dependants=int(dependants),
                spouse=bool(spouse),
                contract=contract,
                leave_taken_ytd=0.0,
                gross_override=float(gross) if gross else None,
            )
            cd.set_company_data(
                list(people) + [new], cd.attendance_records(),
                label=(cd.source_label() if cd.is_uploaded()
                       else "Démonstration + fiches saisies"),
            )
            st.success(
                f"{new.name} ajouté. Droit annuel calculé : "
                f"{new.annual_entitlement()} jours ; brut "
                f"{new.monthly_gross():,.0f} DZD. Toute la plateforme en tient "
                f"compte immédiatement.")
            st.rerun()

    st.divider()
    st.caption(
        "Beaucoup de fiches à saisir ? Importez votre fichier du personnel : "
        "les colonnes sont reconnues automatiquement en français comme en "
        "anglais, et un modèle vide est téléchargeable."
    )
    st.page_link("app_pages/company_data_view.py",
                 label="Importer un fichier du personnel",
                 icon=":material/upload_file:")

col_list, col_detail = st.columns([3, 2])

with col_list:
    with st.container(border=True):
        st.subheader("Liste des employés")
        st.dataframe(
            frame, hide_index=True, width="stretch", height=460,
            column_config={
                "Brut mensuel (DZD)": st.column_config.NumberColumn(format="%d"),
                "Solde acquis (j)": st.column_config.NumberColumn(format="%.1f"),
            },
        )

with col_detail:
    with st.container(border=True):
        st.subheader("Profil")
        names = {f"{e.name} ({e.emp_id})": e for e in people}
        pick = st.selectbox("Employé", list(names), label_visibility="collapsed")
        e = names[pick]
        role = labour_dz.ROLES[e.role_key]
        st.markdown(f"### {e.name}")
        st.caption(f"{role.label} · {e.wilaya} · {e.contract}")

        st.markdown(
            f"""
| | |
|---|---|
| **Matricule** | {e.emp_id} |
| **Embauché le** | {e.hire_date:%d %b %Y} |
| **Ancienneté** | {e.seniority_years(today)} ans (prime {e.seniority_premium(today):.0%}) |
| **Droit annuel** | {e.annual_entitlement()} jours |
| **Solde acquis** | {e.accrued_leave(today):.1f} jours |
| **Personnes à charge** | {e.dependants}{' + conjoint' if e.spouse else ''} |
| **Brut mensuel** | {e.monthly_gross():,.0f} DZD |
"""
        )
        if e.is_southern:
            st.info("Wilaya du sud : 40 jours de congé annuel (30 + 10).", icon=":material/wb_sunny:")

appdata.data_badge()
