"""Accueil , la page d'entrée qui présente la plateforme et ses sections."""

import streamlit as st

from core import appdata

appdata.sidebar_controls()

st.title("WorkForce.dz")
st.caption("La plateforme RH et de planification par l'IA, conçue pour toute "
           "entreprise algérienne : recruter, planifier, payer, se conformer, "
           "décider , sur le vrai calendrier et le droit du travail algériens.")

st.markdown(":violet-badge[:material/verified: Droit du travail algérien] "
            ":blue-badge[:material/bolt: IA locale + langage naturel] "
            ":green-badge[:material/domain: Tous secteurs]")

# --- quick orientation -----------------------------------------------------
with st.container(border=True):
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Par où commencer")
        st.markdown(
            "1. **Importez vos données** dans *Décision IA › Données de "
            "l'entreprise* , tout le reste apprend alors de vos vrais chiffres.\n"
            "2. Ouvrez le **Tableau de bord** pour la charge prévue et le planning.\n"
            "3. Explorez les **KPI**, la **détection d'anomalies** et le "
            "**copilote décisionnel** pour piloter."
        )
    with right:
        st.subheader("La barre latérale")
        st.caption(
            "**Type d'activité** adapte les rôles et les chiffres à votre "
            "secteur. **Wilaya** fixe la météo réelle utilisée. **Source des "
            "données** permet de travailler hors-ligne."
        )

st.subheader("Les sections")

_SECTIONS = [
    (":material/home:", "Accueil",
     "Le **tableau de bord** du matin : charge prévue par shift, planning "
     "recommandé et son coût chargé."),
    (":material/person_search:", "Recrutement",
     "**Évaluation de CV** (verdict IA, points forts/faibles, questions "
     "d'entretien) et **appariement CV/poste** par embeddings locaux qui "
     "classe un lot de candidats."),
    (":material/badge:", "Équipe & présence",
     "**Employés** et leurs droits, **demandes & présence** (congés, sorties, "
     "retards), **risque de départ** chiffré et **négociateur de rétention**."),
    (":material/trending_up:", "Planification",
     "**Prévision de la demande** par shift et **planning & coût** : le "
     "roster le moins cher qui respecte la loi."),
    (":material/receipt_long:", "Paie & conformité",
     "**Paie** et déclarations CNAS/IRG, **détection d'anomalies** paie & "
     "présence, **simulateur d'inspection** et **veille Journal Officiel**."),
    (":material/neurology:", "Décision IA",
     "**KPI**, **simulateur de scénarios**, les **copilotes** (décisionnel, "
     "RH, opérations) et l'**import des données** de l'entreprise. La couche "
     "qui apprend de votre base."),
    (":material/fact_check:", "Preuves & sources",
     "Le **backtest** qui prouve la méthode, le **calendrier algérien**, "
     "l'**analyse économique** et toutes les **sources & hypothèses**."),
]

cols = st.columns(2)
for i, (icon, title, body) in enumerate(_SECTIONS):
    with cols[i % 2]:
        with st.container(border=True):
            st.markdown(f"#### {icon} {title}")
            st.markdown(body)

# --- honesty commitment ----------------------------------------------------
with st.container(border=True):
    st.subheader(":material/verified_user: Notre engagement d'honnêteté")
    st.markdown(
        "Le **calendrier, la météo, le droit du travail et la fiscalité "
        "sont réels**. Pour la démonstration, les **volumes opérationnels "
        "sont simulés** , aucun registre d'entreprise algérienne n'est public. "
        "Dès que vous importez votre fichier, chaque page bascule sur vos "
        "**vraies données** et la méthode reste identique. La source est "
        "affichée sur chaque page."
    )

st.caption(":material/arrow_back: Choisissez une section dans le menu à gauche "
           "pour commencer.")
