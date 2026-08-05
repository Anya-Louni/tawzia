"""Guide , page d'accueil qui explique chaque section et chaque bouton."""

import streamlit as st

from core import appdata

appdata.sidebar_controls()

st.title("Bienvenue sur WorkForce.dz")
st.caption("La plateforme RH et de planification par l'IA, conçue pour le droit "
           "du travail algérien : recruter, planifier, payer, se conformer, fidéliser.")

st.info(
    "Ce guide explique à quoi sert chaque section. Utilisez le menu à gauche "
    "pour naviguer. Bonne visite !",
    icon=":material/waving_hand:",
)

with st.container(border=True):
    st.subheader(":material/tune: La barre latérale (à gauche)")
    st.markdown(
        "- **Type d'activité** : choisit le secteur (hôtellerie, e-commerce, "
        "transport…). Les chiffres et les rôles s'adaptent.\n"
        "- **Wilaya** : détermine la météo réelle utilisée par les prévisions.\n"
        "- **Paramètres de planification** : horizon, niveau de service, "
        "effectif permanent, plafond d'intérimaires.\n"
        "- **Source des données** : à désactiver pour travailler hors-ligne "
        "(utile si le wifi est instable)."
    )

st.subheader("Les sections du menu")

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.markdown("**:material/dashboard: Accueil**")
        st.caption("Le **Tableau de bord** : l'écran du matin. Qui travaille, la "
                   "charge prévue, le planning recommandé et son coût.")
    with st.container(border=True):
        st.markdown("**:material/person_search: Recrutement & équipe**")
        st.caption(
            "- **Recrutement** : déposez un CV (PDF ou texte), l'IA donne un "
            "verdict, les points forts/faibles et des questions d'entretien.\n"
            "- **Employés** : l'annuaire du personnel et ses droits.\n"
            "- **Demandes & présence** : congés, demandes de sortie, retards et "
            "absences."
        )
    with st.container(border=True):
        st.markdown("**:material/trending_up: Planification**")
        st.caption(
            "- **Prévision de la demande** : la charge attendue par shift.\n"
            "- **Planning & coût** : le planning le moins cher qui respecte la loi.\n"
            "- **Aéroport** (si activé) : flux passagers et cascade de retards."
        )

with col2:
    with st.container(border=True):
        st.markdown("**:material/receipt_long: Paie & conformité**")
        st.caption(
            "- **Paie** : bulletins et déclarations CNAS/IRG.\n"
            "- **Simulateur d'inspection** : passe l'inspection du travail sur "
            "vous-même, avec les articles, les amendes indicatives et les corrections.\n"
            "- **Veille Journal Officiel** : vérifie que vos paramètres sont à jour "
            "et simule l'impact d'un changement de règle."
        )
    with st.container(border=True):
        st.markdown("**:material/handshake: Fidélisation**")
        st.caption(
            "- **Risque de départ** : qui risque de partir, pourquoi, et le coût "
            "de son remplacement.\n"
            "- **Négociateur de rétention** : l'action la moins chère pour le "
            "garder, plus le script de l'entretien."
        )
    with st.container(border=True):
        st.markdown("**:material/smart_toy: Copilote IA & :material/fact_check: Preuves**")
        st.caption(
            "- **Copilote RH / Assistant** : posez vos questions en langage "
            "naturel, l'IA répond à partir de vos vrais chiffres.\n"
            "- **Preuves & business** : le backtest qui prouve la méthode, le "
            "calendrier algérien, l'analyse économique et les sources."
        )

with st.container(border=True):
    st.subheader(":material/verified_user: Notre engagement d'honnêteté")
    st.markdown(
        "Pour la démonstration, les **volumes opérationnels sont simulés** , "
        "aucun registre d'entreprise algérienne n'est public. En revanche, le "
        "**calendrier, la météo, le droit du travail et la fiscalité sont réels**. "
        "Sur un client, nous réentraînons les modèles sur ses **vraies données** "
        "et la méthode reste identique. C'est écrit sur chaque page."
    )

st.caption(":material/arrow_back: Choisissez une section dans le menu à gauche pour commencer.")
