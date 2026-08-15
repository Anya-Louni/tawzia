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

# Ce que chaque section promet, en une ligne. Écrit pour un responsable RH :
# pas de vocabulaire technique, pas de nom de modèle, pas de méthode. Ce qui
# compte est la décision que l'écran permet de prendre.
SECTION_NOTES = {
    "Accueil": "Où en est l'activité aujourd'hui.",
    "Recrutement": "Faire venir les bons candidats, puis les trier.",
    "Équipe & présence": "Vos gens : droits, présence, compétences, départs.",
    "Planification": "Combien de personnes, quel jour, à quel coût.",
    "Paie & conformité": "Payer juste, et tenir devant un contrôle.",
    "Décision IA": "Poser une question, obtenir une réponse chiffrée.",
    "Preuves & sources": "De quoi répondre à « prouvez-le ».",
}

# Une phrase par écran, en français simple. Règle : la phrase dit à quoi sert
# l'écran et ce qu'on en retire, jamais comment il est fabriqué. Clé = titre de
# la page (unique).
PAGE_NOTES = {
    "Accueil": "Le tour d'horizon de la plateforme et par où commencer.",
    "Tableau de bord":
        "Votre matinée en un écran : qui est là, qui manque, quelles demandes "
        "attendent une réponse, et la charge des jours qui viennent.",

    "Rédiger une offre":
        "Dites en une phrase ce que vous cherchez : l'annonce est écrite, avec "
        "le salaire que vous pratiquez déjà et les conditions légales. Elle vous "
        "dit aussi qui, en interne, pourrait tenir le poste.",
    "Sourcing & marque employeur":
        "Où passer votre annonce pour recevoir de vraies candidatures, ce que "
        "chaque canal coûte et en combien de temps il remplit un poste.",
    "Évaluation de CV":
        "Déposez un CV : ce qui colle avec le poste, ce qui manque, et les "
        "questions à poser en entretien.",
    "Vivier de candidats":
        "Toutes vos candidatures classées du mieux au moins adapté au poste, "
        "avec de quoi filtrer et ouvrir chaque profil.",
    "Appariement CV/poste":
        "Vous avez reçu vingt CV pour une offre : ils sont classés du plus au "
        "moins adapté, avec la raison du classement.",

    "Employés": "Le dossier de chaque salarié et ses jours de congé restants.",
    "Demandes & présence":
        "Congés, absences et retards. Chaque demande reçoit une réponse tenant "
        "compte de la loi et de la charge de la semaine.",
    "Compétences & mobilité":
        "Qui, dans votre équipe, peut déjà tenir le poste à pourvoir, et ce que "
        "coûterait de le former plutôt que de recruter.",
    "Risque de départ":
        "Qui risque de partir dans les six mois, pourquoi, et ce que son "
        "remplacement vous coûterait.",
    "Négociateur de rétention":
        "Ce qu'il faut proposer pour garder un salarié, comparé au coût de son "
        "départ.",

    "Prévision de la demande":
        "La charge de travail attendue jour par jour, Ramadan, fêtes, saison et "
        "météo compris.",
    "Planning & coût":
        "Le planning le moins cher qui respecte le droit du travail algérien.",
    "Analyse sectorielle":
        "Les indicateurs propres à votre métier, pas ceux d'un autre secteur.",
    "Aéroport":
        "Flux de passagers heure par heure, et l'effet d'un vol en retard sur "
        "toute la journée.",

    "Paie": "Bulletins, CNAS et IRG calculés sur le barème en vigueur.",
    "Échéances & déclarations":
        "Ce que votre comptable doit déposer à la CNAS et aux impôts, avant "
        "quand, et le lien direct vers le portail. Avec rappel dans l'agenda.",
    "Détection d'anomalies":
        "Les erreurs de paie et de présence qu'un contrôle relèverait avant vous.",
    "Contrôle de documents":
        "Déposez un bulletin : les montants sont relus et comparés au salaire "
        "minimum, au taux CNAS et aux heures légales.",
    "Simulateur d'inspection":
        "Ce que verrait un inspecteur du travail s'il passait aujourd'hui.",
    "Veille Journal Officiel":
        "Les textes parus qui changent vos obligations, et ce qu'ils coûtent.",

    "Tableau de KPI": "Vos indicateurs RH, suivis dans le temps.",
    "Simulateur de scénarios":
        "« Et si » : plus de volume, moins d'effectif, une hausse de salaire. "
        "L'effet chiffré avant de décider.",
    "Assistant":
        "Posez n'importe quelle question sur votre entreprise, en français : "
        "planning, personnel, paie, ou une décision à prendre. Il répond avec "
        "vos chiffres.",
    "Données de l'entreprise":
        "Importez votre fichier : toute la plateforme bascule sur vos vrais "
        "chiffres.",

    "Preuves": "La démonstration que la méthode fonctionne, y compris ses ratés.",
    "Calendrier algérien":
        "Ramadan, les deux Aïd et les jours fériés, calculés et vérifiés.",
    "Analyse économique": "Ce que la plateforme vous rapporte, poste par poste.",
    "Sources & hypothèses":
        "Chaque chiffre : d'où il vient, ou pourquoi c'est une hypothèse.",
    "Confidentialité":
        "Ce que la plateforme fait de vos données, ce qui sort vers un service "
        "extérieur, et combien de temps c'est conservé.",
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
        # N'apparaît que si un mot de passe protège l'accès.
        from . import gate
        gate.sign_out_button()


@st.dialog("Choisir une fonctionnalité", width="large")
def _section_picker(section: str, section_pages: list) -> None:
    """
    Le sélecteur modal , le reste de l'écran s'assombrit tout seul.

    « Ouvrir » ne change pas de page ici : appeler `switch_page` depuis
    l'intérieur d'une fenêtre modale change bien de page mais laisse la fenêtre
    ouverte par-dessus. On mémorise donc la cible et on relance ; `render()`
    ouvre la page au tour suivant, hors de la fenêtre, ce qui la referme.
    """
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
                st.session_state["_nav_goto"] = title
                st.rerun()


def _goto_searched() -> None:
    """
    Rappel de la recherche : mémorise la cible et vide le champ.

    Vider le champ doit se faire **ici**, dans le rappel : modifier l'état d'un
    widget après son instanciation lève une exception. Le rappel s'exécute avant
    le script, donc la remise à zéro est légale et le champ ne garde pas la
    dernière page ouverte en mémoire.
    """
    st.session_state["_nav_goto"] = st.session_state.get("wf_search")
    st.session_state["wf_search"] = None


def render(pages: dict, current) -> None:
    """
    Le bandeau : le logo, une recherche, les réglages, puis les sept sections.

    Rendu une fois par `dashboard.py`, avant l'exécution de la page, donc il
    apparaît en haut de l'espace de travail.
    """
    from . import brand as brand_mod, industry

    path = getattr(current, "url_path", None)
    active = next(
        (sec for sec, pgs in pages.items()
         if any(getattr(p, "url_path", None) == path for p in pgs)),
        next(iter(pages)),
    )
    current_title = getattr(current, "title", "")

    # Titre -> objet page, pour que la recherche puisse ouvrir la cible.
    by_title = {getattr(p, "title", ""): p
                for pgs in pages.values() for p in pgs}

    # La recherche a pu être validée au rerun précédent : on ouvre la page ici,
    # pendant l'exécution du script, seul endroit où `switch_page` est permis.
    target = st.session_state.pop("_nav_goto", None)
    if target and target in by_title:
        st.switch_page(by_title[target])

    with st.container(key="wf_topbar"):
        # Les trois réglages tiennent sur une ligne chacun : en dessous de
        # ~150 px, « Réglages » se coupe en trois lignes et le bandeau devient
        # illisible. D'où la part large donnée à la colonne de droite.
        logo, search, controls = st.columns([2.2, 3.2, 4.6],
                                            vertical_alignment="center")
        with logo:
            # Le logo seul. Une édition sectorielle (?industry=hotel) reste
            # annoncée, mais sous forme de mention courte : le reste du temps il
            # n'y a rien à ajouter sous la marque.
            edition = (f'<span class="tz-topsub">{industry.label()}</span>'
                       if industry.is_tailored() else "")
            st.markdown(
                f'<div class="tz-topbrand">{brand_mod.lockup(23)}{edition}</div>',
                unsafe_allow_html=True,
            )
        with search:
            # Pas de conteneur nommé autour : un widget porte déjà sa propre
            # classe `st-key-wf_search`, et réutiliser la clé sur un conteneur
            # ferait deux éléments de même clé.
            st.selectbox(
                "Rechercher", options=list(by_title), index=None,
                key="wf_search", on_change=_goto_searched,
                # Le nombre d'écrans est compté, jamais écrit en dur : il a déjà
                # menti d'un écran le jour où deux pages ont fusionné.
                placeholder=f"Rechercher une fonctionnalité, {len(by_title)} écrans",
                label_visibility="collapsed",
            )
        with controls:
            # Conteneur nommé : la visite guidée vise ce sélecteur.
            with st.container(key="wf_controls"):
                _context_controls()

        st.markdown(
            f'<div class="tz-crumb"><span>{active}</span>'
            f'<b>{current_title}</b></div>',
            unsafe_allow_html=True,
        )

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
