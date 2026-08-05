"""
Preuves , la page qui décide si l'on croit au reste de l'app.

Montre le backtest en marche avant, la comparaison contre un outil RH qui ne
comprend pas l'Algérie, et la comparaison monétaire hors échantillon où les deux
plannings ont été construits à l'aveugle et évalués sur la même demande réalisée.
"""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from core import appdata, demand as demand_mod, sources

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
wilaya = st.session_state["wilaya"]
horizon = st.session_state["horizon"]

st.title("Preuves")
st.caption(
    "Tout ici est hors échantillon. Aucun modèle de cette page n'a jamais vu "
    "les données sur lesquelles il est évalué."
)

st.info(
    "**La réserve honnête, d'emblée.** Nous n'avons pas le registre de volumes "
    "d'un vrai opérateur algérien , personne en dehors de ces entreprises ne "
    "l'a. Les *volumes de demande* de cette page sont simulés. Ce qui est réel, "
    "c'est le **calendrier algérien** auquel la demande répond (vraies dates de "
    "Ramadan et d'Aïd, vrai week-end vendredi-samedi, vrais jours fériés "
    "officiels) et la **météo observée** issue de l'archive ERA5 pour cette "
    "wilaya. Ces résultats valident donc la méthode et la mécanique , pas le "
    "marché. L'ampleur doit être confirmée par un pilote, et nous le disons à "
    "chaque investisseur qui le demande.",
    icon=":material/info:",
)

with st.spinner("Backtest et évaluation des plannings en cours…"):
    ev = appdata.load_evidence(
        st.session_state["profile_key"],
        wilaya,
        horizon,
        st.session_state["regular_pool"],
        st.session_state["temp_ceiling"],
        st.session_state["service_level"],
        st.session_state["allow_network"],
    )

bt = ev.backtest
metrics = bt.metrics
delta = ev.delta

dz = float(metrics.loc[metrics["Model"] == "WorkForce.dz", "MAPE_%"].iloc[0])
gen = float(metrics.loc[metrics["Model"] == "Generic international model", "MAPE_%"].iloc[0])
sn = float(metrics.loc[metrics["Model"] == "Seasonal naive", "MAPE_%"].iloc[0])

# Étiquettes françaises pour l'affichage, sans toucher aux clés internes.
_MODEL_FR = {
    "WorkForce.dz": "WorkForce.dz",
    "Generic international model": "Modèle international générique",
    "Seasonal naive": "Naïf saisonnier",
}

# ---------------------------------------------------------------------------
st.subheader("1. La prévision bat-elle les alternatives ?")

with st.container(horizontal=True):
    st.metric("Notre erreur de prévision (MAPE)", f"{dz:.1f}%", border=True)
    st.metric(
        "vs outil international générique",
        f"{gen:.1f}%",
        f"-{(gen - dz) / gen * 100:.0f}% d'erreur",
        border=True,
        help="Même algorithme, mêmes données, même réglage , mais avec le jeu "
             "de variables qu'aurait un outil RH conçu pour l'Europe : week-end "
             "samedi-dimanche, pas de calendrier hégirien, pas de saison de la "
             "diaspora.",
    )
    st.metric(
        "vs naïf saisonnier",
        f"{sn:.1f}%",
        f"-{(sn - dz) / sn * 100:.0f}% d'erreur",
        border=True,
        help="Même shift, même jour de semaine, la semaine dernière. Ce qu'un "
             "bon chef d'exploitation fait de tête , et une référence "
             "réellement difficile à battre.",
    )
    st.metric("Origines de prévision", f"{bt.n_origins}", border=True)

with st.container(border=True):
    st.markdown("**Métriques complètes du backtest**")
    metrics_show = metrics.copy()
    metrics_show["Model"] = metrics_show["Model"].map(_MODEL_FR).fillna(metrics_show["Model"])
    st.dataframe(
        metrics_show,
        hide_index=True,
        width="stretch",
        column_config={
            "Model": "Modèle",
            "MAE": st.column_config.NumberColumn("MAE", format="%.0f"),
            "RMSE": st.column_config.NumberColumn("RMSE", format="%.0f"),
            "MAPE_%": st.column_config.NumberColumn("MAPE %", format="%.2f"),
            "Bias_%": st.column_config.NumberColumn("Biais %", format="%+.2f"),
            "Under_%": st.column_config.NumberColumn("Sous-prévision %", format="%.1f"),
        },
    )
    st.caption(
        "Le **biais** compte plus que le MAPE pour un planning. Une prévision "
        "biaisée à la baisse sous-dote le planning, et être en sous-effectif "
        "coûte environ "
        f"{sources.value('understaffing_penalty_multiple')}× ce que valaient les "
        "salaires économisés. Le nôtre est laissé délibérément un peu positif , "
        "surestimer est la direction la moins chère."
    )

with st.container(border=True):
    st.markdown("**Erreur par horizon de prévision**")
    st.caption("À quelle vitesse chaque approche se dégrade quand on planifie plus loin.")
    pivot = bt.by_horizon.pivot(index="horizon", columns="Model", values="MAPE_%")
    pivot = pivot.rename(columns=_MODEL_FR)
    st.line_chart(
        pivot,
        height=280,
        color=["#C8102E", "#B78B4A", "#16233A", "#7C8494"],
    )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("2. La meilleure prévision se transforme-t-elle en argent ?")
st.caption(
    "Les deux plannings ont été construits à partir des seules informations "
    "disponibles à l'origine de la prévision , aucun n'a vu la demande qu'il "
    "allait affronter. Les deux paient des taux salariaux identiques, des "
    "majorations légales identiques, et une pénalité identique pour la demande "
    "qu'ils n'ont pas couverte. La seule différence est la qualité de la prévision."
)

with st.container(horizontal=True):
    st.metric(
        "Économie de coût",
        f"{delta['saving_pct']:.1f}%",
        appdata.dzd(delta["saving_dzd"], compact=True),
        border=True,
    )
    st.metric(
        "Gain de niveau de service",
        f"+{delta['service_gain_pp']:.1f} pts",
        border=True,
        help="Part de la demande réellement servie.",
    )
    st.metric(
        "Taux de victoire",
        f"{delta['win_rate']:.0f}%",
        f"sur {delta['origins']} origines",
        border=True,
    )
    st.metric(
        "Pire origine",
        f"{delta['worst_origin_pct']:+.1f}%",
        border=True,
        help="Nous perdons de l'argent sur certaines fenêtres. Une comparaison "
             "qui ne perd jamais est une comparaison truquée.",
    )

with st.container(border=True):
    st.markdown("**Comparaison de coût, agrégée sur chaque fenêtre évaluée**")
    comp = ev.comparison.copy()
    st.dataframe(
        comp,
        hide_index=True,
        width="stretch",
        column_config={
            "Strategy": "Stratégie",
            "Labour cost (DZD)": st.column_config.NumberColumn("Main-d'œuvre", format="%.0f"),
            "Shortfall cost (DZD)": st.column_config.NumberColumn("Manque à couvrir", format="%.0f"),
            "Total cost (DZD)": st.column_config.NumberColumn("Total", format="%.0f"),
            "Unserved units": st.column_config.NumberColumn("Non servies", format="%.0f"),
            "Service level": st.column_config.NumberColumn("Service", format="%.1%%"),
            "Idle units": st.column_config.NumberColumn("Sous-utilisées", format="%.0f"),
            "Worker-shifts": st.column_config.NumberColumn("Shifts-employés", format="%d"),
            "Cost per unit (DZD)": st.column_config.NumberColumn("Coût/unité", format="%.2f"),
        },
    )
    st.caption(
        "Notez que le plan optimisé dépense **plus** en main-d'œuvre et sort "
        "quand même gagnant. C'est là l'enseignement réel : dans les opérations "
        "en shifts en Algérie, l'échec coûteux est d'être en sous-effectif, pas "
        "d'être généreux."
    )

with st.container(border=True):
    st.markdown("**Économie par fenêtre de prévision**")
    st.caption(
        "Chaque barre est une fenêtre indépendante. Les négatives sont réelles , "
        "des fenêtres où un planning fixe s'est trouvé mieux collé à la demande."
    )
    po = ev.per_origin.copy()
    po["origin"] = pd.to_datetime(po["origin"])
    po = po.sort_values("origin")
    po["label"] = po["origin"].dt.strftime("%d %b %y")
    po["sign"] = np.where(po["saving_pct"] >= 0, "Économie", "Perte")

    # Altair plutôt que st.bar_chart : un axe catégoriel serait trié
    # alphabétiquement par label, ce qui brouillerait la chronologie.
    # `sort=None` conserve l'ordre du DataFrame.
    savings_chart = (
        alt.Chart(po)
        .mark_bar()
        .encode(
            x=alt.X("label:N", sort=None, title=None,
                    axis=alt.Axis(labelAngle=-45, labelFontSize=10)),
            y=alt.Y("saving_pct:Q", title="Économie vs planning fixe (%)"),
            color=alt.Color(
                "sign:N",
                scale=alt.Scale(domain=["Économie", "Perte"],
                                range=["#C8102E", "#7C8494"]),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("label:N", title="Fenêtre débutant le"),
                alt.Tooltip("saving_pct:Q", title="Économie %", format="+.1f"),
                alt.Tooltip("saving:Q", title="Économie DZD", format=",.0f"),
            ],
        )
        .properties(height=260)
    )
    st.altair_chart(savings_chart, width="stretch")

st.divider()

# ---------------------------------------------------------------------------
st.subheader("3. Quels signaux algériens gagnent réellement leur place ?")

fi = appdata.load_feature_importance(
    st.session_state["profile_key"], wilaya, st.session_state["allow_network"]
)

label_map = {
    "is_weekend_int": "Week-end vendredi-samedi",
    "is_holiday_int": "Jours fériés algériens",
    "is_ramadan_int": "Ramadan",
    "ramadan_progress": "Position dans le Ramadan",
    "eid_fitr_runup": "Approche de l'Aïd el-Fitr",
    "eid_adha_runup": "Approche de l'Aïd el-Adha",
    "diaspora_intensity": "Saison estivale de la diaspora",
    "is_rentree_int": "Rentrée scolaire",
    "payday_boost": "Cycle de paie de fin de mois",
    "shift_idx": "Shift de la journée",
    "weekday": "Jour de la semaine",
    "log_recent_level": "Niveau d'activité récent",
    "horizon": "Horizon de prévision",
    "temp_max": "Température max (réelle)",
    "precip_mm": "Précipitations (réelles)",
    "heat_stress": "Stress thermique (réel)",
    "weather_demand": "Effet météo sur la demande",
}
fi_show = fi.copy()
fi_show["Signal"] = fi_show["Feature"].map(label_map).fillna(fi_show["Feature"])
fi_show = fi_show[fi_show["Importance"] > 0].head(12)

col_a, col_b = st.columns([3, 2])
with col_a:
    with st.container(border=True):
        st.markdown("**Importance par permutation**")
        # Tri décroissant explicite , un graphe à barres simple ordonnerait les
        # catégories alphabétiquement, ce qui enterre le point de ce graphique.
        fi_show = fi_show.copy()
        fi_show["is_dz"] = fi_show["Feature"].isin([
            "is_weekend_int", "is_holiday_int", "is_ramadan_int",
            "ramadan_progress", "eid_fitr_runup", "eid_adha_runup",
            "diaspora_intensity", "is_rentree_int", "payday_boost",
        ])
        fi_show["Type de signal"] = np.where(
            fi_show["is_dz"], "Spécifique à l'Algérie", "Générique"
        )
        imp_chart = (
            alt.Chart(fi_show)
            .mark_bar()
            .encode(
                y=alt.Y("Signal:N", sort="-x", title=None),
                x=alt.X("Importance:Q", title="Importance par permutation"),
                color=alt.Color(
                    "Type de signal:N",
                    scale=alt.Scale(domain=["Spécifique à l'Algérie", "Générique"],
                                    range=["#C8102E", "#7C8494"]),
                    legend=alt.Legend(title=None, orient="top"),
                ),
                tooltip=[
                    alt.Tooltip("Signal:N"),
                    alt.Tooltip("Importance:Q", format=".4f"),
                    alt.Tooltip("Type de signal:N"),
                ],
            )
            .properties(height=340)
        )
        st.altair_chart(imp_chart, width="stretch")
with col_b:
    with st.container(border=True):
        st.markdown("**Pourquoi c'est le moat**")
        st.markdown(
            "Les signaux propres à l'Algérie , le week-end vendredi-samedi, les "
            "jours fériés officiels, le Ramadan et les approches des Aïds , "
            "portent un vrai poids prédictif.\n\n"
            "Un outil RH conçu pour un marché grégorien, samedi-dimanche, ne "
            "peut représenter aucun d'eux. Ce n'est pas qu'un tel outil est mal "
            "construit ; c'est qu'il est construit pour ailleurs.\n\n"
            "Cet écart est mesurable, et il est sur cette page : "
            f"**{(gen - dz) / gen * 100:.0f}% d'erreur en moins** que le même "
            "algorithme sans le jeu de variables algériennes."
        )
        st.caption(
            "Les variables météo se classent ici plus bas que les variables de "
            "calendrier. Leur effet se concentre dans les wilayas sahariennes et "
            "les hivers côtiers humides , basculez la wilaya sur Ouargla pour les "
            "voir compter davantage."
        )

st.divider()

with st.expander("Méthode et ses limites", icon=":material/science:"):
    for n in bt.notes:
        st.markdown(f"- {n}")
    st.markdown("---")
    for n in ev.notes:
        st.markdown(f"- {n}")

appdata.data_badge()
