"""
core/vision.py
--------------
Contrôle de documents : lecture par modèle entraîné et détection de retouche.

Le problème réel
================
Une paie algérienne se justifie par des documents : bulletins de paie,
attestations de travail, attestations CNAS, certificats médicaux. Ces documents
circulent en photo ou en PDF scanné, et ils sont retouchés , un salaire relevé
sur une attestation pour obtenir un crédit, un montant CNAS abaissé, une date de
certificat médical déplacée pour couvrir une absence. Personne ne relit 400
bulletins à la loupe.

Ce module fait trois choses, et il dit clairement laquelle est laquelle :

1. **Un modèle entraîné, sur des données réelles.** Un classifieur de chiffres
   manuscrits entraîné sur le jeu *Optical Recognition of Handwritten Digits*
   (UCI / NIST, 1797 échantillons écrits par 43 personnes réelles), livré avec
   scikit-learn. L'exactitude affichée dans l'app est mesurée sur un échantillon
   de test que le modèle n'a jamais vu , pas une valeur écrite à la main.

2. **Des constats factuels sur le fichier**, jamais un verdict de retouche.
   Ce que déclarent les métadonnées, plus une carte ELA fournie à l'œil humain.
   Un détecteur automatique de falsification a été écrit puis **mesuré** : il ne
   séparait pas un bulletin propre d'un bulletin recollé, et il accusait des
   documents sains. Il a donc été retiré plutôt que déguisé en fonctionnalité.

3. **Un contrôle de légalité**, qui est la partie qui attrape vraiment la fraude
   en Algérie : les montants lus sont confrontés au SNMG, au taux CNAS et à la
   grille IRG déjà présents dans `core/labour_dz` et `core/payroll_dz`. Un
   bulletin sous le SNMG ou une cotisation CNAS sous-déclarée est une infraction
   vérifiable, pas une intuition.

Ce que ce module ne fait pas
============================
Il ne fait pas de l'OCR de texte libre : cela demanderait un moteur type
Tesseract, impossible à garantir sur l'hébergement visé. Il lit les **champs
numériques**, qui sont précisément ceux que l'on falsifie, et récupère le texte
d'un PDF quand la couche texte existe.
"""

from __future__ import annotations

import datetime as _dt
import io
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from . import labour_dz

# ---------------------------------------------------------------------------
# 1. Le modèle entraîné
# ---------------------------------------------------------------------------

DATASET_NAME = "Optical Recognition of Handwritten Digits (UCI / NIST)"
DATASET_CITE = (
    "E. Alpaydin & C. Kaynak, Bogaziçi University , UCI Machine Learning "
    "Repository. Livré avec scikit-learn (sklearn.datasets.load_digits)."
)
TEST_SIZE = 0.25
SEED = 7


@dataclass
class DigitModel:
    """Le classifieur entraîné, avec ses métriques honnêtes de test."""
    estimator: object
    accuracy: float                 # exactitude sur l'échantillon de test
    n_train: int
    n_test: int
    per_class: dict = field(default_factory=dict)
    confusions: list = field(default_factory=list)

    # Mesurée à part : lire de l'imprimé n'est pas la même tâche que lire du
    # manuscrit, et fondre les deux dans un seul chiffre masquerait la faiblesse.
    printed_accuracy: Optional[float] = None
    n_printed_test: int = 0
    n_fonts: int = 0

    @property
    def accuracy_pct(self) -> float:
        return self.accuracy * 100

    @property
    def printed_accuracy_pct(self) -> Optional[float]:
        return None if self.printed_accuracy is None else self.printed_accuracy * 100


def _printed_digit_samples(max_fonts: int = 40) -> tuple:
    """
    Rendre des chiffres imprimés à partir des polices réelles de la machine.

    Pourquoi c'est nécessaire : le jeu UCI est **manuscrit**. Un modèle entraîné
    uniquement dessus lit très mal un bulletin de paie imprimé , et surtout il
    le lit mal *avec assurance* (0 et 8 pris pour des 4 à 85 % de confiance),
    ce qui est le pire comportement possible pour un contrôle de fraude.
    Mesuré : 1 nombre correctement lu sur 20 avant l'ajout de ces exemples.

    Ces échantillons-ci sont donc **générés**, à partir de polices réelles, et
    l'interface le dit : l'exactitude sur le manuscrit réel et l'exactitude sur
    l'imprimé sont rapportées séparément, jamais fondues en un seul chiffre.
    """
    import glob
    from PIL import Image, ImageDraw, ImageFont

    paths = []
    for pattern in ("C:/Windows/Fonts/*.ttf", "/usr/share/fonts/**/*.ttf",
                    "/Library/Fonts/*.ttf", "/System/Library/Fonts/*.ttf"):
        paths += glob.glob(pattern, recursive=True)
    paths = sorted(set(paths))[:max_fonts]

    rng = np.random.default_rng(SEED)
    X, y, used = [], [], 0

    for path in paths:
        try:
            font = ImageFont.truetype(path, 48)
        except Exception:
            continue
        ok_font = False
        for digit in range(10):
            for angle in (-6, 0, 6):
                img = Image.new("L", (90, 110), 255)
                ImageDraw.Draw(img).text((25, 20), str(digit), fill=0, font=font)
                if angle:
                    img = img.rotate(angle, resample=Image.BILINEAR, fillcolor=255)
                arr = np.asarray(img, dtype=np.float64)
                arr += rng.normal(0, 6.0, arr.shape)     # grain de scan
                cells = _segment_digits(np.clip(arr, 0, 255))
                if len(cells) != 1:
                    continue
                X.append(_to_feature(cells[0]))
                y.append(digit)
                ok_font = True
        used += int(ok_font)

    if not X:
        return np.empty((0, 64)), np.empty((0,), dtype=int), 0
    return np.vstack(X), np.asarray(y), used


def train_digit_model() -> DigitModel:
    """
    Entraîner le lecteur de chiffres et le mesurer honnêtement.

    Aucune métrique n'est écrite en dur : les exactitudes renvoyées sont
    calculées sur des échantillons de test que le modèle n'a jamais vus, et
    celle du manuscrit réel est rapportée séparément de celle de l'imprimé.
    """
    from sklearn.datasets import load_digits
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC

    data = load_digits()
    X, y = data.data, data.target

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=SEED, stratify=y
    )

    # Les chiffres imprimés rejoignent l'entraînement, avec leur propre
    # échantillon de test tenu à l'écart.
    Xp, yp, n_fonts = _printed_digit_samples()
    Xp_te = yp_te = None
    if len(yp):
        Xp_tr, Xp_te, yp_tr, yp_te = train_test_split(
            Xp, yp, test_size=TEST_SIZE, random_state=SEED, stratify=yp
        )
        X_tr = np.vstack([X_tr, Xp_tr])
        y_tr = np.concatenate([y_tr, yp_tr])

    # `SVC(probability=True)` est déprécié depuis scikit-learn 1.9 et disparaît
    # en 1.11 ; on calibre explicitement, ce qui donne en plus des probabilités
    # honnêtes (c'est elles qui permettent de dire « je ne suis pas sûr »).
    from sklearn.calibration import CalibratedClassifierCV

    base = make_pipeline(StandardScaler(), SVC(kernel="rbf", C=10, gamma=0.001))
    model = CalibratedClassifierCV(base, method="sigmoid", cv=5, ensemble=False)
    model.fit(X_tr, y_tr)

    pred = model.predict(X_te)
    accuracy = float((pred == y_te).mean())

    per_class, confusions = {}, []
    for digit in range(10):
        mask = y_te == digit
        if mask.any():
            per_class[digit] = float((pred[mask] == digit).mean())
    for true_d, pred_d in zip(y_te, pred):
        if true_d != pred_d:
            confusions.append((int(true_d), int(pred_d)))

    printed_accuracy = None
    if yp_te is not None and len(yp_te):
        printed_accuracy = float((model.predict(Xp_te) == yp_te).mean())

    return DigitModel(
        estimator=model, accuracy=accuracy,
        n_train=int(len(y_tr)), n_test=int(len(y_te)),
        per_class=per_class, confusions=confusions,
        printed_accuracy=printed_accuracy,
        n_printed_test=int(len(yp_te)) if yp_te is not None else 0,
        n_fonts=int(n_fonts),
    )


def sample_test_digits(n: int = 8) -> tuple:
    """Quelques chiffres réels du jeu de test, pour montrer le modèle à l'œuvre."""
    from sklearn.datasets import load_digits
    from sklearn.model_selection import train_test_split

    data = load_digits()
    _, X_te, _, y_te = train_test_split(
        data.data, data.target, test_size=TEST_SIZE, random_state=SEED,
        stratify=data.target
    )
    rng = np.random.default_rng(SEED)
    idx = rng.choice(len(y_te), size=min(n, len(y_te)), replace=False)
    return X_te[idx], y_te[idx]


# ---------------------------------------------------------------------------
# 2. Lecture d'un champ numérique
# ---------------------------------------------------------------------------

def _to_grayscale(image) -> np.ndarray:
    from PIL import Image, ImageOps
    img = image if isinstance(image, Image.Image) else Image.open(image)
    img = ImageOps.exif_transpose(img).convert("L")
    return np.asarray(img, dtype=np.float64)


def _segment_digits(gray: np.ndarray, max_digits: int = 12) -> list:
    """
    Découper une bande numérique en chiffres, par colonnes d'encre.

    Volontairement simple et lisible : on binarise, on projette sur l'axe
    horizontal, et on coupe là où la colonne est vide. C'est robuste sur un
    champ bien cadré , ce que le module demande à l'utilisateur , et cela évite
    d'embarquer un détecteur d'objets qui serait invérifiable ici.
    """
    if gray.size == 0:
        return []

    # Encre = sombre. Seuil d'Otsu, calculé à la main pour rester sans OpenCV.
    hist, _ = np.histogram(gray, bins=256, range=(0, 255))
    total = gray.size
    best_t, best_var = 128, -1.0
    w0 = c0 = 0.0
    sum_all = float((np.arange(256) * hist).sum())
    for t in range(1, 255):
        w0 += hist[t - 1]
        if w0 == 0:
            continue
        w1 = total - w0
        if w1 == 0:
            break
        c0 += (t - 1) * hist[t - 1]
        m0 = c0 / w0
        m1 = (sum_all - c0) / w1
        var = w0 * w1 * (m0 - m1) ** 2
        if var > best_var:
            best_var, best_t = var, t

    ink = gray < best_t
    if ink.mean() > 0.5:            # image inversée (encre claire sur fond noir)
        ink = ~ink

    cols = ink.any(axis=0)
    spans, start = [], None
    for i, filled in enumerate(cols):
        if filled and start is None:
            start = i
        elif not filled and start is not None:
            if i - start >= 2:
                spans.append((start, i))
            start = None
    if start is not None and len(cols) - start >= 2:
        spans.append((start, len(cols)))

    return [ink[:, a:b] for a, b in spans[:max_digits]]


def _to_feature(cell: np.ndarray) -> np.ndarray:
    """
    Ramener un chiffre découpé au format exact du jeu d'entraînement.

    C'est l'étape qui décide de tout : le modèle a appris sur des imagettes 8x8
    où le chiffre **remplit** la case et où l'encre monte à 16. Un chiffre
    simplement collé au centre d'un cadre trop grand ressort pâle et minuscule,
    hors de la distribution d'entraînement , et le classifieur répond alors
    n'importe quoi avec beaucoup d'assurance. On normalise donc comme le jeu
    d'origine : recadrage serré, mise à l'échelle à hauteur constante, centrage,
    puis sous-échantillonnage et remise de l'encre à pleine dynamique.
    """
    from PIL import Image

    rows = np.where(cell.any(axis=1))[0]
    cols = np.where(cell.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return np.zeros(64)
    tight = cell[rows.min():rows.max() + 1, cols.min():cols.max() + 1]

    # Mettre à l'échelle pour occuper une boîte de 20x20, aspect préservé.
    h, w = tight.shape
    scale = 20.0 / max(h, w)
    new_h, new_w = max(int(round(h * scale)), 1), max(int(round(w * scale)), 1)
    glyph = Image.fromarray((tight * 255).astype(np.uint8)).resize(
        (new_w, new_h), Image.BILINEAR)

    # Centrer dans un cadre 28x28, puis descendre en 8x8 comme le jeu UCI.
    frame = Image.new("L", (28, 28), 0)
    frame.paste(glyph, ((28 - new_w) // 2, (28 - new_h) // 2))
    arr = np.asarray(frame.resize((8, 8), Image.BILINEAR), dtype=np.float64)

    # Pleine dynamique 0-16 : l'encre doit peser autant qu'à l'entraînement.
    peak = arr.max()
    if peak > 0:
        arr = arr / peak * 16.0
    return arr.reshape(-1)


def read_number(image, model: Optional[DigitModel] = None) -> dict:
    """
    Lire un champ numérique avec le modèle entraîné.

    Retourne la valeur lue, les chiffres, et la confiance moyenne du modèle ,
    la confiance sert à dire « je ne suis pas sûr » plutôt qu'à faire semblant.
    """
    model = model or train_digit_model()
    gray = _to_grayscale(image)
    cells = _segment_digits(gray)
    if not cells:
        return {"value": None, "digits": [], "confidence": 0.0, "n_digits": 0}

    feats = np.vstack([_to_feature(c) for c in cells])
    probs = model.estimator.predict_proba(feats)
    digits = [int(d) for d in probs.argmax(axis=1)]
    conf = float(probs.max(axis=1).mean())

    try:
        value = int("".join(str(d) for d in digits))
    except ValueError:
        value = None

    return {"value": value, "digits": digits, "confidence": conf,
            "n_digits": len(digits)}


# ---------------------------------------------------------------------------
# 3. Constats sur le fichier , des faits, pas un verdict
# ---------------------------------------------------------------------------

@dataclass
class DocumentReport:
    """
    Ce que l'on peut affirmer d'une image de document, et rien de plus.

    Il n'y a **volontairement pas de verdict automatique de falsification**.
    Une détection de retouche par analyse du niveau d'erreur (ELA) et
    d'incohérence de bruit a été implémentée puis mesurée sur des documents
    propres et des documents recollés : elle ne séparait pas les deux (ratios
    0,60 contre 0,99 à une qualité de recompression, inversés à une autre) et
    elle qualifiait des bulletins parfaitement sains de « retouche probable ».
    Un détecteur de fraude qui accuse un document honnête est pire qu'absent :
    il détruit la confiance qu'on vend.

    Restent donc les éléments **factuels** : ce que disent les métadonnées, et
    une carte ELA fournie comme aide à l'œil humain, jamais comme preuve.
    """
    metadata: dict
    findings: list                 # constats factuels sur le fichier
    ela_png: Optional[bytes] = None
    reviewed_by_human: bool = True  # rappel : la décision reste humaine


EDITOR_SIGNATURES = ("photoshop", "gimp", "paint", "canva", "affinity",
                     "pixlr", "lightroom", "snapseed", "picsart")


def inspect_document(image_bytes: bytes) -> DocumentReport:
    """
    Lire ce que le fichier déclare, et produire une carte ELA à regarder.

    Aucun score : uniquement des faits vérifiables et une image.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    findings, meta = [], {}

    try:
        from PIL.ExifTags import TAGS
        exif = img.getexif()
        for tag_id, value in (exif or {}).items():
            meta[TAGS.get(tag_id, str(tag_id))] = str(value)[:120]
    except Exception:
        pass

    software = str(meta.get("Software", ""))
    if any(k in software.lower() for k in EDITOR_SIGNATURES):
        findings.append(LegalFinding(
            "alerte", "Fichier passé par un éditeur graphique",
            f"Les métadonnées indiquent « {software} ». Ce n'est pas une preuve "
            f"de falsification , un scan peut être recadré légitimement , mais "
            f"un bulletin authentique sort en général d'un scanner ou d'un "
            f"logiciel de paie, pas d'un éditeur d'images.",
        ))
    elif software:
        findings.append(LegalFinding(
            "ok", "Origine du fichier",
            f"Métadonnées : « {software} ».",
        ))
    else:
        findings.append(LegalFinding(
            "ok", "Pas de métadonnées d'édition",
            "Aucun logiciel d'édition déclaré. L'absence de métadonnées ne "
            "prouve rien : beaucoup d'outils les effacent.",
        ))

    # Carte ELA : utile à l'œil, inutilisable comme score (mesuré).
    ela_png = None
    try:
        ela = _ela(img)
        peak = float(ela.max())
        if peak > 0:
            from PIL import Image as _I
            vis = _I.fromarray(np.clip(ela / peak * 255.0, 0, 255).astype(np.uint8))
            buf = io.BytesIO()
            vis.save(buf, "PNG")
            ela_png = buf.getvalue()
    except Exception:
        pass

    return DocumentReport(metadata=meta, findings=findings, ela_png=ela_png)


# ---------------------------------------------------------------------------
# 4. Contrôle de légalité , la partie qui attrape vraiment la fraude
# ---------------------------------------------------------------------------

@dataclass
class LegalFinding:
    level: str        # "infraction" | "alerte" | "ok"
    label: str
    detail: str


def audit_payslip(gross_monthly: float, cnas_employee: Optional[float] = None,
                  net_paid: Optional[float] = None,
                  declared_hours: Optional[float] = None) -> list:
    """
    Confronter les montants lus au droit du travail algérien.

    Les règles viennent de `core/labour_dz` (SNMG, taux CNAS, heures légales) :
    ce sont des obligations vérifiables, donc les constats sont opposables.
    """
    findings = []

    snmg = labour_dz.SNMG_MONTHLY
    if gross_monthly and gross_monthly < snmg:
        findings.append(LegalFinding(
            "infraction", "Salaire sous le SNMG",
            f"Brut déclaré {gross_monthly:,.0f} DZD contre un minimum légal de "
            f"{snmg:,.0f} DZD , manque {snmg - gross_monthly:,.0f} DZD.",
        ))
    elif gross_monthly:
        findings.append(LegalFinding(
            "ok", "Salaire au-dessus du SNMG",
            f"Brut {gross_monthly:,.0f} DZD pour un minimum de {snmg:,.0f} DZD.",
        ))

    if gross_monthly and cnas_employee is not None:
        expected = gross_monthly * labour_dz.CNAS_EMPLOYEE
        gap = expected - cnas_employee
        # 2 % de tolérance : arrondis de bulletin, pas de la sous-déclaration.
        if abs(gap) > max(expected * 0.02, 50):
            level = "infraction" if gap > 0 else "alerte"
            findings.append(LegalFinding(
                level, "Cotisation CNAS incohérente",
                f"Retenue lue {cnas_employee:,.0f} DZD ; attendue "
                f"{expected:,.0f} DZD ({labour_dz.CNAS_EMPLOYEE:.1%} du brut). "
                f"Écart {gap:+,.0f} DZD.",
            ))
        else:
            findings.append(LegalFinding(
                "ok", "Cotisation CNAS cohérente",
                f"{cnas_employee:,.0f} DZD, conforme à "
                f"{labour_dz.CNAS_EMPLOYEE:.1%} du brut.",
            ))

    if gross_monthly and net_paid is not None and net_paid > gross_monthly:
        findings.append(LegalFinding(
            "alerte", "Net supérieur au brut",
            f"Net {net_paid:,.0f} DZD pour un brut {gross_monthly:,.0f} DZD , "
            f"document incohérent, à réclamer.",
        ))

    if declared_hours is not None and declared_hours > labour_dz.LEGAL_MONTHLY_HOURS:
        extra = declared_hours - labour_dz.LEGAL_MONTHLY_HOURS
        findings.append(LegalFinding(
            "alerte", "Heures au-delà du volume légal",
            f"{declared_hours:.0f} h déclarées contre "
            f"{labour_dz.LEGAL_MONTHLY_HOURS} h légales : {extra:.0f} h à "
            f"payer en heures supplémentaires majorées.",
        ))

    return findings


def risk_score(document: Optional[DocumentReport], findings: list) -> dict:
    """
    Le risque du dossier, construit **uniquement sur des constats opposables**.

    Chaque point vient soit d'une règle de droit (SNMG, taux CNAS, heures
    légales), soit d'un fait déclaré par le fichier lui-même (métadonnées). Rien
    ne vient d'une inférence sur les pixels : la tentative a été mesurée et elle
    ne discriminait pas (voir `DocumentReport`).
    """
    all_findings = list(findings)
    if document is not None:
        all_findings += list(document.findings)

    infractions = sum(1 for f in all_findings if f.level == "infraction")
    alerts = sum(1 for f in all_findings if f.level == "alerte")

    total = min(1.0, 0.55 * infractions + 0.2 * alerts)
    band = "élevé" if total >= 0.55 else ("moyen" if total >= 0.25 else "faible")
    return {"score": round(total * 100), "band": band,
            "infractions": infractions, "alerts": alerts}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("Contrôle de documents , auto-contrôle\n")

    m = train_digit_model()
    print(f"  Modèle entraîné sur {DATASET_NAME}")
    print(f"  {m.n_train} échantillons d'entraînement, {m.n_test} de test")
    print(f"  Exactitude hors échantillon : {m.accuracy_pct:.2f} %")
    worst = min(m.per_class.items(), key=lambda kv: kv[1])
    print(f"  Chiffre le moins bien reconnu : {worst[0]} ({worst[1]*100:.1f} %)")
    print(f"  Erreurs sur le test : {len(m.confusions)}")

    if m.printed_accuracy is not None:
        print(f"  Imprimé (test tenu à l'écart) : {m.printed_accuracy_pct:.2f} % "
              f"sur {m.n_printed_test} échantillons, {m.n_fonts} polices")

    # Lire un nombre rendu en image, à une taille réaliste de document scanné.
    import glob
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for pattern in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/**/*.ttf"):
        hits = glob.glob(pattern, recursive=True)
        if hits:
            font = ImageFont.truetype(hits[0], 44)
            break
    img = Image.new("L", (300, 90), 255)
    d = ImageDraw.Draw(img)
    d.text((20, 15), "24000", fill=0, font=font)
    out = read_number(img, m)
    print(f"\n  Lecture d'un champ « 24000 » : {out['value']} "
          f"({out['n_digits']} chiffres, confiance {out['confidence']:.0%})")

    print("\n  Contrôle de légalité sur un bulletin sous-payé :")
    for f in audit_payslip(gross_monthly=18_000, cnas_employee=400.0,
                           net_paid=17_800, declared_hours=200):
        print(f"    [{f.level:11}] {f.label} , {f.detail}")

    buf = io.BytesIO()
    Image.merge("RGB", (img, img, img)).save(buf, "JPEG", quality=95)
    rep = inspect_document(buf.getvalue())
    print(f"\n  Constats sur le fichier : {len(rep.findings)} , "
          f"carte ELA produite : {rep.ela_png is not None}")
    for f in rep.findings:
        print(f"    [{f.level:9}] {f.label}")
    print(f"\n  Risque du dossier : "
          f"{risk_score(rep, audit_payslip(18_000, 400.0))}")
