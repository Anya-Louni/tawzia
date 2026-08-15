"""
core/tour.py
------------
La visite guidée du produit, au premier lancement.

Pourquoi elle existe
====================
Une plateforme de vingt-huit écrans perd la personne qui l'ouvre pour la
première fois, et une personne perdue n'achète pas. La visite dit en cinq
étapes ce que l'outil fait, où l'on clique, et ce qu'on y gagne , puis elle
s'efface et ne revient plus, sauf demande explicite.

Comment c'est branché
=====================
`driver.js` (MIT, embarqué dans `assets/vendor/`, jamais chargé depuis un CDN :
la démonstration doit tenir sans réseau) est monté dans un composant
**Custom Components v2**. CCv2 ne met pas le composant dans une iframe : le
script s'exécute dans le document de l'application, il peut donc mettre en
évidence les vrais éléments de l'interface , le bandeau, les sections, les
réglages , et pas une copie dans un cadre isolé.

`isolate_styles=False` est nécessaire : driver.js pose son voile et sa bulle
sur `document.body`, hors du shadow root, donc sa feuille de style doit être
globale.

Les sélecteurs visés sont nos propres conteneurs nommés (`st-key-*`), jamais
des classes `st-emotion-cache-*`, qui changent à chaque version de Streamlit.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

_VENDOR = Path(__file__).resolve().parent.parent / "assets" / "vendor"

_SEEN_KEY = "_tour_seen"
_REPLAY_KEY = "_tour_replay"


def _read(name: str) -> str:
    try:
        return (_VENDOR / name).read_text(encoding="utf-8")
    except OSError:
        return ""


# driver.js est distribué en IIFE : sa première instruction est
# `this.driver = this.driver || {}`. Dans un module ES, `this` vaut `undefined`
# au niveau racine, ce qui lèverait une TypeError. On l'exécute donc avec
# `window` comme `this`.
_DRIVER_SRC = _read("driver.iife.js")
_DRIVER_CSS = _read("driver.css")

_JS = """
(function () {
%s
}).call(window);

export default function (component) {
  const { data, setTriggerValue } = component;
  if (!data || !data.run) return;

  const factory = window.driver && window.driver.js && window.driver.js.driver;
  if (typeof factory !== "function") return;

  // Une seule visite à la fois, même si Streamlit remonte le composant.
  if (window.__wfTourRunning) return;
  window.__wfTourRunning = true;

  const steps = (data.steps || [])
    .filter(function (s) { return !s.element || document.querySelector(s.element); })
    .map(function (s) {
      return {
        element: s.element || undefined,
        popover: {
          title: s.title,
          description: s.text,
          side: s.side || "bottom",
          align: s.align || "start",
        },
      };
    });

  if (!steps.length) { window.__wfTourRunning = false; return; }

  const finish = function () {
    window.__wfTourRunning = false;
    setTriggerValue("finished", true);
  };

  const tour = factory({
    showProgress: true,
    allowClose: true,
    overlayColor: "#0A2540",
    overlayOpacity: 0.68,
    stagePadding: 6,
    stageRadius: 8,
    popoverClass: "wf-tour",
    nextBtnText: "Suivant",
    prevBtnText: "Précédent",
    doneBtnText: "Commencer",
    progressText: "{{current}} / {{total}}",
    steps: steps,
    onDestroyed: finish,
  });

  // Laisse Streamlit finir de peindre la page avant de mesurer les cibles.
  // `setTimeout` et non `requestAnimationFrame` : rAF ne se déclenche pas
  // dans un onglet non visible, et la visite resterait alors bloquée.
  setTimeout(function () {
    try {
      tour.drive();
    } catch (err) {
      window.__wfTourRunning = false;
      console.error("Tawzia , visite guidée :", err);
    }
  }, 300);
}
""" % _DRIVER_SRC

_CSS = _DRIVER_CSS + """
/* La bulle prend la langue visuelle du produit : navy, bleu d'action,
   angles équerrés, aucun dégradé. */
.driver-popover.wf-tour {
  background:#FFFFFF; border:1px solid #CBD5E1; border-radius:10px;
  box-shadow:0 24px 60px -20px rgba(10,37,64,.6);
  font-family:'Inter', system-ui, sans-serif; max-width:360px;
}
.driver-popover.wf-tour .driver-popover-title {
  font-size:16px; font-weight:800; color:#0A2540; letter-spacing:-.015em;
}
.driver-popover.wf-tour .driver-popover-description {
  font-size:13.5px; line-height:1.55; color:#334155;
}
.driver-popover.wf-tour .driver-popover-progress-text {
  font-size:12px; color:#475569; font-weight:600;
}
.driver-popover.wf-tour button {
  background:#FFFFFF; color:#0A2540; border:1px solid #CBD5E1;
  border-radius:6px; padding:6px 14px; font-size:13px; font-weight:600;
  text-shadow:none; transition:background .13s ease, border-color .13s ease;
}
.driver-popover.wf-tour button:hover {
  background:#E8F0FC; border-color:#1355C4; color:#0E42A0;
}
.driver-popover.wf-tour .driver-popover-next-btn {
  background:#1355C4; border-color:#1355C4; color:#FFFFFF;
}
.driver-popover.wf-tour .driver-popover-next-btn:hover {
  background:#0E42A0; border-color:#0E42A0; color:#FFFFFF;
}
.driver-popover.wf-tour .driver-popover-arrow { border-color:#FFFFFF; }
"""

# Les étapes : ce que l'outil fait, où l'on clique, ce qu'on y gagne.
STEPS = [
    {
        "element": ".st-key-wf_topbar",
        "title": "Bienvenue sur Tawzia",
        "text": "La plateforme RH et de planification conçue pour l'Algérie : "
                "le vrai calendrier, la vraie météo, le vrai droit du travail. "
                "Tout se pilote depuis ce bandeau.",
        "side": "bottom",
    },
    {
        "element": ".st-key-wf_sections",
        "title": "Sept sections, tout le métier",
        "text": "Recruter, gérer l'équipe, planifier, payer, décider, prouver. "
                "Cliquez sur une section : l'écran s'assombrit et vous choisissez "
                "la fonctionnalité exacte.",
        "side": "bottom",
    },
    {
        "element": ".st-key-wf_controls",
        "title": "Votre contexte",
        "text": "Choisissez votre activité et votre wilaya : les rôles, les "
                "coûts et la météo utilisée par le modèle s'adaptent aussitôt. "
                "Un hôtel à Oran ne se planifie pas comme un hub à Alger.",
        "side": "bottom",
        "align": "end",
    },
    {
        "element": "[data-testid='stMainBlockContainer']",
        "title": "Des chiffres, pas des promesses",
        "text": "Chaque écran affiche sa source. Ce qui est réel est cité ; ce "
                "qui est une hypothèse est marqué comme telle. C'est ce qui "
                "tient devant un directeur financier.",
        "side": "top",
    },
    {
        "element": ".st-key-wf_sec_active",
        "title": "Commencez ici",
        "text": "Importez vos données dans « Décision IA », puis ouvrez le "
                "tableau de bord : la plateforme bascule sur vos vrais chiffres "
                "et la méthode ne change pas.",
        "side": "bottom",
    },
]


_COMPONENT = st.components.v2.component(
    "wf_onboarding_tour",
    html="<div hidden></div>",
    css=_CSS,
    js=_JS,
    # driver.js dessine son voile sur document.body, hors du shadow root :
    # sa feuille de style doit donc être globale.
    isolate_styles=False,
)


def available() -> bool:
    """La visite n'est possible que si driver.js a bien été embarqué."""
    return bool(_DRIVER_SRC)


def maybe_run(current) -> None:
    """
    Lancer la visite au premier affichage de la session, ou sur demande.

    Appelée après le rendu de la page, pour que les cibles existent déjà dans
    le document au moment où driver.js les mesure.
    """
    if not available():
        return

    replay = st.session_state.pop(_REPLAY_KEY, False)
    first_time = not st.session_state.get(_SEEN_KEY, False)

    # Au premier lancement, la visite ne se déclenche que sur l'accueil : sur
    # une page interne elle commenterait un écran que l'utilisateur a choisi.
    on_home = getattr(current, "url_path", "") in ("", "guide")
    run = replay or (first_time and on_home)

    if run:
        st.session_state[_SEEN_KEY] = True

    _COMPONENT(
        key="wf_tour",
        data={"run": bool(run), "steps": STEPS},
        on_finished_change=lambda: None,
    )
