"""
core/brand.py
-------------
The Tawzia brand, in one place.

The logo appears on several surfaces (app header, favicon, landing pages,
exports). Copying the SVG everywhere guarantees most copies go stale, so it is
written once here and every surface asks for it.

The name: Tawzia, from the Arabic توزيع (tawzi'), "distribution, assignment".
Exactly what the engine does: assign people to shifts and roles.

The mark: three heads, one body, the W of Tawzia read as three people side by
side. The two gaps are cut out of the body (`fill-rule="evenodd"`), not painted
white, so the mark sits on any background. The reference file is
`assets/brand/tawzia-mark.svg`; the path below is the copy served to the app,
and both must stay identical (tested in `__main__`).
"""

from __future__ import annotations

import base64
import re
from pathlib import Path
from urllib.parse import quote

# --- Palette ---------------------------------------------------------------
# Les deux bleus du logo, puis ce qu'il faut pour en faire une interface.
SKY = "#6CBEF5"        # the logo light blue: accent, light series
BLUE = "#0B57A8"       # the logo deep blue: action, titles, wordmark
BLUE_DARK = "#084684"  # active/hover state of actions
BLUE_MID = "#4E98E0"   # mid tone for charts
BLUE_WASH = "#E7F1FC"  # chip background, selected surface
INK = "#0A1628"        # encre des chiffres et des titres
MUTED = "#3E4C60"      # texte secondaire
GROUND = "#EDF1F6"     # fond de page
SURFACE = "#FFFFFF"    # carte
LINE = "#C5D0DE"       # filet, presque invisible : la profondeur vient de l'ombre

# The three blues of a stacked chart, darkest to lightest.
STACK = [BLUE, BLUE_MID, "#A5D4F7"]

NAME = "Tawzia"
TAGLINE_FR = "The AI HR platform built for Algeria"
TAGLINE_EN = "The AI HR platform built for Algeria"

_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "brand"
_MARK_PATH = _ASSETS / "tawzia-mark.svg"

# The mark body without its <svg> wrapper: reused at every size.
_BODY = (
    f'<circle cx="48" cy="24" r="22"/>'
    f'<circle cx="100" cy="24" r="22"/>'
    f'<circle cx="152" cy="24" r="22"/>'
    f'<path fill-rule="evenodd" d="M4,58 L196,58 L100,170 Z '
    f'M56,58 C54,92 66,118 88,132 Q92,134 94,128 C92,104 88,80 82,58 Z '
    f'M144,58 C146,92 134,118 112,132 Q108,134 106,128 C108,104 112,80 118,58 Z"/>'
)


def mark(height: int | str = 28, fill: str = SKY, css_class: str = "") -> str:
    """La marque seule, en SVG inline. `height` en px, ou une valeur CSS."""
    h = f"{height}px" if isinstance(height, int) else height
    cls = f' class="{css_class}"' if css_class else ""
    return (
        f'<svg{cls} viewBox="0 0 200 176" style="height:{h};width:auto;'
        f'display:block;flex:none" fill="{fill}" aria-hidden="true">{_BODY}</svg>'
    )


# Le logo fourni en image. S'il est présent, il gagne : c'est le fichier de
# référence de la marque. Sinon on retombe sur la reconstruction vectorielle
# ci-dessous, pour que l'app ne dépende pas d'un binaire absent du dépôt.
LOGO_PNG = _ASSETS / "tawzia-logo.png"


def _png_data_uri(path: Path) -> str:
    return ("data:image/png;base64,"
            + base64.b64encode(path.read_bytes()).decode("ascii"))


def lockup(size: int = 20, ink: str = BLUE, fill: str = SKY, text_only: bool = False) -> str:
    """
    Le logo complet : TA + la marque en guise de W + ZIA.

    Si `assets/brand/tawzia-logo.png` existe, c'est cette image qui est servie,
    intégrée en base64 pour qu'aucune requête ne soit nécessaire. Déposez-y le
    fichier fourni et tout le produit le reprend, sans autre changement.

    À défaut, les lettres sont du texte et non des contours : elles héritent de
    la police de la page (Inter partout dans le produit), donc le logo reste net
    à toutes les tailles et se pose dans un bouton comme dans un titre.
    """
    if LOGO_PNG.exists() and not text_only:
        # Le fichier fourni est recadré sur ses glyphes (rapport ~3,04:1), donc
        # la hauteur demandée est bien la hauteur des lettres et non celle d'une
        # marge. Le facteur 1,3 rattrape la différence de perception entre un
        # texte de `size` pixels et une image de la même hauteur : les capitales
        # d'Inter n'occupent qu'environ 72% de la taille de police.
        return (f'<img src="{_png_data_uri(LOGO_PNG)}" alt="Tawzia" '
                f'style="height:{size * 1.3:.0f}px;width:auto;display:block">')
    return (
        f'<span style="display:inline-flex;align-items:center;gap:.05em;'
        f'font-weight:800;letter-spacing:-.015em;line-height:1;'
        f'font-size:{size}px;color:{ink};white-space:nowrap">'
        f'TA{mark(height=size, fill=fill)}ZIA</span>'
    )


def favicon_data_uri(fill: str = SKY) -> str:
    """
    Le favicon : la marque en data-URI, sans requête réseau ni fichier .ico.

    `#` doit être encodé, sinon le navigateur coupe l'URI au premier dièse.
    """
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-14 -22 228 220" '
        f'fill="{fill}">{_BODY}</svg>'
    )
    return "data:image/svg+xml," + quote(svg, safe="")


def _normalise(svg: str) -> str:
    """Comparaison de formes, pas de mise en page : l'espace entre balises ne compte pas."""
    return re.sub(r">\s+<", "><", re.sub(r"\s+", " ", svg)).strip()


def _svg_file_body() -> str:
    """Le corps du fichier de référence, normalisé pour comparaison."""
    raw = _MARK_PATH.read_text(encoding="utf-8")
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    inner = raw[raw.index("<g "):raw.rindex("</g>")]
    inner = inner[inner.index(">") + 1:]
    return _normalise(inner)


if __name__ == "__main__":
    print("Brand - self check\n")

    # Le SVG en dur et le fichier de référence doivent décrire la même forme.
    a = _normalise(_BODY)
    b = _svg_file_body()
    same = a == b
    print(f"{'OK ' if same else 'ECHEC'} le module et {_MARK_PATH.name} "
          f"décrivent la même marque")
    if not same:
        print(f"  module : {a[:110]}...")
        print(f"  fichier: {b[:110]}...")

    uri = favicon_data_uri()
    print(f"{'OK ' if '#' not in uri else 'ECHEC'} favicon : aucun # non encodé "
          f"({len(uri)} caractères)")

    lk = lockup(20)
    if LOGO_PNG.exists():
        ok = "<img" in lk and "data:image/png;base64," in lk
        print(f"{'OK ' if ok else 'ECHEC'} lockup : le logo fourni "
              f"({LOGO_PNG.name}) est servi, intégré en base64")
    else:
        ok = lk.count("TA") == 1 and lk.count("ZIA") == 1 and "<svg" in lk
        print(f"{'OK ' if ok else 'ECHEC'} lockup : reconstruction vectorielle "
              f"(TA + marque + ZIA), aucun PNG fourni")
    print(f"\nPalette : logo {SKY} / {BLUE}, fond {GROUND}, encre {INK}")
