"""
core/nav.py
-----------
La navigation : cinq écrans et les réglages, un clic, les sous-écrans dessous.

Le problème que ça règle
========================
L'ancienne barre ouvrait une fenêtre modale à chaque section : deux clics et une
liste à lire avant d'arriver où que ce soit. Moins de choix, c'est moins
d'hésitation. Un clic sur un espace ouvre donc directement son premier écran, et
les autres écrans de l'espace s'alignent en pastilles sous la barre. Le premier
espace, l'autopilote, rend la plupart des autres facultatifs : on y va pour
signer, pas pour chercher.
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

# Ce que chaque espace promet, en une ligne, écrit pour un responsable RH.
SECTION_NOTES = {
    "Décisions": "Le travail est fait. Il reste à signer.",
    "Personnel": "Dossiers, présence, compétences, rétention.",
    "Planning": "Combien de personnes, quel jour, à quel coût.",
    "Recrutement": "L'offre, l'ANEM, les candidats classés.",
    "Paie & déclarations": "Payer juste, déclarer à temps, tenir devant un contrôle.",
    "Réglages": "Vos données, la confidentialité, l'assistant et les preuves.",
}

# Une phrase par écran : à quoi il sert, jamais comment il est fabriqué. Elle
# apparaît au survol de la pastille. Clé = titre de la page (unique).
PAGE_NOTES = {
    "Boîte de décisions": "Les agents ont traité les dossiers du jour : il reste vos décisions.",
    "Guichet salarié": "Attestations, soldes, bulletins et congés, répondus sans vous.",
    "Tableau de bord": "Qui est là, qui manque, et la charge des jours qui viennent.",
    "Rédiger une offre": "Une phrase suffit : l'annonce est écrite, salaire et loi compris.",
    "Canaux de sourcing": "Où publier, ce que chaque canal coûte et en combien de temps il remplit.",
    "Candidats": "Toutes les candidatures classées, chaque rang expliqué.",
    "Intégration": "Le nouvel embauché remplit son dossier, l'agent vérifie, vous signez une carte.",
    "Employés": "Le dossier de chaque salarié et ses jours de congé restants.",
    "Demandes & présence": "Congés, absences et retards, jugés sur la loi et la charge.",
    "Compétences & mobilité": "Qui en interne peut déjà tenir le poste, et le coût de le former.",
    "Rétention": "Qui risque de partir, et l'action la moins chère pour le garder.",
    "Planning de la semaine": "Un bouton : le planning légal le plus stable et le moins cher.",
    "Prévision de la demande": "La charge attendue jour par jour, Ramadan, fêtes et météo compris.",
    "Planning & coût": "Le planning le moins cher qui respecte le droit du travail algérien.",
    "Analyse sectorielle": "Les indicateurs propres à votre métier.",
    "Aéroport": "Flux de passagers heure par heure, et l'effet d'un vol en retard.",
    "Paie": "Bulletins, CNAS et IRG calculés sur le barème en vigueur.",
    "Échéances & déclarations": "Ce qu'il faut déposer à la CNAS et aux impôts, et avant quand.",
    "Détection d'anomalies": "Les erreurs de paie et de présence qu'un contrôle relèverait.",
    "Simulateur d'inspection": "Ce que verrait un inspecteur du travail aujourd'hui.",
    "Veille Journal Officiel": "Les textes qui changent vos obligations, et ce qu'ils coûtent.",
    "Demander à Tawzia": "Posez une question sur votre entreprise : il répond avec vos chiffres.",
    "Simulateur de scénarios": "« Et si » : l'effet chiffré d'une décision avant de la prendre.",
    "Données de l'entreprise": "Importez votre fichier : toute la plateforme passe sur vos chiffres.",
    "Preuves": "La démonstration que la méthode fonctionne, ratés compris.",
    "Calendrier algérien": "Ramadan, les deux Aïd et les jours fériés, calculés et vérifiés.",
    "Analyse économique": "Ce que la plateforme rapporte, poste par poste.",
    "Sources & hypothèses": "Chaque chiffre : d'où il vient, ou pourquoi c'est une hypothèse.",
    "Confidentialité": "Ce que la plateforme fait de vos données, et combien de temps.",
}

def _context_controls() -> None:
    """
    Les réglages qui valaient autrefois un rail latéral entier, en trois menus.

    Ils vivent dans le bandeau parce qu'ils s'appliquent à toutes les pages :
    le secteur et la wilaya changent les rôles, les chiffres et la météo réelle
    utilisée par le modèle.
    """
    from . import demand as demand_mod, i18n, weather_dz

    profile_labels = {k: p.label for k, p in demand_mod.PROFILES.items()}
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.2])

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

    with c2.popover("Prévision", icon=":material/tune:", width="stretch"):
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

    with c4:
        st.segmented_control("Langue", options=list(i18n.LANGS), key="lang",
                             format_func=i18n.LANGS.get, required=True,
                             label_visibility="collapsed")

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


def _ask(titles: list) -> None:
    """
    « Demander à Tawzia » : une phrase, et la plateforme agit.

    Trois issues, dans cet ordre :
      1. la phrase nomme un écran : on l'ouvre ;
      2. elle nomme un salarié et une demande connue (attestation, solde,
         bulletin, congé) : le guichet la traite pour lui, la carte part dans
         la boîte de décisions ;
      3. sinon c'est une question : elle part à l'assistant, déjà posée.

    Rappel de widget : il s'exécute avant le script, seul moment où vider le
    champ est permis.
    """
    from . import company_data as cd, self_service as svc

    ss = st.session_state
    q = (ss.get("wf_ask") or "").strip()
    ss["wf_ask"] = ""
    if not q:
        return
    plain = svc._plain(q)

    # « Ramadan commence jeudi, refais le planning » : le planning se régénère.
    if "ramadan" in plain or ("planning" in plain and any(
            w in plain for w in ("refai", "refais", "genere", "redo", "regenere", "nouveau"))):
        ss["sched_ramadan"] = "ramadan" in plain
        ss["sched_autorun"] = True
        ss["_nav_goto"] = "Planning de la semaine"
        return

    # Le salarié nommé passe avant l'écran : « fiche de paie pour Amina » est
    # une demande, pas l'écran « Paie ».
    intent = svc.classify(q)
    if intent != "autre":
        for e in cd.people():
            if svc._plain(e.name) in plain:
                n = len(ss.setdefault("guichet_tickets", [])) + 100
                r = svc.answer(q, e, company=ss.get("guichet_company", "Votre entreprise"),
                               signatory=ss.get("guichet_signatory", "Le responsable RH"),
                               ticket_id=f"ask{n}")
                if r["ticket"]:
                    ss["guichet_tickets"].append(r["ticket"])
                if r["request"]:
                    ss.setdefault("guichet_requests", []).append(r["request"])
                ss["_ask_toast"] = f"{e.name} : {r['reply']}"
                ss["_nav_goto"] = "Boîte de décisions"
                return

    for t in titles:
        if svc._plain(t) in plain:
            ss["_nav_goto"] = t
            return

    ss.setdefault("assistant_messages", []).append({"role": "user", "content": q})
    ss["assistant_pending"] = q
    ss["_nav_goto"] = "Demander à Tawzia"


def render(pages: dict, current) -> None:
    """
    Le bandeau : le logo, une recherche, les réglages, les sept espaces, puis
    les écrans de l'espace ouvert.

    Rendu une fois par `dashboard.py`, avant l'exécution de la page, donc il
    apparaît en haut de l'espace de travail.
    """
    from . import brand as brand_mod, i18n, industry
    st.session_state.setdefault("lang", "fr")

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
    rtl = i18n.rtl_css()
    if rtl:
        st.markdown(rtl, unsafe_allow_html=True)
    toast = st.session_state.pop("_ask_toast", None)
    if toast:
        st.toast(toast, icon=":material/smart_toy:")

    with st.container(key="wf_topbar"):
        # Les trois réglages tiennent sur une ligne chacun : en dessous de
        # ~150 px, « Réglages » se coupe en trois lignes et le bandeau devient
        # illisible. D'où la part large donnée à la colonne de droite.
        logo, search, controls = st.columns([1.6, 3.4, 5.0],
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
            st.text_input(
                "Demander à Tawzia", key="wf_ask", on_change=_ask,
                args=(list(by_title),), icon=":material/auto_awesome:",
                placeholder=i18n.t("ask_placeholder"),
                label_visibility="collapsed",
            )
        with controls:
            # Conteneur nommé : la visite guidée vise ce sélecteur.
            with st.container(key="wf_controls"):
                _context_controls()

        # Les cinq écrans et les réglages : un clic ouvre le premier sous-écran.
        with st.container(key="wf_sections"):
            cols = st.columns(len(pages), gap="small")
            for i, (col, (sec, pgs)) in enumerate(zip(cols, pages.items())):
                if not pgs:
                    continue
                with col:
                    # Clé stable (l'index, pas un hash) : l'espace ouvert porte
                    # `wf_sec_active`, que la visite guidée vise aussi.
                    wrapper = "wf_sec_active" if sec == active else f"wf_sec_{i}"
                    with st.container(key=wrapper):
                        if st.button(i18n.t(sec), key=f"nav_{sec}", width="stretch",
                                     icon=SECTION_ICONS.get(sec),
                                     help=SECTION_NOTES.get(sec)):
                            st.session_state["_nav_goto"] = getattr(pgs[0], "title", "")
                            st.rerun()

        # Les écrans de l'espace ouvert, en pastilles. L'écran courant n'est
        # pas un lien : il n'y a nulle part où aller.
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
