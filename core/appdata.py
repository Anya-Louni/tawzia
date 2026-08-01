"""
core/appdata.py
---------------
Cached loaders shared by every page of the app.

The heavy work - fetching real weather, building history, running the
walk-forward backtest, solving rosters - happens once per parameter set and is
then reused across pages. Without this the evidence page alone would rerun a
49-origin backtest on every widget interaction.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from . import (
    calendar_dz,
    demand as demand_mod,
    forecast as forecast_mod,
    labour_dz,
    macro_dz,
    market,
    pipeline,
    sources,
    staffing,
    weather_dz,
)

DEFAULT_PROFILE = "ecom_hub"
DEFAULT_WILAYA = "Alger"
HISTORY_START = "2023-01-01"


# ---------------------------------------------------------------------------
# Session defaults
# ---------------------------------------------------------------------------

def init_state() -> None:
    defaults = {
        "profile_key": DEFAULT_PROFILE,
        "wilaya": DEFAULT_WILAYA,
        "horizon": 14,
        "service_level": 0.80,
        "regular_pool": 80,
        "temp_ceiling": 60,
        "penalty_multiple": float(sources.value("understaffing_penalty_multiple")),
        "allow_network": True,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def current_constraints() -> staffing.SiteConstraints:
    profile = demand_mod.PROFILES[st.session_state["profile_key"]]
    return staffing.SiteConstraints(
        regular_pool=int(st.session_state["regular_pool"]),
        temp_available_per_shift=int(st.session_state["temp_ceiling"]),
        service_level=float(st.session_state["service_level"]),
        role=profile.primary_role,
    )


# ---------------------------------------------------------------------------
# Cached loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl="6h", show_spinner="Loading real Algerian weather and calendar…")
def _load_history(hijri_offset: int, profile_key: str, wilaya: str, allow_network: bool) -> pd.DataFrame:
    return demand_mod.build_history(
        profile_key, wilaya, HISTORY_START, seed=7, allow_network=allow_network
    )


@st.cache_data(ttl="6h", show_spinner="Running walk-forward backtest…")
def _load_backtest(hijri_offset: int, profile_key: str, wilaya: str, horizon: int, allow_network: bool):
    hist = _load_history(hijri_offset, profile_key, wilaya, allow_network)
    return forecast_mod.walk_forward(hist, horizon=horizon, step=28, min_train_days=400)


@st.cache_data(ttl="6h", show_spinner="Scoring rosters against realised demand…")
def _load_evidence(
    hijri_offset: int,
    profile_key: str,
    wilaya: str,
    horizon: int,
    regular_pool: int,
    temp_ceiling: int,
    service_level: float,
    allow_network: bool,
):
    hist = _load_history(hijri_offset, profile_key, wilaya, allow_network)
    bt = _load_backtest(hijri_offset, profile_key, wilaya, horizon, allow_network)
    profile = demand_mod.PROFILES[profile_key]
    cons = staffing.SiteConstraints(
        regular_pool=regular_pool,
        temp_available_per_shift=temp_ceiling,
        service_level=service_level,
        role=profile.primary_role,
    )
    return pipeline.run_evidence(
        profile_key,
        wilaya,
        horizon=horizon,
        constraints=cons,
        allow_network=allow_network,
        history=hist,
        backtest=bt,
    )


@st.cache_data(ttl="6h", show_spinner="Forecasting the next horizon…")
def _load_forward_plan(
    hijri_offset: int,
    profile_key: str,
    wilaya: str,
    horizon: int,
    regular_pool: int,
    temp_ceiling: int,
    service_level: float,
    allow_network: bool,
):
    """Forecast forward from today and build the roster the site should run."""
    hist = _load_history(hijri_offset, profile_key, wilaya, allow_network)
    bt = _load_backtest(hijri_offset, profile_key, wilaya, horizon, allow_network)

    start = hist["date"].max() + pd.Timedelta(days=1)
    fut = demand_mod.future_features(
        profile_key, wilaya, start, days=horizon, allow_network=allow_network
    )
    fc = forecast_mod.forecast_forward(hist, fut, bt.residual_quantiles)

    profile = demand_mod.PROFILES[profile_key]
    cons = staffing.SiteConstraints(
        regular_pool=regular_pool,
        temp_available_per_shift=temp_ceiling,
        service_level=service_level,
        role=profile.primary_role,
    )

    plan = fc.copy()
    # Staff to the service-level band, not the point forecast.
    band = "p90" if service_level >= 0.85 else ("p75" if "p75" in plan.columns else "forecast")
    plan["forecast_for_roster"] = plan[band] if band in plan.columns else plan["forecast"]

    req = staffing.required_workers(
        plan, role=profile.primary_role, volume_col="forecast_for_roster"
    )
    if "is_holiday_int" not in req.columns:
        cal = calendar_dz.calendar_frame(req["date"].min(), req["date"].max())
        req = req.merge(cal[["date", "is_holiday_int"]], on="date", how="left")
    req["is_holiday_int"] = req["is_holiday_int"].fillna(0).astype(int)

    try:
        roster = staffing.optimise_roster(req, cons)
        infeasible = False
    except RuntimeError:
        roster = req.copy()
        for c in ("regular", "overtime", "temp", "total_staff", "supervisors", "planned_cost"):
            roster[c] = 0
        infeasible = True

    return {
        "forecast": fc,
        "roster": roster,
        "infeasible": infeasible,
        "weather_provenance": fut.attrs.get("weather_provenance", "unknown"),
    }


@st.cache_data(ttl="24h", show_spinner=False)
def load_macro(allow_network: bool) -> pd.DataFrame:
    return macro_dz.snapshot(allow_network=allow_network)


@st.cache_data(ttl="24h", show_spinner=False)
def load_calendar_events(days: int = 240) -> pd.DataFrame:
    return calendar_dz.describe_upcoming(days=days)


@st.cache_data(ttl="24h", show_spinner=False)
def load_hijri_check(allow_network: bool) -> pd.DataFrame:
    """Verify our calendar on the dates that matter (Ramadan / the two Aids)."""
    if not allow_network:
        import pandas as _pd
        return _pd.DataFrame(columns=["Event", "Our date", "Reference says", "Agreement"])
    return calendar_dz.verify_key_dates()


@st.cache_data(ttl="6h", show_spinner=False)
def _load_feature_importance(hijri_offset: int, profile_key: str, wilaya: str, allow_network: bool) -> pd.DataFrame:
    hist = _load_history(hijri_offset, profile_key, wilaya, allow_network)
    return forecast_mod.feature_importance(hist)


# ---------------------------------------------------------------------------
# Public wrappers
# ---------------------------------------------------------------------------
# The cached loaders above take the active Hijri offset as their first
# argument purely so it forms part of the cache key: a session that synced
# online (offset applied) must never reuse a history frame built offline on
# the raw tabular calendar. These wrappers inject it so pages never have to
# think about it.

def _off() -> int:
    return calendar_dz.get_default_offset()


def load_history(profile_key, wilaya, allow_network):
    return _load_history(_off(), profile_key, wilaya, allow_network)


def load_backtest(profile_key, wilaya, horizon, allow_network):
    return _load_backtest(_off(), profile_key, wilaya, horizon, allow_network)


def load_evidence(profile_key, wilaya, horizon, regular_pool, temp_ceiling,
                  service_level, allow_network):
    return _load_evidence(_off(), profile_key, wilaya, horizon, regular_pool,
                          temp_ceiling, service_level, allow_network)


def load_forward_plan(profile_key, wilaya, horizon, regular_pool, temp_ceiling,
                      service_level, allow_network):
    return _load_forward_plan(_off(), profile_key, wilaya, horizon, regular_pool,
                              temp_ceiling, service_level, allow_network)


def load_feature_importance(profile_key, wilaya, allow_network):
    return _load_feature_importance(_off(), profile_key, wilaya, allow_network)


# ---------------------------------------------------------------------------
# Airport operations (aviation module)
# ---------------------------------------------------------------------------

@st.cache_data(ttl="6h", show_spinner="Building the ALG flight schedule…")
def load_flight_day(hijri_offset: int, date_iso: str):
    import datetime as _d
    from . import aviation
    d = _d.date.fromisoformat(date_iso)
    return aviation.build_day_schedule(d)


@st.cache_data(ttl="6h", show_spinner=False)
def load_cascade(hijri_offset: int, date_iso: str, severity: float):
    from . import delay_cascade
    sched = load_flight_day(hijri_offset, date_iso)
    return delay_cascade.predict_cascade(sched, severity=severity)


@st.cache_data(ttl="6h", show_spinner=False)
def load_pax_flow(hijri_offset: int, date_iso: str):
    from . import pax_flow
    sched = load_flight_day(hijri_offset, date_iso)
    return pax_flow.compute_flow(sched)


def flight_day(date_iso: str):
    return load_flight_day(_off(), date_iso)


def cascade(date_iso: str, severity: float):
    return load_cascade(_off(), date_iso, severity)


def pax_flow_for(date_iso: str):
    return load_pax_flow(_off(), date_iso)


# ---------------------------------------------------------------------------
# HR: people, requests, attendance, compliance
# ---------------------------------------------------------------------------

@st.cache_data(ttl="6h", show_spinner=False)
def load_workforce(profile_key: str, wilaya: str, headcount: int):
    from . import hr, demand as _d
    role = _d.PROFILES[profile_key].primary_role
    return hr.sample_workforce(role, int(headcount), wilaya)


@st.cache_data(ttl="6h", show_spinner=False)
def load_requests(profile_key: str, wilaya: str, headcount: int):
    from . import attendance
    people = load_workforce(profile_key, wilaya, headcount)
    return attendance.sample_requests(people)


@st.cache_data(ttl="6h", show_spinner=False)
def load_attendance(profile_key: str, wilaya: str, headcount: int, days: int = 14):
    from . import attendance
    people = load_workforce(profile_key, wilaya, headcount)
    return attendance.sample_attendance(people, days=days)


def workforce_headcount() -> int:
    """Site headcount for the HR demo: the permanent pool."""
    return int(st.session_state.get("regular_pool", 80))


def hr_people():
    return load_workforce(st.session_state["profile_key"], st.session_state["wilaya"],
                          workforce_headcount())


def hr_requests():
    return load_requests(st.session_state["profile_key"], st.session_state["wilaya"],
                         workforce_headcount())


def hr_attendance():
    return load_attendance(st.session_state["profile_key"], st.session_state["wilaya"],
                           workforce_headcount())


@st.cache_data(ttl="6h", show_spinner=False)
def load_attrition(profile_key: str, wilaya: str, headcount: int):
    from . import attrition
    people = load_workforce(profile_key, wilaya, headcount)
    records = load_attendance(profile_key, wilaya, headcount)
    return attrition.score_workforce(people, records)


def hr_attrition():
    return load_attrition(st.session_state["profile_key"], st.session_state["wilaya"],
                          workforce_headcount())


# ---------------------------------------------------------------------------
# Small shared UI helpers
# ---------------------------------------------------------------------------

def dzd(n: float, compact: bool = False) -> str:
    """Format a DZD amount."""
    if compact:
        if abs(n) >= 1e9:
            return f"{n / 1e9:,.2f} Md DZD"
        if abs(n) >= 1e6:
            return f"{n / 1e6:,.1f} M DZD"
        if abs(n) >= 1e3:
            return f"{n / 1e3:,.0f} k DZD"
    return f"{n:,.0f} DZD"


def data_badge() -> None:
    """Show where the data on this page comes from."""
    hist_wx = "live" if st.session_state.get("allow_network", True) else "cached/offline"
    st.caption(
        f":material/database: Weather: Open-Meteo ERA5 ({hist_wx}) · "
        f"Calendar: computed Hijri + Algerian civil holidays · "
        f"Macro: World Bank · "
        f"Wages: SNMG {labour_dz.SNMG_MONTHLY:,.0f} DZD + CNAS "
        f"{labour_dz.CNAS_EMPLOYER:.0%} · "
        f"**Operational volumes are simulated** — see Sources."
    )


def inject_theme() -> None:
    """Flat, sharp, trust-blue polish so the app matches the marketing site."""
    st.markdown(
        """
        <style>
        .stApp h1 { color:#16172A; font-weight:800; letter-spacing:-0.02em; }
        .stApp h2, .stApp h3 { color:#16172A; letter-spacing:-0.01em; }
        .stButton > button[kind="primary"], .stDownloadButton > button {
            background:#2563EB; border:1px solid #2563EB; color:#fff; border-radius:0;
            font-weight:700;
            box-shadow:0 2px 0 0 #1D4ED8, 0 8px 18px -8px rgba(37,99,235,.45);
        }
        .stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {
            background:#1D4ED8; border-color:#1D4ED8;
        }
        [data-testid="stMetric"] {
            background:#fff; border:1px solid #E6E6EE; border-radius:0; padding:14px 16px;
            box-shadow:0 1px 2px rgba(28,40,90,.05), 0 10px 22px -14px rgba(28,55,130,.20);
        }
        [data-testid="stSidebar"] > div:first-child { border-top:3px solid #2563EB; }
        .stTabs [aria-selected="true"] { color:#2563EB !important; }
        a, .stMarkdown a { color:#2563EB; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_controls() -> None:
    """The shared control panel, rendered on every page."""
    init_state()
    inject_theme()

    with st.sidebar:
        from . import industry
        st.markdown("### WorkForce.dz")
        if industry.is_tailored():
            st.caption(f":material/storefront: {industry.label()} edition")
        else:
            st.caption("The AI HR platform for Algerian operations")

        profile_labels = {k: p.label for k, p in demand_mod.PROFILES.items()}
        st.selectbox(
            "Operation type",
            options=list(profile_labels),
            format_func=lambda k: profile_labels[k],
            key="profile_key",
        )
        st.selectbox(
            "Wilaya",
            options=list(weather_dz.WILAYAS),
            key="wilaya",
            help="Drives the real weather series used by the model.",
        )

        with st.expander("Planning parameters", icon=":material/tune:"):
            st.slider("Forecast horizon (days)", 7, 21, key="horizon")
            st.select_slider(
                "Service level",
                options=[0.50, 0.75, 0.80, 0.90],
                key="service_level",
                format_func=lambda v: f"p{v * 100:.0f}",
                help="Roster to this demand quantile. Higher means fewer "
                     "missed deliveries and more idle wages.",
            )
            st.number_input("Permanent workforce", 20, 400, key="regular_pool")
            st.number_input("Temp ceiling per shift", 0, 200, key="temp_ceiling")

        with st.expander("Data source", icon=":material/cloud:"):
            st.toggle(
                "Allow live API calls",
                key="allow_network",
                help="Turn off to run entirely from the on-disk cache — "
                     "useful if the venue wifi is unreliable.",
            )
            st.caption(
                "Open-Meteo and World Bank responses are cached to disk on "
                "first fetch, so the app works offline afterwards."
            )
