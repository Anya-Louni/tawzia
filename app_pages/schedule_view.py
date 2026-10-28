"""
Planning de la semaine , un bouton : « Générer ». Le reste est expliqué.

Le solveur CP-SAT (core/scheduler.py) place chaque salarié en respectant le
droit du travail en contraintes dures, part de la semaine passée pour rester
stable, et lit la charge dans la prévision. Le planning part ensuite en carte
dans la boîte de décisions : rien n'est publié aux équipes sans validation.
"""

import datetime as dt

import streamlit as st

from core import appdata, db, scheduler as sch, seed_company as sc

appdata.sidebar_controls()
ss = st.session_state

st.markdown(
    '<div class="tz-hero"><div><h1 class="tz-hero-h">Planning de la semaine</h1>'
    '<div class="tz-hero-s">Le planning le plus stable et le moins cher qui respecte '
    'la loi : 48 h au plus, un jour de repos, aucune nuit interdite. <b>Vous validez, '
    'il part aux équipes.</b></div></div></div>',
    unsafe_allow_html=True,
)

ws = sch.next_week_start()
c1, c2, c3 = st.columns([1.4, 1, 1])
site = c1.selectbox("Site", list(sc.SITES), format_func=lambda k: sc.SITES[k]["name"],
                    key="sched_site")
ramadan = c2.toggle("Horaires de Ramadan", key="sched_ramadan",
                    help="Shifts de 6 h 30, réglables dans la configuration.")
derog = c3.toggle("Dérogation nuit (art. 29)", key=f"sched_derog_{site}",
                  value=sc.SITES[site]["women_night_derogation"],
                  help="Accordée par l'inspecteur du travail. Elle ouvre aux "
                       "travailleuses l'accès égal aux postes de nuit.")

try:
    fc = appdata.expected_demand(ss["profile_key"], ss["wilaya"], 21, ss["allow_network"])
except Exception:  # noqa: BLE001 , sans prévision, charge moyenne
    fc = None
load = sch.load_from_forecast(fc, ws)
peak = max(range(7), key=lambda d: load[d])
pday = ws + dt.timedelta(days=peak)
st.caption(f":material/trending_up: Charge attendue : {(load[peak] - 1) * 100:+.0f} % le "
           f"{sch.DAYS_FR[pday.weekday()]} {pday.day}, d'après la prévision (calendrier "
           f"algérien et météo réelle){', Ramadan' if ramadan else ''}.")


@st.cache_data(show_spinner=False)
def _last_week(site: str, week: dt.date, derog: bool) -> dict:
    # La semaine passée, résolue une fois : c'est la référence de stabilité.
    r = sch.solve(site, week - dt.timedelta(days=7), women_derogation=derog)
    return {f"{k[0]}|{k[1]}": v for k, v in r.assign.items()}


if st.button("Générer", type="primary", icon=":material/auto_awesome:") or ss.pop("sched_autorun", False):
    with st.spinner("Le solveur cherche le meilleur planning légal…"):
        last = {tuple([k.split("|")[0], int(k.split("|")[1])]): v
                for k, v in _last_week(site, ws, derog).items()}
        ss["sched_result"] = sch.solve(site, ws, load, ramadan=ramadan,
                                       women_derogation=derog, last_week=last)

res = ss.get("sched_result")
if res is None or res.site != site:
    st.caption("L'agent attend votre clic. Il lit la prévision, les congés approuvés et "
               "la semaine passée.")
    appdata.data_badge()
    st.stop()

if res.status not in ("OPTIMAL", "FEASIBLE"):
    st.error("Aucun planning légal ne couvre cette semaine. Ajoutez du renfort ou "
             "réduisez le besoin.", icon=":material/error:")
    st.stop()

short = sum(res.shortfall.values())
with st.container(border=True):
    st.markdown(f"**Planning du {ws:%d/%m} prêt.** {len(res.violations)} infraction légale · "
                f"heures sup. {res.overtime_hours:.0f} h ({appdata.dzd(res.overtime_cost)}) · "
                f"stabilité {res.stability:.0%} par rapport à la semaine passée"
                + (f" · {short} poste(s) non couvert(s)" if short else " · demande couverte"))
    st.caption(":material/gavel: Ord. 97-03 (40 h) · loi 90-11 art. 27, 28, 29, 31, 33")
    if st.button("Envoyer pour validation", icon=":material/inbox:"):
        con = db.seed(db.connect())
        db.add_card(con, source="planning", agent="Planning",
                    title=f"Planning du {ws:%d/%m}, {sc.SITES[site]['name']} : prêt",
                    detail=(f"0 infraction. Heures sup. {res.overtime_hours:.0f} h. Stabilité "
                            f"{res.stability:.0%}. {short} poste(s) non couvert(s)."
                            + (" Horaires de Ramadan." if res.ramadan else "")),
                    law="Ord. 97-03 · loi 90-11 art. 27 à 33",
                    decision="Planning publié aux équipes dans le guichet salarié.")
        st.toast("Carte envoyée dans la boîte de décisions.", icon=":material/inbox:")

art29 = [n for n, a in res.blocked_nights if a == "art. 29"]
art28 = [n for n, a in res.blocked_nights if a == "art. 28"]
if art29 or art28:
    with st.expander(f"Pourquoi {len(res.blocked_nights)} personne(s) ne sont pas de nuit"):
        if art29:
            st.markdown(f"**Art. 29** · {len(art29)} travailleuse(s). Le site n'a pas de "
                        f"dérogation de l'inspecteur du travail pour le travail de nuit des "
                        f"femmes. La demander ouvre l'accès égal aux postes de nuit : activez "
                        f"le réglage ci-dessus pour voir l'effet.")
        if art28:
            st.markdown(f"**Art. 28** · {', '.join(art28)} : moins de 19 ans, pas de nuit.")

st.dataframe(sch.grid(res), hide_index=True, width="stretch", height=420)
st.caption("M matin · A après-midi · N nuit · « · » repos")
appdata.data_badge()
