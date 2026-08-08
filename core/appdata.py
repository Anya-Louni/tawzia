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

@st.cache_data(ttl="7d", persist="disk",
               show_spinner="Chargement de la météo et du calendrier algériens…")
def _load_history(hijri_offset: int, profile_key: str, wilaya: str, allow_network: bool) -> pd.DataFrame:
    return demand_mod.build_history(
        profile_key, wilaya, HISTORY_START, seed=7, allow_network=allow_network
    )


@st.cache_data(ttl="7d", persist="disk",
               show_spinner="Backtest walk-forward (calculé une seule fois)…")
def _load_backtest(hijri_offset: int, profile_key: str, wilaya: str, horizon: int, allow_network: bool):
    hist = _load_history(hijri_offset, profile_key, wilaya, allow_network)
    return forecast_mod.walk_forward(hist, horizon=horizon, step=28, min_train_days=400)


@st.cache_data(ttl="7d", persist="disk",
               show_spinner="Évaluation des plannings sur la demande réalisée…")
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
               show_spinner="Prévision de l'horizon à venir…")
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
               show_spinner="Estimation de la demande attendue…")
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
               show_spinner="Construction du programme de vols d'Alger…")
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
    hist_wx = "en direct" if st.session_state.get("allow_network", True) else "cache/hors-ligne"
    st.caption(
        f":material/database: Météo : Open-Meteo ERA5 ({hist_wx}) · "
        f"Calendrier : Hijri calculé + jours fériés algériens · "
        f"Macro : Banque mondiale · "
        f"Salaires : SNMG {labour_dz.SNMG_MONTHLY:,.0f} DZD + CNAS "
        f"{labour_dz.CNAS_EMPLOYER:.0%} · "
        f"**Les volumes opérationnels sont simulés** , voir Sources."
    )


def inject_theme() -> None:
    """
    La couche visuelle, par-dessus le thème de .streamlit/config.toml.

    THESIS , l'app se lit comme un registre public algérien, pas comme un
    dashboard SaaS : réglé, équerré, lisible au vidéoprojecteur. Elle refuse
    l'arrangement qu'elle avait avant (dégradé indigo-violet), parce qu'un
    public qui évalue une promesse de conformité et de paie escompte la
    décoration.

    OWN-WORLD , fond ardoise #F1F5F9, surfaces blanches cerclées d'un trait
    1px #CBD5E1 toujours visible, une seule couleur d'action (#1355C4) et un
    navy (#0A2540) pour les titres et les chiffres. Aucun dégradé, nulle part.

    FIRST VIEWPORT , barre de navigation navy en haut, bande de contexte sous
    elle, puis l'espace de travail. Pas de rail latéral : les sept sections
    sont l'architecture entière et se voient d'un coup d'œil.

    FORM , le contraste fait le design : le fond est ardoise pour qu'une carte
    blanche soit un objet avec un bord, ce qui remplace toutes les ombres que
    l'ancien thème utilisait pour simuler la profondeur.
    """
    st.markdown(
        """
        <style>
        :root {
            --wf-navy:#0A2540; --wf-blue:#1355C4; --wf-blue-d:#0E42A0;
            --wf-blue-soft:#E8F0FC; --wf-line:#CBD5E1; --wf-line-soft:#E2E8F0;
            --wf-text:#0F172A; --wf-muted:#475569;
            --wf-ground:#F1F5F9; --wf-surface:#FFFFFF;
            /* Une ombre a un décalage et un vrai flou, sinon c'est un halo. */
            --wf-shadow:0 1px 2px rgba(10,37,64,.06), 0 2px 8px -2px rgba(10,37,64,.08);
        }

        /* Fond plat. Aucun dégradé radial : la profondeur vient du trait. */
        [data-testid="stApp"] { background:var(--wf-ground); }

        /* Le chrome natif s'efface : notre bandeau le remplace. */
        [data-testid="stHeader"] { background:transparent; }
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
            display:none !important;
        }
        /* La page commence sous le bandeau, pas 6rem plus bas. */
        [data-testid="stMainBlockContainer"] { padding-top:2.4rem; }

        /* ---- Bandeau navy : marque + les sept sections en grand ----------- */
        .st-key-wf_topbar {
            background:var(--wf-navy) !important;
            border-radius:8px; padding:14px 18px 16px;
            box-shadow:0 2px 4px rgba(10,37,64,.16), 0 10px 24px -12px rgba(10,37,64,.42);
            margin-bottom:26px;
        }
        .wf-brand-light {
            color:#FFFFFF; font-weight:800; font-size:19px;
            letter-spacing:-.02em; line-height:1.7;
        }
        .wf-crumb {
            text-align:right; color:#8FA9C7; font-size:13px; line-height:1.7;
        }
        .wf-crumb strong { color:#FFFFFF; font-weight:700; }
        .wf-crumb-sep { margin:0 7px; opacity:.55; }
        .wf-crumb-ed {
            display:block; font-size:11.5px; color:#7590B2; letter-spacing:.01em;
        }

        /* Les sept boutons de section : taille identique, cliquables en grand.
           C'est la seule règle de dimension qui compte pour la cohérence , tous
           les boutons du bandeau partagent exactement la même boîte. */
        /* Sélecteur descendant, pas `>` : `help=` enveloppe le bouton dans un
           `stTooltipHoverTarget`, ce qui casserait la relation directe. */
        .st-key-wf_topbar .stButton button {
            background:rgba(255,255,255,.07) !important;
            border:1px solid rgba(255,255,255,.16) !important;
            color:#DCE8F7 !important; font-weight:600 !important;
            min-height:58px !important; height:58px !important;
            padding:8px 10px !important; border-radius:7px !important;
            font-size:13.5px !important; line-height:1.25 !important;
            white-space:normal !important;
            transition:background .14s ease, border-color .14s ease,
                       transform .14s ease, box-shadow .14s ease;
        }
        .st-key-wf_topbar .stButton button p {
            color:inherit !important; font-weight:inherit !important;
        }
        .st-key-wf_topbar .stButton button:hover {
            background:rgba(255,255,255,.15) !important;
            border-color:rgba(255,255,255,.4) !important;
            color:#FFFFFF !important;
            transform:translateY(-2px);
            box-shadow:0 6px 14px -6px rgba(0,0,0,.5);
        }
        .st-key-wf_topbar .stButton button:active { transform:translateY(0); }
        /* Section ouverte : bleu plein, aucun dégradé. */
        .st-key-wf_sec_active .stButton button {
            background:var(--wf-blue) !important;
            border-color:#4D82DC !important; color:#FFFFFF !important;
            box-shadow:0 4px 12px -4px rgba(19,85,196,.75);
        }
        .st-key-wf_sec_active .stButton button:hover {
            background:var(--wf-blue-d) !important;
        }

        /* ---- Sélecteur modal : le reste de l'écran s'assombrit ------------ */
        /* `st.dialog` pose lui-même le voile ; on le fonce pour que le choix
           soit la seule chose lisible à l'écran. */
        [data-testid="stDialog"] > div:first-child,
        div[role="dialog"] ~ div[aria-hidden="true"] { background:rgba(10,37,64,.62); }
        [data-testid="stDialog"] div[role="dialog"] {
            border:1px solid var(--wf-line); border-radius:10px;
            box-shadow:0 24px 60px -20px rgba(10,37,64,.55);
        }
        /* Les entrées du sélecteur : cartes de taille égale, effet de survol. */
        [data-testid="stDialog"] [data-testid="stLayoutWrapper"]
            > [data-testid="stVerticalBlock"] {
            transition:border-color .14s ease, box-shadow .14s ease,
                       transform .14s ease;
        }
        [data-testid="stDialog"] [data-testid="stLayoutWrapper"]
            > [data-testid="stVerticalBlock"]:hover {
            border-color:var(--wf-blue) !important;
            box-shadow:0 6px 18px -8px rgba(19,85,196,.5);
            transform:translateY(-2px);
        }

        /* ---- Typographie ------------------------------------------------- */
        [data-testid="stMain"] h1 {
            color:var(--wf-navy); letter-spacing:-.022em; font-weight:800;
        }
        [data-testid="stMain"] h2 { color:var(--wf-navy); letter-spacing:-.014em; }
        [data-testid="stMain"] h3 { color:var(--wf-text); letter-spacing:-.01em; }
        /* Le secondaire est teinté de l'encre, jamais d'un gris neutre. */
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
            color:var(--wf-muted) !important;
        }

        /* ---- Cartes et métriques ----------------------------------------- */
        /* Hauteur minimale commune : une rangée de métriques dont les libellés
           font une ou deux lignes ne doit pas produire des tuiles inégales. */
        [data-testid="stMetric"] {
            background:var(--wf-surface); border:1px solid var(--wf-line);
            border-radius:8px; padding:15px 17px 14px;
            min-height:96px;
            box-shadow:var(--wf-shadow);
            transition:border-color .14s ease, box-shadow .14s ease,
                       transform .14s ease;
        }
        [data-testid="stMetric"]:hover {
            border-color:#9DB6D6;
            box-shadow:0 3px 6px rgba(10,37,64,.09), 0 12px 24px -12px rgba(10,37,64,.28);
            transform:translateY(-2px);
        }
        [data-testid="stMetricValue"] {
            font-weight:800; letter-spacing:-.02em; color:var(--wf-navy);
        }
        [data-testid="stMetricLabel"] p {
            color:var(--wf-muted) !important; font-weight:600;
            text-transform:none; font-size:13px;
        }

        /* Les conteneurs bordés deviennent de vraies cartes blanches.
           Streamlit ne leur donne aucun marqueur propre : le seul repère
           stable est d'être l'enfant direct d'un stLayoutWrapper. On exclut
           nos propres conteneurs nommés (st-key-*), qui ont leur style.
           Aucune classe emotion (st-emotion-cache-…) n'est ciblée : ces
           empreintes changent à chaque version de Streamlit, et cette app est
           déployée sans borne haute de version. */
        [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:not([class*="st-key-"]) {
            background:var(--wf-surface);
            border-radius:8px;
            box-shadow:var(--wf-shadow);
            transition:box-shadow .16s ease, border-color .16s ease;
        }
        [data-testid="stMain"] [data-testid="stLayoutWrapper"]
            > [data-testid="stVerticalBlock"]:not([class*="st-key-"]):hover {
            box-shadow:0 3px 6px rgba(10,37,64,.08), 0 14px 28px -14px rgba(10,37,64,.26);
        }

        /* ---- Actions ------------------------------------------------------ */
        /* Une seule boîte pour TOUS les boutons de l'application, y compris
           ceux des fenêtres modales : restreindre la règle à `stMain` laissait
           les boutons du sélecteur à 38 px pendant que le reste était à 42, ce
           qui est précisément l'incohérence de tailles qu'on corrige ici.
           Le bandeau navy garde sa propre boîte (58 px) et n'est pas visé. */
        [data-testid="stMain"] .stButton button,
        [data-testid="stDialog"] .stButton button,
        .stDownloadButton button,
        [data-testid="stPopover"] > div > button,
        [data-testid="stFormSubmitButton"] button {
            min-height:42px; padding:0 18px; border-radius:7px;
            font-weight:600; font-size:14px;
        }
        /* Le bandeau reprend la main sur sa propre hauteur. */
        .st-key-wf_topbar .stButton button { min-height:58px; }
        .stButton > button[kind="primary"], .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] > button {
            background:var(--wf-blue); border:1px solid var(--wf-blue);
            color:#FFFFFF; font-weight:600;
            box-shadow:0 1px 2px rgba(10,37,64,.14), 0 5px 12px -6px rgba(19,85,196,.6);
            transition:background .13s ease, border-color .13s ease,
                       transform .13s ease, box-shadow .13s ease;
        }
        .stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            background:var(--wf-blue-d); border-color:var(--wf-blue-d);
            transform:translateY(-1px);
            box-shadow:0 2px 4px rgba(10,37,64,.18), 0 10px 20px -8px rgba(19,85,196,.68);
        }
        .stButton > button[kind="primary"]:active, .stDownloadButton > button:active {
            transform:translateY(0);
            box-shadow:0 1px 2px rgba(10,37,64,.2);
        }
        .stButton > button[kind="secondary"],
        [data-testid="stPopover"] > div > button {
            background:var(--wf-surface); border:1px solid var(--wf-line);
            color:var(--wf-navy); font-weight:600;
            box-shadow:0 1px 2px rgba(10,37,64,.05);
            transition:background .13s ease, border-color .13s ease,
                       transform .13s ease, box-shadow .13s ease;
        }
        .stButton > button[kind="secondary"]:hover,
        [data-testid="stPopover"] > div > button:hover {
            background:var(--wf-blue-soft); border-color:var(--wf-blue);
            color:var(--wf-blue-d); transform:translateY(-1px);
            box-shadow:0 4px 10px -4px rgba(19,85,196,.35);
        }
        .stButton > button[kind="secondary"]:active { transform:translateY(0); }
        .stButton > button:disabled,
        .stButton > button:disabled:hover {
            opacity:.45; transform:none; box-shadow:none;
        }

        /* Champs de saisie : même hauteur que les boutons, même bord. */
        [data-testid="stMain"] [data-baseweb="input"],
        [data-testid="stMain"] [data-baseweb="select"] > div,
        [data-testid="stMain"] [data-baseweb="base-input"] {
            min-height:42px; border-radius:7px;
        }

        /* Anneau de focus visible : la navigation au clavier doit se voir. */
        .stButton > button:focus-visible, .stDownloadButton > button:focus-visible,
        a:focus-visible {
            outline:2px solid var(--wf-blue); outline-offset:2px;
        }
        [data-baseweb="select"]:focus-within {
            outline:2px solid var(--wf-blue); outline-offset:1px;
        }

        /* ---- Signalements ------------------------------------------------- */
        [data-testid="stAlert"] {
            border-radius:6px; border:1px solid var(--wf-line);
            box-shadow:none;
        }

        [data-testid="stExpander"] details {
            border-radius:6px !important; border:1px solid var(--wf-line);
            background:var(--wf-surface);
        }
        [data-testid="stExpander"] summary { font-weight:600; color:var(--wf-navy); }

        /* ---- Onglets : soulignés, pas des pastilles ----------------------- */
        .stTabs [data-baseweb="tab-list"] {
            gap:2px; background:transparent; padding:0;
            border-bottom:1px solid var(--wf-line);
        }
        .stTabs [data-baseweb="tab"] {
            border-radius:0; padding:8px 16px; font-weight:600;
            color:var(--wf-muted);
        }
        .stTabs [aria-selected="true"] {
            color:var(--wf-blue-d) !important;
            box-shadow:inset 0 -2px 0 0 var(--wf-blue);
        }
        .stTabs [data-baseweb="tab-highlight"] { display:none; }

        /* ---- Tableaux ----------------------------------------------------- */
        [data-testid="stDataFrame"], [data-testid="stTable"] {
            border-radius:6px; border:1px solid var(--wf-line); overflow:hidden;
        }

        /* ---- Bande de contexte -------------------------------------------- */
        .wf-context {
            display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;
        }
        .wf-brand {
            font-weight:800; font-size:17px; color:var(--wf-navy);
            letter-spacing:-.02em;
        }
        .wf-chip {
            display:inline-block; padding:2px 9px; border-radius:4px;
            background:var(--wf-blue-soft); color:var(--wf-blue-d);
            border:1px solid #C3D9F6; font-size:12.5px; font-weight:600;
        }
        .wf-meta { color:var(--wf-muted); font-size:13px; }

        [data-testid="stMain"] hr { border-color:var(--wf-line-soft); opacity:1; }
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
