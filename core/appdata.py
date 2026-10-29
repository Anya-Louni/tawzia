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

import html
from typing import Optional

import pandas as pd
import streamlit as st

from . import (
    brand,
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

@st.cache_data(ttl="7d", persist="disk",
               show_spinner="Loading Algerian weather and calendar…")
def _load_history(hijri_offset: int, profile_key: str, wilaya: str, allow_network: bool) -> pd.DataFrame:
    return demand_mod.build_history(
        profile_key, wilaya, HISTORY_START, seed=7, allow_network=allow_network
    )


@st.cache_data(ttl="7d", persist="disk",
               show_spinner="Walk-forward backtest (computed once)…")
def _load_backtest(hijri_offset: int, profile_key: str, wilaya: str, horizon: int, allow_network: bool):
    hist = _load_history(hijri_offset, profile_key, wilaya, allow_network)
    return forecast_mod.walk_forward(hist, horizon=horizon, step=28, min_train_days=400)


@st.cache_data(ttl="7d", persist="disk",
               show_spinner="Scoring schedules against actual demand…")
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


@st.cache_data(ttl="7d", persist="disk",
               show_spinner="Forecasting the coming days…")
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


@st.cache_data(ttl="7d", persist="disk",
               show_spinner="Estimating expected demand…")
def _load_expected_demand(hijri_offset: int, profile_key: str, wilaya: str,
                          horizon: int, allow_network: bool) -> pd.DataFrame:
    import datetime as _d
    start = _d.date.today() + _d.timedelta(days=1)
    return demand_mod.expected_forward(profile_key, wilaya, start, days=horizon,
                                       allow_network=allow_network)


def expected_demand(profile_key, wilaya, horizon, allow_network):
    """Fast expected forward demand for the sector features (no backtest)."""
    return _load_expected_demand(_off(), profile_key, wilaya, horizon, allow_network)


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


@st.cache_data(ttl="7d", persist="disk", show_spinner=False)
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

@st.cache_data(ttl="7d", persist="disk",
               show_spinner="Building the Algiers flight schedule…")
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
    # The HR demo runs on one fictional company (core/seed_company.py), 140
    # employees on two sites, whatever sector the forecast uses. An imported
    # file replaces it (company_data.people()).
    from . import seed_company
    return list(seed_company.people())


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
    hist_wx = "live" if st.session_state.get("allow_network", True) else "cache/offline"
    st.caption(
        f":material/database: Weather: Open-Meteo ERA5 ({hist_wx}) · "
        f"Calendar: computed Hijri + Algerian public holidays · "
        f"Macro: World Bank · "
        f"Pay: SNMG {labour_dz.SNMG_MONTHLY:,.0f} DZD + CNAS "
        f"{labour_dz.CNAS_EMPLOYER:.1%} · "
        f"**Operational volumes and the demo company are simulated**, see Sources."
    )


# ---------------------------------------------------------------------------
# Visual vocabulary: CSS tokens derived from core/brand.py
# ---------------------------------------------------------------------------
# One source for colours. The `:root` block is the only place a hex code is
# interpolated; the rest of the sheet uses `var(--tz-*)`, so changing the brand
# here changes the whole app.
_ROOT_VARS = f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;600;700;800&display=swap');
        :root {{
            /* Ink and ground: high contrast, nothing washed out. */
            --tz-navy:#0A2540; --tz-navy-2:#173B66; --tz-navy-line:rgba(255,255,255,.16);
            --tz-ink:#0A1628; --tz-muted:#3E4C60; --tz-faint:#5B6A80;
            --tz-ground:#EDF1F6; --tz-surface:#FFFFFF; --tz-surface-2:#F6F8FB;
            --tz-line:#C5D0DE; --tz-line-strong:#9AABC2;
            /* Action and focus. */
            --tz-blue:{brand.BLUE}; --tz-blue-d:{brand.BLUE_DARK}; --tz-sky:{brand.SKY};
            --tz-wash:#E3EEFB; --tz-mid:{brand.BLUE_MID};
            /* One colour per agent, each 4.5:1 or better on white. */
            --tz-a-presence:#0B57A8; --tz-a-paie:#6D28D9; --tz-a-decl:#B45309;
            --tz-a-conf:#B91C1C; --tz-a-ret:#15803D; --tz-a-rec:#0F766E;
            --tz-a-guichet:#334155; --tz-a-onb:#4338CA; --tz-a-plan:#0E7490;
            /* Status, always paired with a word. */
            --tz-ok:#15803D; --tz-ok-wash:#DCFCE7; --tz-warn:#B45309; --tz-warn-wash:#FEF3C7;
            --tz-danger:#B91C1C; --tz-danger-wash:#FEE2E2;
            /* Depth: sharp corners, clay underneath. A lit top edge, a shaded
               bottom edge inside, and a soft lift outside, so every surface
               reads as a moulded slab rather than a flat box. */
            --tz-shadow:inset 0 2px 0 rgba(255,255,255,.95), inset 0 -4px 0 rgba(10,37,64,.07),
                        0 2px 3px rgba(10,22,40,.07), 0 16px 32px -14px rgba(10,37,64,.30);
            --tz-shadow-lift:inset 0 2px 0 rgba(255,255,255,.95), inset 0 -4px 0 rgba(10,37,64,.09),
                        0 3px 5px rgba(10,22,40,.09), 0 26px 44px -18px rgba(10,37,64,.38);
            --tz-press:inset 0 2px 5px rgba(4,20,45,.35);
            --tz-r-card:8px; --tz-r-ctrl:3px; --tz-r-chip:3px;
        }}
"""


def stat_card(label: str, value: str, delta: str | None = None,
              direction: str = "flat", caption: str | None = None) -> None:
    """
    Une tuile de chiffre : libellé, valeur en grand, pastille d'évolution.

    `direction` vaut "up", "down" ou "flat" et ne décide que de la couleur de
    la pastille. Le sens , une hausse d'absences est une mauvaise nouvelle ,
    appartient à l'appelant, qui sait ce que le chiffre veut dire.
    """
    chip = (f'<span class="tz-chip {direction}">{delta}</span>'
            if delta else "")
    cap = f'<div class="tz-stat-c">{caption}</div>' if caption else ""
    st.markdown(
        f'<div class="tz-stat"><div class="tz-stat-l">{label}</div>'
        f'<div class="tz-stat-row"><span class="tz-stat-v">{value}</span>{chip}'
        f'</div>{cap}</div>',
        unsafe_allow_html=True,
    )


def card_head(title: str, meta: str | None = None) -> None:
    """Le titre d'une carte, avec sa mention secondaire alignée à droite."""
    right = f'<span class="tz-head-m">{meta}</span>' if meta else ""
    st.markdown(
        f'<div class="tz-head"><span class="tz-head-t">{title}</span>{right}</div>',
        unsafe_allow_html=True,
    )


def legend(items: list[tuple[str, str]]) -> None:
    """La légende d'un graphique : pastille de couleur + libellé."""
    parts = "".join(
        f'<span><i style="background:{colour}"></i>{name}</span>'
        for name, colour in items
    )
    st.markdown(f'<div class="tz-leg">{parts}</div>', unsafe_allow_html=True)


def _initials(name: str) -> str:
    bits = [b for b in str(name).replace("-", " ").split() if b]
    return (bits[0][0] + (bits[-1][0] if len(bits) > 1 else "")).upper() or "?"


def list_rows(rows: list[dict], empty: str = "Nothing to report.",
              avatars: bool = True, wrap: bool = False) -> None:
    """
    Une liste de lignes « avatar, titre, sous-titre, valeur à droite ».

    Chaque ligne : {"name", "sub", "meta", "hot": bool}. `hot` passe l'avatar et
    la valeur en rouge , réservé à ce qui demande une action aujourd'hui.

    `avatars=False` retire la pastille d'initiales : les initiales n'ont de sens
    que pour une personne, et « OD » devant « Ouverture de la saison » ne veut
    rien dire. `wrap=True` laisse le titre passer à la ligne au lieu d'être
    tronqué, pour les libellés longs qui ne sont pas des noms.
    """
    if not rows:
        st.markdown(f'<div class="tz-empty">{empty}</div>',
                    unsafe_allow_html=True)
        return
    cls = "tz-row" + (" wrap" if wrap else "")
    out = []
    for r in rows:
        hot = " hot" if r.get("hot") else ""
        name = html.escape(str(r.get("name", "")))
        sub = html.escape(str(r.get("sub", "")))
        meta = html.escape(str(r.get("meta", "")))
        av = (f'<div class="tz-av{hot}">{html.escape(_initials(name))}</div>'
              if avatars else "")
        out.append(
            f'<div class="{cls}">{av}'
            f'<div class="tz-row-txt"><div class="tz-row-t">{name}</div>'
            f'<div class="tz-row-s">{sub}</div></div>'
            f'<div class="tz-row-m{hot}">{meta}</div></div>'
        )
    st.markdown("".join(out), unsafe_allow_html=True)


def inject_theme() -> None:
    """
    The visual layer: sharp, high contrast, action first.

    A navy command band, white worksheets with a visible edge, square
    controls, one colour per agent. The single primary action on a card is
    solid blue and sinks when pressed. Tokens live in `_ROOT_VARS`; DESIGN.md
    describes the system.
    """
    st.markdown(
        _ROOT_VARS + """
        /* ==================================================================
           Sharp, high-contrast, action first. A navy command band, white
           worksheets with a visible edge, square controls, one colour per
           agent. The single primary action on a card is solid blue and
           presses in when clicked.
           ================================================================== */
        html, body, [data-testid="stApp"] {
            font-family:'Manrope','Noto Sans Arabic','Segoe UI',system-ui,sans-serif;
        }
        [data-testid="stApp"] { background:var(--tz-ground); color:var(--tz-ink); }
        [data-testid="stHeader"] { background:transparent; }
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display:none !important; }
        [data-testid="stMainBlockContainer"] { padding:.6rem 2.5rem 4rem; max-width:1440px; }
        [data-testid="stMain"] h1 { padding:.35rem 0 .15rem !important; font-size:2.15rem !important; letter-spacing:-.025em; }
        [data-testid="stMain"] [data-testid="stCaptionContainer"] { font-size:14px; color:var(--tz-muted); }

        ::selection { background:rgba(108,190,245,.5); color:var(--tz-ink); }
        input, textarea { caret-color:var(--tz-blue); }
        * { scrollbar-width:thin; scrollbar-color:var(--tz-line-strong) transparent; }
        ::-webkit-scrollbar { width:10px; height:10px; }
        ::-webkit-scrollbar-thumb { background:var(--tz-line-strong); border:3px solid var(--tz-ground); }
        [data-testid="stMain"] a { text-underline-offset:3px; }
        [data-testid="stMetricValue"], .tz-stat-v, .tz-row-m, .tz-num,
        [data-testid="stDataFrame"] { font-variant-numeric:tabular-nums; }

        /* ---- The navy command band --------------------------------------- */
        .st-key-wf_topbar {
            position:sticky; top:.5rem; z-index:60;
            background:var(--tz-navy) !important; color:#FFFFFF;
            border:1px solid var(--tz-navy); border-radius:var(--tz-r-card);
            padding:14px 18px 12px; margin-bottom:12px;
            box-shadow:0 14px 34px -18px rgba(10,37,64,.7);
        }
        .tz-topbrand { display:flex; flex-direction:column; gap:2px; padding-left:2px; }
        .tz-topsub { font-size:11px; font-weight:700; color:#B9C8DC; }

        /* Ask Tawzia: a white field, the brightest thing in the band. */
        .st-key-wf_ask [data-baseweb="input"] {
            background:#FFFFFF !important; border:2px solid #FFFFFF !important;
            border-radius:var(--tz-r-ctrl) !important; min-height:46px !important;
        }
        .st-key-wf_ask [data-baseweb="input"] input {
            background:transparent !important; color:var(--tz-ink) !important;
            font-size:14px; font-weight:600;
        }
        .st-key-wf_ask [data-baseweb="input"] input::placeholder { color:var(--tz-faint) !important; opacity:1; }
        .st-key-wf_ask [data-baseweb="input"]:focus-within {
            border-color:var(--tz-sky) !important; box-shadow:0 0 0 3px rgba(108,190,245,.45);
        }
        .st-key-wf_ask [data-testid="stTextInputRootElement"] svg,
        .st-key-wf_ask [data-baseweb="input"] span { color:var(--tz-blue) !important; }

        /* Context controls inside the band: outlined, light on navy. */
        .st-key-wf_controls [data-testid="stPopover"] > div > button,
        .st-key-wf_controls [data-testid="stTooltipHoverTarget"] > button {
            border-radius:var(--tz-r-ctrl) !important; min-height:44px !important;
            background:transparent !important; border:1px solid var(--tz-navy-line) !important;
            color:#FFFFFF !important; font-size:12.5px !important; font-weight:700 !important;
            padding:0 12px !important; box-shadow:none !important;
        }
        .st-key-wf_controls [data-testid="stPopover"] button *,
        .st-key-wf_controls [data-testid="stPopover"] button { white-space:nowrap !important; color:#FFFFFF !important; }
        .st-key-wf_controls [data-testid="stPopover"] > div > button:hover,
        .st-key-wf_controls [data-testid="stTooltipHoverTarget"] > button:hover {
            background:var(--tz-navy-2) !important; border-color:rgba(255,255,255,.35) !important;
        }
        .st-key-wf_controls [data-testid="stButtonGroup"] [data-baseweb="button-group"] {
            background:transparent; border:1px solid var(--tz-navy-line); box-shadow:none;
        }
        .st-key-wf_controls [data-testid="stButtonGroup"] button { color:#C9D6E8 !important; }
        .st-key-wf_controls [data-testid="stButtonGroup"] button[aria-checked="true"],
        .st-key-wf_controls [data-testid="stButtonGroup"] button[kind*="Active"] {
            background:#FFFFFF !important; color:var(--tz-navy) !important; box-shadow:none !important;
        }
        .st-key-wf_controls [data-testid="stButtonGroup"] button[aria-checked="true"] p,
        .st-key-wf_controls [data-testid="stButtonGroup"] button[kind*="Active"] p { color:var(--tz-navy) !important; }
        .st-key-wf_controls [data-testid="stButtonGroup"] button { padding:0 12px !important; min-height:40px !important; min-width:38px !important; }
        .st-key-wf_controls [data-testid="stHorizontalBlock"] { align-items:center !important; }
        .st-key-wf_controls [data-testid="stButtonGroup"] { display:flex; align-items:center; }

        /* The six spaces: tabs on the band, the open one is a white slab. */
        .st-key-wf_sections { margin-top:14px; border-top:1px solid var(--tz-navy-line); padding-top:12px; }
        .st-key-wf_sections [data-testid="stHorizontalBlock"] { gap:6px !important; }
        .st-key-wf_topbar .st-key-wf_sections .stButton button {
            background:transparent !important; border:1px solid transparent !important;
            color:#C9D6E8 !important; font-weight:700 !important;
            min-height:46px !important; height:46px !important; border-radius:var(--tz-r-ctrl) !important;
            padding:6px 10px !important; font-size:13.5px !important; line-height:1.2 !important;
            white-space:normal !important; box-shadow:none !important;
            transition:background .14s ease, color .14s ease, border-color .14s ease;
        }
        .st-key-wf_topbar .st-key-wf_sections .stButton button p { color:inherit !important; font-weight:inherit !important; }
        .st-key-wf_topbar .st-key-wf_sections .stButton button:hover {
            color:#FFFFFF !important; background:var(--tz-navy-2) !important;
            border-color:var(--tz-navy-line) !important;
        }
        .st-key-wf_topbar .st-key-wf_sec_active .stButton button,
        .st-key-wf_topbar .st-key-wf_sec_active .stButton button:hover {
            background:#FFFFFF !important; color:var(--tz-navy) !important;
            border-color:#FFFFFF !important; box-shadow:inset 0 -3px 0 var(--tz-sky) !important;
        }

        /* Sub-screens: compact tabs, the current one underlined in sky. */
        .st-key-wf_subnav { margin-top:10px; flex-wrap:wrap; gap:4px !important; }
        .st-key-wf_subnav [data-testid="stPageLink"] a {
            border-radius:var(--tz-r-ctrl); padding:6px 12px; border:1px solid transparent;
        }
        .st-key-wf_subnav [data-testid="stPageLink"] a:hover { background:var(--tz-navy-2); }
        .st-key-wf_subnav [data-testid="stPageLink"] p { font-size:13.5px; font-weight:700; color:#C9D6E8 !important; }
        .st-key-wf_subnav [data-testid="stPageLink"] span { color:#C9D6E8 !important; }
        .tz-sub-on {
            display:inline-block; padding:6px 12px; color:#FFFFFF;
            border-bottom:3px solid var(--tz-sky); font-size:13.5px; font-weight:800; line-height:1.5;
        }

        /* ---- Type -------------------------------------------------------- */
        [data-testid="stMain"] h1 { color:var(--tz-ink); letter-spacing:-.03em; font-weight:800; }
        [data-testid="stMain"] h2, [data-testid="stMain"] h3 { color:var(--tz-ink); letter-spacing:-.018em; font-weight:800; }
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color:var(--tz-muted) !important; }
        [data-testid="stMain"] p { line-height:1.55; }

        /* Page header: no box, a strong title and one sentence. */
        .tz-hero { display:flex; align-items:flex-end; justify-content:space-between; gap:22px;
                   flex-wrap:wrap; padding:2px 2px 6px; margin-bottom:14px; }
        .tz-hero-h { font-size:32px; font-weight:800; letter-spacing:-.035em; color:var(--tz-ink); line-height:1.1; margin:0; }
        .tz-hero-s { font-size:15px; color:var(--tz-muted); margin-top:8px; line-height:1.55; max-width:72ch; }
        .tz-hero-s b { color:var(--tz-blue); font-weight:800; }
        .tz-hero-r { display:flex; gap:9px; flex-wrap:wrap; }

        /* ---- Worksheets: white, edged, lifted ---------------------------- */
        [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:not([class*="st-key-"]) {
            background:var(--tz-surface); border:1px solid var(--tz-line) !important;
            border-radius:var(--tz-r-card); padding:22px 24px !important; box-shadow:var(--tz-shadow);
            transition:box-shadow .2s ease, border-color .2s ease;
        }
        [data-testid="stMain"] [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:not([class*="st-key-"]):hover {
            box-shadow:var(--tz-shadow-lift); border-color:var(--tz-line-strong) !important;
        }
        [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:not([class*="st-key-"])
            [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:not([class*="st-key-"]) {
            background:var(--tz-surface-2); box-shadow:none; border-radius:6px;
        }

        /* Stat tiles: one accent per position, a tinted wash and a soft disc, so a
           row of numbers reads as four distinct facts rather than four white boxes. */
        [data-testid="stMetric"], .tz-stat {
            --acc:var(--tz-a-presence);
            position:relative; overflow:hidden; height:100%;
            background:linear-gradient(155deg, color-mix(in srgb, var(--acc) 10%, #FFFFFF) 0%, #FFFFFF 58%);
            border:1px solid var(--tz-line); border-top:4px solid var(--acc) !important;
            border-radius:var(--tz-r-card); padding:20px 22px 18px !important; box-shadow:var(--tz-shadow);
        }
        [data-testid="stMetric"]::after, .tz-stat::after {
            content:""; position:absolute; right:-34px; top:-34px; width:110px; height:110px;
            border-radius:50%; background:color-mix(in srgb, var(--acc) 13%, transparent); pointer-events:none;
        }
        [data-testid="stElementContainer"]:nth-child(4n+2) > [data-testid="stMetric"],
        [data-testid="stColumn"]:nth-child(4n+2) [data-testid="stMetric"],
        [data-testid="stColumn"]:nth-child(4n+2) .tz-stat { --acc:var(--tz-a-rec); }
        [data-testid="stElementContainer"]:nth-child(4n+3) > [data-testid="stMetric"],
        [data-testid="stColumn"]:nth-child(4n+3) [data-testid="stMetric"],
        [data-testid="stColumn"]:nth-child(4n+3) .tz-stat { --acc:var(--tz-a-decl); }
        [data-testid="stElementContainer"]:nth-child(4n) > [data-testid="stMetric"],
        [data-testid="stColumn"]:nth-child(4n) [data-testid="stMetric"],
        [data-testid="stColumn"]:nth-child(4n) .tz-stat { --acc:var(--tz-a-paie); }
        /* In a horizontal row every tile takes an equal share. */
        [data-testid="stElementContainer"]:has(> [data-testid="stMetric"]) { flex:1 1 0 !important; min-width:170px; width:auto !important; }
        [data-testid="stMetric"] { min-height:118px; }
        [data-testid="stMetricValue"] { font-weight:800; letter-spacing:-.035em; color:var(--tz-navy); }
        [data-testid="stMetricValue"] > div { font-size:2.35rem !important; line-height:1.1; }
        [data-testid="stMetricLabel"] p { color:color-mix(in srgb, var(--acc) 70%, var(--tz-ink)) !important; font-weight:800; font-size:12px;
                                          text-transform:uppercase; letter-spacing:.06em; }
        .tz-stat { display:flex; flex-direction:column; gap:8px; min-height:124px; }
        .tz-stat-l { font-size:12px; font-weight:800; color:color-mix(in srgb, var(--acc) 70%, var(--tz-ink)); text-transform:uppercase; letter-spacing:.06em; }
        .tz-stat-row { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
        .tz-stat-v { font-size:38px; font-weight:800; letter-spacing:-.035em; color:var(--tz-navy); line-height:1.05; }
        .tz-stat-c { font-size:12.5px; color:var(--tz-muted); line-height:1.35; }
        .tz-chip { font-size:11.5px; font-weight:800; padding:3px 8px; border-radius:var(--tz-r-chip); white-space:nowrap; }
        .tz-chip.up { background:var(--tz-wash); color:var(--tz-blue-d); }
        .tz-chip.down { background:var(--tz-danger-wash); color:var(--tz-danger); }
        .tz-chip.flat { background:var(--tz-surface-2); color:var(--tz-muted); border:1px solid var(--tz-line); }

        /* ---- Lists, card heads, legends ----------------------------------- */
        .tz-head { display:flex; align-items:baseline; justify-content:space-between; gap:12px; margin:0 0 8px; }
        .tz-head-t { font-size:16px; font-weight:800; color:var(--tz-ink); letter-spacing:-.015em; }
        .tz-head-m { font-size:12px; font-weight:800; color:var(--tz-blue-d); background:var(--tz-wash);
                     padding:2px 8px; border-radius:var(--tz-r-chip); }
        .tz-row { display:flex; align-items:center; gap:12px; padding:9px 6px; transition:background .14s ease; }
        .tz-row + .tz-row { border-top:1px solid var(--tz-line); }
        .tz-row:hover { background:var(--tz-surface-2); }
        .tz-av { width:34px; height:34px; border-radius:var(--tz-r-ctrl); flex:none; display:grid; place-items:center;
                 font-size:11.5px; font-weight:800; background:var(--tz-wash); color:var(--tz-blue-d); }
        .tz-av.hot { background:var(--tz-danger-wash); color:var(--tz-danger); }
        .tz-row-txt { min-width:0; }
        .tz-row-t { font-size:13.5px; font-weight:700; color:var(--tz-ink); line-height:1.35;
                    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .tz-row.wrap .tz-row-t { white-space:normal; overflow:visible; }
        .tz-row-s { font-size:12px; color:var(--tz-muted); line-height:1.4; }
        .tz-row-m { margin-inline-start:auto; flex:none; text-align:end; font-size:11.5px; font-weight:800; color:var(--tz-muted); }
        .tz-row-m.hot { color:var(--tz-danger); }
        .tz-empty { font-size:13px; color:var(--tz-muted); padding:12px 4px; }
        .tz-leg { display:flex; gap:15px; flex-wrap:wrap; font-size:12px; font-weight:700; color:var(--tz-muted); margin:2px 0 6px; }
        .tz-leg i { width:10px; height:10px; display:inline-block; margin-inline-end:6px; }

        /* ---- Buttons: square, solid, decisive ----------------------------- */
        [data-testid="stMain"] .stButton button, [data-testid="stDialog"] .stButton button,
        .stDownloadButton button, [data-testid="stPopover"] > div > button,
        [data-testid="stPopover"] [data-testid="stTooltipHoverTarget"] > button,
        [data-testid="stFormSubmitButton"] button {
            min-height:44px; padding:0 20px; border-radius:var(--tz-r-ctrl);
            font-weight:800; font-size:14px; letter-spacing:.005em;
            transition:background .14s ease, color .14s ease, border-color .14s ease, box-shadow .14s ease;
        }
        .stButton > button[kind="secondary"], .stDownloadButton > button,
        [data-testid="stPopover"] > div > button,
        [data-testid="stPopover"] [data-testid="stTooltipHoverTarget"] > button {
            background:var(--tz-surface); border:1.5px solid var(--tz-ink); color:var(--tz-ink);
            box-shadow:inset 0 -3px 0 rgba(10,37,64,.08), 0 2px 3px rgba(10,22,40,.06);
        }
        .stButton > button[kind="secondary"]:hover, .stDownloadButton > button:hover,
        [data-testid="stPopover"] > div > button:hover {
            background:var(--tz-ink); color:#FFFFFF; border-color:var(--tz-ink);
        }
        .stButton > button[kind="secondary"]:hover p, .stDownloadButton > button:hover p { color:#FFFFFF; }
        .stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button {
            background:linear-gradient(180deg, #1466BF 0%, var(--tz-blue) 100%); border:1.5px solid var(--tz-blue); color:#FFFFFF;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.28), inset 0 -3px 0 rgba(4,28,60,.30),
                       0 2px 3px rgba(10,22,40,.2), 0 10px 20px -10px rgba(11,87,168,.85);
        }
        .stButton > button[kind="primary"] p, [data-testid="stFormSubmitButton"] > button p { color:#FFFFFF; }
        .stButton > button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] > button:hover {
            background:var(--tz-blue-d); border-color:var(--tz-blue-d); color:#FFFFFF;
        }
        /* Press to sign: the button sinks the instant it is pressed. */
        .stButton > button:active, .stDownloadButton > button:active, [data-testid="stFormSubmitButton"] > button:active {
            transform:translateY(1px); box-shadow:var(--tz-press) !important; transition-duration:0s !important;
        }
        .stButton > button:disabled, .stButton > button:disabled:hover {
            opacity:.45; box-shadow:none; background:var(--tz-surface-2); color:var(--tz-muted); border-color:var(--tz-line);
        }
        [data-testid="stMain"] [data-testid="stPageLink"] a { border-radius:var(--tz-r-ctrl); padding:8px 10px; }
        [data-testid="stMain"] [data-testid="stPageLink"] a:hover { background:var(--tz-wash); }
        [data-testid="stMain"] [data-testid="stPageLink"] p { color:var(--tz-blue-d); font-weight:800; }

        /* ---- Fields --------------------------------------------------------- */
        [data-testid="stMain"] [data-baseweb="input"], [data-testid="stMain"] [data-baseweb="select"] > div,
        [data-testid="stMain"] [data-baseweb="textarea"], [data-testid="stMain"] [data-baseweb="base-input"] {
            min-height:44px; border-radius:var(--tz-r-ctrl) !important; background:var(--tz-surface) !important;
            border:1.5px solid var(--tz-line-strong) !important;
        }
        [data-testid="stMain"] [data-baseweb="input"] input, [data-testid="stMain"] [data-baseweb="textarea"] textarea { background:transparent !important; }
        [data-testid="stChatInput"] { border-radius:var(--tz-r-ctrl) !important; border:1.5px solid var(--tz-line-strong) !important; background:var(--tz-surface) !important; }
        [data-testid="stFileUploaderDropzone"] { border:2px dashed var(--tz-line-strong) !important; border-radius:var(--tz-r-card) !important; background:var(--tz-surface) !important; }

        /* Focus: a 3px blue ring on every control (6:1). */
        .stButton > button:focus-visible, .stDownloadButton > button:focus-visible,
        [data-testid="stPopover"] button:focus-visible, [data-testid="stButtonGroup"] button:focus-visible,
        .stTabs [data-baseweb="tab"]:focus-visible, [data-testid="stMain"] a:focus-visible, summary:focus-visible {
            outline:3px solid var(--tz-blue) !important; outline-offset:3px;
        }
        .st-key-wf_topbar .stButton button:focus-visible, .st-key-wf_topbar a:focus-visible,
        .st-key-wf_topbar [data-testid="stPopover"] button:focus-visible { outline-color:var(--tz-sky) !important; }
        [data-testid="stMain"] [data-baseweb="select"]:focus-within > div,
        [data-testid="stMain"] [data-baseweb="input"]:focus-within { border-color:var(--tz-blue) !important; box-shadow:0 0 0 2px var(--tz-blue) !important; }

        /* ---- Segmented controls and tabs ---------------------------------- */
        [data-testid="stButtonGroup"] [data-baseweb="button-group"], .stTabs [data-baseweb="tab-list"] {
            background:var(--tz-surface); border:1.5px solid var(--tz-line-strong); border-radius:var(--tz-r-ctrl);
            padding:3px; gap:3px; width:fit-content; max-width:100%;
        }
        [data-testid="stButtonGroup"] button {
            border-radius:2px !important; border:0 !important; background:transparent !important;
            font-weight:800 !important; min-height:36px; color:var(--tz-muted) !important; padding:0 12px !important; min-width:0 !important;
        }
        [data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[kind*="Active"],
        .stTabs [aria-selected="true"] {
            background:var(--tz-ink) !important; color:#FFFFFF !important; box-shadow:none !important;
        }
        [data-testid="stButtonGroup"] button[aria-checked="true"] p, .stTabs [aria-selected="true"] p { color:#FFFFFF !important; }
        .stTabs [data-baseweb="tab"], [data-testid="stTabs"] [role="tab"] { border-radius:2px !important; padding:8px 18px !important; font-weight:800; color:var(--tz-muted); background:transparent; height:auto !important; }
        [data-testid="stTabs"] [role="tablist"] { background:var(--tz-surface); border:1.5px solid var(--tz-line-strong); border-radius:var(--tz-r-ctrl);
            padding:3px; gap:3px; width:fit-content; max-width:100%; margin-bottom:14px; }
        [data-testid="stTabs"] [role="tab"][aria-selected="true"] { background:var(--tz-ink) !important; }
        [data-testid="stTabs"] [role="tab"][aria-selected="true"] p { color:#FFFFFF !important; }
        .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }

        /* ---- Alerts, expanders, tables, chat -------------------------------- */
        [data-testid="stAlert"] { border-radius:var(--tz-r-card); border:1px solid var(--tz-line); }
        [data-testid="stExpander"] details { border-radius:var(--tz-r-ctrl) !important; border:1px solid var(--tz-line) !important; background:var(--tz-surface-2) !important; }
        [data-testid="stExpander"] summary { font-weight:800; color:var(--tz-ink); }
        [data-testid="stExpander"] summary:hover { color:var(--tz-blue); }
        [data-testid="stDataFrame"], [data-testid="stTable"] { border-radius:var(--tz-r-card); border:1px solid var(--tz-line); overflow:hidden; }
        [data-testid="stChatMessage"] { background:var(--tz-surface-2); border-radius:var(--tz-r-card); padding:12px 14px; border:1px solid var(--tz-line); }
        [data-testid="stMain"] hr { border-color:var(--tz-line); opacity:1; }

        .tz-meter { height:8px; background:var(--tz-surface-2); border:1px solid var(--tz-line); overflow:hidden; margin:10px 0 4px; }
        .tz-meter span { display:block; height:100%; background:var(--tz-blue); }
        .tz-meter-l { display:flex; justify-content:space-between; font-size:12px; color:var(--tz-muted); font-weight:700; }

        /* The employee's phone. */
        .st-key-tz_phone { max-width:380px; margin:0 auto; border-radius:28px !important; border:10px solid var(--tz-navy) !important;
                           padding:18px 14px !important; background:var(--tz-surface); box-shadow:var(--tz-shadow-lift); }
        [data-testid="stDialog"] div[role="dialog"] { border:1px solid var(--tz-line); border-radius:var(--tz-r-card); box-shadow:0 30px 70px -24px rgba(10,22,40,.5); }

        /* ---- Inbox: the action-first layout ---------------------------------- */
        .tz-today { display:grid; grid-template-columns:minmax(0,1.25fr) minmax(0,1fr); gap:0;
                    background:var(--tz-surface); border:1px solid var(--tz-line); border-radius:var(--tz-r-card);
                    box-shadow:var(--tz-shadow); overflow:hidden; margin-bottom:18px; }
        .tz-today-main { padding:28px 30px 26px; display:flex; flex-direction:column; justify-content:center; gap:4px; }
        .tz-today-k { font-size:13px; font-weight:800; color:var(--tz-blue-d); }
        .tz-today-h { font-size:34px; line-height:1.08; font-weight:800; letter-spacing:-.035em; color:var(--tz-ink); margin:6px 0 8px; }
        .tz-today-h em { font-style:normal; color:var(--tz-blue); }
        .tz-today-s { font-size:15px; color:var(--tz-muted); line-height:1.5; max-width:56ch; }
        .tz-prog { margin-top:16px; }
        .tz-prog-bar { display:flex; height:12px; border:1px solid var(--tz-line-strong); background:var(--tz-surface-2); }
        .tz-prog-bar span { display:block; height:100%; }
        .tz-prog-l { display:flex; justify-content:space-between; margin-top:7px; font-size:12.5px; font-weight:800; color:var(--tz-muted); }
        .tz-today-viz { background:var(--tz-navy); color:#FFFFFF; padding:18px 20px; display:flex; flex-direction:column; gap:10px; }
        .tz-today-viz h4 { margin:0; font-size:13px; font-weight:800; color:#B9C8DC; letter-spacing:.02em; }
        .tz-agent-bar { display:grid; grid-template-columns:112px 1fr 38px; align-items:center; gap:10px; font-size:12.5px; font-weight:700; }
        .tz-agent-bar i { display:block; height:10px; min-width:3px; }
        .tz-agent-bar b { text-align:end; font-variant-numeric:tabular-nums; }
        .tz-agent-bar span { color:#E2EAF4; }
        .tz-card-top { display:flex; gap:12px; align-items:flex-start; }
        .tz-agent { width:38px; height:38px; flex:none; display:grid; place-items:center; color:#FFFFFF;
                    border-radius:var(--tz-r-ctrl); font-size:13px; font-weight:800; }
        .tz-card-t { font-size:15.5px; font-weight:800; color:var(--tz-ink); line-height:1.35; }
        .tz-card-m { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:3px; }
        .tz-tag { font-size:11px; font-weight:800; padding:2px 7px; border-radius:var(--tz-r-chip); letter-spacing:.02em; }
        .tz-tag.urgent { background:var(--tz-danger); color:#FFFFFF; }
        .tz-tag.money { background:var(--tz-ok-wash); color:var(--tz-ok); }
        .tz-tag.agent { background:var(--tz-surface-2); color:var(--tz-ink); border:1px solid var(--tz-line); }
        .tz-why { font-size:13.5px; color:var(--tz-muted); line-height:1.5; margin:8px 0 4px; }
        .tz-why b { color:var(--tz-ink); }
        .tz-law { font-size:12.5px; color:var(--tz-ink); font-weight:700; display:flex; gap:6px; align-items:center; }
        .tz-law::before { content:""; width:8px; height:8px; background:var(--tz-a-decl); display:inline-block; }
        .tz-deadline { background:var(--tz-warn-wash); border:1px solid #F3C969; border-radius:var(--tz-r-card); padding:14px 16px; }
        .tz-deadline b { display:block; font-size:22px; font-weight:800; color:var(--tz-ink); margin:2px 0; }
        .tz-deadline span { font-size:12.5px; font-weight:800; color:var(--tz-warn); }
        .tz-deadline.late { background:var(--tz-danger-wash); border-color:#F5A3A3; }
        .tz-deadline.late span { color:var(--tz-danger); }

        @keyframes tz-rise { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
        @keyframes tz-fill { from { transform:scaleX(0); } }
        .tz-today, [data-testid="stMain"] [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:not([class*="st-key-"]) {
            animation:tz-rise .3s cubic-bezier(.16,1,.3,1) both;
        }
        .tz-prog-bar span, .tz-agent-bar i { transform-origin:left; animation:tz-fill .7s cubic-bezier(.16,1,.3,1) both; }
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after { animation-duration:.001ms !important; animation-iteration-count:1 !important; transition-duration:.001ms !important; }
        }

        @media (max-width: 760px) {
            .st-key-wf_topbar { position:static; padding:12px; }
            .tz-hero-h, .tz-today-h { font-size:26px; }
            .tz-stat-v { font-size:28px; }
            .tz-today { grid-template-columns:1fr; }
            .st-key-wf_sections [data-testid="stHorizontalBlock"], .st-key-wf_controls [data-testid="stHorizontalBlock"] {
                flex-direction:row !important; flex-wrap:wrap !important; gap:6px !important;
            }
            .st-key-wf_sections [data-testid="stColumn"], .st-key-wf_controls [data-testid="stColumn"] {
                flex:1 1 45% !important; min-width:0 !important; width:auto !important;
            }
            .st-key-wf_topbar .st-key-wf_sections .stButton button {
                font-size:12.5px !important; padding:4px 8px !important; word-break:keep-all !important; overflow-wrap:normal !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_controls() -> None:
    """
    Point d'entrée conservé : les 26 pages l'appellent en première ligne.

    La navigation et les réglages sont passés dans le bandeau supérieur, rendu
    par `page_header()` depuis `dashboard.py`. Il ne reste ici que la garantie
    que l'état et le thème existent, quel que soit l'ordre d'exécution.
    """
    init_state()
    inject_theme()
