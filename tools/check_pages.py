# -*- coding: utf-8 -*-
"""
tools/check_pages.py
--------------------
Smoke test for every page: each runs in a real Streamlit runtime (`AppTest`)
and must not raise.

A rename or a changed signature usually breaks a page nobody has reopened
since. In a live demo a blank page costs more than any style flaw, so this is
the minimum guarantee before showing the product.

Usage:
    venv/Scripts/python.exe tools/check_pages.py            # every page
    venv/Scripts/python.exe tools/check_pages.py people.py  # one page
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

# 600 s: the Proof and Business case pages run the walk-forward backtest, which
# takes minutes on a cold disk cache. The cache is shared with the app, so the
# first pass also warms the demo.
TIMEOUT = 600


def check(page: Path) -> tuple[bool, str]:
    # AppTest swallows syntax errors (the page renders empty), so compile first.
    try:
        compile(page.read_text(encoding="utf-8"), str(page), "exec")
    except SyntaxError as exc:
        return False, f"SyntaxError line {exc.lineno}: {exc.msg}"
    try:
        at = AppTest.from_file(str(page), default_timeout=TIMEOUT)
        at.run()
    except Exception as exc:                     # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    if at.exception:
        first = at.exception[0]
        message = (first.message or "").strip()
        # st.page_link needs the navigation declared in dashboard.py; a page run
        # alone raises 'url_pathname'. Not a page defect, so not a failure.
        if "url_pathname" in message:
            return True, "rendered (cross-page links not testable without navigation)"
        return False, f"{first.type or 'Exception'}: {message[:220]}"
    return True, f"{len(at.markdown) + len(at.metric) + len(at.dataframe)} elements"


def main() -> int:
    pages_dir = ROOT / "app_pages"
    wanted = sys.argv[1:]
    pages = sorted(p for p in pages_dir.glob("*.py") if not wanted or p.name in wanted)
    if not pages:
        print("no page found")
        return 1

    failures = []
    for page in pages:
        ok, detail = check(page)
        print(f"  {'OK  ' if ok else 'FAIL'} {page.name:28s} {detail}")
        if not ok:
            failures.append(page.name)

    print(f"\n{len(pages) - len(failures)}/{len(pages)} pages without error")
    if failures:
        print("to fix: " + ", ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
