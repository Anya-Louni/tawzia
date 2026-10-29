"""
core/ai.py
----------
One brain socket, one brain.

The AI features (decision copilot, plain-language answers, legal-risk
explanations) call `chat()` here and never care about the wiring. The natural-
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
# Llama 3.3 70B was retired on Groq in 2026 ; gpt-oss-120b is the strongest open model left.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")


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


def _setting(name: str, default: bool) -> bool:
    """A switch from the Settings screen (session) or the environment."""
    try:
        import streamlit as st
        if name in st.session_state:
            return bool(st.session_state[name])
    except Exception:
        pass
    v = os.environ.get(name.upper())
    return default if v is None else v not in ("0", "false", "no")


def local_model() -> Optional[str]:
    """The open-weights model served by Ollama on this machine, if configured."""
    return _secret("TAWZIA_LOCAL_MODEL")


def providers_available() -> dict:
    """Which brains can actually answer right now."""
    return {
        "groq": bool(_secret("GROQ_API_KEY")) and _has_module("groq"),
        "local": bool(local_model()),
    }


def choose_provider(prefer: Optional[str] = None) -> Optional[str]:
    av = providers_available()
    # Sovereign mode: nothing leaves the machine when the local model is chosen.
    if av["local"] and _setting("llm_local", False):
        return "local"
    return "groq" if av["groq"] else ("local" if av["local"] else None)


def status_line() -> str:
    """Human-readable summary for the UI."""
    if choose_provider() == "local":
        return f"Local model ({local_model()}): nothing leaves the machine."
    if providers_available()["groq"]:
        model = _secret("GROQ_MODEL") or GROQ_MODEL
        return f"Groq ({model}) active. Natural language is on; the in-house models run without a key."
    return ("No AI key configured. Add GROQ_API_KEY (free key at "
            "console.groq.com) for natural language. Every in-house model works "
            "without a key.")


# ---------------------------------------------------------------------------
# Provider call
# ---------------------------------------------------------------------------

def _call_local(system: str, user: str, max_tokens: int, temperature: float) -> AIResult:
    import requests
    url = (_secret("OLLAMA_URL") or "http://localhost:11434").rstrip("/") + "/api/chat"
    model = local_model()
    r = requests.post(url, timeout=120, json={
        "model": model, "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    })
    r.raise_for_status()
    return AIResult(text=r.json()["message"]["content"].strip(), provider="local",
                    model=model, ok=True)


def _known_names() -> list:
    try:
        from . import company_data
        return [e.name for e in company_data.people()]
    except Exception:  # noqa: BLE001 , hors Streamlit, pas de fichier du personnel
        return []

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
    provider = choose_provider()
    if provider is None:
        return AIResult(
            text="", provider="none", model="", ok=False,
            error="No AI key configured. Add GROQ_API_KEY (free key at "
                  "console.groq.com). The rest of the app works without it.",
        )
    # Law 25-11: before any external call, personal data is replaced by tokens,
    # restored in the answer.
    table = {}
    if provider != "local" and _setting("pii_redaction", True):
        from . import pii
        names = _known_names()
        system, t1 = pii.redact(system, names)
        user, t2 = pii.redact(user, names)
        table = {**t1, **t2}
    try:
        call = _call_local if provider == "local" else _call_groq
        res = call(system, user, max_tokens, temperature)
    except Exception as exc:  # noqa: BLE001 - a provider error must not crash the app
        return AIResult(text="", provider=provider, model="", ok=False, error=str(exc))
    if table:
        from . import pii
        res.text = pii.restore(res.text, table)
    _log_call(provider, len(table))
    return res


def _log_call(provider: str, masked: int) -> None:
    """Every model call goes to the log: who, what, how many masks."""
    try:
        from . import db
        con = db.connect()
        db.log(con, "agent", "system", f"appel_ia:{provider}", "-",
               f"{masked} personal item(s) masked")
    except Exception:  # noqa: BLE001 - logging must never block an answer
        pass


if __name__ == "__main__":
    print("AI provider plumbing - self check\n")
    print("  available :", providers_available())
    print("  chosen    :", choose_provider())
    print("  status    :", status_line())
    r = chat("You are a terse assistant.", "Say 'ready' and nothing else.", max_tokens=20)
    print(f"  test call : ok={r.ok} provider={r.provider} text={r.text!r} err={r.error}")
