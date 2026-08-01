"""
core/industry.py
----------------
Industry mode. One app, tailored per prospect.

Instead of building a separate portal per industry, the app reads an
`?industry=hotel` (or delivery / transport / retail / airport) query parameter
once, sets the default vertical, tailors the copy, and hides the modules that do
not apply. Same codebase, same engine, same data flywheel - it just walks in
speaking the prospect's language.

Send a hotel this link:   https://<app>.streamlit.app/?industry=hotel
Send a delivery firm:     https://<app>.streamlit.app/?industry=delivery
No parameter = the full, all-industries platform.
"""

from __future__ import annotations

import streamlit as st

INDUSTRIES = {
    "all": {
        "label": "All operations",
        "profile": None,
        "show_airport": True,
        "hook": "Forecast demand, staff every shift legally, and keep your people, "
                "on the real Algerian calendar and labour law.",
    },
    "delivery": {
        "label": "E-commerce delivery",
        "profile": "ecom_hub",
        "show_airport": False,
        "hook": "In a 95% cash-on-delivery market, a mis-staffed wave is a failed "
                "delivery you pay for twice. Staff to demand, legally and lean.",
    },
    "hotel": {
        "label": "Hotels & hospitality",
        "profile": "hotel",
        "show_airport": False,
        "hook": "Match housekeeping, front desk and F&B to real occupancy swings, "
                "Ramadan and the summer peak, at the lowest legal labour cost.",
    },
    "transport": {
        "label": "Transport & fleet",
        "profile": "transport",
        "show_airport": False,
        "hook": "Plan drivers to demand within the labour code, and keep them "
                "from leaving.",
    },
    "retail": {
        "label": "Retail & distribution",
        "profile": "retail_dc",
        "show_airport": False,
        "hook": "Staff the distribution centre to the real Algerian calendar with "
                "the cheapest legal roster.",
    },
    "airport": {
        "label": "Airport & ground ops",
        "profile": "airport_ground",
        "show_airport": True,
        "hook": "Passenger-flow staffing and delay-cascade control on the real "
                "Algiers network.",
    },
}

_ALIASES = {
    "ecom": "delivery", "ecommerce": "delivery", "e-commerce": "delivery",
    "cod": "delivery", "livraison": "delivery",
    "hotels": "hotel", "hospitality": "hotel", "hotellerie": "hotel",
    "logistics": "transport", "fleet": "transport", "transport_fleet": "transport",
    "warehouse": "retail", "distribution": "retail", "dc": "retail",
    "aviation": "airport", "ground": "airport",
}


def apply() -> None:
    """Read ?industry once and set the default vertical, without locking later edits."""
    if st.session_state.get("_industry_applied"):
        return
    raw = (st.query_params.get("industry") or "all").strip().lower()
    key = _ALIASES.get(raw, raw)
    if key not in INDUSTRIES:
        key = "all"
    st.session_state["industry"] = key
    cfg = INDUSTRIES[key]
    if cfg["profile"]:
        # set before init_state()'s setdefault, so it sticks as the default
        st.session_state["profile_key"] = cfg["profile"]
    st.session_state["_industry_applied"] = True


def current() -> dict:
    return INDUSTRIES.get(st.session_state.get("industry", "all"), INDUSTRIES["all"])


def is_tailored() -> bool:
    return st.session_state.get("industry", "all") != "all"


def label() -> str:
    return current()["label"]


def banner() -> None:
    """A small tailored banner a page can show under its title."""
    if not is_tailored():
        return
    cfg = current()
    st.info(f"**{cfg['label']} edition** - {cfg['hook']}", icon=":material/storefront:")
