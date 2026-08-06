"""Données de l'entreprise , importez votre fichier, l'app apprend dessus."""

import pandas as pd
import streamlit as st

from core import appdata, company_data as cd

appdata.sidebar_controls()

st.title("Données de l'entreprise")
st.caption(
    "Importez votre fichier du personnel et votre journal de présence : "
    "l'appariement CV, la détection d'anomalies, les KPI, le simulateur et le "
    "copilote apprennent alors de VOS données. Sans import, tout fonctionne sur "
    "une démonstration clairement étiquetée."
)

# --- current source --------------------------------------------------------
if cd.is_uploaded():
    st.success(
        f":material/database: Source active : **{cd.source_label()}** , "
        f"{len(cd.people())} employés, {len(cd.attendance_records())} pointages.",
        icon=":material/check_circle:",
    )
    if st.button("Revenir à la démonstration", icon=":material/restart_alt:"):
        cd.clear_company_data()
        st.rerun()
else:
    st.info(
        ":material/science: Source active : **données de démonstration "
        "(simulées)**. Le calendrier, la météo et le droit du travail sont réels ; "
        "les effectifs sont un échantillon de démonstration.",
        icon=":material/info:",
    )

st.divider()

# --- templates -------------------------------------------------------------
with st.expander("Modèles de fichier (colonnes reconnues, FR/EN)", icon=":material/table:"):
    st.caption("Les noms de colonnes sont reconnus de façon souple, en français "
               "ou en anglais. Voici la forme attendue :")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Personnel**")
        st.dataframe(cd.workforce_template(), hide_index=True, width="stretch")
        st.download_button(
            "Télécharger le modèle personnel",
            cd.workforce_template().to_csv(index=False).encode("utf-8"),
            "modele_personnel.csv", "text/csv", icon=":material/download:",
        )
    with c2:
        st.markdown("**Présence / pointage**")
        st.dataframe(cd.attendance_template(), hide_index=True, width="stretch")
        st.download_button(
            "Télécharger le modèle présence",
            cd.attendance_template().to_csv(index=False).encode("utf-8"),
            "modele_presence.csv", "text/csv", icon=":material/download:",
        )

# --- upload ----------------------------------------------------------------
st.subheader("Importer")
up1, up2 = st.columns(2)
with up1:
    people_file = st.file_uploader("Fichier du personnel (.csv)", type=["csv"],
                                   key="up_people")
with up2:
    att_file = st.file_uploader("Journal de présence (.csv , optionnel)",
                                type=["csv"], key="up_att")


def _read_csv(f):
    for sep in (",", ";", "\t"):
        try:
            f.seek(0)
            df = pd.read_csv(f, sep=sep)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    f.seek(0)
    return pd.read_csv(f)


if people_file is not None:
    try:
        pdf = _read_csv(people_file)
        people = cd.parse_workforce(pdf)
        records = []
        if att_file is not None:
            adf = _read_csv(att_file)
            records = cd.parse_attendance(adf, people)
        st.markdown(f"**Aperçu :** {len(people)} employés détectés"
                    + (f", {len(records)} pointages" if records else ""))
        preview = pd.DataFrame([{
            "ID": p.emp_id, "Nom": p.name, "Poste (reconnu)": p.role_key,
            "Wilaya": p.wilaya, "Contrat": p.contract,
            "À charge": p.dependants,
        } for p in people[:12]])
        st.dataframe(preview, hide_index=True, width="stretch")
        if st.button("Utiliser ces données", type="primary",
                     icon=":material/upload:"):
            label = f"Données importées ({people_file.name})"
            cd.set_company_data(people, records, label)
            st.success("Données chargées. Toutes les pages IA apprennent "
                       "maintenant de votre fichier.")
            st.rerun()
    except Exception as exc:
        st.error(f"Lecture impossible : {exc}. Vérifiez le séparateur et les "
                 f"en-têtes de colonnes (voir les modèles ci-dessus).")

st.caption(":material/lock: Vos fichiers restent dans votre session ; ils ne "
           "sont ni envoyés à un service externe ni stockés sur le serveur.")
