"""
Le calendrier algérien , le moat, rendu visible.

Cette page existe pour rendre un argument concret : le calendrier de la demande
en Algérie n'est pas celui pour lequel un outil RH mondial a été conçu, et
l'écart est grand, récurrent et mesurable.
"""

import datetime as dt

import pandas as pd
import streamlit as st

from core import appdata, calendar_dz

appdata.sidebar_controls()

st.title("Le calendrier algérien")
st.caption("Pourquoi un outil RH conçu ailleurs se trompe ici, chaque semaine.")

# ---------------------------------------------------------------------------
st.subheader("Le week-end")

today = dt.date.today()
week_start = today - dt.timedelta(days=today.weekday())
week = [week_start + dt.timedelta(days=i) for i in range(7)]

rows = []
for d in week:
    ctx = calendar_dz.day_context(d)
    rows.append({
        "Date": d.strftime("%d %b"),
        "Jour": ctx.weekday_name,
        "Algérie": "Week-end" if ctx.is_weekend else "Jour ouvré",
        "La plupart des outils supposent": "Week-end" if d.weekday() in (5, 6) else "Jour ouvré",
        "Concordance": "✓" if (ctx.is_weekend == (d.weekday() in (5, 6))) else "✗ FAUX",
    })

col1, col2 = st.columns([3, 2])
with col1:
    with st.container(border=True):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
with col2:
    with st.container(border=True):
        st.markdown("**Deux jours faux, chaque semaine**")
        st.markdown(
            "Le week-end algérien, c'est **vendredi-samedi**. Un outil qui suppose "
            "samedi-dimanche se trompe sur le jeudi, le vendredi et le dimanche, "
            "sur un cycle hebdomadaire récurrent.\n\n"
            "Il planifie lourd le vendredi , le jour le plus calme , et léger le "
            "dimanche, un jour ouvré complet. Ce n'est pas un problème de réglage "
            "que plus de données corrigent ; l'outil n'a aucun moyen d'exprimer la "
            "bonne réponse."
        )
        st.caption(
            "La première version de ce projet avait le même bug : son motif "
            "hebdomadaire marquait les jours 5 et 6 comme les jours creux. Nous "
            "l'avons trouvé en reconstruisant , ce qui illustre bien le propos."
        )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("L'année mobile")

st.markdown(
    "Le Ramadan et les deux Aïds sont fixés par le calendrier hégirien, environ "
    "11 jours plus court que l'année grégorienne. Les deux plus grands événements "
    "de demande en Algérie **reculent donc à travers les saisons**. Un modèle qui "
    "a appris « mars est chargé » est déjà faux au moment où il est livré."
)

years = list(range(today.year - 2, today.year + 4))
drift = []
for y in years:
    hy_guess = calendar_dz.to_hijri(dt.date(y, 6, 1))[0]
    for hy in (hy_guess - 1, hy_guess, hy_guess + 1):
        try:
            r_start = calendar_dz.from_hijri(hy, 9, 1)
            fitr = calendar_dz.from_hijri(hy, 10, 1)
            adha = calendar_dz.from_hijri(hy, 12, 10)
        except (ValueError, OverflowError):
            continue
        if r_start.year == y:
            drift.append({
                "Année grégorienne": y,
                "Année hégirienne": hy,
                "Début du Ramadan": r_start.strftime("%d %b"),
                "Aïd el-Fitr": fitr.strftime("%d %b %Y"),
                "Aïd el-Adha": adha.strftime("%d %b %Y"),
            })

col_a, col_b = st.columns([3, 2])
with col_a:
    with st.container(border=True):
        st.dataframe(pd.DataFrame(drift), hide_index=True, width="stretch")
        st.caption(
            "Calculé avec le calendrier islamique tabulaire, vérifié en "
            "aller-retour sur 60 années hégiriennes. Exact à un jour ou deux près "
            "de l'annonce officielle de l'observation lunaire , l'app signale les "
            "jours où cette ambiguïté compte."
        )
with col_b:
    with st.container(border=True):
        st.markdown("**Pourquoi c'est difficile à ajouter après coup**")
        st.markdown(
            "Le Ramadan n'augmente pas seulement le volume. Il **réorganise la "
            "journée** : l'activité passe au soir après le f'tour, les horaires se "
            "raccourcissent, et les dix dernières nuits portent le pic d'achats de "
            "l'Aïd.\n\n"
            "Puis les deux jours d'Aïd sont une quasi-fermeture, suivie d'un "
            "rebond. Encoder cela exige le calendrier hégirien comme élément à part "
            "entière du modèle , pas un simple drapeau de jour férié collé dessus."
        )

st.markdown("**Vérifié contre la référence, sur les dates qui comptent**")
hijri_check = appdata.load_hijri_check(st.session_state["allow_network"])
if not hijri_check.empty:
    exact = (hijri_check["Agreement"] == "exact").sum()
    show = hijri_check.rename(columns={
        "Event": "Événement", "Our date": "Notre date",
        "Reference says": "La référence indique", "Agreement": "Concordance",
    })
    with st.container(border=True):
        st.dataframe(show, hide_index=True, width="stretch")
    st.caption(
        f"{exact} des {len(hijri_check)} dates clés correspondent exactement à la "
        "référence Aladhan ; les autres diffèrent d'un seul jour. Ce ±1 jour est "
        "la vraie incertitude d'observation lunaire, pas un bug , la Commission "
        "Nationale d'Observation du Croissant Lunaire fixe la date réelle, et "
        "l'app signale les jours concernés pour que la prévision élargisse son "
        "intervalle plutôt que d'être faussement sûre. Les débuts de Ramadan, qui "
        "portent le plus grand changement de demande, tombent exactement juste."
    )
else:
    st.info(
        "Fonctionne sur le calendrier tabulaire local (pas de vérification "
        "réseau). Exact à un jour ou deux près de l'annonce officielle , ce que "
        "l'app signale par jour.",
        icon=":material/wifi_off:",
    )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("Le reste de l'année algérienne")

drivers = pd.DataFrame([
    {
        "Facteur": "Saison de retour de la diaspora",
        "Quand": "mi-juin → début septembre, pic fin juillet",
        "Pourquoi c'est important": "Plusieurs millions d'Algériens résidant à "
                          "l'étranger rentrent. Dans un modèle entraîné en Europe, "
                          "l'été est un creux de demande. Ici, c'est le pic annuel.",
    },
    {
        "Facteur": "Rentrée scolaire",
        "Quand": "fin août → mi-septembre",
        "Pourquoi c'est important": "Pic commercial et de livraison net et étroit "
                          "sur les fournitures, uniformes et manuels scolaires.",
    },
    {
        "Facteur": "Paie de fin de mois",
        "Quand": "autour du 27, chaque mois",
        "Pourquoi c'est important": "Les salaires algériens sont massivement payés "
                          "en fin de mois. La demande grimpe les premiers jours du "
                          "mois suivant et s'amincit avant.",
    },
    {
        "Facteur": "Yennayer",
        "Quand": "12 janvier",
        "Pourquoi c'est important": "Nouvel An amazigh, jour férié officiel depuis "
                          "2018. Absent de quasiment toutes les bibliothèques de "
                          "calendrier étrangères.",
    },
    {
        "Facteur": "Chaleur saharienne",
        "Quand": "juin → septembre, au sud de l'Atlas",
        "Pourquoi c'est important": "Ouargla a enregistré 84 jours au-dessus de "
                          "38°C à l'été 2024 (observé, ERA5). La chaleur réduit le "
                          "rythme tenable et augmente l'absentéisme , le même "
                          "volume demande plus de bras.",
    },
])

with st.container(border=True):
    st.dataframe(
        drivers, hide_index=True, width="stretch",
        column_config={
            "Pourquoi c'est important": st.column_config.TextColumn(
                "Pourquoi c'est important", width="large")
        },
    )

st.subheader("Les 8 prochains mois")
events = appdata.load_calendar_events(days=240)
with st.container(border=True):
    if events.empty:
        st.caption("Aucun événement majeur détecté dans cette fenêtre.")
    else:
        st.dataframe(
            events, hide_index=True, width="stretch",
            column_config={"Impact": st.column_config.TextColumn("Impact", width="large")},
        )

appdata.data_badge()
