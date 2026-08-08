"""Contrôle de documents , lire un bulletin et le confronter au droit algérien."""

import io

import numpy as np
import streamlit as st

from core import appdata, vision

appdata.sidebar_controls()

st.title("Contrôle de documents")
st.caption("Un modèle entraîné lit les montants d'un bulletin ou d'une "
           "attestation, et la plateforme les confronte au SNMG, au taux CNAS "
           "et au volume horaire légal. Ce qui ressort est opposable.")


@st.cache_resource(show_spinner="Entraînement du lecteur de chiffres…")
def _model():
    return vision.train_digit_model()


model = _model()

st.info(
    f"**Le modèle est réellement entraîné, et mesuré devant vous.** Il apprend "
    f"sur le jeu *{vision.DATASET_NAME}* , {model.n_test} chiffres manuscrits "
    f"réels sont mis de côté et ne servent jamais à l'entraînement. "
    f"L'exactitude affichée est celle obtenue sur ces chiffres-là. "
    f"Aucune de ces valeurs n'est écrite en dur dans le code.",
    icon=":material/model_training:",
)

tab_read, tab_model = st.tabs(["Contrôler un document", "Le modèle et ses limites"])

# ---------------------------------------------------------------------------
# Contrôler un document
# ---------------------------------------------------------------------------

with tab_read:
    left, right = st.columns([3, 2])

    with left:
        with st.container(border=True):
            st.subheader("Le document")
            up = st.file_uploader(
                "Photo ou scan du bulletin (.png / .jpg)",
                type=["png", "jpg", "jpeg"],
            )
            st.caption("Le fichier n'est ni envoyé à un service externe ni "
                       "conservé : tout est calculé sur le serveur de l'app.")

            if up is not None:
                data = up.getvalue()
                st.image(data, caption=up.name, width="stretch")

                report = vision.inspect_document(data)
                st.markdown("**Ce que dit le fichier lui-même**")
                for f in report.findings:
                    icon = {"infraction": ":material/gpp_bad:",
                            "alerte": ":material/warning:",
                            "ok": ":material/check_circle:"}[f.level]
                    st.markdown(f"{icon} **{f.label}** , {f.detail}")

                if report.ela_png:
                    with st.expander("Carte de recompression (ELA)",
                                     icon=":material/image_search:"):
                        st.image(report.ela_png, width="stretch")
                        st.caption(
                            "Aide à l'œil, **pas une preuve**. Une zone qui "
                            "tranche nettement mérite un regard ; une carte "
                            "uniforme ne garantit rien."
                        )
                st.session_state["doc_report"] = report

    with right:
        with st.container(border=True):
            st.subheader("Lire un montant")
            st.caption("Recadrez le champ chiffré (le brut, la retenue CNAS) et "
                       "déposez-le : le modèle le lit et affiche sa confiance.")
            crop = st.file_uploader("Champ numérique recadré",
                                    type=["png", "jpg", "jpeg"], key="crop")
            if crop is not None:
                from PIL import Image
                img = Image.open(io.BytesIO(crop.getvalue()))
                st.image(img, width="stretch")
                out = vision.read_number(img, model)
                if out["value"] is None:
                    st.warning("Aucun chiffre isolé sur cette image. Recadrez "
                               "plus serré, sans texte autour.",
                               icon=":material/crop:")
                else:
                    st.metric("Valeur lue", f"{out['value']:,}".replace(",", " "))
                    st.progress(out["confidence"],
                                text=f"Confiance moyenne {out['confidence']:.0%}")
                    if out["confidence"] < 0.75:
                        st.warning(
                            "Confiance faible : à saisir à la main plutôt qu'à "
                            "croire. Le modèle a le droit de douter.",
                            icon=":material/help:",
                        )
                    st.session_state["doc_read"] = out["value"]

    # --- le contrôle de légalité -------------------------------------------
    st.subheader("Confronter au droit du travail algérien")

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        gross = c1.number_input("Brut mensuel (DZD)", 0, 2_000_000,
                                int(st.session_state.get("doc_read", 24_000)),
                                step=500)
        cnas = c2.number_input("Retenue CNAS (DZD)", 0, 500_000, 2_160, step=10)
        net = c3.number_input("Net payé (DZD)", 0, 2_000_000, 21_840, step=100)
        hours = c4.number_input("Heures déclarées", 0, 400, 173)

        findings = vision.audit_payslip(gross, cnas, net, hours)
        risk = vision.risk_score(st.session_state.get("doc_report"), findings)

    m1, m2, m3 = st.columns(3)
    m1.metric("Risque du dossier", f"{risk['score']} / 100",
              help="Construit uniquement sur des constats opposables.")
    m2.metric("Infractions", risk["infractions"])
    m3.metric("Points à vérifier", risk["alerts"])

    band_msg = {
        "élevé": ("Dossier à reprendre : au moins une obligation légale n'est "
                  "pas respectée.", "error"),
        "moyen": ("Des points à clarifier avant de classer ce dossier.", "warning"),
        "faible": ("Rien d'opposable relevé sur les éléments fournis.", "success"),
    }[risk["band"]]
    getattr(st, band_msg[1])(band_msg[0], icon=":material/gavel:")

    with st.container(border=True):
        st.subheader("Le détail, article par article")
        for f in findings:
            icon = {"infraction": ":material/gpp_bad:",
                    "alerte": ":material/warning:",
                    "ok": ":material/check_circle:"}[f.level]
            st.markdown(f"{icon} **{f.label}** , {f.detail}")

# ---------------------------------------------------------------------------
# Le modèle
# ---------------------------------------------------------------------------

with tab_model:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Exactitude , manuscrit réel", f"{model.accuracy_pct:.1f} %",
              help=f"Sur {model.n_test} chiffres manuscrits réels jamais vus "
                   f"à l'entraînement.")
    c2.metric("Exactitude , imprimé",
              f"{model.printed_accuracy_pct:.1f} %" if model.printed_accuracy
              else "-",
              help=f"Sur {model.n_printed_test} chiffres imprimés tenus à "
                   f"l'écart, rendus depuis {model.n_fonts} polices réelles.")
    c3.metric("Échantillons d'entraînement", f"{model.n_train:,}".replace(",", " "))
    c4.metric("Erreurs sur le test", len(model.confusions))

    with st.container(border=True):
        st.subheader("Le modèle à l'œuvre, sur des chiffres réels jamais vus")
        X, y = vision.sample_test_digits(10)
        preds = model.estimator.predict(X)
        cols = st.columns(10)
        for col, feat, true_d, pred_d in zip(cols, X, y, preds):
            with col:
                img = (feat.reshape(8, 8) / 16.0 * 255).astype(np.uint8)
                st.image(255 - img, width="stretch")
                if pred_d == true_d:
                    st.markdown(f":green[**{pred_d}**]")
                else:
                    st.markdown(f":red[**{pred_d}**] (vrai {true_d})")
        st.caption("Ces imagettes viennent de l'échantillon de test : le modèle "
                   "ne les avait jamais vues avant cet écran.")

    col_a, col_b = st.columns(2)
    with col_a:
        with st.container(border=True):
            st.subheader("Exactitude par chiffre")
            rows = [{"Chiffre": d, "Exactitude": round(a * 100, 1)}
                    for d, a in sorted(model.per_class.items())]
            st.dataframe(rows, hide_index=True, width="stretch",
                         column_config={"Exactitude": st.column_config.ProgressColumn(
                             "Exactitude %", min_value=0, max_value=100,
                             format="%.1f%%")})

    with col_b:
        with st.container(border=True):
            st.subheader("Ce que le modèle ne sait pas faire")
            st.markdown(
                "- Il lit des **chiffres**, pas du texte libre : pas de noms, "
                "pas d'adresses. Un OCR de texte complet exigerait un moteur "
                "que l'hébergement ne garantit pas.\n"
                "- Il a besoin d'un **champ recadré** et net. Sur une photo "
                "de travers, il refuse plutôt que de deviner.\n"
                "- Il annonce sa **confiance** : en dessous de 75 %, la valeur "
                "se saisit à la main."
            )
            st.markdown("**Aucune détection automatique de falsification.**")
            st.caption(
                "Elle a été implémentée (analyse ELA et incohérence de bruit) "
                "puis mesurée : elle ne séparait pas un bulletin propre d'un "
                "bulletin recollé, et elle qualifiait des documents sains de "
                "« retouche probable ». Elle a été retirée. Un détecteur de "
                "fraude qui accuse un document honnête coûte plus cher que "
                "l'absence de détecteur."
            )

    with st.expander("Provenance des données d'entraînement",
                     icon=":material/menu_book:"):
        st.markdown(f"**{vision.DATASET_NAME}**")
        st.caption(vision.DATASET_CITE)
        st.markdown(
            f"Les chiffres **manuscrits** sont des données réelles écrites par "
            f"des personnes réelles. Les chiffres **imprimés** sont rendus par "
            f"nos soins depuis {model.n_fonts} polices réelles installées sur "
            f"le serveur, avec rotation et grain de scan , ils sont générés, et "
            f"c'est pourquoi leur exactitude est rapportée séparément."
        )

appdata.data_badge()
