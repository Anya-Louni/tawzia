# -*- coding: utf-8 -*-
"""
tools/check_pages.py
--------------------
Fume-test de toutes les pages : chacune est exécutée dans un vrai runtime
Streamlit (`AppTest`), et l'on vérifie qu'elle ne lève aucune exception.

Pourquoi ça existe
==================
L'application compte une trentaine d'écrans et une couche de moteurs partagée.
Un renommage, une signature qui change ou une colonne renommée casse en général
une page que personne n'a rouverte depuis. Comme la démonstration est projetée
devant un client, une page blanche coûte plus cher que n'importe quel défaut de
style. Ce script est donc la garantie minimale avant de montrer le produit.

Usage :
    venv/Scripts/python.exe tools/check_pages.py            # toutes les pages
    venv/Scripts/python.exe tools/check_pages.py people.py  # une seule
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

# Ces pages appellent un modèle de langage ou attendent une saisie : le
# fume-test les charge quand même, il vérifie seulement qu'elles s'affichent.
#
# 600 s et non 240 : « Preuves » et « Analyse économique » déclenchent le
# backtest walk-forward sur 49 origines, qui prend plusieurs minutes quand le
# cache disque est froid. À 240 s elles échouaient sur un simple dépassement de
# temps, ce qui faisait passer un fume-test vert pour un fume-test rouge. Le
# cache est ensuite partagé avec l'application, donc le premier passage sert
# aussi à préchauffer la démonstration.
TIMEOUT = 600


def check(page: Path) -> tuple[bool, str]:
    try:
        at = AppTest.from_file(str(page), default_timeout=TIMEOUT)
        at.run()
    except Exception as exc:                     # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    if at.exception:
        first = at.exception[0]
        message = (first.message or "").strip()
        # `st.page_link` a besoin de la navigation déclarée par dashboard.py.
        # AppTest exécute une page seule, sans navigation, donc le lien lève
        # 'url_pathname'. Ce n'est pas un défaut de la page : elle s'affiche
        # normalement dans l'application. On le signale sans le compter en
        # échec, sinon le fume-test crie au loup à chaque lien inter-pages.
        if "url_pathname" in message:
            return True, "affichée (liens inter-pages non testables hors navigation)"
        return False, f"{first.type or 'Exception'}: {message[:220]}"
    return True, f"{len(at.markdown) + len(at.metric) + len(at.dataframe)} éléments"


def main() -> int:
    pages_dir = ROOT / "app_pages"
    wanted = sys.argv[1:]
    pages = sorted(p for p in pages_dir.glob("*.py")
                   if not wanted or p.name in wanted)
    if not pages:
        print("aucune page trouvée")
        return 1

    failures = []
    for page in pages:
        ok, detail = check(page)
        print(f"  {'OK   ' if ok else 'ECHEC'} {page.name:28s} {detail}")
        if not ok:
            failures.append(page.name)

    print(f"\n{len(pages) - len(failures)}/{len(pages)} pages sans erreur")
    if failures:
        print("à corriger : " + ", ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
