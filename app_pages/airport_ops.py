"""
IA opérations aéroportuaires — le module Air Algérie / Aéroport d'Alger.

Trois fonctionnalités de niveau aéronautique sur le vrai réseau ALG et le vrai
calendrier algérien :
  1. Prévision du flux de passagers -> effectif du terminal
  2. Prédicteur de cascade de retards (la « journée chaotique », prédite)
  3. Tableau des risques de rotation
"""

import datetime as dt

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from core import appdata, aviation, calendar_dz

appdata.sidebar_controls()

st.title("IA opérations aéroportuaires")
st.caption(
    "Aéroport d'Alger (ALG) · réseau Air Algérie · construit sur la vraie carte "
    "des routes et le vrai calendrier algérien"
)

st.info(
    "**Pourquoi c'est important maintenant.** Air Algérie passe de ~8,8M "
    "passagers (2025) vers ~10M (2026) et intègre ~60 nouveaux appareils sur un "
    "hub déjà congestionné au pic. Les deux modes d'échec coûteux , surges de "
    "passagers non dotées et retards qui cascadent sur toute la journée , sont "
    "exactement ce que ce module prédit. Les horaires de vols et les retards "
    "sont simulés ; le réseau de routes et le calendrier qui pilote la demande "
    "sont réels.",
    icon=":material/flight_takeoff:",
)

_DIR_FR = {"Arrival": "Arrivée", "Departure": "Départ"}
_CAUSE_FR = {
    "On time": "À l'heure", "On plan": "Conforme au plan",
    "Root cause": "Cause racine", "Cascade (inherited)": "Cascade (héritée)",
}

# --- Sélecteur de date -----------------------------------------------------
col_d, col_info = st.columns([1, 3])
with col_d:
    day = st.date_input(
        "Journée d'exploitation",
        value=dt.date(2026, 7, 25),
        min_value=dt.date(2026, 1, 1),
        max_value=dt.date(2027, 12, 31),
        help="Essayez un samedi d'été (pic diaspora) vs un jour de semaine en janvier.",
    )
day_iso = day.isoformat()
ctx = calendar_dz.day_context(day)

with col_info:
    tags = []
    if ctx.diaspora_intensity > 0.1:
        tags.append(f":material/beach_access: Saison diaspora ({ctx.diaspora_intensity:.0%} du pic)")
    if ctx.is_ramadan:
        tags.append(f":material/nightlight: Ramadan jour {ctx.ramadan_day}")
    if ctx.is_public_holiday:
        tags.append(f":material/celebration: {ctx.holiday_name}")
    if ctx.is_weekend:
        tags.append(":material/weekend: Week-end algérien (ven-sam)")
    st.markdown(f"**{day:%A %d %B %Y}** — " + (" · ".join(tags) if tags else "journée ordinaire"))

sched = appdata.flight_day(day_iso)
day_ctx = sched.attrs["day_context"]

tab_flow, tab_cascade, tab_turnaround, tab_board = st.tabs([
    "Flux passagers & effectif",
    "Prédicteur de cascade de retards",
    "Risque de rotation",
    "Tableau des vols",
])

# ===========================================================================
# TAB 1 — Flux passagers & effectif du terminal
# ===========================================================================
with tab_flow:
    flow = appdata.pax_flow_for(day_iso)
    s = flow.summary

    st.subheader("Flux de passagers dans le terminal")
    st.caption(
        "Les passagers n'arrivent pas d'un bloc au départ , ils s'accumulent sur "
        "une fenêtre de présentation avant chaque vol, plus longue pour le "
        "long-courrier. Cumulé sur tous les vols, c'est la foule réellement dans "
        "le bâtiment à chaque heure. Le **pic**, pas le total quotidien, "
        "détermine combien de comptoirs ouvrir."
    )

    with st.container(horizontal=True):
        st.metric("Départs aujourd'hui", f"{s['total_departing_pax']:,}", border=True)
        st.metric("Arrivées aujourd'hui", f"{s['total_arriving_pax']:,}", border=True)
        st.metric(
            "Heure de pointe du terminal",
            f"{s['peak_hour']:%H:%M}",
            f"{s['peak_terminal_pax']:,} pax dans le bâtiment",
            border=True,
        )
        st.metric(
            "Agents d'enregistrement au pic",
            f"{s['peak_checkin_agents']}",
            f"à {s['peak_checkin_hour']:%H:%M}",
            border=True,
        )
        st.metric("Files de sûreté au pic", f"{s['peak_security_lanes']}", border=True)

    with st.container(border=True):
        st.markdown("**Passagers à chaque processus, par heure**")
        h = flow.hourly.copy()
        h_long = h.melt(
            id_vars="hour",
            value_vars=["checkin", "security", "boarding", "immigration", "baggage"],
            var_name="Processus", value_name="Passagers",
        )
        proc_labels = {
            "checkin": "Enregistrement", "security": "Sûreté", "boarding": "Embarquement",
            "immigration": "Immigration (arr)", "baggage": "Bagages (arr)",
        }
        h_long["Processus"] = h_long["Processus"].map(proc_labels)
        chart = (
            alt.Chart(h_long)
            .mark_area(opacity=0.75)
            .encode(
                x=alt.X("hour:T", title=None, axis=alt.Axis(format="%H:%M")),
                y=alt.Y("Passagers:Q", stack=None, title="Passagers en cours de traitement"),
                color=alt.Color("Processus:N",
                                scale=alt.Scale(range=["#C8102E", "#16233A", "#B78B4A",
                                                       "#1E6F5C", "#7C8494"])),
                tooltip=["hour:T", "Processus:N", alt.Tooltip("Passagers:Q", format=".0f")],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, width="stretch")

    with st.container(border=True):
        st.markdown("**Effectif recommandé du terminal, par heure**")
        st.caption(
            "Agents par processus et par heure pour écouler la demande sans file "
            "d'attente , les heures de nuit (21:00-05:00) portent la majoration "
            "légale de +30% dans le total chiffré ci-dessous."
        )
        stf = flow.staffing.copy()
        stf_show = stf[stf["total_agents"] > 0].copy()
        stf_show["hour"] = pd.to_datetime(stf_show["hour"]).dt.strftime("%a %H:%M")
        st.dataframe(
            stf_show.rename(columns={
                "hour": "Heure", "checkin": "Enregistrement", "security": "Sûreté",
                "boarding": "Embarquement", "immigration": "Immigration",
                "baggage": "Bagages", "total_agents": "Total",
            }),
            hide_index=True, width="stretch", height=280,
        )
        st.metric("Coût d'effectif du terminal sur la journée",
                  appdata.dzd(s["daily_staff_cost"], compact=True), border=True)

# ===========================================================================
# TAB 2 — Prédicteur de cascade de retards (fonction phare)
# ===========================================================================
with tab_cascade:
    st.subheader("Prédicteur de cascade de retards")
    st.caption(
        "Les avions volent en chaînes , un même appareil fait "
        "ALG→CDG→ALG→ORN→ALG toute la journée. Un vol entrant en retard mange sa "
        "rotation et repousse chaque vol suivant. Ceci prédit la chaîne **avant** "
        "qu'elle ne se produise et nomme le vol unique à protéger pour la briser."
    )

    severity = st.select_slider(
        "Sévérité de la journée",
        options=[0.8, 1.0, 1.3, 1.6, 2.0, 2.4],
        value=1.3,
        format_func=lambda v: {0.8: "Calme", 1.0: "Normale", 1.3: "Chargée",
                               1.6: "Difficile", 2.0: "Mauvais temps",
                               2.4: "Journée chaotique"}[v],
        help="Module combien de vols prennent leur propre retard racine. "
             "Regardez la cascade grandir à mesure que la journée empire.",
    )

    res = appdata.cascade(day_iso, severity)
    cs = res.summary

    with st.container(horizontal=True):
        st.metric("Ponctualité", f"{cs['on_time_pct']:.0f}%", border=True)
        st.metric("Vols retardés", f"{cs['delayed_flights']}",
                  f"sur {cs['total_flights']}", border=True)
        st.metric(
            "Part de cascade",
            f"{cs['cascade_share']:.0f}%",
            "des retards sont hérités",
            border=True,
            help="Retards qui étaient la faute d'un autre vol, pas les leurs. "
                 "Dans l'industrie, ce retard « réactionnaire » représente 40-50%.",
        )
        st.metric("Passagers sur un vol retardé", f"{cs['pax_affected']:,}", border=True)

    if cs["worst_keystone"]:
        k = cs["worst_keystone"]
        st.error(
            f"**Vol pivot : {k['flight_no']} ({k['route_city']}, "
            f"{_DIR_FR.get(k['direction'], k['direction']).lower()}).** Si son "
            f"entrant glisse, **{int(k['downstream_flights'])} vols en aval** et "
            f"**{int(k['downstream_pax']):,} passagers** sont touchés "
            f"({int(k['downstream_delay_min'])} minutes de retard). Protégez "
            f"cette rotation en priorité , gardez un équipage de réserve ou "
            f"changez d'appareil.",
            icon=":material/priority_high:",
        )

    col_k, col_w = st.columns([3, 2])
    with col_k:
        with st.container(border=True):
            st.markdown("**Vols pivots — à protéger en priorité**")
            st.caption("Classés par passagers touchés en aval.")
            if len(res.keystones):
                kk = res.keystones.copy()
                kk["sched_time"] = pd.to_datetime(kk["sched_time"]).dt.strftime("%H:%M")
                kk["direction"] = kk["direction"].map(_DIR_FR).fillna(kk["direction"])
                st.dataframe(
                    kk[["flight_no", "route_city", "direction", "sched_time",
                        "downstream_flights", "downstream_pax", "downstream_delay_min"]]
                    .rename(columns={
                        "flight_no": "Vol", "route_city": "Route",
                        "direction": "Sens", "sched_time": "Prévu",
                        "downstream_flights": "↓Vols", "downstream_pax": "↓Pax",
                        "downstream_delay_min": "↓Retard min",
                    }),
                    hide_index=True, width="stretch",
                )
            else:
                st.success("Aucune cascade prédite à cette sévérité.")
    with col_w:
        with st.container(border=True):
            st.markdown("**Répartition des retards**")
            breakdown = pd.DataFrame({
                "Type": ["À l'heure", "Cause racine", "Cascade (héritée)"],
                "Vols": [
                    cs["total_flights"] - cs["delayed_flights"],
                    cs["root_flights"], cs["cascade_flights"],
                ],
            })
            donut = (
                alt.Chart(breakdown)
                .mark_arc(innerRadius=55)
                .encode(
                    theta="Vols:Q",
                    color=alt.Color("Type:N", scale=alt.Scale(
                        domain=["À l'heure", "Cause racine", "Cascade (héritée)"],
                        range=["#1E6F5C", "#9C6209", "#C8102E"])),
                    tooltip=["Type:N", "Vols:Q"],
                )
                .properties(height=240)
            )
            st.altair_chart(donut, width="stretch")
            st.caption(
                "La tranche rouge est le gain : des retards que l'on peut "
                "prévenir en amont au lieu de les absorber partout."
            )

    with st.container(border=True):
        st.markdown("**Carte des rotations — les appareils les plus chargés**")
        st.caption("Le retard total prédit de chaque appareil sur sa chaîne de vols du jour.")
        rot = res.rotations.head(12).copy()
        rot_chart = (
            alt.Chart(rot)
            .mark_bar()
            .encode(
                y=alt.Y("tail:N", sort="-x", title="Appareil"),
                x=alt.X("total_delay:Q", title="Retard total prédit (min)"),
                color=alt.value("#C8102E"),
                tooltip=["tail:N", "aircraft:N", "legs:Q", "total_delay:Q", "pax:Q"],
            )
            .properties(height=300)
        )
        st.altair_chart(rot_chart, width="stretch")

# ===========================================================================
# TAB 3 — Risque de rotation
# ===========================================================================
with tab_turnaround:
    st.subheader("Tableau des risques de rotation")
    st.caption(
        "Pour chaque appareil arrivant avec un vol de continuation, à quel point "
        "le temps au sol est-il serré face à la rotation minimale ? Un temps au "
        "sol serré est là où un petit retard entrant devient un retard au départ "
        ", le cas d'usage d'optimisation de rotation de Boeing lui-même, sur le "
        "programme ALG."
    )

    res2 = appdata.cascade(day_iso, 1.3)
    fl = res2.flights.copy()

    # Calcule la marge au sol de chaque appareil entre une arrivée et son départ suivant.
    fl = fl.sort_values(["tail", "sched_time"])
    rows = []
    for tail, grp in fl.groupby("tail"):
        legs = grp.to_dict("records")
        for a, b in zip(legs, legs[1:]):
            if a["direction"] == "Arrival" and b["direction"] == "Departure":
                ground = (pd.Timestamp(b["sched_time"]) - pd.Timestamp(a["sched_time"])).total_seconds() / 60
                slack = ground - a["min_turnaround"]
                rows.append({
                    "Entrant": a["flight_no"], "de": a["route_city"],
                    "Sortant": b["flight_no"], "vers": b["route_city"],
                    "Appareil": a["aircraft_name"], "tail": tail,
                    "Au sol (min)": int(ground), "Rotation min (min)": int(a["min_turnaround"]),
                    "Marge (min)": int(slack), "Pax sortant": int(b["passengers"]),
                })
    turn = pd.DataFrame(rows)
    if not turn.empty:
        def risk(slack):
            if slack < 10:
                return "🔴 Critique"
            if slack < 25:
                return "🟠 Serrée"
            return "🟢 Confortable"
        turn["Risque"] = turn["Marge (min)"].apply(risk)
        turn = turn.sort_values("Marge (min)")

        with st.container(horizontal=True):
            st.metric("Rotations aujourd'hui", f"{len(turn)}", border=True)
            st.metric("Critiques (<10 min de marge)",
                      f"{(turn['Marge (min)'] < 10).sum()}", border=True)
            st.metric("Serrées (<25 min de marge)",
                      f"{(turn['Marge (min)'] < 25).sum()}", border=True)
            st.metric("Pax sur rotations serrées",
                      f"{turn.loc[turn['Marge (min)'] < 25, 'Pax sortant'].sum():,}",
                      border=True)

        with st.container(border=True):
            st.dataframe(
                turn[["Risque", "Entrant", "de", "Sortant", "vers", "Appareil",
                      "Au sol (min)", "Rotation min (min)", "Marge (min)", "Pax sortant"]],
                hide_index=True, width="stretch", height=380,
            )
    else:
        st.caption("Aucune rotation liée dans ce programme.")

# ===========================================================================
# TAB 4 — Tableau des vols
# ===========================================================================
with tab_board:
    st.subheader("Tableau des vols prédit")
    st.caption("La journée complète avec les retards prédits et leur cause.")

    res3 = appdata.cascade(day_iso, 1.3)
    board = res3.flights.copy()
    board["sched_time"] = pd.to_datetime(board["sched_time"])
    board = board.sort_values("sched_time")

    c1, c2 = st.columns(2)
    with c1:
        dirs = st.multiselect("Sens", ["Arrival", "Departure"],
                              default=["Arrival", "Departure"],
                              format_func=lambda d: _DIR_FR.get(d, d))
    with c2:
        show_delayed = st.toggle("Vols retardés seulement", value=False)

    view = board[board["direction"].isin(dirs)]
    if show_delayed:
        view = view[view["is_delayed"]]

    disp = view[["sched_time", "flight_no", "direction", "route_city",
                 "aircraft_name", "passengers", "predicted_delay", "delay_source"]].copy()
    disp["sched_time"] = disp["sched_time"].dt.strftime("%H:%M")
    disp["direction"] = disp["direction"].map(_DIR_FR).fillna(disp["direction"])
    disp["delay_source"] = disp["delay_source"].map(_CAUSE_FR).fillna(disp["delay_source"])
    st.dataframe(
        disp.rename(columns={
            "sched_time": "Prévu", "flight_no": "Vol", "direction": "Sens",
            "route_city": "Route", "aircraft_name": "Appareil",
            "passengers": "Pax", "predicted_delay": "Retard (min)",
            "delay_source": "Cause",
        }),
        hide_index=True, width="stretch", height=460,
        column_config={
            "Retard (min)": st.column_config.NumberColumn("Retard (min)", format="%d"),
        },
    )

st.divider()
with st.expander("Ce qui est réel vs modélisé ici", icon=":material/science:"):
    st.markdown(
        """
- **Réel :** le réseau de routes ALG (destinations réelles), des types d'appareils
  et des nombres de sièges réalistes, les temps de rotation minimaux publiés, et
  le calendrier algérien qui pilote les taux de remplissage et le trafic (été de
  la diaspora, Ramadan, Aïd).
- **Modélisé :** le programme quotidien précis, l'affectation des appareils, et les
  retards. Aucune compagnie ne publie son plan de rotation en direct ni son
  journal de retards , ils sont donc simulés à la manière dont le système se
  comporte réellement.
- **Les modèles sont, eux, réels.** La propagation en cascade et la montée du flux
  passagers sont les calculs exacts que l'on ferait sur des données AODB/FIDS en
  direct , déployer sur le vrai flux d'Air Algérie est une connexion de données,
  pas une refonte.
"""
    )
appdata.data_badge()
