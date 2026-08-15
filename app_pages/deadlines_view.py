"""
Échéances & déclarations , ce que le comptable doit déposer, et avant quand.

L'écran répond à une seule question : qu'est-ce qui doit partir cette semaine, et
où. Il montre donc l'échéance la plus proche en grand, avec le bouton qui ouvre
le portail officiel, puis la liste complète en dessous.
"""

import datetime as _dt

import streamlit as st

from core import appdata, brand, deadlines_dz as dl, demand as demand_mod, payroll_dz

appdata.sidebar_controls()

profile = demand_mod.PROFILES[st.session_state["profile_key"]]
headcount = appdata.workforce_headcount()
today = _dt.date.today()

_MONTHS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre")

st.markdown(
    f'<div class="tz-hero"><div>'
    f'<h1 class="tz-hero-h">Échéances & déclarations</h1>'
    f'<div class="tz-hero-s">Ce qui doit partir à la CNAS et aux impôts, et '
    f'avant quand. Effectif suivi : <b>{headcount}</b> salariés, donc '
    f'cotisations CNAS '
    f'<b>{"mensuelles" if headcount >= dl.CNAS_MONTHLY_THRESHOLD else "trimestrielles"}</b>.'
    f'</div></div></div>',
    unsafe_allow_html=True,
)

horizon = st.segmented_control(
    "Fenêtre", options=[60, 120, 365],
    format_func=lambda d: f"{d} jours" if d < 365 else "1 an",
    default=120, key="dl_horizon", label_visibility="collapsed",
) or 120

items = dl.upcoming(today, headcount=headcount, horizon_days=horizon)
counts = dl.counts(today, headcount=headcount, horizon_days=horizon)

# ---------------------------------------------------------------------------
# L'alerte : la prochaine échéance, en grand, avec le lien du portail
# ---------------------------------------------------------------------------
nxt = dl.next_critical(today, headcount=headcount)
if nxt:
    left = nxt.days_left(today)
    if left < 0:
        st.error(
            f"**{nxt.label} , en retard de {abs(left)} jours.** Elle était due "
            f"le {nxt.due:%d/%m/%Y} pour le {nxt.period}. {nxt.penalty}",
            icon=":material/priority_high:",
        )
    elif left <= 7:
        st.warning(
            f"**{nxt.label} , dans {left} jours** (le {nxt.due:%d/%m/%Y}). "
            f"{nxt.what}",
            icon=":material/schedule:",
        )
    else:
        st.info(
            f"**Prochaine échéance : {nxt.label}**, le {nxt.due:%d/%m/%Y} "
            f"(dans {left} jours). {nxt.what}",
            icon=":material/event_upcoming:",
        )

k1, k2, k3, k4 = st.columns(4)
with k1, st.container(border=True, height="stretch"):
    appdata.stat_card("En retard", f"{counts['en_retard']}",
                      "à traiter" if counts["en_retard"] else "aucune",
                      "down" if counts["en_retard"] else "up",
                      "une cotisation en retard reste due, majorée")
with k2, st.container(border=True, height="stretch"):
    appdata.stat_card("Dans les 7 jours", f"{counts['urgent']}", None, "flat",
                      "à déposer cette semaine")
with k3, st.container(border=True, height="stretch"):
    appdata.stat_card("Dans les 30 jours", f"{counts['a_venir']}", None, "flat",
                      "à préparer")
with k4, st.container(border=True, height="stretch"):
    appdata.stat_card("Sur la fenêtre", f"{len(items)}", f"{horizon} j", "flat",
                      "toutes obligations confondues")

# ---------------------------------------------------------------------------
# Le montant qui part ce mois-ci : ce que le retard mettrait en jeu
# ---------------------------------------------------------------------------
plan = appdata.load_forward_plan(
    st.session_state["profile_key"], st.session_state["wilaya"],
    st.session_state["horizon"], st.session_state["regular_pool"],
    st.session_state["temp_ceiling"], st.session_state["service_level"],
    st.session_state["allow_network"],
)
register = payroll_dz.payroll_register(plan["roster"], profile.primary_role)
declarations = payroll_dz.declaration_lines(register)

left_col, right_col = st.columns([3, 2])

with left_col:
    with st.container(border=True):
        appdata.card_head("Ce qui part sur la période",
                          "calculé sur le planning en cours")
        st.dataframe(declarations, hide_index=True, width="stretch")
        st.caption(
            "C'est la base sur laquelle une majoration de retard s'appliquerait. "
            "Déposer à l'heure ne fait pas gagner d'argent : cela évite d'en "
            "perdre sur une somme déjà due."
        )

with right_col:
    with st.container(border=True):
        appdata.card_head("Où déposer", "portails officiels")
        st.link_button("CNAS , télédéclaration (DAS et cotisations)",
                       dl.PORTAL_CNAS, width="stretch", type="primary",
                       icon=":material/open_in_new:")
        st.link_button("DGI , Jibaya'tic (G50)", dl.PORTAL_DGI,
                       width="stretch", icon=":material/open_in_new:")
        st.link_button("CNAS , site principal", dl.PORTAL_CNAS_MAIN,
                       width="stretch", icon=":material/open_in_new:")
        st.link_button("CASNOS , non-salariés", dl.PORTAL_CASNOS,
                       width="stretch", icon=":material/open_in_new:")
        st.divider()
        st.download_button(
            "Ajouter à l'agenda (.ics)",
            data=dl.to_ics(items).encode("utf-8"),
            file_name="tawzia-echeances.ics",
            mime="text/calendar",
            width="stretch",
            icon=":material/calendar_add_on:",
            help="Importez le fichier dans Outlook, Google Agenda ou tout "
                 "autre agenda : chaque échéance arrive avec un rappel 7 jours "
                 "avant.",
        )

# ---------------------------------------------------------------------------
# La liste complète, filtrable
# ---------------------------------------------------------------------------
with st.container(border=True):
    appdata.card_head("Toutes les échéances", f"{len(items)} sur {horizon} jours")

    f1, f2 = st.columns(2)
    bodies = sorted({o.body for o in items})
    keep_bodies = f1.multiselect("Organisme", bodies, default=bodies,
                                 key="dl_bodies")
    statuses = [dl.STATUS_FR[k] for k in ("en_retard", "urgent", "a_venir",
                                          "plus_tard")]
    keep_status = f2.multiselect("Statut", statuses, default=statuses,
                                 key="dl_status")

    df = dl.frame(today, headcount=headcount, horizon_days=horizon)
    if not df.empty:
        df = df[df["Organisme"].isin(keep_bodies) & df["Statut"].isin(keep_status)]

    if df.empty:
        st.markdown('<div class="tz-empty">Aucune échéance avec ces filtres.</div>',
                    unsafe_allow_html=True)
    else:
        st.dataframe(
            df[["Échéance", "Jours restants", "Statut", "Obligation",
                "Organisme", "Période couverte", "Fiabilité"]],
            hide_index=True, width="stretch",
            column_config={
                "Échéance": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Jours restants": st.column_config.NumberColumn(format="%d j"),
            },
        )
        st.download_button(
            "Exporter en CSV", df.to_csv(index=False).encode("utf-8-sig"),
            file_name="tawzia-echeances.csv", mime="text/csv",
            icon=":material/download:",
        )

    for o in items[:4]:
        with st.expander(f"{o.due:%d/%m/%Y} , {o.label} ({o.body})",
                         icon=":material/description:"):
            st.markdown(f"**À faire.** {o.what}")
            st.markdown(f"**Période couverte.** {o.period}")
            st.markdown(f"**En cas de retard.** {o.penalty}")
            st.link_button("Ouvrir le portail", o.portal,
                           icon=":material/open_in_new:")
            if o.confidence == "sourcee":
                st.caption(f":material/verified: Source : {o.source}")
            else:
                st.caption(f":material/help: {o.source}. Cette règle existe, "
                           f"mais sa date ou son montant varie selon les lois "
                           f"de finances : faites-la confirmer par votre "
                           f"comptable ou votre agence.")

# ---------------------------------------------------------------------------
# Les obligations déclenchées par un événement, pas par le calendrier
# ---------------------------------------------------------------------------
with st.container(border=True):
    appdata.card_head("Déclenché par un événement", "pas par le calendrier")
    for e in dl.EVENT_DRIVEN:
        st.markdown(f"**{e['label']}** , {e['trigger']} · {e['body']}")
        st.caption(f"{e['what']} {e['note']}")

st.caption(
    ":material/gavel: Cet écran rappelle des échéances, il ne remplace pas "
    "votre comptable. Les dates marquées « Sourcé » viennent d'une source "
    "nommée ; celles marquées « À confirmer » existent mais varient, et la "
    "plateforme préfère le dire."
)
appdata.data_badge()
