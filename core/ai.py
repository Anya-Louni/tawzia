"""
core/ai.py
----------
One brain socket, one brain.

The AI features (copilote décisionnel, réponses en langage clair, explications de
risque légal) call `chat()` here and never care about the wiring. The natural-
language layer runs on **Groq (Llama)** with a single free API key, read from the
environment or from Streamlit secrets. It is deliberately the *thin* part of the
product: the real intelligence is the owned models (forecast, roster optimiser,
attrition, anomaly detection, CV matching), which run locally with no key. Groq
only translates questions and narrates the computed results.

Key handling (security)
=======================
The key is NEVER hardcoded here. It is read at runtime via `_secret()` from:
  1. the environment (GROQ_API_KEY), or
  2. Streamlit secrets (st.secrets["GROQ_API_KEY"]) — set in the Streamlit Cloud
     dashboard for the deployed app, or in a gitignored .streamlit/secrets.toml
     for local development.

If no key is configured, nothing crashes: `chat()` returns ok=False with a clear
message, and the rest of the app (all the owned models) keeps working.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Optional

# Model id is read from env/secrets so it can be changed without a code edit.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


@dataclass
class AIResult:
    text: str
    provider: str          # "groq" | "none"
    model: str
    ok: bool
    error: Optional[str] = None


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


_DOTENV_LOADED = False


def _load_dotenv_once() -> None:
    """Load a local .env if python-dotenv is available (no-op on Cloud)."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass


def _secret(name: str):
    """Read a key from the environment, a local .env, or Streamlit secrets (Cloud)."""
    v = os.environ.get(name)
    if v:
        return v
    _load_dotenv_once()
    v = os.environ.get(name)
    if v:
        return v
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return None


def providers_available() -> dict:
    """Which brains can actually answer right now."""
    return {
        "groq": bool(_secret("GROQ_API_KEY")) and _has_module("groq"),
    }


def choose_provider(prefer: Optional[str] = None) -> Optional[str]:
    return "groq" if providers_available().get("groq") else None


def status_line() -> str:
    """Human-readable summary for the UI."""
    if providers_available()["groq"]:
        model = _secret("GROQ_MODEL") or GROQ_MODEL
        return f"Groq ({model}) actif. Le langage naturel tourne ; les modèles maison tournent sans clé."
    return ("Aucune clé IA configurée. Ajoutez GROQ_API_KEY (clé gratuite sur "
            "console.groq.com) pour le langage naturel. Tous les modèles maison "
            "fonctionnent sans clé.")


# ---------------------------------------------------------------------------
# Provider call
# ---------------------------------------------------------------------------

def _call_groq(system: str, user: str, max_tokens: int, temperature: float) -> AIResult:
    from groq import Groq  # lazy: only imported when the key is present

    client = Groq(api_key=_secret("GROQ_API_KEY"))
    model = _secret("GROQ_MODEL") or GROQ_MODEL
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return AIResult(text=resp.choices[0].message.content.strip(),
                    provider="groq", model=model, ok=True)


def chat(
    system: str,
    user: str,
    prefer: Optional[str] = None,
    max_tokens: int = 700,
    temperature: float = 0.2,
) -> AIResult:
    """
    Ask the Groq brain. Never raises for a missing key or a provider error — it
    returns an AIResult with ok=False and a clear message, so the UI can show
    something useful instead of a stack trace.

    `prefer` is accepted for backward compatibility and ignored (Groq is the
    only provider now).
    """
    if choose_provider() is None:
        return AIResult(
            text="", provider="none", model="", ok=False,
            error="Aucune clé IA configurée. Ajoutez GROQ_API_KEY (clé gratuite "
                  "sur console.groq.com). Le reste de l'app fonctionne sans elle.",
        )
    try:
        return _call_groq(system, user, max_tokens, temperature)
    except Exception as exc:  # noqa: BLE001 - a provider error must not crash the app
        return AIResult(text="", provider="groq", model="", ok=False, error=str(exc))


if __name__ == "__main__":
    print("AI provider plumbing - self check\n")
    print("  available :", providers_available())
    print("  chosen    :", choose_provider())
    print("  status    :", status_line())
    r = chat("You are a terse assistant.", "Say 'ready' and nothing else.", max_tokens=20)
    print(f"  test call : ok={r.ok} provider={r.provider} text={r.text!r} err={r.error}")
