"""
core/gate.py
------------
L'accès à l'application : un mot de passe, seulement s'il en existe un.

Pourquoi c'est fait comme ça
============================
La plateforme manipule un registre du personnel et des salaires. Déployée sur
une URL publique, elle ne doit pas être ouverte à tout le monde. Mais une
démonstration commerciale ne doit pas non plus se heurter à un écran de
connexion quand personne n'a configuré de mot de passe.

D'où la règle : **si un mot de passe est configuré, il est exigé ; sinon l'accès
reste libre et l'application le dit.** Aucun compte à créer, aucune base
d'utilisateurs à gérer, donc rien à fuiter.

Configurer le mot de passe
==========================
Dans `.streamlit/secrets.toml` (ou une variable d'environnement) :

    APP_PASSWORD = "votre-mot-de-passe"

La comparaison passe par `hmac.compare_digest`, donc elle ne fuit pas la
longueur du secret par le temps de réponse. Le mot de passe n'est jamais écrit
dans l'état de session : seul un drapeau « authentifié » y est stocké.

Ce que ce n'est pas
===================
Ce n'est pas de la gestion d'identité : pas de comptes nominatifs, pas de rôles,
pas de journal d'accès. Pour un déploiement multi-clients il faudra un vrai
fournisseur d'identité (`st.login` avec OIDC). C'est écrit ici pour que personne
ne prenne ce portillon pour davantage qu'un portillon.
"""

from __future__ import annotations

import hmac
import os

import streamlit as st

_FLAG = "_gate_ok"
_ATTEMPTS = "_gate_attempts"
MAX_ATTEMPTS = 5


def _configured_password() -> str | None:
    """Le mot de passe attendu, depuis les secrets puis l'environnement."""
    try:
        value = st.secrets.get("APP_PASSWORD")  # type: ignore[attr-defined]
        if value:
            return str(value)
    except Exception:
        # Aucun fichier de secrets : ce n'est pas une erreur, juste pas de mot
        # de passe configuré.
        pass
    return os.environ.get("APP_PASSWORD") or None


def is_protected() -> bool:
    return _configured_password() is not None


def require_access() -> bool:
    """
    True si l'accès est autorisé. À appeler avant de rendre quoi que ce soit.

    Renvoie False après avoir affiché l'écran de connexion : l'appelant doit
    alors arrêter le script.
    """
    expected = _configured_password()
    if expected is None:
        return True
    if st.session_state.get(_FLAG):
        return True

    from . import brand

    st.markdown(
        f'<div style="max-width:420px;margin:12vh auto 22px;text-align:center">'
        f'<div style="display:flex;justify-content:center;margin-bottom:18px">'
        f'{brand.lockup(30)}</div>'
        f'<div style="font-size:15px;color:{brand.MUTED};line-height:1.5">'
        f'Cet espace contient un registre du personnel et des salaires. '
        f'Entrez le mot de passe pour continuer.</div></div>',
        unsafe_allow_html=True,
    )

    left, mid, right = st.columns([1, 2, 1])
    with mid:
        with st.form("gate"):
            pwd = st.text_input("Mot de passe", type="password",
                                label_visibility="collapsed",
                                placeholder="Mot de passe")
            ok = st.form_submit_button("Entrer", type="primary",
                                       width="stretch",
                                       icon=":material/login:")
        tries = int(st.session_state.get(_ATTEMPTS, 0))
        if tries >= MAX_ATTEMPTS:
            st.error("Trop de tentatives. Rechargez la page pour réessayer.",
                     icon=":material/block:")
            return False
        if ok:
            if hmac.compare_digest(pwd or "", expected):
                st.session_state[_FLAG] = True
                st.session_state.pop(_ATTEMPTS, None)
                st.rerun()
            st.session_state[_ATTEMPTS] = tries + 1
            st.error(f"Mot de passe incorrect. "
                     f"{MAX_ATTEMPTS - tries - 1} tentative(s) restante(s).",
                     icon=":material/error:")
        st.caption("Le mot de passe n'est jamais conservé : seule la session "
                   "retient que vous êtes entré.")
    return False


def sign_out_button() -> None:
    """Bouton de sortie, affiché seulement si un mot de passe protège l'accès."""
    if not is_protected() or not st.session_state.get(_FLAG):
        return
    if st.button("Quitter la session", icon=":material/logout:"):
        st.session_state.pop(_FLAG, None)
        st.rerun()


if __name__ == "__main__":
    print("Portillon d'accès - auto-vérification\n")

    had = os.environ.pop("APP_PASSWORD", None)
    print(f"{'OK ' if not is_protected() else 'ECHEC'} sans mot de passe "
          f"configuré : accès libre")

    os.environ["APP_PASSWORD"] = "secret-de-test"
    print(f"{'OK ' if is_protected() else 'ECHEC'} avec APP_PASSWORD : "
          f"accès protégé")

    ok = hmac.compare_digest("secret-de-test", _configured_password() or "")
    print(f"{'OK ' if ok else 'ECHEC'} comparaison à temps constant du secret")

    if had is None:
        os.environ.pop("APP_PASSWORD", None)
    else:
        os.environ["APP_PASSWORD"] = had
    print("\nPour protéger l'app : APP_PASSWORD dans .streamlit/secrets.toml")
