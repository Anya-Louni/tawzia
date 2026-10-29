"""
core/gate.py
------------
App access: a password, only when one is configured.

The platform handles a staff and salary register, so on a public URL it must
not be open to everyone. A sales demo must not hit a sign-in screen when nobody
set a password either. Rule: if a password is configured it is required;
otherwise access stays open and the app says so. No accounts, no user database,
so nothing to leak.

Set it in `.streamlit/secrets.toml` or the environment: APP_PASSWORD = "...".
Comparison uses `hmac.compare_digest` (no timing leak). The password is never
stored in session state, only an "authenticated" flag.

This is not identity management: multi-tenant deployments need a real identity
provider (`st.login` with OIDC).
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
    True when access is allowed. Call before rendering anything.

    Returns False after showing the sign-in screen: the caller must then stop
    the script.
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
        f'This space holds a staff and salary register. '
        f'Enter the password to continue.</div></div>',
        unsafe_allow_html=True,
    )

    left, mid, right = st.columns([1, 2, 1])
    with mid:
        with st.form("gate"):
            pwd = st.text_input("Password", type="password",
                                label_visibility="collapsed",
                                placeholder="Password")
            ok = st.form_submit_button("Sign in", type="primary",
                                       width="stretch",
                                       icon=":material/login:")
        tries = int(st.session_state.get(_ATTEMPTS, 0))
        if tries >= MAX_ATTEMPTS:
            st.error("Too many attempts. Reload the page to try again.",
                     icon=":material/block:")
            return False
        if ok:
            if hmac.compare_digest(pwd or "", expected):
                st.session_state[_FLAG] = True
                st.session_state.pop(_ATTEMPTS, None)
                st.rerun()
            st.session_state[_ATTEMPTS] = tries + 1
            st.error(f"Wrong password. "
                     f"{MAX_ATTEMPTS - tries - 1} attempt(s) left.",
                     icon=":material/error:")
        st.caption("The password is never stored: the session only remembers "
                   "that you signed in.")
    return False


def sign_out_button() -> None:
    """Sign-out button, shown only when a password protects access."""
    if not is_protected() or not st.session_state.get(_FLAG):
        return
    if st.button("Sign out", icon=":material/logout:"):
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
