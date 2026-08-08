"""
core/nav.py
-----------
La navigation : sept grands titres, et un sélecteur qui assombrit le reste.

Le problème que ça règle
========================
Vingt-six pages ne tiennent pas dans une barre. Une barre qui les comprime
cache le produit : un visiteur qui ne voit pas les fonctionnalités croit
qu'elles n'existent pas, et sur une démonstration commerciale c'est le seul
défaut qui coûte vraiment de l'argent.

Donc : les **sept sections restent visibles en permanence**, en grand. Cliquer
sur l'une d'elles ouvre un sélecteur modal qui **assombrit le reste de l'écran**
(`st.dialog` le fait nativement) pour qu'il ne reste qu'une décision à prendre :
quelle fonctionnalité ouvrir. Chaque entrée porte une phrase qui dit ce qu'elle
rapporte, pas ce qu'elle fait techniquement , c'est là que se vend le produit.

Le sélecteur est refermé en retirant le drapeau de session dès qu'il est rendu :
sans cela, la fermeture par l'utilisateur déclenche un rerun qui le rouvrirait
aussitôt.
"""

from __future__ import annotations

import streamlit as st

SECTION_ICONS = {
    "Accueil": ":material/home:",
    "Recrutement": ":material/person_search:",
    "Équipe & présence": ":material/badge:",
    "Planification": ":material/trending_up:",
    "Paie & conformité": ":material/receipt_long:",
    "Décision IA": ":material/neurology:",
    "Preuves & sources": ":material/fact_check:",
}

# Ce que chaque section promet, en une ligne.
SECTION_NOTES = {
    "Accueil": "Où en est l'activité aujourd'hui.",
    "Recrutement": "Faire venir les bons candidats, puis les trier.",
    "Équipe & présence": "Vos gens : droits, présence, compétences, départs.",
    "Planification": "Combien de personnes, quel jour, à quel coût.",
    "Paie & conformité": "Payer juste, et tenir devant un contrôle.",
    "Décision IA": "Poser une question, obtenir une décision chiffrée.",
    "Preuves & sources": "De quoi répondre à « prouvez-le ».",
}

# Une phrase par page, orientée bénéfice. Clé = titre de la page (unique).
PAGE_NOTES = {
    "Accueil": "Le tour d'horizon de la plateforme et par où commencer.",
    "Tableau de bord": "La charge prévue, le planning recommandé et son coût, en une vue.",

    "Sourcing & marque employeur":
        "Par quels canaux algériens réels faire venir des candidats, à quel coût "
        "et en combien de temps.",
    "Évaluation de CV":
        "Déposez un CV : verdict d'adéquation, points forts, lacunes et questions "
        "d'entretien.",
    "Appariement CV/poste":
        "Classez un lot de candidats face à une offre, sans clé IA et hors ligne.",

    "Employés": "Le registre du personnel et les droits à congé calculés par la loi.",
    "Demandes & présence":
        "Congés, absences et retards, arbitrés avec la charge prévue de la semaine.",
    "Compétences & mobilité":
        "Qui, dans l'effectif, peut déjà tenir le poste à pourvoir , et ce que "
        "coûterait de l'y former plutôt que de recruter.",
    "Risque de départ":
        "Qui risque de partir dans les six mois, pourquoi, et ce que coûte son "
        "remplacement.",
    "Négociateur de rétention":
        "Ce qu'il faut proposer pour garder un salarié, chiffré contre le coût de "
        "son départ.",

    "Prévision de la demande":
        "La charge des prochains jours, calendrier algérien et météo réelle compris.",
    "Planning & coût":
        "Le planning le moins cher qui respecte le droit du travail algérien.",
    "Analyse sectorielle":
        "Les indicateurs propres à votre activité, pas ceux d'un modèle importé.",
    "Aéroport":
        "Flux passagers et cascades de retard sur le réseau réel d'Alger.",

    "Paie": "Bulletins, CNAS et IRG calculés sur le barème algérien en vigueur.",
    "Détection d'anomalies":
        "Les écarts de paie et de présence qu'un contrôle relèverait avant vous.",
    "Contrôle de documents":
        "Un modèle entraîné lit les montants d'un bulletin, et la plateforme "
        "les confronte au SNMG et au taux CNAS.",
    "Simulateur d'inspection":
        "Ce que verrait un inspecteur du travail s'il passait aujourd'hui.",
    "Veille Journal Officiel":
        "Les textes parus qui changent vos obligations.",

    "Tableau de KPI": "Les indicateurs qui décident, suivis dans le temps.",
    "Simulateur de scénarios":
        "« Et si » : volume, effectif, salaires , l'effet chiffré avant de trancher.",
    "Copilote décisionnel":
        "Posez la question en français, obtenez la décision et son raisonnement.",
    "Copilote RH": "Les questions RH et de droit du travail, répondues en clair.",
    "Assistant opérations": "L'assistant qui lit vos données et répond en langage naturel.",
    "Données de l'entreprise":
        "Importez votre fichier : toute la plateforme bascule sur vos vrais chiffres.",

    "Preuves": "Le backtest hors échantillon qui prouve la méthode, pertes comprises.",
    "Calendrier algérien":
        "Ramadan, les deux Aïd et les fériés, calculés et vérifiés.",
    "Analyse économique": "Ce que la plateforme rapporte, poste par poste.",
    "Sources & hypothèses":
        "Chaque chiffre : sa source réelle, ou son statut d'hypothèse.",
}

_OPEN_KEY = "_nav_open_section"


def _context_controls() -> None:
    """
    Les réglages qui valaient autrefois un rail latéral entier, en trois menus.

    Ils vivent dans le bandeau parce qu'ils s'appliquent à toutes les pages :
    le secteur et la wilaya changent les rôles, les chiffres et la météo réelle
    utilisée par le modèle.
    """
    from . import demand as demand_mod, weather_dz

    profile_labels = {k: p.label for k, p in demand_mod.PROFILES.items()}
    c1, c2, c3 = st.columns(3)

    with c1.popover("Activité", icon=":material/storefront:", width="stretch",
                    help=f"{profile_labels[st.session_state['profile_key']]} "
                         f"· {st.session_state['wilaya']}"):
        st.selectbox(
            "Type d'activité", options=list(profile_labels),
            format_func=lambda k: profile_labels[k], key="profile_key",
        )
        st.selectbox(
            "Wilaya", options=list(weather_dz.WILAYAS), key="wilaya",
            help="Détermine la série météo réelle utilisée par le modèle.",
        )

    with c2.popover("Réglages", icon=":material/tune:", width="stretch"):
        st.slider("Horizon de prévision (jours)", 7, 21, key="horizon")
        st.select_slider(
            "Niveau de service", options=[0.50, 0.75, 0.80, 0.90],
            key="service_level", format_func=lambda v: f"p{v * 100:.0f}",
            help="Dimensionner à ce quantile de demande. Plus élevé = moins de "
                 "ruptures de service, mais plus de temps payé inactif.",
        )
        st.number_input("Effectif permanent", 20, 400, key="regular_pool")
        st.number_input("Plafond d'intérimaires par shift", 0, 200,
                        key="temp_ceiling")

    with c3.popover("Données", icon=":material/cloud:", width="stretch"):
        st.toggle(
            "Autoriser les appels API en direct", key="allow_network",
            help="Désactiver pour fonctionner entièrement depuis le cache "
                 "local , utile si le wifi du lieu est instable.",
        )
        st.caption("Les réponses d'Open-Meteo et de la Banque mondiale sont "
                   "mises en cache au premier appel : l'app fonctionne ensuite "
                   "hors-ligne.")
        st.divider()
        if st.button("Revoir la visite guidée", icon=":material/tour:",
                     width="stretch"):
            st.session_state["_tour_replay"] = True
            st.rerun()


@st.dialog("Choisir une fonctionnalité", width="large")
def _section_picker(section: str, section_pages: list) -> None:
    """Le sélecteur modal , le reste de l'écran s'assombrit tout seul."""
    st.caption(SECTION_NOTES.get(section, ""))

    for page in section_pages:
        title = getattr(page, "title", "")
        with st.container(border=True):
            st.markdown(f"**{title}**")
            note = PAGE_NOTES.get(title)
            if note:
                st.caption(note)
            if st.button("Ouvrir", key=f"pick_{title}", width="stretch",
                         type="primary", icon=":material/arrow_forward:"):
                st.switch_page(page)


def render(pages: dict, current) -> None:
    """
    Le bandeau : la marque, puis les sept sections en grand.

    Rendu une fois par `dashboard.py`, avant l'exécution de la page, donc il
    apparaît en haut de l'espace de travail.
    """
    from . import industry

    path = getattr(current, "url_path", None)
    active = next(
        (sec for sec, pgs in pages.items()
         if any(getattr(p, "url_path", None) == path for p in pgs)),
        next(iter(pages)),
    )
    current_title = getattr(current, "title", "")

    with st.container(key="wf_topbar"):
        brand, crumb, controls = st.columns([2.6, 4.4, 3],
                                            vertical_alignment="center")
        with brand:
            st.markdown('<div class="wf-brand-light">WorkForce.dz</div>',
                        unsafe_allow_html=True)
        with crumb:
            edition = (industry.label() if industry.is_tailored()
                       else "Plateforme RH par l'IA, conçue pour l'Algérie")
            st.markdown(
                f'<div class="wf-crumb">{active}'
                f'<span class="wf-crumb-sep">/</span>'
                f'<strong>{current_title}</strong>'
                f'<span class="wf-crumb-ed">{edition}</span></div>',
                unsafe_allow_html=True,
            )
        with controls:
            # Conteneur nommé : la visite guidée vise ce sélecteur.
            with st.container(key="wf_controls"):
                _context_controls()

        # Les sept sections, largeur égale : cliquer ouvre le sélecteur.
        with st.container(key="wf_sections"):
            cols = st.columns(len(pages), gap="small")
            for i, (col, (sec, pgs)) in enumerate(zip(cols, pages.items())):
                if not pgs:
                    continue
                with col:
                    # Clé stable (l'index, pas un hash) : la section ouverte
                    # porte `wf_sec_active`, que la visite guidée vise aussi.
                    wrapper = "wf_sec_active" if sec == active else f"wf_sec_{i}"
                    with st.container(key=wrapper):
                        if st.button(sec, key=f"nav_{sec}", width="stretch",
                                     icon=SECTION_ICONS.get(sec),
                                     help=SECTION_NOTES.get(sec)):
                            st.session_state[_OPEN_KEY] = sec
                            st.rerun()

    # Retiré dès l'ouverture : sinon une fermeture manuelle rouvrirait le
    # sélecteur au rerun suivant.
    opened = st.session_state.pop(_OPEN_KEY, None)
    if opened and opened in pages:
        _section_picker(opened, pages[opened])
