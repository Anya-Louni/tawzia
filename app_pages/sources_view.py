"""
Sources & hypothèses — chaque chiffre du produit, et d'où il vient.

Avoir cette page fait partie du pitch. Elle dit : nous savons lesquels de nos
chiffres sont mesurés et lesquels sont supposés, et nous n'espérons pas que vous
ne poserez pas la question.
"""

import pandas as pd
import streamlit as st

from core import appdata, sources

appdata.sidebar_controls()

st.title("Sources & hypothèses")
st.caption("Chaque chiffre d'origine externe, chaque choix de modélisation, en un seul endroit.")

measured = sources.measured()
live = sources.live_sources()
assumptions = sources.assumptions()

with st.container(horizontal=True):
    st.metric("Mesures citées", len(measured), border=True)
    st.metric("Flux de données en direct", len(live), border=True)
    st.metric("Hypothèses déclarées", len(assumptions), border=True)

st.divider()

# ---------------------------------------------------------------------------
st.subheader("Ce qui est réel dans cette app")

with st.container(border=True):
    st.markdown(
        """
| Couche | Statut |
|---|---|
| **Calendrier algérien** — Ramadan, les deux Aïds, Yennayer, jours fériés officiels, week-end vendredi-samedi | **Réel.** Calculé à partir du calendrier islamique tabulaire, vérifié en aller-retour sur 60 années hégiriennes et recoupé avec le service de référence Aladhan. |
| **Météo** — température, précipitations et stress thermique quotidiens par wilaya | **Réel.** Réanalyse ERA5 (historique observé) et prévision opérationnelle, via Open-Meteo. |
| **Macroéconomie** — population, population active, IPC, chômage | **Réel.** World Bank Open Data, récupéré en direct. |
| **Coûts de main-d'œuvre** — SNMG, charges patronales CNAS, majorations et plafonds légaux | **Réel.** Dérivés des taux algériens publiés et du code du travail. Notre plancher horaire dérivé de 138,46 DZD reproduit exactement le chiffre officiellement publié. |
| **Volumes opérationnels** — colis, passagers, cartons par shift | **Simulés.** Le registre d'aucun vrai opérateur algérien n'est public. Les volumes sont synthétiques ; le calendrier et la météo auxquels ils répondent ne le sont pas. |
| **Chiffre d'économie** | **Hors échantillon, sur des volumes simulés.** La méthode est solide et se transférerait inchangée à de vraies données. L'ampleur exige un pilote. |
"""
    )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("Mesures citées")
st.caption("Chiffres publiés. Chacun renvoie à sa source.")

rows = []
for f in measured:
    rows.append({
        "Quoi": f.label,
        "Valeur": f"{f.value:,}" if isinstance(f.value, (int, float)) else str(f.value),
        "Unité": f.unit,
        "Source": f.source,
        "En date de": f.as_of,
        "Lien": f.url,
    })
with st.container(border=True):
    st.dataframe(
        pd.DataFrame(rows), hide_index=True, width="stretch",
        column_config={
            "Source": st.column_config.TextColumn("Source", width="medium"),
            "Lien": st.column_config.LinkColumn("Lien", display_text="ouvrir"),
        },
    )

with st.expander("Pourquoi chacune compte", icon=":material/help:"):
    for f in measured:
        st.markdown(f"**{f.label}** — {f.note}")

st.divider()

# ---------------------------------------------------------------------------
st.subheader("Flux de données en direct")

with st.container(border=True):
    for f in live:
        st.markdown(f"**{f.label}** — {f.source}")
        st.caption(f"{f.note}  \n{f.url}")

st.divider()

# ---------------------------------------------------------------------------
st.subheader("Hypothèses")
st.warning(
    "Ce sont nos choix de modélisation, pas des conclusions. Ce sont les "
    "chiffres qu'un client pilote remplace par les siens dès le premier jour, "
    "et ceux sur lesquels un investisseur devrait insister le plus.",
    icon=":material/warning:",
)

for f in assumptions:
    with st.container(border=True):
        st.markdown(f"**{f.label}** = `{f.value}` {f.unit}")
        st.caption(f.note)

st.divider()

# ---------------------------------------------------------------------------
st.subheader("Ce que nous avons retiré du prototype précédent")

with st.container(border=True):
    st.markdown(
        """
Être explicite là-dessus vaut mieux que de le cacher , cela montre que le
travail est tenu à un standard.

- **Une référence truquée.** L'ancienne comparaison de coût imputait à la
  stratégie « naïve » une surcharge d'urgence de 1,3× que le plan optimisé ne
  payait jamais. L'économie était un artefact de ce choix. Les deux stratégies
  affrontent désormais des structures de coût et de pénalité identiques.

- **Une validation circulaire.** L'ancien prévisionniste était entraîné sur une
  formule à graine fixe puis évalué sur cette même formule, donc sa précision
  était garantie. Il est désormais évalué par backtest en marche avant contre
  des périodes tenues à l'écart, avec des chocs délibérément imprévisibles
  laissés dedans.

- **Le mauvais week-end.** Le motif hebdomadaire d'origine traitait le samedi et
  le dimanche comme les jours creux. Le week-end algérien est vendredi-samedi.

- **Des coûts de main-d'œuvre inventés.** « 3 000 DZD par employé par shift »
  apparaissait sans aucune dérivation. Les coûts se construisent désormais à
  partir du SNMG et du barème CNAS.

- **Un tableau des vols décoratif.** Un faux flux de vols d'apparence live ne
  pilotait rien et ne prouvait rien. Il a été retiré plutôt que maquillé.
"""
    )

appdata.data_badge()
