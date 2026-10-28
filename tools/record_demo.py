# -*- coding: utf-8 -*-
"""
tools/record_demo.py
--------------------
Enregistre une démonstration de l'application, en vidéo, depuis la vraie app.

Pourquoi un script et pas une capture à la main
===============================================
Une démonstration se rejoue : à chaque changement d'écran, la vidéo doit pouvoir
être refaite à l'identique, sans qu'un humain reclique dans le bon ordre. Le
scénario ci-dessous est donc du code, et ce qui est filmé est **l'application
réelle** qui tourne, pas une maquette.

Ce qui est produit
==================
    assets/demo/tawzia-demo.webm   la vidéo du parcours
    assets/demo/frames/NN-*.png    une image par étape, pour les slides
    assets/demo/tawzia-demo.gif    version animée légère (facultative)

Prérequis
=========
L'application doit tourner (par défaut sur http://localhost:8501) :

    venv/Scripts/python.exe -m streamlit run dashboard.py

Puis :

    venv/Scripts/python.exe tools/record_demo.py

Le premier passage peut être long : les écrans de preuve déclenchent le backtest.
Lancez-le une fois avant d'enregistrer pour que les caches soient chauds, sinon
la vidéo montre des écrans de chargement.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "demo"
FRAMES = OUT / "frames"

VIEWPORT = {"width": 1440, "height": 900}

# Le scénario : l'ordre dans lequel un responsable découvre le produit. Chaque
# étape est (chemin, titre, secondes de pause). La pause laisse le temps de lire
# à l'image, et laisse Streamlit finir son rendu avant la capture.
SCENARIO = [
    ("autopilot", "Le travail RH déjà fait, il reste à signer", 4.0),
    ("self_service", "Le salarié demande, le guichet répond", 3.5),
    ("job_post_view", "Dicter une offre, la plateforme la rédige", 3.5),
    ("talent_pool", "Le vivier, classé du mieux au moins adapté", 4.0),
    ("deadlines_view", "Les échéances CNAS et impôts", 3.5),
    ("requests_view", "Congés et présence, arbitrés avec la charge", 3.0),
    ("roster_view", "Le planning le moins cher qui respecte la loi", 3.5),
    ("retention_negotiator", "Qui risque de partir, et comment le garder", 3.0),
    ("assistant", "Une seule conversation pour toute la plateforme", 3.5),
    ("evidence", "La preuve : le backtest, pertes comprises", 3.5),
    ("privacy_view", "Ce que la plateforme fait de vos données", 3.0),
]


def _wait_settled(page, timeout: float = 90.0) -> None:
    """
    Attendre que Streamlit ait fini de calculer.

    Le marqueur fiable n'est pas le réseau (websocket toujours ouvert) mais le
    bouton « Stop » de la barre d'outils, présent uniquement pendant un run.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            running = page.locator('[data-testid="stAppToolbar"]').inner_text(
                timeout=2000)
        except Exception:
            running = ""
        if "Stop" not in running:
            # Le run Python est fini, mais les graphiques ne sont pas peints :
            # Vega-Lite et les tableaux se dessinent après, côté navigateur. Sans
            # cette attente, la vidéo montre des cartes vides à la place des
            # graphiques. On attend donc qu'il n'y ait plus de squelette de
            # chargement, puis on laisse une marge de peinture.
            try:
                page.wait_for_function(
                    "() => !document.querySelector('[data-testid=\"stSkeleton\"]')",
                    timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(1800)
            return
        page.wait_for_timeout(500)


def record(base_url: str, make_gif: bool) -> int:
    from playwright.sync_api import sync_playwright

    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=1,
            record_video_dir=str(OUT / "_raw"),
            record_video_size=VIEWPORT,
        )
        page = context.new_page()

        print(f"Enregistrement de {len(SCENARIO)} étapes depuis {base_url}\n")
        for i, (path, title, hold) in enumerate(SCENARIO, start=1):
            url = f"{base_url.rstrip('/')}/{path}"
            print(f"  {i:02d}. {title} ... ", end="", flush=True)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                _wait_settled(page)
            except Exception as exc:                      # noqa: BLE001
                print(f"ECHEC ({type(exc).__name__})")
                continue

            # On fait défiler lentement : la vidéo montre le bas de l'écran,
            # qui est souvent là où se trouve la substance.
            page.mouse.move(VIEWPORT["width"] // 2, VIEWPORT["height"] // 2)
            page.wait_for_timeout(int(hold * 1000 * 0.45))
            page.evaluate(
                "() => { const m = document.querySelector('[data-testid=\"stMain\"]');"
                " if (m) m.scrollTo({top: 520, behavior: 'smooth'}); }")
            page.wait_for_timeout(int(hold * 1000 * 0.55))

            shot = FRAMES / f"{i:02d}-{path}.png"
            page.evaluate(
                "() => { const m = document.querySelector('[data-testid=\"stMain\"]');"
                " if (m) m.scrollTo({top: 0}); }")
            page.wait_for_timeout(400)
            page.screenshot(path=str(shot))
            print(f"OK  ({shot.name})")

        context.close()      # c'est la fermeture du contexte qui écrit la vidéo
        browser.close()

    raw = sorted((OUT / "_raw").glob("*.webm"))
    if not raw:
        print("\nAucune vidéo produite.")
        return 1
    final = OUT / "tawzia-demo.webm"
    if final.exists():
        final.unlink()
    raw[0].replace(final)
    shutil.rmtree(OUT / "_raw", ignore_errors=True)
    size_mb = final.stat().st_size / 1e6
    print(f"\nVidéo : {final.relative_to(ROOT)}  ({size_mb:.1f} Mo)")

    frames = sorted(FRAMES.glob("*.png"))
    print(f"Images : {len(frames)} dans {FRAMES.relative_to(ROOT)}")

    if make_gif and frames:
        from PIL import Image
        # Un GIF partageable : demi-résolution, 2 s par écran. Le GIF est un
        # complément, pas le livrable principal , il ne rend ni le défilement
        # ni les transitions.
        images = []
        for f in frames:
            im = Image.open(f).convert("RGB")
            im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
            images.append(im.convert("P", palette=Image.ADAPTIVE, colors=128))
        gif = OUT / "tawzia-demo.gif"
        images[0].save(gif, save_all=True, append_images=images[1:],
                       duration=2000, loop=0, optimize=True)
        print(f"GIF : {gif.relative_to(ROOT)}  "
              f"({gif.stat().st_size / 1e6:.1f} Mo)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://localhost:8501",
                    help="URL de l'application qui tourne")
    ap.add_argument("--no-gif", action="store_true",
                    help="ne pas produire le GIF")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    return record(args.url, make_gif=not args.no_gif)


if __name__ == "__main__":
    sys.exit(main())
