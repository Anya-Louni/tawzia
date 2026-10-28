"""
Tableau de bord , l'écran qu'un responsable ouvre chaque matin.

L'ordre de lecture est délibéré : d'abord ce qui se passe aujourd'hui (présence,
absences, demandes qui attendent une décision), ensuite ce qui arrive (calendrier
algérien, charge prévue), enfin le planning recommandé et son coût. Un
responsable qui n'a que trente secondes ne lit que la première bande, et elle
suffit à savoir s'il doit agir.

Toutes les évolutions affichées sont comparées à une base réelle et nommée , la
moyenne de la fenêtre de pointage chargée , jamais à un « mois dernier » qui
n'existe pas dans les données.
"""

import datetime as _dt

import altair as alt
import pandas as pd
import streamlit as st

from core import (appdata, attendance as att_mod, brand, calendar_dz,
                  company_data as cd, deadlines_dz as dl, demand as demand_mod,
                  industry, sector_features as sf)

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]
horizon = st.session_state["horizon"]

_MONTHS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre")

# Couleurs de la présence : le bleu de marque pour ce qui va bien, deux tons
# chauds pour les deux problèmes. Le modèle de référence empilait trois bleus ;
# une absence rendue en nuance de bleu se lit comme une variante de présence, ce
# qui est exactement l'erreur qu'un tableau de bord RH ne peut pas faire.
C_OK, C_LATE, C_ABS = brand.BLUE, "#E4A13B", "#DE5B4F"


def _date_fr(d: _dt.date) -> str:
    return (f"{calendar_dz.WEEKDAY_NAMES_FR[d.weekday()]} {d.day} "
            f"{_MONTHS_FR[d.month - 1]} {d.year}")


def _hijri_fr(d: _dt.date) -> str:
    hy, hm, hd = calendar_dz.to_hijri(d)
    return f"{hd} {calendar_dz.HIJRI_MONTHS[hm]} {hy}"


# ---------------------------------------------------------------------------
# Les données du jour : effectif, pointage, demandes, risque de départ
# ---------------------------------------------------------------------------
people = appdata.hr_people()
records = appdata.hr_attendance()
requests = appdata.hr_requests()
risk = appdata.hr_attrition()

adf = pd.DataFrame([{"date": r.date, "flag": r.flag} for r in records])
# Deux dates différentes, et l'écran doit le dire : la journée réelle, et le
# dernier jour effectivement pointé. Le journal de pointage s'arrête à la
# veille, donc appeler « aujourd'hui » le dernier pointage serait faux.
now = _dt.date.today()
last_clocked = adf["date"].max() if not adf.empty else now
day = adf[adf["date"] == last_clocked] if not adf.empty else adf
clocked_label = f"{last_clocked.day} {_MONTHS_FR[last_clocked.month - 1]}"
is_today = last_clocked == now

planned_today = len(day)
absent_today = int((day["flag"] == "absent").sum()) if planned_today else 0
late_today = int((day["flag"] == "late").sum()) if planned_today else 0
present_today = planned_today - absent_today

# Base de comparaison : la même mesure, moyennée sur toute la fenêtre chargée.
n_days = adf["date"].nunique() if not adf.empty else 0
mean_absent = (adf["flag"] == "absent").sum() / n_days if n_days else 0.0
present_rate = present_today / planned_today * 100 if planned_today else 0.0
mean_present_rate = (
    (adf["flag"] != "absent").sum() / len(adf) * 100 if len(adf) else 0.0
)

pending = [r for r in requests if r.status == "pending"]
leave_pending = [r for r in pending if r.kind in ("annual", "unpaid", "family")]

cdd = sum(1 for e in people if str(e.contract).upper() == "CDD")
cdd_share = cdd / len(people) * 100 if people else 0.0

high_risk = int((risk["Band"] == "high").sum()) if not risk.empty else 0

# ---------------------------------------------------------------------------
# Le planning : prévision de charge et roster recommandé
# ---------------------------------------------------------------------------
plan = appdata.load_forward_plan(
    st.session_state["profile_key"],
    wilaya,
    horizon,
    st.session_state["regular_pool"],
    st.session_state["temp_ceiling"],
    st.session_state["service_level"],
    st.session_state["allow_network"],
)
fc, roster = plan["forecast"], plan["roster"]

daily = fc.groupby("date", as_index=False).agg(
    forecast=("forecast", "sum"), p10=("p10", "sum"), p90=("p90", "sum")
)
daily_staff = roster.groupby("date", as_index=False).agg(
    staff=("total_staff", "sum"), cost=("planned_cost", "sum")
)
peak_row = daily.loc[daily["forecast"].idxmax()]
# La fenêtre est nommée par ses dates réelles, jamais par « les N prochains
# jours ». La prévision part du lendemain du dernier jour d'historique, et
# l'historique s'arrête au dernier jour où la météo réelle est publiée (ERA5
# a quelques jours de retard). Dire « prochains jours » alors que la fenêtre
# est déjà passée est le genre de détail qu'un client repère en réunion.
win_start = pd.to_datetime(daily["date"].min()).date()
win_end = pd.to_datetime(daily["date"].max()).date()
win_label = (f"du {win_start.day} {_MONTHS_FR[win_start.month - 1]} "
             f"au {win_end.day} {_MONTHS_FR[win_end.month - 1]}")
win_stale = win_end < now
total_cost = float(daily_staff["cost"].sum())
peak_staff = int(roster.groupby("date")["total_staff"].sum().max())
temp_share = (
    roster["temp"].sum() / roster["total_staff"].sum() * 100
    if roster["total_staff"].sum() else 0
)

# ---------------------------------------------------------------------------
# Bandeau d'accueil : la date du jour, la date hijri, le contexte
# ---------------------------------------------------------------------------
st.markdown(
    f'<div class="tz-hero"><div>'
    f'<h1 class="tz-hero-h">Tableau de bord</h1>'
    f'<div class="tz-hero-s">{_date_fr(now)} · {_hijri_fr(now)} · '
    f'<b>{profile.label}</b> · {wilaya} · charge mesurée en '
    f'{profile.demand_unit}</div></div></div>',
    unsafe_allow_html=True,
)
industry.banner()

if plan["infeasible"]:
    st.error(
        "**Ce site ne peut pas couvrir légalement la prévision.** L'effectif "
        "permanent plus le plafond d'intérimaires ne suffit pas, dans les limites "
        "du plafond d'heures supplémentaires et du repos hebdomadaire, à servir la "
        "demande prévue. C'est un vrai constat, pas une erreur : le site a besoin "
        "de plus d'effectif. Augmentez l'effectif permanent ou le plafond "
        "d'intérimaires dans « Réglages » pour voir ce qu'il faudrait.",
        icon=":material/warning:",
    )

# ---------------------------------------------------------------------------
# Première bande : les quatre chiffres du jour
# ---------------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)

with k1, st.container(border=True, height="stretch"):
    appdata.stat_card(
        "Effectif suivi", f"{len(people)}",
        f"{cdd_share:.0f}% CDD", "flat",
        f"{len(people) - cdd} CDI · {cdd} CDD · {wilaya}",
    )
with k2, st.container(border=True, height="stretch"):
    appdata.stat_card(
        "Présents" + ("" if is_today else " au dernier pointage"),
        f"{present_today}",
        f"{present_rate - mean_present_rate:+.1f} pt",
        "up" if present_rate >= mean_present_rate else "down",
        f"{clocked_label} · sur {planned_today} postes · moyenne "
        f"{mean_present_rate:.0f}% sur {n_days} jours",
    )
with k3, st.container(border=True, height="stretch"):
    appdata.stat_card(
        "Absents" + ("" if is_today else " au dernier pointage"),
        f"{absent_today}",
        (f"{(absent_today - mean_absent) / mean_absent * 100:+.0f}%"
         if mean_absent else "premier jour"),
        "down" if absent_today > mean_absent else "up",
        f"{clocked_label} · moyenne {mean_absent:.1f} par jour · "
        f"{late_today} en retard",
    )
with k4, st.container(border=True, height="stretch"):
    appdata.stat_card(
        "Demandes en attente", f"{len(pending)}",
        f"{len(leave_pending)} congés", "flat",
        "à arbitrer avec la charge de la semaine",
    )

# ---------------------------------------------------------------------------
# Deuxième bande : présence dans le temps, et ce qui arrive
# ---------------------------------------------------------------------------
left, right = st.columns([3, 2])

with left:
    with st.container(border=True):
        appdata.card_head("Présence par jour",
                          f"{n_days} derniers jours ouvrés")
        appdata.legend([("À l'heure", C_OK), ("En retard", C_LATE),
                        ("Absent", C_ABS)])
        if adf.empty:
            st.markdown('<div class="tz-empty">Aucun pointage chargé.</div>',
                        unsafe_allow_html=True)
        else:
            _FR = {"on_time": "À l'heure", "late": "En retard",
                   "absent": "Absent"}
            per_day = (adf.assign(statut=adf["flag"].map(_FR))
                       .groupby(["date", "statut"]).size()
                       .rename("agents").reset_index())
            per_day["jour"] = pd.to_datetime(per_day["date"]).dt.strftime("%d/%m")
            order = ["À l'heure", "En retard", "Absent"]
            chart = (
                alt.Chart(per_day)
                # Coins arrondis sur chaque segment : c'est ce qui donne au
                # graphique empilé son allure de blocs posés, pas de colonne.
                .mark_bar(cornerRadius=5, size=26)
                .encode(
                    x=alt.X("jour:N", title=None, sort=None,
                            axis=alt.Axis(labelAngle=0, labelColor=brand.MUTED,
                                          labelFontSize=11, domain=False,
                                          ticks=False)),
                    y=alt.Y("agents:Q", title=None, stack=True,
                            axis=alt.Axis(labelColor=brand.MUTED,
                                          labelFontSize=11, domain=False,
                                          ticks=False, gridOpacity=.5,
                                          tickCount=4)),
                    color=alt.Color("statut:N", sort=order, legend=None,
                                    scale=alt.Scale(domain=order,
                                                    range=[C_OK, C_LATE, C_ABS])),
                    # « À l'heure » repose au sol : c'est la base de la journée.
                    # Les deux problèmes s'empilent au-dessus, donc leur hauteur
                    # se compare d'un jour à l'autre sans effort.
                    order=alt.Order("color_statut_sort_index:Q",
                                    sort="ascending"),
                    tooltip=[alt.Tooltip("jour:N", title="Jour"),
                             alt.Tooltip("statut:N", title="Statut"),
                             alt.Tooltip("agents:Q", title="Agents")],
                )
                .properties(height=268)
                .configure_view(strokeWidth=0, fill=None)
                .configure_axis(grid=False)
                .configure_axisY(grid=True, gridColor="#DDE4EE",
                                 gridDash=[3, 4])
            )
            st.altair_chart(chart, width="stretch")
            st.caption(
                "Pointages simulés pour la démonstration ; en production la "
                "plateforme lit la pointeuse ou le fichier de présence."
            )

with right:
    with st.container(border=True):
        appdata.card_head("Ce qui arrive", "calendrier algérien")
        events = appdata.load_calendar_events(days=max(horizon + 60, 120))
        if events.empty:
            st.markdown('<div class="tz-empty">Aucun grand événement du '
                        'calendrier algérien dans cette fenêtre.</div>',
                        unsafe_allow_html=True)
        else:
            rows = []
            for _, e in events.head(6).iterrows():
                d = pd.to_datetime(e["Date"]).date()
                delta = (d - now).days
                rows.append({
                    "name": f"{d.day} {_MONTHS_FR[d.month - 1]} · {e['Event']}",
                    "sub": e["Impact"],
                    "meta": f"J+{delta}" if delta > 0 else "aujourd'hui",
                    "hot": 0 <= delta <= 7,
                })
            appdata.list_rows(rows, avatars=False, wrap=True)
        st.page_link("app_pages/calendar_view.py",
                     label="Calendrier complet et vérification",
                     icon=":material/calendar_month:")

# ---------------------------------------------------------------------------
# Troisième bande : ce qui demande une décision aujourd'hui
# ---------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)

with c1, st.container(border=True, height="stretch"):
    appdata.card_head("Demandes à traiter", f"{len(pending)} en attente")
    appdata.list_rows([
        {"name": r.emp_name,
         "sub": f"{r.kind_label} · {r.start:%d/%m}"
                + (f" au {r.end:%d/%m}" if r.end != r.start else ""),
         "meta": (f"{(r.end - r.start).days + 1} j" if not r.is_sortie
                  else f"{r.hours:.0f} h" if r.hours else "sortie"),
         "hot": (r.start - now).days <= 3}
        for r in pending[:4]
    ], empty="Aucune demande en attente.")
    st.page_link("app_pages/requests_view.py",
                 label="Arbitrer les demandes",
                 icon=":material/how_to_reg:")

with c2, st.container(border=True, height="stretch"):
    appdata.card_head("Risque de départ", f"{high_risk} à risque élevé")
    appdata.list_rows([
        {"name": r["Name"], "sub": r["Top driver"],
         "meta": f"{r['Risk %']:.0f} %", "hot": r["Band"] == "high"}
        for _, r in risk.head(4).iterrows()
    ], empty="Aucun profil scoré.")
    st.page_link("app_pages/retention_negotiator.py",
                 label="Voir les causes et le coût",
                 icon=":material/trending_down:")

with c3, st.container(border=True, height="stretch"):
    # L'échéance qui coûte de l'argent si elle passe : elle a sa place ici,
    # au-dessus du pli, pas seulement dans la page qui lui est dédiée.
    appdata.card_head("À déclarer", "CNAS et impôts")
    _dls = dl.upcoming(now, headcount=len(people), horizon_days=60)
    appdata.list_rows([
        {"name": o.label,
         "sub": f"{o.body} · {o.period}",
         "meta": (f"en retard" if o.days_left(now) < 0
                  else f"J+{o.days_left(now)}"),
         "hot": o.status(now) in ("en_retard", "urgent")}
        for o in _dls[:3]
    ], empty="Rien à déclarer dans les 60 jours.",
        avatars=False, wrap=True)
    st.page_link("app_pages/deadlines_view.py",
                 label="Toutes les échéances et les portails",
                 icon=":material/event_available:")

with c4, st.container(border=True, height="stretch"):
    appdata.card_head("Retards et absences",
                      f"{late_today + absent_today} signalements")
    flags = att_mod.todays_flags(records)
    appdata.list_rows([
        {"name": r["Nom"], "sub": f"{r['Statut']} · prévu {r['Prévu']}",
         "meta": (f"+{r['Retard (min)']} min" if r["Retard (min)"] != ""
                  else "absence"),
         "hot": r["Statut"].startswith("Absent")}
        for _, r in flags.head(4).iterrows()
    ], empty="Tout le monde à l'heure aujourd'hui.")
    st.page_link("app_pages/requests_view.py", label="Registre de présence",
                 icon=":material/schedule:")

# ---------------------------------------------------------------------------
# Quatrième bande : la charge prévue et le planning qui en découle
# ---------------------------------------------------------------------------
st.markdown("### Charge prévue et planning")
st.caption(
    f"Fenêtre de prévision : **{win_label}** ({horizon} jours), calculée à "
    f"partir du dernier jour d'historique disponible."
)
if win_stale:
    st.warning(
        "Cette fenêtre est déjà passée : le calcul en cache date d'avant "
        "aujourd'hui. Relancez le calcul pour prévoir à partir de la date du "
        "jour (menu « Données », puis décochez et recochez les appels en "
        "direct pour forcer un recalcul).",
        icon=":material/history:",
    )

# Conteneur nommé : deux de ces quatre tuiles portent une courbe et deux non,
# donc sans hauteur commune la rangée est bancale. La règle est limitée à cette
# rangée pour ne pas grandir toutes les métriques de l'application.
with st.container(key="tz_planrow"):
    m1, m2, m3, m4 = st.columns(4)
m1.metric(
    f"Charge ({profile.demand_unit})", f"{daily['forecast'].sum():,.0f}",
    border=True, chart_data=daily["forecast"].tolist(), chart_type="line",
    help=f"Total sur la fenêtre {win_label}.",
)
m2.metric(
    "Jour de pic", pd.to_datetime(peak_row["date"]).strftime("%d/%m"),
    f"{peak_row['forecast']:,.0f}", border=True,
    help="Le jour où la charge prévue est la plus forte.",
)
m3.metric(
    "Effectif de pic", f"{peak_staff}", border=True,
    chart_data=daily_staff["staff"].tolist(), chart_type="bar",
    help="Jour le plus chargé, tous shifts confondus.",
)
m4.metric(
    "Coût planifié", appdata.dzd(total_cost, compact=True), border=True,
    help="Coût chargé, charges patronales CNAS et primes légales comprises.",
)

pl, pr = st.columns([3, 2])

with pl:
    with st.container(border=True):
        appdata.card_head("Demande prévue",
                          f"quantile p{st.session_state['service_level'] * 100:.0f}")
        st.caption(
            "La zone entre les deux bornes est l'intervalle p10-p90, dérivé de "
            "l'erreur réelle du backtest à chaque horizon. Ce n'est pas une "
            "distribution supposée."
        )
        chart_df = daily.set_index("date")[["p10", "forecast", "p90"]]
        chart_df.columns = ["Bas (p10)", "Prévision", "Haut (p90)"]
        st.line_chart(chart_df, height=272,
                      color=["#C6D2E2", brand.BLUE, "#C6D2E2"])

with pr:
    with st.container(border=True):
        appdata.card_head("Composition du planning", "sur l'horizon")
        st.markdown(
            f'<div class="tz-meter"><span style="width:'
            f'{min(temp_share, 100):.1f}%"></span></div>'
            f'<div class="tz-meter-l"><span>Intérim {temp_share:.0f}%</span>'
            f'<span>Permanents {100 - temp_share:.0f}%</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Un intérimaire porte une majoration de 35%. Au-delà d'un quart du "
            "planning, la question n'est plus le planning mais l'effectif "
            "permanent."
        )
        ot = float(roster["overtime"].sum())
        st.markdown(
            f'<div class="tz-row"><div class="tz-av">HS</div>'
            f'<div class="tz-row-txt"><div class="tz-row-t">'
            f'{ot:,.0f} heures supplémentaires</div>'
            f'<div class="tz-row-s">dans le plafond légal</div></div></div>'
            f'<div class="tz-row"><div class="tz-av">SU</div>'
            f'<div class="tz-row-txt"><div class="tz-row-t">'
            f'{int(roster["supervisors"].sum())} postes de superviseur</div>'
            f'<div class="tz-row-s">taux d\'encadrement respecté</div></div></div>',
            unsafe_allow_html=True,
        )
        st.page_link("app_pages/roster_view.py",
                     label="Planning détaillé et coût",
                     icon=":material/groups:")

# --- Spotlight secteur : la fonctionnalité propre à l'activité choisie ------
try:
    _sfc = appdata.expected_demand(
        st.session_state["profile_key"], wilaya, horizon,
        st.session_state["allow_network"])
    _sec_plan = {"forecast": _sfc}
except Exception:
    _sec_plan = plan
_feat = sf.compute(st.session_state["profile_key"], _sec_plan, cd.people())
if _feat is not None:
    with st.container(border=True):
        appdata.card_head(f"{_feat.icon} {_feat.title}", "propre à votre activité")
        cols = st.columns(len(_feat.metrics)) if _feat.metrics else []
        for col, (label, display, help_txt) in zip(cols, _feat.metrics):
            col.metric(label, display, help=help_txt or None)
        if _feat.insight:
            st.caption(f":material/lightbulb: {_feat.insight}")
        st.page_link("app_pages/sector_view.py", label="Analyse sectorielle",
                     icon=":material/insights:")

with st.container(border=True):
    appdata.card_head("Planning recommandé", win_label)
    st.caption(
        f"Construit au quantile de demande "
        f"p{st.session_state['service_level'] * 100:.0f}, dans les limites du "
        f"plafond d'heures supplémentaires et du repos hebdomadaire."
    )
    show = roster[[
        "date", "shift", "forecast_for_roster", "required_workers",
        "regular", "overtime", "temp", "total_staff", "supervisors", "planned_cost",
    ]].copy()
    show["date"] = pd.to_datetime(show["date"]).dt.strftime("%a %d %b")
    st.dataframe(
        show,
        hide_index=True,
        width="stretch",
        column_config={
            "date": "Date",
            "shift": "Shift",
            "forecast_for_roster": st.column_config.NumberColumn(
                f"Prévision ({profile.demand_unit})", format="%d"
            ),
            "required_workers": st.column_config.NumberColumn("Requis", format="%d"),
            "regular": st.column_config.NumberColumn("Permanents", format="%d"),
            "overtime": st.column_config.NumberColumn("Heures sup", format="%d"),
            "temp": st.column_config.NumberColumn("Intérim", format="%d"),
            "total_staff": st.column_config.NumberColumn("Total", format="%d"),
            "supervisors": st.column_config.NumberColumn("Superviseurs", format="%d"),
            "planned_cost": st.column_config.NumberColumn("Coût (DZD)", format="%.0f"),
        },
    )

st.caption(f":material/cloud: Météo de la prévision : {plan['weather_provenance']}")
appdata.data_badge()
