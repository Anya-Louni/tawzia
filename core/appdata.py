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


# ---------------------------------------------------------------------------
# Le vocabulaire visuel : jetons CSS dérivés de core/brand.py
# ---------------------------------------------------------------------------
# Une seule source pour les couleurs. Le bloc `:root` est le seul endroit où un
# code hexadécimal est interpolé ; tout le reste de la feuille passe par
# `var(--tz-*)`, donc changer la marque ici change l'app entière.
_ROOT_VARS = f"""
        <style>
        :root {{
            --tz-sky:{brand.SKY}; --tz-blue:{brand.BLUE};
            --tz-blue-d:{brand.BLUE_DARK}; --tz-mid:{brand.BLUE_MID};
            --tz-wash:{brand.BLUE_WASH}; --tz-ink:{brand.INK};
            --tz-muted:{brand.MUTED}; --tz-surface:{brand.SURFACE};
            --tz-line:{brand.LINE};
            /* Le fond est légèrement bleuté : un verre dépoli n'a l'air de
               verre que s'il a quelque chose de coloré à flouter derrière lui. */
            --tz-ground:#EDF2FA;
            /* Verre : deux opacités. La forte porte du texte, la faible ne
               porte que du décor , en dessous de ~.80 le texte perd son
               contraste dès qu'une tache colorée passe derrière. */
            --tz-glass:rgba(255,255,255,.86);
            --tz-glass-strong:rgba(255,255,255,.94);
            --tz-glass-line:#DEE6F1;
            --tz-blur:saturate(140%) blur(14px);
            --tz-shadow:0 1px 2px rgba(16,26,40,.05), 0 8px 24px -14px rgba(16,26,40,.22);
            --tz-shadow-lift:0 2px 6px rgba(16,26,40,.07), 0 18px 36px -18px rgba(16,26,40,.30);
            /* Une seule echelle de rayons, franche : carte, controle, pastille.
               Aucun degrade nulle part , la couleur d'action est plate. */
            --tz-r-card:8px; --tz-r-ctrl:6px; --tz-r-chip:4px;
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
    La couche visuelle, par-dessus le thème de .streamlit/config.toml.

    THESIS , l'app porte la marque Tawzia : deux bleus, des cartes blanches
    arrondies posées sur un fond clair, et le chiffre comme objet principal de
    chaque tuile. Elle abandonne le bandeau navy et le trait 1px omniprésent de
    la version « registre public » : la profondeur vient maintenant d'une ombre
    portée douce, ce qui laisse les chiffres et le bleu de marque porter seuls
    l'attention.

    OWN-WORLD , fond #F3F5F9, cartes blanches r=16 avec ombre douce et filet
    presque invisible, bleu profond #0B57A8 pour l'action et les titres, bleu
    clair #6CBEF5 du logo pour les accents et les séries claires. Palette et
    marque viennent de `core/brand.py`, jamais recopiées ici.

    FIRST VIEWPORT , bandeau blanc : le logo, une recherche qui ouvre vraiment
    une page, les réglages de contexte ; puis les sept sections en pastilles,
    l'active en bleu plein. Pas de rail latéral : les sept sections sont
    l'architecture entière et se voient d'un coup d'œil.

    FORM , une seule échelle de rayon (10 pour les contrôles, 16 pour les
    cartes) et une seule ombre, déclinée en deux intensités. Tout ce qui n'est
    ni un chiffre ni une action est gris ardoise.
    """
    st.markdown(
        _ROOT_VARS + """
        /* Le fond : trois halos très dilués dans les bleus de la marque. Ils ne
           sont pas là pour décorer mais pour donner au verre dépoli quelque
           chose à flouter , sur un fond uni, un panneau translucide est
           indiscernable d'un panneau opaque. `fixed` : ils ne défilent pas. */
        [data-testid="stApp"] { background:var(--tz-ground); }

        /* Le chrome natif s'efface : notre bandeau le remplace. */
        [data-testid="stHeader"] { background:transparent; }
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
            display:none !important;
        }
        /* La page commence sous le bandeau, pas 6rem plus bas. */
        [data-testid="stMainBlockContainer"] { padding-top:1.7rem; }

        /* ---- Bandeau de verre : logo + recherche + réglages + sections ---- */
        /* Il colle en haut : sur une page longue, la navigation reste sous la
           main. `-webkit-` est conservé, Safari n'accepte pas encore la
           propriété non préfixée. */
        .st-key-wf_topbar {
            position:sticky; top:.4rem; z-index:60;
            background:var(--tz-glass-strong) !important;
            -webkit-backdrop-filter:var(--tz-blur);
            backdrop-filter:var(--tz-blur);
            border:1px solid var(--tz-glass-line);
            border-radius:var(--tz-r-card); padding:13px 18px 15px;
            box-shadow:var(--tz-shadow);
            margin-bottom:20px;
        }

        /* Les sept pastilles de section : taille identique, cliquables en
           grand. Sélecteur descendant, pas `>` : `help=` enveloppe le bouton
           dans un `stTooltipHoverTarget`, ce qui casserait la relation. */
        .st-key-wf_topbar .stButton button {
            background:rgba(255,255,255,.55) !important;
            border:1px solid rgba(11,87,168,.10) !important;
            color:var(--tz-muted) !important; font-weight:600 !important;
            min-height:52px !important; height:52px !important;
            padding:8px 10px !important; border-radius:var(--tz-r-ctrl) !important;
            font-size:13px !important; line-height:1.25 !important;
            white-space:normal !important;
            /* Ressort court : l'accélération inversée donne l'impression que la
               pastille se pose, plutôt qu'elle ne glisse. */
            transition:background .18s cubic-bezier(.34,1.4,.64,1),
                       color .18s ease, transform .18s cubic-bezier(.34,1.4,.64,1),
                       box-shadow .18s ease;
        }
        .st-key-wf_topbar .stButton button p {
            color:inherit !important; font-weight:inherit !important;
        }
        .st-key-wf_topbar .stButton button:hover {
            background:rgba(255,255,255,.92) !important;
            color:var(--tz-blue) !important;
            border-color:rgba(11,87,168,.22) !important;
            transform:translateY(-2px);
            box-shadow:0 10px 20px -10px rgba(11,87,168,.45);
        }
        .st-key-wf_topbar .stButton button:active { transform:translateY(0); }
        /* Section ouverte : le dégradé de marque, la seule surface de l'app qui
           le porte en pleine largeur. C'est ce qui dit « vous êtes ici ». */
        .st-key-wf_sec_active .stButton button {
            background:var(--tz-blue) !important;
            border-color:transparent !important;
            color:#FFFFFF !important;
            box-shadow:0 10px 22px -8px rgba(11,87,168,.6);
        }
        /* La section active doit REDÉCLARER son fond au survol. Sans cette
           ligne, la règle de survol générique du bandeau pose un fond blanc
           sous un texte blanc, et l'onglet actif disparaît sous le curseur. */
        .st-key-wf_sec_active .stButton button:hover {
            background:var(--tz-blue-d) !important;
            border-color:transparent !important;
            color:#FFFFFF !important; transform:translateY(-2px);
            box-shadow:0 14px 26px -10px rgba(11,87,168,.68);
        }

        /* Le logo et son sous-titre, calés sur la même ligne de base. */
        .tz-topbrand { display:flex; flex-direction:column; gap:2px; }
        .tz-topsub {
            font-size:11px; font-weight:600; color:var(--tz-muted);
            letter-spacing:.005em; padding-left:1px;
        }
        /* Le fil d'Ariane : section, puis écran courant. */
        .tz-crumb {
            display:flex; align-items:center; gap:9px; flex-wrap:wrap;
            margin:11px 2px 1px; font-size:12px; color:var(--tz-muted);
        }
        .tz-crumb span::after { content:"/"; margin-left:9px; opacity:.5; }
        .tz-crumb b { color:var(--tz-ink); font-weight:700; }

        /* La recherche : une pastille avec sa loupe, pas un champ de formulaire. */
        .st-key-wf_search [data-baseweb="select"] > div {
            background:var(--tz-ground) !important;
            border-color:transparent !important;
            border-radius:var(--tz-r-ctrl) !important; min-height:44px !important;
            padding-left:34px !important;
            background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%235A6B80' stroke-width='2.2' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='M16.5 16.5 21 21'/%3E%3C/svg%3E") !important;
            background-repeat:no-repeat !important;
            background-position:12px center !important;
            background-size:16px 16px !important;
        }
        .st-key-wf_search [data-baseweb="select"] > div:focus-within {
            background-color:var(--tz-surface) !important;
            border-color:var(--tz-blue) !important;
        }

        /* Les trois réglages de contexte : pastilles compactes, pas des boutons.
           Un popover portant `help=` est enveloppé dans un
           `stTooltipHoverTarget` : sans la seconde forme du sélecteur, celui
           d'« Activité » reste à la taille par défaut et la rangée devient
           inégale. */
        .st-key-wf_controls [data-testid="stPopover"] > div > button,
        .st-key-wf_controls [data-testid="stTooltipHoverTarget"] > button {
            border-radius:var(--tz-r-ctrl) !important; min-height:44px !important;
            background:rgba(255,255,255,.55) !important;
            border:1px solid rgba(11,87,168,.10) !important;
            color:var(--tz-ink) !important; font-size:12.5px !important;
            padding:0 12px !important;
        }
        /* Un libellé de réglage ne se coupe jamais : mieux vaut le tronquer que
           d'empiler « Ré / gla / ges » sur trois lignes. Le libellé d'un
           `st.popover` n'est pas dans un <p> mais dans une pile de <span>, donc
           la règle vise le bouton et tout ce qu'il contient. */
        .st-key-wf_controls [data-testid="stPopover"] button,
        .st-key-wf_controls [data-testid="stPopover"] button * {
            white-space:nowrap !important;
        }
        .st-key-wf_controls [data-testid="stPopover"] > div > button:hover,
        .st-key-wf_controls [data-testid="stTooltipHoverTarget"] > button:hover {
            background:rgba(255,255,255,.92) !important;
            color:var(--tz-blue) !important;
            border-color:rgba(11,87,168,.22) !important;
        }

        /* ---- Sélecteur modal : le reste de l'écran s'assombrit ------------ */
        /* `st.dialog` pose lui-même le voile ; on le fonce pour que le choix
           soit la seule chose lisible à l'écran. */
        [data-testid="stDialog"] > div:first-child,
        div[role="dialog"] ~ div[aria-hidden="true"] { background:rgba(16,26,40,.58); }
        [data-testid="stDialog"] div[role="dialog"] {
            border:1px solid var(--tz-line); border-radius:var(--tz-r-card);
            box-shadow:0 24px 56px -22px rgba(16,26,40,.45);
        }
        /* Les entrées du sélecteur : cartes de taille égale, effet de survol. */
        [data-testid="stDialog"] [data-testid="stLayoutWrapper"]
            > [data-testid="stVerticalBlock"] {
            transition:border-color .14s ease, box-shadow .14s ease,
                       transform .14s ease;
        }
        [data-testid="stDialog"] [data-testid="stLayoutWrapper"]
            > [data-testid="stVerticalBlock"]:hover {
            border-color:var(--tz-blue) !important;
            box-shadow:0 8px 22px -10px rgba(11,87,168,.45);
            transform:translateY(-2px);
        }

        /* ---- Typographie ------------------------------------------------- */
        [data-testid="stMain"] h1 {
            color:var(--tz-ink); letter-spacing:-.026em; font-weight:800;
        }
        [data-testid="stMain"] h2 { color:var(--tz-ink); letter-spacing:-.016em; }
        [data-testid="stMain"] h3 { color:var(--tz-ink); letter-spacing:-.01em; }
        /* Le secondaire est teinté de l'encre, jamais d'un gris neutre. */
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
            color:var(--tz-muted) !important;
        }

        /* ---- Cartes et métriques ----------------------------------------- */
        /* Hauteur minimale commune : une rangée de métriques dont les libellés
           font une ou deux lignes ne doit pas produire des tuiles inégales. */
        [data-testid="stMetric"] {
            background:var(--tz-glass-strong);
            -webkit-backdrop-filter:var(--tz-blur);
            backdrop-filter:var(--tz-blur);
            border:1px solid var(--tz-glass-line);
            border-radius:var(--tz-r-card); padding:16px 18px 15px;
            min-height:104px; position:relative; overflow:hidden;
            box-shadow:var(--tz-shadow);
            transition:box-shadow .2s ease, transform .2s cubic-bezier(.34,1.3,.64,1);
        }
        [data-testid="stMetric"]:hover {
            box-shadow:var(--tz-shadow-lift); transform:translateY(-3px);
        }
        [data-testid="stMetricValue"] {
            font-weight:800; letter-spacing:-.03em; color:var(--tz-ink);
        }
        [data-testid="stMetricLabel"] p {
            color:var(--tz-muted) !important; font-weight:600;
            text-transform:none; font-size:13px;
        }

        /* ---- Tuile de chiffre (appdata.stat_card) ------------------------- */
        /* Le modèle du tableau de bord : libellé, chiffre en grand, pastille
           d'évolution, puis la base de comparaison en petit. */
        .tz-stat { display:flex; flex-direction:column; gap:7px; }
        .tz-stat-l {
            font-size:13.5px; font-weight:600; color:var(--tz-muted);
            line-height:1.25;
        }
        .tz-stat-row { display:flex; align-items:center; gap:9px; flex-wrap:wrap; }
        .tz-stat-v {
            font-size:34px; font-weight:800; letter-spacing:-.035em;
            color:var(--tz-ink); line-height:1.02;
        }
        .tz-chip {
            font-size:11.5px; font-weight:700; padding:3px 8px;
            border-radius:var(--tz-r-chip); white-space:nowrap;
        }
        .tz-chip.up { background:var(--tz-wash); color:var(--tz-blue); }
        .tz-chip.down { background:#FDECEC; color:#B3261E; }
        .tz-chip.flat { background:var(--tz-ground); color:var(--tz-muted); }
        .tz-stat-c { font-size:11.5px; color:#8494A8; line-height:1.3; }

        /* ---- Lignes de liste (appdata.list_rows) -------------------------- */
        .tz-row {
            display:flex; align-items:center; gap:11px; padding:9px 0;
            border-top:1px solid var(--tz-line);
        }
        .tz-row:first-child { border-top:0; padding-top:2px; }
        .tz-av {
            width:34px; height:34px; border-radius:50%; flex:none;
            display:grid; place-items:center; font-size:11.5px; font-weight:700;
            background:var(--tz-wash); color:var(--tz-blue);
        }
        .tz-av.hot { background:#FDECEC; color:#B3261E; }
        .tz-row-txt { min-width:0; }
        .tz-row-t {
            font-size:13.5px; font-weight:600; color:var(--tz-ink);
            line-height:1.3; overflow:hidden; text-overflow:ellipsis;
            white-space:nowrap;
        }
        .tz-row.wrap .tz-row-t { white-space:normal; overflow:visible; }
        .tz-row-s { font-size:11.5px; color:var(--tz-muted); line-height:1.35; }
        .tz-row-m {
            margin-left:auto; flex:none; text-align:right; font-size:11.5px;
            font-weight:700; color:var(--tz-muted);
        }
        .tz-row-m.hot { color:#B3261E; }
        .tz-empty {
            font-size:12.5px; color:var(--tz-muted); padding:10px 0;
        }

        /* ---- Titre de carte et légende ----------------------------------- */
        .tz-head {
            display:flex; align-items:baseline; justify-content:space-between;
            gap:12px; margin:0 0 4px;
        }
        .tz-head-t {
            font-size:15.5px; font-weight:700; color:var(--tz-ink);
            letter-spacing:-.012em;
        }
        .tz-head-m { font-size:12px; font-weight:600; color:var(--tz-blue); }
        .tz-leg {
            display:flex; gap:15px; flex-wrap:wrap; font-size:11.5px;
            font-weight:600; color:var(--tz-muted); margin:2px 0 6px;
        }
        .tz-leg i {
            width:10px; height:10px; border-radius:2px; display:inline-block;
            margin-right:6px;
        }

        /* Les conteneurs bordés deviennent de vraies cartes blanches.
           Streamlit ne leur donne aucun marqueur propre : le seul repère
           stable est d'être l'enfant direct d'un stLayoutWrapper. On exclut
           nos propres conteneurs nommés (st-key-*), qui ont leur style.
           Aucune classe emotion (st-emotion-cache-…) n'est ciblée : ces
           empreintes changent à chaque version de Streamlit, et cette app est
           déployée sans borne haute de version. */
        [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:not([class*="st-key-"]) {
            background:var(--tz-glass-strong);
            -webkit-backdrop-filter:var(--tz-blur);
            backdrop-filter:var(--tz-blur);
            border-color:var(--tz-glass-line) !important;
            border-radius:var(--tz-r-card);
            position:relative;
            box-shadow:var(--tz-shadow);
            transition:box-shadow .2s ease;
        }
        [data-testid="stMain"] [data-testid="stLayoutWrapper"]
            > [data-testid="stVerticalBlock"]:not([class*="st-key-"]):hover {
            box-shadow:var(--tz-shadow-lift);
        }

        /* ---- Actions ------------------------------------------------------ */
        /* Une seule boîte pour TOUS les boutons de l'application, y compris
           ceux des fenêtres modales : restreindre la règle à `stMain` laissait
           les boutons du sélecteur à 38 px pendant que le reste était à 42, ce
           qui est précisément l'incohérence de tailles qu'on corrige ici.
           Le bandeau garde sa propre boîte (52 px) et n'est pas visé. */
        [data-testid="stMain"] .stButton button,
        [data-testid="stDialog"] .stButton button,
        .stDownloadButton button,
        [data-testid="stPopover"] > div > button,
        [data-testid="stPopover"] [data-testid="stTooltipHoverTarget"] > button,
        [data-testid="stFormSubmitButton"] button {
            min-height:42px; padding:0 18px; border-radius:var(--tz-r-ctrl);
            font-weight:600; font-size:14px;
        }
        /* Le bandeau reprend la main sur sa propre hauteur. */
        .st-key-wf_topbar .stButton button { min-height:52px; }
        .stButton > button[kind="primary"], .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] > button {
            background:var(--tz-blue); border:1px solid var(--tz-blue);
            color:#FFFFFF; font-weight:600;
            box-shadow:0 1px 2px rgba(16,26,40,.12), 0 8px 18px -8px rgba(11,87,168,.62);
            transition:background .15s ease, border-color .15s ease,
                       transform .15s cubic-bezier(.34,1.3,.64,1), box-shadow .15s ease;
        }
        .stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            background:var(--tz-blue-d); border-color:var(--tz-blue-d);
            transform:translateY(-2px);
            box-shadow:0 2px 4px rgba(16,26,40,.16), 0 16px 28px -10px rgba(11,87,168,.7);
        }
        .stButton > button[kind="primary"]:active, .stDownloadButton > button:active {
            transform:translateY(0);
            box-shadow:0 1px 2px rgba(16,26,40,.2);
        }
        .stButton > button[kind="secondary"],
        [data-testid="stPopover"] > div > button,
        [data-testid="stPopover"] [data-testid="stTooltipHoverTarget"] > button {
            background:var(--tz-surface); border:1px solid var(--tz-line);
            color:var(--tz-ink); font-weight:600;
            box-shadow:0 1px 2px rgba(16,26,40,.04);
            transition:background .13s ease, border-color .13s ease,
                       transform .13s ease, box-shadow .13s ease;
        }
        .stButton > button[kind="secondary"]:hover,
        [data-testid="stPopover"] > div > button:hover,
        [data-testid="stPopover"] [data-testid="stTooltipHoverTarget"] > button:hover {
            background:var(--tz-wash); border-color:var(--tz-sky);
            color:var(--tz-blue); transform:translateY(-1px);
            box-shadow:0 5px 12px -5px rgba(11,87,168,.32);
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
            min-height:42px; border-radius:var(--tz-r-ctrl);
        }

        /* Anneau de focus visible : la navigation au clavier doit se voir. */
        .stButton > button:focus-visible, .stDownloadButton > button:focus-visible,
        a:focus-visible {
            outline:2px solid var(--tz-blue); outline-offset:2px;
        }
        [data-baseweb="select"]:focus-within {
            outline:2px solid var(--tz-blue); outline-offset:1px;
        }

        /* ---- Signalements ------------------------------------------------- */
        [data-testid="stAlert"] {
            border-radius:var(--tz-r-card); border:1px solid var(--tz-line);
            box-shadow:none;
        }

        [data-testid="stExpander"] details {
            border-radius:var(--tz-r-card) !important; border:1px solid var(--tz-line);
            background:var(--tz-surface);
        }
        [data-testid="stExpander"] summary { font-weight:600; color:var(--tz-ink); }

        /* ---- Onglets : soulignés, pas des pastilles ----------------------- */
        .stTabs [data-baseweb="tab-list"] {
            gap:2px; background:transparent; padding:0;
            border-bottom:1px solid var(--tz-line);
        }
        .stTabs [data-baseweb="tab"] {
            border-radius:0; padding:8px 16px; font-weight:600;
            color:var(--tz-muted);
        }
        .stTabs [aria-selected="true"] {
            color:var(--tz-blue) !important;
            box-shadow:inset 0 -2px 0 0 var(--tz-blue);
        }
        .stTabs [data-baseweb="tab-highlight"] { display:none; }

        /* ---- Tableaux ----------------------------------------------------- */
        [data-testid="stDataFrame"], [data-testid="stTable"] {
            border-radius:var(--tz-r-card); border:1px solid var(--tz-line); overflow:hidden;
        }

        /* ---- Bandeau d'accueil du tableau de bord ------------------------- */
        /* Le seul panneau teinté de l'app : il porte la date, l'état du jour et
           les raccourcis. Teinté, donc il ne peut pas être confondu avec une
           carte de données. */
        .tz-hero {
            display:flex; align-items:flex-end; justify-content:space-between;
            gap:22px; flex-wrap:wrap;
            background:var(--tz-wash);
            border:1px solid #D3E3F7;
            border-radius:var(--tz-r-card); padding:18px 22px;
            box-shadow:var(--tz-shadow);
            margin-bottom:16px;
        }
        .tz-hero-h {
            font-size:25px; font-weight:800; letter-spacing:-.028em;
            color:var(--tz-ink); line-height:1.15; margin:0;
        }
        .tz-hero-s {
            font-size:13px; color:var(--tz-muted); margin-top:5px;
            line-height:1.45;
        }
        .tz-hero-s b { color:var(--tz-blue); font-weight:700; }
        .tz-hero-r { display:flex; gap:9px; flex-wrap:wrap; }

        /* Jauge fine : la couverture d'un planning se lit mieux qu'un chiffre. */
        .tz-meter {
            height:7px; border-radius:2px; background:rgba(11,87,168,.12);
            overflow:hidden; margin:9px 0 3px;
        }
        .tz-meter span {
            display:block; height:100%; border-radius:2px;
            background:var(--tz-blue);
        }
        .tz-meter-l {
            display:flex; justify-content:space-between; font-size:11.5px;
            color:var(--tz-muted); font-weight:600;
        }


        /* ---- Mouvement ---------------------------------------------------
           Une seule idee : ce qui apparait monte de quelques pixels en se
           revelant, et ce qui reagit au curseur le fait en 140 ms. Les durees
           restent sous 400 ms , au-dela, un tableau de bord consulte vingt fois
           par jour devient lent a utiliser. Streamlit ne recree pas un element
           inchange, donc l'animation ne joue qu'a l'apparition, pas a chaque
           rerun. */
        @keyframes tz-rise {
            from { opacity:0; transform:translateY(6px); }
            to   { opacity:1; transform:none; }
        }
        @keyframes tz-fill { from { width:0; } }

        .tz-hero, [data-testid="stMetric"],
        [data-testid="stMain"] [data-testid="stLayoutWrapper"]
            > [data-testid="stVerticalBlock"]:not([class*="st-key-"]) {
            animation:tz-rise .32s cubic-bezier(.2,.7,.3,1) both;
        }
        /* Cascade sur une rangee de colonnes : 40 ms d'ecart, assez pour que
           l'oeil suive la lecture de gauche a droite sans attendre. */
        [data-testid="stColumn"]:nth-child(2) > div { animation-delay:.04s; }
        [data-testid="stColumn"]:nth-child(3) > div { animation-delay:.08s; }
        [data-testid="stColumn"]:nth-child(4) > div { animation-delay:.12s; }

        .tz-meter span { animation:tz-fill .6s cubic-bezier(.2,.7,.3,1) both; }

        /* Les lignes de liste repondent au survol : sur une liste de demandes a
           traiter, savoir quelle ligne on pointe evite de cliquer a cote. */
        .tz-row {
            border-radius:var(--tz-r-chip);
            transition:background .14s ease;
        }
        .tz-row:hover { background:rgba(11,87,168,.045); }
        .tz-av, .tz-chip { transition:transform .14s ease; }
        [data-testid="stMetric"]:hover .tz-av { transform:scale(1.04); }

        [data-testid="stMain"] a { transition:color .13s ease, opacity .13s ease; }

        /* Respect du reglage systeme : plus aucun mouvement si l'utilisateur
           l'a desactive. */
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration:.001ms !important;
                animation-iteration-count:1 !important;
                transition-duration:.001ms !important;
            }
        }

        /* ---- Bande de contexte -------------------------------------------- */
        .wf-context {
            display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;
        }
        .wf-brand {
            font-weight:800; font-size:17px; color:var(--tz-ink);
            letter-spacing:-.02em;
        }
        .wf-chip {
            display:inline-block; padding:2px 9px; border-radius:var(--tz-r-chip);
            background:var(--tz-wash); color:var(--tz-blue);
            border:1px solid #CFE4FA; font-size:12.5px; font-weight:600;
        }
        .wf-meta { color:var(--tz-muted); font-size:13px; }

        [data-testid="stMain"] hr { border-color:var(--tz-line); opacity:1; }
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
