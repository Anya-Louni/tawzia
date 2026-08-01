"""
core/ai.py
----------
One brain socket, two brains.

The AI features (HR copilot, plain-language answers, law-risk explanations) call
`chat()` here and never care which model answers. Two providers are wired:

  * **Provider (the AI model)** - the best answers, used for the jury demonstration.
    Enabled when PROVIDER_API_KEY is set and the `provider` package is
    installed.
  * **Groq (Llama)** - free, fast, no cost. The safety net: if the Provider
    subscription lapses, everything keeps working on Groq with no code change.

Selection order (override with WORKFORCE_AI_PROVIDER = provider | groq):
  1. Explicit `prefer` argument, if that provider is available.
  2. Provider if its key + SDK are present.
  3. Groq if its key is present.
  4. Otherwise a clear, honest "no AI key configured" message - the rest of the
     app keeps working; only the chat surface is affected.

Nothing here is Algeria-specific; it is pure plumbing so the HR brain can be
swapped without touching a single feature.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Optional

# Model ids are read from env so they can be changed without a code edit.
PROVIDER_MODEL = os.environ.get("PROVIDER_MODEL", "model-name")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


@dataclass
class AIResult:
    text: str
    provider: str          # "provider" | "groq" | "none"
    model: str
    ok: bool
    error: Optional[str] = None


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _secret(name: str):
    """Read a key from the environment or from Streamlit secrets (Cloud)."""
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
        "provider": bool(_secret("PROVIDER_API_KEY")) and _has_module("provider"),
        "groq": bool(_secret("GROQ_API_KEY")) and _has_module("groq"),
    }


def choose_provider(prefer: Optional[str] = None) -> Optional[str]:
    avail = providers_available()
    env_pref = os.environ.get("WORKFORCE_AI_PROVIDER")
    for candidate in (prefer, env_pref, "provider", "groq"):
        if candidate and avail.get(candidate):
            return candidate
    return None


def status_line() -> str:
    """Human-readable summary for the UI."""
    a = providers_available()
    if a["provider"]:
        return f"Provider the AI model ({PROVIDER_MODEL}) - jury mode. Groq standby: {'yes' if a['groq'] else 'no'}."
    if a["groq"]:
        return f"Groq ({GROQ_MODEL}) - free mode. Set PROVIDER_API_KEY for the AI model in the demo."
    return "No AI key configured. Set PROVIDER_API_KEY (best) or GROQ_API_KEY (free)."


# ---------------------------------------------------------------------------
# Provider calls
# ---------------------------------------------------------------------------

def _call_provider(system: str, user: str, max_tokens: int, temperature: float) -> AIResult:
    import provider  # lazy: only needed if this provider is chosen

    client = provider.Provider(api_key=_secret("PROVIDER_API_KEY"))
    resp = client.messages.create(
        model=_secret("PROVIDER_MODEL") or PROVIDER_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    # Concatenate any text blocks in the response.
    text = "".join(getattr(b, "text", "") for b in resp.content).strip()
    return AIResult(text=text, provider="provider", model=PROVIDER_MODEL, ok=True)


def _call_groq(system: str, user: str, max_tokens: int, temperature: float) -> AIResult:
    from groq import Groq  # lazy

    client = Groq(api_key=_secret("GROQ_API_KEY"))
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return AIResult(text=resp.choices[0].message.content.strip(),
                    provider="groq", model=GROQ_MODEL, ok=True)


def chat(
    system: str,
    user: str,
    prefer: Optional[str] = None,
    max_tokens: int = 700,
    temperature: float = 0.2,
) -> AIResult:
    """
    Ask the best available brain. Never raises for a missing key or a provider
    error - it returns an AIResult with ok=False and a clear message, so the UI
    can show something useful instead of a stack trace.
    """
    provider = choose_provider(prefer)
    if provider is None:
        return AIResult(
            text="", provider="none", model="", ok=False,
            error="No AI provider configured. Set PROVIDER_API_KEY (best, for "
                  "the jury demo) or GROQ_API_KEY (free). The rest of the app "
                  "works without it.",
        )
    try:
        if provider == "provider":
            return _call_provider(system, user, max_tokens, temperature)
        return _call_groq(system, user, max_tokens, temperature)
    except Exception as exc:  # noqa: BLE001 - one provider failing must not crash the app
        # If the preferred provider errored, try the other one once.
        other = "groq" if provider == "provider" else "provider"
        if providers_available().get(other):
            try:
                if other == "provider":
                    r = _call_provider(system, user, max_tokens, temperature)
                else:
                    r = _call_groq(system, user, max_tokens, temperature)
                r.error = f"(fell back to {other}: {provider} failed - {exc})"
                return r
            except Exception as exc2:  # noqa: BLE001
                return AIResult(text="", provider=provider, model="", ok=False,
                                error=f"Both providers failed: {exc}; {exc2}")
        return AIResult(text="", provider=provider, model="", ok=False, error=str(exc))


if __name__ == "__main__":
    print("AI provider plumbing - self check\n")
    print("  available :", providers_available())
    print("  chosen    :", choose_provider())
    print("  status    :", status_line())
    r = chat("You are a terse assistant.", "Say 'ready' and nothing else.", max_tokens=20)
    print(f"  test call : ok={r.ok} provider={r.provider} text={r.text!r} err={r.error}")
