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
    # La démo RH tourne sur une seule société fictive (core/seed_company.py),
    # 140 salariés sur deux sites, quel que soit le secteur choisi pour la
    # prévision. Un fichier importé la remplace (company_data.people()).
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
    hist_wx = "en direct" if st.session_state.get("allow_network", True) else "cache/hors-ligne"
    st.caption(
        f":material/database: Météo : Open-Meteo ERA5 ({hist_wx}) · "
        f"Calendrier : Hijri calculé + jours fériés algériens · "
        f"Macro : Banque mondiale · "
        f"Salaires : SNMG {labour_dz.SNMG_MONTHLY:,.0f} DZD + CNAS "
        f"{labour_dz.CNAS_EMPLOYER:.0%} · "
        f"**Les volumes opérationnels sont simulés** , voir Sources."
    )


# ---------------------------------------------------------------------------
# Le vocabulaire visuel : jetons CSS dérivés de core/brand.py
# ---------------------------------------------------------------------------
# Une seule source pour les couleurs. Le bloc `:root` est le seul endroit où un
# code hexadécimal est interpolé ; tout le reste de la feuille passe par
# `var(--tz-*)`, donc changer la marque ici change l'app entière.
_ROOT_VARS = f"""
        <style>
        /* Le visage arabe : Streamlit n'accepte qu'une famille par URL de
           police, l'arabe se charge donc ici. */
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;600;700;800&display=swap');
        :root {{
            --tz-sky:{brand.SKY}; --tz-blue:{brand.BLUE};
            --tz-blue-d:{brand.BLUE_DARK}; --tz-mid:{brand.BLUE_MID};
            --tz-wash:{brand.BLUE_WASH}; --tz-ink:#0F1B2D;
            --tz-muted:#475870; --tz-surface:#F1F5FA; --tz-line:#D5DEEA;
            /* L'argile : le fond et les surfaces sont d'une même teinte ; seule
               la lumière les sépare. */
            --tz-ground:#E6ECF5; --tz-clay:#EEF3F9; --tz-clay-hi:#F6F9FC;
            --tz-edge:rgba(255,255,255,.72); --tz-well-line:rgba(30,58,105,.09);
            --tz-rim:rgba(255,255,255,.85) rgba(30,58,105,.18) rgba(30,58,105,.18) rgba(255,255,255,.85);
            /* Lumière en haut à gauche, ombre bleu-encre en bas à droite. */
            --tz-raise:12px 12px 28px rgba(30,58,105,.20), -10px -10px 26px rgba(255,255,255,.92),
                       inset 0 1px 0 rgba(255,255,255,.95);
            --tz-raise-sm:6px 6px 14px rgba(30,58,105,.20), -5px -5px 12px rgba(255,255,255,.95),
                          inset 0 1px 0 rgba(255,255,255,.95);
            --tz-raise-xs:3px 3px 8px rgba(30,58,105,.13), -3px -3px 7px rgba(255,255,255,.9);
            --tz-inset:inset 5px 5px 12px rgba(30,58,105,.14), inset -5px -5px 12px rgba(255,255,255,.95);
            --tz-inset-sm:inset 3px 3px 7px rgba(30,58,105,.12), inset -3px -3px 7px rgba(255,255,255,.95);
            /* L'argile bleue : convexe, reflet en haut, appui en bas. */
            --tz-clay-blue:6px 9px 20px rgba(11,87,168,.36), -4px -4px 12px rgba(255,255,255,.85),
                           inset 0 2px 0 rgba(255,255,255,.30), inset 0 -3px 0 rgba(4,32,66,.28);
            --tz-press:inset 4px 4px 10px rgba(4,32,66,.30), inset -3px -3px 8px rgba(255,255,255,.22);
            --tz-r-card:24px; --tz-r-ctrl:16px; --tz-r-chip:999px;
            --tz-danger:#A32019; --tz-danger-wash:#FBE3E1; --tz-info-wash:#DCEBFB;
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


def list_rows(rows: list[dict], empty: str = "Rien à signaler.",
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
    La couche visuelle : de l'argile en relief sur un fond néomorphique.

    THESIS , le bureau qu'on touche. Les cartes des agents sont des tuiles
    d'argile posées sur un plan doux ; approuver enfonce le bouton dans la
    matière. Une seule lumière (haut gauche) pour toute l'app ; ce qui est en
    relief et ce qui est en creux se lisent sans un mot. Le contrat complet vit
    dans .impeccable/surfaces/core-appdata-py.md ; DESIGN.md le décrit.
    """
    st.markdown(
        _ROOT_VARS + """
        /* ==================================================================
           Le bureau qu'on touche : argile en relief, creux en néomorphisme.
           Une seule règle de lumière pour toute l'app : la lumière vient du
           haut à gauche. Ce qui est en relief porte un reflet blanc en haut à
           gauche et une ombre bleu-encre en bas à droite ; ce qui est en creux
           (champs, piste de navigation, état actif) inverse les deux.
           Le geste signature : appuyer pour signer. Un bouton passe du relief
           au creux quand on le presse, et tout état actif se lit « enfoncé ».
           ================================================================== */

        /* La police vient du thème natif ; ici seulement le repli arabe. Jamais
           de sélecteur universel : il écraserait la police des icônes. */
        html, body, [data-testid="stApp"] {
            font-family:'Manrope','Noto Sans Arabic','Segoe UI',system-ui,sans-serif;
        }
        [data-testid="stApp"] { background:var(--tz-ground); color:var(--tz-ink); }
        [data-testid="stHeader"] { background:transparent; }
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
            display:none !important;
        }
        [data-testid="stMainBlockContainer"] { padding-top:1.4rem; max-width:1320px; }

        /* Les surfaces que le navigateur dessine portent aussi la marque. */
        ::selection { background:rgba(108,190,245,.45); color:var(--tz-ink); }
        input, textarea { caret-color:var(--tz-blue); }
        * { scrollbar-width:thin; scrollbar-color:#B8C6D9 transparent; }
        ::-webkit-scrollbar { width:10px; height:10px; }
        ::-webkit-scrollbar-thumb {
            background:#C3CFDF; border-radius:999px; border:3px solid var(--tz-ground);
        }
        [data-testid="stMain"] a { text-underline-offset:3px; }
        [data-testid="stMetricValue"], .tz-stat-v, .tz-row-m,
        [data-testid="stDataFrame"] { font-variant-numeric:tabular-nums; }

        /* ---- La dalle du haut : logo, « Demander à Tawzia », réglages ------ */
        .st-key-wf_topbar {
            position:sticky; top:.5rem; z-index:60;
            background:var(--tz-clay) !important;
            border:1px solid var(--tz-edge);
            border-color:var(--tz-rim) !important;
            border-radius:28px; padding:14px 18px 14px;
            box-shadow:var(--tz-raise);
            margin-bottom:26px;
        }
        .tz-topbrand { display:flex; flex-direction:column; gap:2px; padding-left:4px; }
        .tz-topsub { font-size:11px; font-weight:700; color:var(--tz-muted); }

        /* La barre de commande : un puits, la seule entrée de texte du haut. */
        .st-key-wf_ask [data-baseweb="input"] {
            background:var(--tz-ground) !important;
            border:1px solid var(--tz-well-line) !important;
            border-radius:18px !important; min-height:48px !important;
            box-shadow:var(--tz-inset);
            transition:box-shadow .16s ease, background .16s ease;
        }
        .st-key-wf_ask [data-baseweb="input"] input {
            background:transparent !important; font-size:14px; font-weight:500;
        }
        .st-key-wf_ask [data-baseweb="input"]:focus-within {
            background:var(--tz-clay-hi) !important;
            box-shadow:var(--tz-inset), 0 0 0 2px var(--tz-blue);
        }

        /* Réglages de contexte : petites pièces d'argile. */
        .st-key-wf_controls [data-testid="stPopover"] > div > button,
        .st-key-wf_controls [data-testid="stTooltipHoverTarget"] > button {
            border-radius:14px !important; min-height:44px !important;
            background:var(--tz-clay) !important;
            border:1px solid var(--tz-edge) !important;
            color:var(--tz-ink) !important; font-size:12.5px !important;
            font-weight:700 !important; padding:0 12px !important;
            box-shadow:var(--tz-raise-sm) !important;
        }
        .st-key-wf_controls [data-testid="stPopover"] button,
        .st-key-wf_controls [data-testid="stPopover"] button * { white-space:nowrap !important; }
        .st-key-wf_controls [data-testid="stPopover"] > div > button:hover,
        .st-key-wf_controls [data-testid="stTooltipHoverTarget"] > button:hover {
            color:var(--tz-blue) !important;
        }

        /* ---- La piste des espaces : un creux, l'espace actif en relief bleu ---- */
        .st-key-wf_sections {
            margin-top:14px; padding:6px; border-radius:22px;
            background:var(--tz-ground); box-shadow:var(--tz-inset);
            border:1px solid var(--tz-well-line);
        }
        .st-key-wf_sections [data-testid="stHorizontalBlock"] { gap:6px !important; }
        .st-key-wf_topbar .st-key-wf_sections .stButton button {
            background:transparent !important; border:1px solid transparent !important;
            color:var(--tz-muted) !important; font-weight:700 !important;
            min-height:48px !important; height:48px !important; border-radius:16px !important;
            padding:6px 10px !important; font-size:13.5px !important; line-height:1.2 !important;
            white-space:normal !important; box-shadow:none !important;
            transition:color .16s ease, background .16s ease, box-shadow .2s ease,
                       transform .16s cubic-bezier(.2,.8,.3,1);
        }
        .st-key-wf_topbar .st-key-wf_sections .stButton button p {
            color:inherit !important; font-weight:inherit !important;
        }
        .st-key-wf_topbar .st-key-wf_sections .stButton button:hover {
            color:var(--tz-blue) !important; background:var(--tz-clay) !important;
            box-shadow:var(--tz-raise-xs) !important;
        }
        .st-key-wf_topbar .st-key-wf_sec_active .stButton button,
        .st-key-wf_topbar .st-key-wf_sec_active .stButton button:hover {
            background:var(--tz-blue) !important; color:#FFFFFF !important;
            border-color:rgba(255,255,255,.18) !important;
            box-shadow:var(--tz-clay-blue) !important;
        }
        .st-key-wf_topbar .st-key-wf_sections .stButton button:active {
            transform:translateY(1px) scale(.985); box-shadow:var(--tz-press) !important;
            transition-duration:0s !important;
        }

        /* Les sous-écrans : de petites pastilles, la courante enfoncée. */
        .st-key-wf_subnav { margin-top:12px; flex-wrap:wrap; gap:6px !important; }
        .st-key-wf_subnav [data-testid="stPageLink"] a {
            border-radius:999px; padding:6px 14px; background:transparent;
            border:1px solid transparent;
            transition:background .16s ease, box-shadow .16s ease;
        }
        .st-key-wf_subnav [data-testid="stPageLink"] a:hover {
            background:var(--tz-clay); box-shadow:var(--tz-raise-xs);
        }
        .st-key-wf_subnav [data-testid="stPageLink"] p {
            font-size:13.5px; font-weight:700; color:var(--tz-muted) !important;
        }
        .tz-sub-on {
            display:inline-block; border-radius:999px; padding:7px 15px;
            background:var(--tz-ground); color:var(--tz-blue);
            box-shadow:var(--tz-inset-sm); border:1px solid var(--tz-well-line);
            font-size:13.5px; font-weight:800; line-height:1.5;
        }

        /* ---- Typographie : une échelle franche, lisible au projecteur ------ */
        [data-testid="stMain"] h1 {
            color:var(--tz-ink); letter-spacing:-.03em; font-weight:800;
        }
        [data-testid="stMain"] h2 { color:var(--tz-ink); letter-spacing:-.02em; font-weight:800; }
        [data-testid="stMain"] h3 { color:var(--tz-ink); letter-spacing:-.012em; font-weight:700; }
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
            color:var(--tz-muted) !important;
        }
        [data-testid="stMain"] p { line-height:1.55; }

        /* L'en-tête d'écran : pas de boîte, le titre porte seul. */
        .tz-hero {
            display:flex; align-items:flex-end; justify-content:space-between;
            gap:22px; flex-wrap:wrap; padding:2px 4px 6px; margin-bottom:14px;
        }
        .tz-hero-h {
            font-size:32px; font-weight:800; letter-spacing:-.035em;
            color:var(--tz-ink); line-height:1.1; margin:0;
        }
        .tz-hero-s {
            font-size:15px; color:var(--tz-muted); margin-top:8px;
            line-height:1.55; max-width:72ch;
        }
        .tz-hero-s b { color:var(--tz-blue); font-weight:800; }
        .tz-hero-r { display:flex; gap:9px; flex-wrap:wrap; }

        /* ---- Cartes : des tuiles d'argile ------------------------------------ */
        [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:not([class*="st-key-"]) {
            background:var(--tz-clay);
            border:1px solid var(--tz-edge) !important;
            border-radius:24px; padding:20px 22px !important;
            border-color:var(--tz-rim) !important;
            box-shadow:var(--tz-raise);
            transition:box-shadow .22s ease, transform .22s cubic-bezier(.2,.8,.3,1);
        }
        /* Une carte dans une carte n'est pas une autre tuile : c'est un creux. */
        [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:not([class*="st-key-"])
            [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:not([class*="st-key-"]) {
            background:var(--tz-ground); box-shadow:var(--tz-inset-sm);
            border-color:var(--tz-well-line) !important; border-radius:18px;
        }

        /* Métriques natives et tuiles de chiffre : même argile. */
        [data-testid="stMetric"] {
            background:var(--tz-clay); border:1px solid var(--tz-edge);
            border-radius:24px; padding:18px 20px 16px; min-height:108px;
            border-color:var(--tz-rim) !important;
            box-shadow:var(--tz-raise);
        }
        [data-testid="stMetricValue"] { font-weight:800; letter-spacing:-.03em; color:var(--tz-ink); }
        [data-testid="stMetricLabel"] p {
            color:var(--tz-muted) !important; font-weight:700; font-size:13px;
        }
        .tz-stat {
            display:flex; flex-direction:column; gap:8px;
            background:var(--tz-clay); border:1px solid var(--tz-edge);
            border-radius:24px; padding:18px 20px 16px; min-height:118px;
            border-color:var(--tz-rim) !important;
            box-shadow:var(--tz-raise);
        }
        .tz-stat-l { font-size:13.5px; font-weight:700; color:var(--tz-muted); line-height:1.25; }
        .tz-stat-row { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
        .tz-stat-v {
            font-size:34px; font-weight:800; letter-spacing:-.035em;
            color:var(--tz-ink); line-height:1.05;
        }
        .tz-stat-c { font-size:12px; color:var(--tz-muted); line-height:1.35; }
        .tz-chip {
            font-size:11.5px; font-weight:800; padding:4px 10px; border-radius:999px;
            white-space:nowrap; box-shadow:var(--tz-raise-xs);
        }
        .tz-chip.up { background:var(--tz-info-wash); color:var(--tz-blue-d); }
        .tz-chip.down { background:var(--tz-danger-wash); color:var(--tz-danger); }
        .tz-chip.flat { background:var(--tz-clay-hi); color:var(--tz-muted); }

        /* ---- Listes, titres de carte, légendes -------------------------------- */
        .tz-head {
            display:flex; align-items:baseline; justify-content:space-between;
            gap:12px; margin:0 0 8px;
        }
        .tz-head-t { font-size:16px; font-weight:800; color:var(--tz-ink); letter-spacing:-.015em; }
        .tz-head-m {
            font-size:12px; font-weight:800; color:var(--tz-blue);
            background:var(--tz-ground); box-shadow:var(--tz-inset-sm);
            padding:3px 10px; border-radius:999px;
        }
        .tz-row {
            display:flex; align-items:center; gap:12px; padding:10px 8px;
            border-radius:14px; transition:background .16s ease;
        }
        .tz-row + .tz-row { border-top:1px solid rgba(30,58,105,.07); }
        .tz-row:hover { background:rgba(255,255,255,.55); }
        .tz-av {
            width:36px; height:36px; border-radius:50%; flex:none;
            display:grid; place-items:center; font-size:11.5px; font-weight:800;
            background:var(--tz-clay-hi); color:var(--tz-blue); box-shadow:var(--tz-raise-xs);
        }
        .tz-av.hot { color:var(--tz-danger); }
        .tz-row-txt { min-width:0; }
        .tz-row-t {
            font-size:13.5px; font-weight:700; color:var(--tz-ink); line-height:1.35;
            overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
        }
        .tz-row.wrap .tz-row-t { white-space:normal; overflow:visible; }
        .tz-row-s { font-size:12px; color:var(--tz-muted); line-height:1.4; }
        .tz-row-m {
            margin-inline-start:auto; flex:none; text-align:end; font-size:11.5px;
            font-weight:800; color:var(--tz-muted);
        }
        .tz-row-m.hot { color:var(--tz-danger); }
        .tz-empty { font-size:13px; color:var(--tz-muted); padding:12px 4px; }
        .tz-leg {
            display:flex; gap:15px; flex-wrap:wrap; font-size:12px; font-weight:700;
            color:var(--tz-muted); margin:2px 0 6px;
        }
        .tz-leg i { width:10px; height:10px; border-radius:50%; display:inline-block; margin-inline-end:6px; }

        /* ---- Boutons : une boîte pour tous, l'argile bleue pour l'unique action ---- */
        [data-testid="stMain"] .stButton button,
        [data-testid="stDialog"] .stButton button,
        .stDownloadButton button,
        [data-testid="stPopover"] > div > button,
        [data-testid="stPopover"] [data-testid="stTooltipHoverTarget"] > button,
        [data-testid="stFormSubmitButton"] button {
            min-height:44px; padding:0 20px; border-radius:16px;
            font-weight:700; font-size:14px;
            transition:transform .14s cubic-bezier(.2,.8,.3,1), box-shadow .18s ease,
                       background .16s ease, color .16s ease;
        }
        /* Secondaire : de l'argile claire en relief. */
        .stButton > button[kind="secondary"], .stDownloadButton > button,
        [data-testid="stPopover"] > div > button,
        [data-testid="stPopover"] [data-testid="stTooltipHoverTarget"] > button {
            background:var(--tz-clay); border:1px solid var(--tz-edge);
            color:var(--tz-ink); box-shadow:var(--tz-raise-sm);
            border-color:var(--tz-rim) !important;
        }
        .stButton > button[kind="secondary"]:hover, .stDownloadButton > button:hover,
        [data-testid="stPopover"] > div > button:hover {
            background:var(--tz-clay-hi); color:var(--tz-blue);
            border-color:var(--tz-edge); transform:translateY(-1px);
        }
        /* Primaire : l'argile bleue, convexe. Une seule par carte. */
        .stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button {
            background:var(--tz-blue); border:1px solid rgba(255,255,255,.16);
            color:#FFFFFF; box-shadow:var(--tz-clay-blue);
        }
        .stButton > button[kind="primary"] p, [data-testid="stFormSubmitButton"] > button p { color:#FFFFFF; }
        .stButton > button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] > button:hover {
            background:var(--tz-blue-d); border-color:rgba(255,255,255,.16);
            color:#FFFFFF; transform:translateY(-1px);
        }
        /* Appuyer pour signer : le relief passe en creux. */
        .stButton > button:active, .stDownloadButton > button:active,
        [data-testid="stFormSubmitButton"] > button:active {
            transform:translateY(1px) scale(.985) !important;
            box-shadow:var(--tz-press) !important;
            transition-duration:0s !important;
        }
        .stButton > button:disabled, .stButton > button:disabled:hover {
            opacity:.5; transform:none; box-shadow:var(--tz-inset-sm);
        }
        /* Les liens de page dans une carte (« Modifier », « Voir le détail »). */
        [data-testid="stMain"] [data-testid="stPageLink"] a {
            border-radius:14px; padding:8px 12px; transition:background .16s ease, box-shadow .16s ease;
        }
        [data-testid="stMain"] [data-testid="stPageLink"] a:hover {
            background:var(--tz-clay-hi); box-shadow:var(--tz-raise-xs);
        }
        [data-testid="stMain"] [data-testid="stPageLink"] p { color:var(--tz-blue); font-weight:700; }

        /* ---- Champs : des puits ---------------------------------------------- */
        [data-testid="stMain"] [data-baseweb="input"],
        [data-testid="stMain"] [data-baseweb="select"] > div,
        [data-testid="stMain"] [data-baseweb="textarea"],
        [data-testid="stMain"] [data-baseweb="base-input"] {
            min-height:44px; border-radius:14px !important;
            background:var(--tz-ground) !important;
            border-color:var(--tz-well-line) !important;
            box-shadow:var(--tz-inset-sm);
        }
        [data-testid="stMain"] [data-baseweb="input"] input,
        [data-testid="stMain"] [data-baseweb="textarea"] textarea { background:transparent !important; }
        [data-testid="stChatInput"] {
            border-radius:20px !important; background:var(--tz-ground) !important;
            box-shadow:var(--tz-inset) !important; border:1px solid var(--tz-well-line) !important;
        }

        /* Anneau de focus : visible, couleur ciel, jamais retiré. */
        .stButton > button:focus-visible, .stDownloadButton > button:focus-visible,
        [data-testid="stPopover"] button:focus-visible,
        [data-testid="stButtonGroup"] button:focus-visible,
        .stTabs [data-baseweb="tab"]:focus-visible,
        [data-testid="stMain"] a:focus-visible, summary:focus-visible {
            outline:3px solid var(--tz-blue) !important; outline-offset:3px;
        }
        [data-testid="stMain"] [data-baseweb="select"]:focus-within > div,
        [data-testid="stMain"] [data-baseweb="input"]:focus-within {
            box-shadow:var(--tz-inset-sm), 0 0 0 2px var(--tz-blue) !important;
        }

        /* ---- Commandes segmentées et onglets : une piste en creux -------------- */
        [data-testid="stButtonGroup"] [data-baseweb="button-group"],
        .stTabs [data-baseweb="tab-list"] {
            background:var(--tz-clay); box-shadow:var(--tz-raise-xs);
            border:1px solid var(--tz-edge); border-radius:16px; padding:4px; gap:4px;
        }
        [data-testid="stButtonGroup"] button {
            border-radius:12px !important; border:0 !important; background:transparent !important;
            font-weight:800 !important; min-height:36px; color:var(--tz-muted) !important;
            padding:0 10px !important; min-width:0 !important;
        }
        [data-testid="stButtonGroup"] [data-baseweb="button-group"] { width:fit-content; max-width:100%; }
        /* Un choix fait se lit enfoncé : c'est le geste « appuyer » au repos. */
        [data-testid="stButtonGroup"] button[aria-checked="true"],
        [data-testid="stButtonGroup"] button[kind*="Active"],
        .stTabs [aria-selected="true"] {
            background:var(--tz-ground) !important; color:var(--tz-blue) !important;
            box-shadow:var(--tz-inset-sm) !important;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius:12px; padding:8px 16px; font-weight:800; color:var(--tz-muted);
            background:transparent;
        }
        .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }

        /* ---- Signalements, dépliants, tableaux, conversation ------------------ */
        [data-testid="stAlert"] {
            border-radius:18px; border:1px solid var(--tz-edge); box-shadow:var(--tz-raise-xs);
        }
        [data-testid="stExpander"] details {
            border-radius:16px !important; border:1px solid var(--tz-well-line) !important;
            background:var(--tz-ground) !important; box-shadow:var(--tz-inset-sm);
        }
        [data-testid="stExpander"] summary { font-weight:700; color:var(--tz-ink); border-radius:16px; }
        [data-testid="stExpander"] summary:hover { color:var(--tz-blue); }
        [data-testid="stDataFrame"], [data-testid="stTable"] {
            border-radius:18px; border:1px solid var(--tz-edge); overflow:hidden;
            box-shadow:var(--tz-raise-xs);
        }
        [data-testid="stChatMessage"] {
            background:var(--tz-clay-hi); border-radius:20px; padding:12px 14px;
            box-shadow:var(--tz-raise-xs); border:1px solid var(--tz-edge);
        }
        [data-testid="stMain"] hr { border-color:rgba(30,58,105,.12); opacity:1; }

        /* La jauge : un sillon en creux, rempli d'argile bleue. */
        .tz-meter {
            height:10px; border-radius:999px; background:var(--tz-ground);
            box-shadow:var(--tz-inset-sm); overflow:hidden; margin:10px 0 4px;
        }
        .tz-meter span { display:block; height:100%; border-radius:999px; background:var(--tz-blue); }
        .tz-meter-l { display:flex; justify-content:space-between; font-size:12px; color:var(--tz-muted); font-weight:700; }

        /* Le téléphone du salarié : un appareil d'argile, bord épais en relief. */
        .st-key-tz_phone {
            max-width:380px; margin:0 auto; border-radius:40px !important;
            border:10px solid var(--tz-ink) !important; padding:18px 14px !important;
            background:var(--tz-clay); box-shadow:var(--tz-raise);
        }

        /* La fenêtre modale : un voile encre, la fenêtre en argile. */
        [data-testid="stDialog"] div[role="dialog"] {
            background:var(--tz-clay); border:1px solid var(--tz-edge);
            border-radius:28px; box-shadow:0 30px 70px -24px rgba(15,27,45,.5);
        }

        /* ---- Mouvement : une apparition, un appui. Rien d'autre. --------------- */
        @keyframes tz-rise { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:none; } }
        @keyframes tz-fill { from { width:0; } }
        [data-testid="stMain"] [data-testid="stLayoutWrapper"]
            > [data-testid="stVerticalBlock"]:not([class*="st-key-"]),
        .tz-stat, [data-testid="stMetric"] {
            animation:tz-rise .34s cubic-bezier(.16,1,.3,1) both;
        }
        .tz-meter span { animation:tz-fill .7s cubic-bezier(.16,1,.3,1) both; }
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration:.001ms !important; animation-iteration-count:1 !important;
                transition-duration:.001ms !important;
            }
        }

        /* Petits écrans : la dalle ne colle plus, les espaces passent sur deux lignes. */
        @media (max-width: 760px) {
            .st-key-wf_topbar { position:static; border-radius:22px; padding:12px; }
            .tz-hero-h { font-size:26px; }
            .tz-stat-v { font-size:28px; }
            /* Les six espaces en grille 2 x 3 : la navigation tient dans un
               pouce, et un mot ne se coupe jamais en deux. */
            .st-key-wf_sections [data-testid="stHorizontalBlock"] {
                flex-direction:row !important; flex-wrap:wrap !important;
            }
            .st-key-wf_sections [data-testid="stColumn"] {
                flex:1 1 45% !important; min-width:0 !important; width:auto !important;
            }
            .st-key-wf_topbar .st-key-wf_sections .stButton button {
                font-size:12.5px !important; padding:4px 8px !important;
                word-break:keep-all !important; overflow-wrap:normal !important;
            }
            .st-key-wf_controls [data-testid="stHorizontalBlock"] {
                flex-direction:row !important; flex-wrap:wrap !important; gap:8px !important;
            }
            .st-key-wf_controls [data-testid="stColumn"] {
                flex:1 1 45% !important; min-width:0 !important; width:auto !important;
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
