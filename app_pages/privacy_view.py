"""
Confidentialité , ce que la plateforme fait des données, et ce qu'elle n'en fait pas.

Un DRH qui confie un registre du personnel a le droit de savoir où partent ces
données. Cette page répond précisément, y compris quand la réponse est gênante :
le texte d'un CV envoyé au copilote transite chez un fournisseur d'IA. Le dire
vaut mieux que le laisser découvrir.
"""

import streamlit as st

from core import ai, appdata, company_data as cd, db, deadlines_dz as dl

appdata.sidebar_controls()

st.markdown(
    '<div class="tz-hero"><div>'
    '<h1 class="tz-hero-h">Confidentialité et données</h1>'
    '<div class="tz-hero-s">Ce qui est traité, où, par qui, et pendant combien '
    'de temps. Écrit pour être lu avant de confier un fichier du personnel.'
    '</div></div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Les réglages de confiance : ce que le jury et un DRH veulent voir en vrai
# ---------------------------------------------------------------------------
_con = db.seed(db.connect())
with st.container(border=True):
    appdata.card_head("Réglages de confiance", "loi 25-11")
    t1, t2 = st.columns(2)
    t1.toggle("Masquer les données personnelles avant tout appel IA", value=True,
              key="pii_redaction",
              help="Noms, téléphones, NIN, RIB et courriels remplacés par des jetons, "
                   "remis en place dans la réponse.")
    t2.toggle("Modèle local (rien ne quitte la machine)", key="llm_local",
              disabled=not ai.local_model(),
              help="Un modèle ouvert servi par Ollama. Réglez TAWZIA_LOCAL_MODEL "
                   "pour l'activer : c'est l'option d'hébergement souverain.")
    st.caption(f":material/smart_toy: {ai.status_line()}")
    st.caption(":material/how_to_reg: Chaque embauche, refus, paie et déclaration passe "
               "par un clic humain. Aucun agent n'envoie ni ne dépose seul.")

with st.expander("Journal des actions", icon=":material/history:"):
    st.dataframe(db.recent_log(_con, 40), hide_index=True, width="stretch",
                 column_config={"at": "Quand", "actor": "Qui", "role": "Rôle",
                                "action": "Quoi", "target": "Sur", "why": "Pourquoi"})
    st.caption("Collecte, consultation, modification et effacement sont tracés, comme "
               "l'attend la loi 25-11. Les champs sensibles sont chiffrés en AES-256-GCM.")

with st.expander("Registre des incidents", icon=":material/report:"):
    st.caption("Une violation de données se notifie à l'ANPDP dans un délai court "
               "(5 jours selon le brief, à vérifier sur le texte au JO).")
    with st.form("incident"):
        what = st.text_area("Ce qui s'est passé")
        if st.form_submit_button("Enregistrer l'incident") and what.strip():
            db.log(_con, "hr", "hr", "incident", "ANPDP", what.strip()[:300])
            st.success("Incident enregistré au journal. Une carte de notification ANPDP "
                       "est à préparer.", icon=":material/check:")
    st.caption("Sauvegardes : chiffrées, restauration testée, à documenter au déploiement.")


providers = ai.providers_available()
ai_on = any(providers.values())
_ai_note = ("La couche IA est active sur cette instance." if ai_on else
            "Aucune clé IA n'est configurée ici, donc rien ne part.")

k1, k2, k3 = st.columns(3)
with k1, st.container(border=True, height="stretch"):
    appdata.stat_card("Données de cette session", cd.source_label(), None, "flat",
                      "affiché sur chaque écran, à côté des chiffres")
with k2, st.container(border=True, height="stretch"):
    appdata.stat_card("Conservation", "Session", None, "flat",
                      "rien n'est enregistré côté serveur après la fermeture")
with k3, st.container(border=True, height="stretch"):
    appdata.stat_card("Couche IA", "Active" if ai_on else "Inactive",
                      "Groq" if providers.get("groq") else "aucune",
                      "up" if ai_on else "flat",
                      "utilisée seulement pour rédiger, jamais pour calculer")

with st.container(border=True):
    appdata.card_head("Ce que la plateforme traite", "et pourquoi")
    st.markdown(
        "- **Fiches du personnel** : nom, matricule, poste, wilaya, date "
        "d'embauche, contrat, personnes à charge, salaire. Servent au calcul des "
        "droits à congé, de la paie, des cotisations et du planning.\n"
        "- **Présence** : pointages, retards, absences. Servent au suivi de "
        "présence et à l'estimation du risque de départ.\n"
        "- **Demandes** : congés, sorties, arrêts. Servent à l'arbitrage.\n"
        "- **CV déposés** : le texte du CV, pour l'évaluation et le classement.\n\n"
        "La plateforme ne demande ni numéro de sécurité sociale, ni numéro de "
        "compte bancaire, ni pièce d'identité, ni donnée de santé détaillée. Si "
        "votre fichier en contient, retirez ces colonnes avant l'import : elles "
        "ne servent à aucun calcul ici."
    )

with st.container(border=True):
    appdata.card_head("Où vont les données", "la liste complète")
    st.markdown(
        "**Restent sur le serveur de l'application, en mémoire de session :**\n"
        "- toutes les fiches du personnel, la présence, les demandes, la paie, "
        "les plannings et les calculs qui en découlent.\n\n"
        "**Sortent vers un service tiers :**\n"
        f"- **Le texte que vous soumettez à l'assistant, au contrôle de CV ou à "
        f"la rédaction d'offre** est envoyé à **Groq** (fournisseur du modèle de "
        f"langage) pour être rédigé ou analysé. Cela peut inclure des noms et le "
        f"contenu d'un CV. {_ai_note}\n"
        "- **Open-Meteo** reçoit une wilaya et une plage de dates pour la météo. "
        "Aucune donnée de personne.\n"
        "- **Banque mondiale** reçoit un code pays pour les indicateurs macro. "
        "Aucune donnée de personne.\n"
        "- **Aladhan** reçoit une date pour vérifier le calendrier hégirien. "
        "Aucune donnée de personne.\n\n"
        "Rien n'est envoyé à la CNAS, aux impôts ni à aucun organisme : les "
        "déclarations se déposent sur leurs portails, par vous."
    )
    st.info(
        "Pour travailler sans aucun appel réseau, ouvrez le menu **Données** du "
        "bandeau et désactivez « Autoriser les appels API en direct ». Les "
        "écrans continuent de fonctionner sur le cache local ; seule la "
        "conversation IA devient indisponible.",
        icon=":material/wifi_off:",
    )

with st.container(border=True):
    appdata.card_head("Conservation et suppression", "session par session")
    st.markdown(
        "- Les fichiers importés vivent **dans la session** : fermer l'onglet "
        "les efface. Il n'y a pas de base de données de clients dans cette "
        "version.\n"
        "- Le bouton **« Revenir aux données de démonstration »** de l'écran "
        "*Données de l'entreprise* retire immédiatement votre fichier.\n"
        "- Les caches techniques (météo, calendrier, backtest) sont conservés "
        "sur disque pour la vitesse et **ne contiennent aucune donnée de "
        "personne**."
    )
    st.page_link("app_pages/company_data_view.py",
                 label="Gérer ou retirer vos données",
                 icon=":material/database:")

with st.container(border=True):
    appdata.card_head("Cadre légal algérien", "à faire valider par un juriste")
    st.markdown(
        "Le traitement de données personnelles en Algérie est encadré par la "
        "**loi 18-07 du 10 juin 2018** relative à la protection des personnes "
        "physiques dans le traitement des données à caractère personnel. Ce "
        "qu'elle implique pour un employeur qui utilise cette plateforme :\n"
        "- informer les salariés du traitement et de sa finalité ;\n"
        "- ne collecter que ce qui sert à cette finalité ;\n"
        "- permettre l'accès et la rectification ;\n"
        "- sécuriser les accès et limiter la conservation.\n\n"
        "Les obligations déclaratives sociales et fiscales restent celles des "
        "portails officiels."
    )
    st.warning(
        "Cette page décrit le fonctionnement technique de la plateforme. Elle "
        "n'est pas un avis juridique : faites valider votre politique de "
        "confidentialité et vos mentions d'information par un juriste avant un "
        "déploiement réel.",
        icon=":material/gavel:",
    )
    cols = st.columns(2)
    cols[0].link_button("Portail CNAS", dl.PORTAL_CNAS_MAIN, width="stretch",
                        icon=":material/open_in_new:")
    cols[1].link_button("Portail DGI", dl.PORTAL_DGI, width="stretch",
                        icon=":material/open_in_new:")

with st.container(border=True):
    appdata.card_head("Ce que la plateforme n'invente pas", "notre règle")
    st.markdown(
        "Les chiffres affichés viennent des moteurs de calcul, jamais du modèle "
        "de langage : celui-ci rédige, il ne calcule pas. Les volumes "
        "opérationnels de la démonstration sont simulés et signalés comme tels "
        "sur chaque écran ; le calendrier, la météo, le SNMG, les taux CNAS et "
        "le barème IRG sont réels et sourcés."
    )
    st.page_link("app_pages/sources_view.py",
                 label="Voir chaque chiffre et sa source",
                 icon=":material/menu_book:")

appdata.data_badge()
