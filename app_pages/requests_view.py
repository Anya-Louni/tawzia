"""Demandes & présence , demandes de sortie, congés, et qui est en retard."""

import streamlit as st

from core import appdata, attendance

appdata.sidebar_controls()

st.title("Demandes & présence")
st.caption("Les demandes des employés décidées selon la loi et la demande, plus "
           "le tableau des retards et absences.")

people = appdata.hr_people()
lookup = {e.emp_id: e for e in people}
requests = appdata.hr_requests()
records = appdata.hr_attendance()

# Contexte de prévision pour savoir si un jour est un pic.
plan = appdata.load_forward_plan(
    st.session_state["profile_key"], st.session_state["wilaya"],
    st.session_state["horizon"], st.session_state["regular_pool"],
    st.session_state["temp_ceiling"], st.session_state["service_level"],
    st.session_state["allow_network"],
)
forecast = plan["forecast"]

flags_today = attendance.todays_flags(records)
summary = attendance.lateness_summary(records)

with st.container(horizontal=True):
    st.metric("Demandes en attente", f"{len(requests)}", border=True)
    st.metric("Retards / absences aujourd'hui", f"{len(flags_today)}", border=True)
    chronic = int((summary["Absent %"] >= 15).sum()) if not summary.empty else 0
    st.metric("Surveillance départ", f"{chronic}", border=True,
              help="Employés avec 15%+ d'absence, le plus fort signal de départ.")

_REC_FR = {
    "approve": "approuver",
    "approve_with_cover": "approuver avec remplacement",
    "approve_with_note": "approuver avec note",
    "reject": "refuser",
    "record": "enregistrer",
    "review": "à revoir",
}

tab_req, tab_att = st.tabs(["Boîte de demandes", "Présence & retards"])

# ---------------------------------------------------------------------------
with tab_req:
    st.subheader("Boîte de demandes")
    st.caption(
        "Chaque demande reçoit une recommandation : contrôle légal (solde de "
        "congés, préavis) plus un contrôle de la demande, afin de signaler une "
        "approbation en pic de charge prévu."
    )
    for r in requests:
        emp = lookup.get(r.emp_id)
        if emp is None:
            continue
        d = attendance.decide_request(r, emp, forecast=forecast)
        rec = d["recommend"]
        icon = {"approve": ":material/check_circle:", "approve_with_cover": ":material/warning:",
                "approve_with_note": ":material/warning:", "reject": ":material/cancel:",
                "record": ":material/description:", "review": ":material/help:"}.get(rec, ":material/help:")
        with st.container(border=True):
            top = st.columns([3, 2, 2])
            with top[0]:
                st.markdown(f"**{r.emp_name}** · {r.kind_label}")
                span = f"{r.start:%d %b}" if r.is_sortie else f"{r.start:%d %b} au {r.end:%d %b}"
                extra = f" ({r.hours:.0f}h)" if r.is_sortie and r.hours else ""
                st.caption(f"{span}{extra} · « {r.reason} »")
            with top[1]:
                st.markdown(f"{icon} **{_REC_FR.get(rec, rec)}**")
                if d.get("load") == "peak":
                    st.caption(":material/trending_up: pic de demande")
            with top[2]:
                st.caption(f"Solde après : {d['balance_after']:.1f} j")
            for w in d["warnings"]:
                st.caption(f":material/warning: {w}")
            for rn in d["reasons"][:1]:
                st.caption(rn)

# ---------------------------------------------------------------------------
with tab_att:
    st.subheader("En retard / absents aujourd'hui")
    if flags_today.empty:
        st.success("Tout le monde à l'heure aujourd'hui.", icon=":material/check_circle:")
    else:
        st.dataframe(flags_today, hide_index=True, width="stretch",
                     column_config={"Statut": st.column_config.TextColumn("Statut")})

    st.subheader("Bilan de présence (14 jours)")
    st.caption("Les retards et absences chroniques sont le signal brut du risque de départ.")
    if not summary.empty:
        def _risk(row):
            if row["Absent %"] >= 20 or row["Late %"] >= 35:
                return "Élevé"
            if row["Absent %"] >= 10 or row["Late %"] >= 20:
                return "À surveiller"
            return "OK"
        summary = summary.copy()
        summary["Risque de départ"] = summary.apply(_risk, axis=1)
        show = summary.rename(columns={
            "Name": "Nom", "Late": "Retards", "Absent": "Absences",
            "Late minutes": "Minutes de retard", "Late %": "Retard %", "Absent %": "Absence %",
        })
        st.dataframe(
            show, hide_index=True, width="stretch", height=380,
            column_config={
                "Retard %": st.column_config.NumberColumn(format="%.1f"),
                "Absence %": st.column_config.NumberColumn(format="%.1f"),
            },
        )

appdata.data_badge()
