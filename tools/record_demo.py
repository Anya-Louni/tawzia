# -*- coding: utf-8 -*-
"""
tools/record_demo.py
--------------------
Capture the demo screens from the real running app, at 1920x1080, for the
pitch video and the deck. The scenario is code so it can be replayed after any
UI change.

Prerequisite: the app runs on http://localhost:8501
    venv/Scripts/python.exe -m streamlit run dashboard.py

Then:
    venv/Scripts/python.exe tools/record_demo.py --out assets/demo/shots
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8501"
VIEW = {"width": 1920, "height": 1080}


def settle(page, quiet: float = 1.5, timeout: float = 240.0) -> None:
    """Wait until Streamlit has finished running (no status widget for `quiet` s)."""
    deadline = time.time() + timeout
    calm_since = None
    while time.time() < deadline:
        running = page.evaluate(
            "() => !!document.querySelector('[data-testid=\"stStatusWidget\"]')"
            " || !!document.querySelector('[data-testid=\"stSpinner\"]')"
            " || !!document.querySelector('[data-testid=\"stSkeleton\"]')")
        if running:
            calm_since = None
        elif calm_since is None:
            calm_since = time.time()
        elif time.time() - calm_since >= quiet:
            return
        time.sleep(0.25)


def dismiss_tour(page, wait: float = 4.0) -> None:
    """The first-visit tour (driver.js) appears a moment after render: close it."""
    end = time.time() + wait
    while time.time() < end and not page.locator(".driver-popover").count():
        time.sleep(0.25)
    for _ in range(6):
        if not page.locator(".driver-popover, .driver-overlay").count():
            return
        close = page.locator(".driver-popover-close-btn")
        if close.count():
            close.first.click(force=True)
        else:
            page.keyboard.press("Escape")
        time.sleep(0.5)
    page.evaluate("() => document.querySelectorAll('.driver-overlay,.driver-popover,"
                  ".driver-active-element').forEach(e => e.remove())")
    page.evaluate("() => document.body.classList.remove('driver-active')")


def goto(page, path: str) -> None:
    page.goto(f"{BASE}/{path}", wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid="stApp"]', timeout=60000)
    time.sleep(2.0)
    settle(page)
    dismiss_tour(page)
    page.mouse.move(1900, 1070)


def scroll_to_text(page, text: str, offset: int = 140) -> None:
    page.evaluate(
        """([t, off]) => {
            const els = [...document.querySelectorAll('p,h1,h2,h3,h4,div,span,button,td')]
              .filter(e => e.innerText && e.innerText.includes(t))
              .sort((a, b) => a.innerText.length - b.innerText.length);
            if (!els.length) return;
            const main = document.querySelector('[data-testid="stMain"]');
            const y = els[0].getBoundingClientRect().top + main.scrollTop - off;
            main.scrollTo(0, Math.max(0, y));
        }""", [text, offset])
    time.sleep(0.8)


def shot(page, out: Path, name: str) -> None:
    dismiss_tour(page, wait=0.5)
    page.mouse.move(1900, 1070)
    time.sleep(0.4)
    page.screenshot(path=str(out / f"{name}.png"))
    print("  shot", name)


def click_button(page, label: str) -> bool:
    btn = page.get_by_role("button", name=label).first
    if not btn.count():
        print("  (button not found)", label)
        return False
    btn.scroll_into_view_if_needed()
    btn.click()
    time.sleep(1.0)
    settle(page)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets/demo/shots")
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEW, device_scale_factor=1)

        # Approval inbox
        goto(page, "")
        shot(page, out, "01_inbox_top")
        scroll_to_text(page, "payslips recomputed", 260)
        shot(page, out, "02_inbox_payroll_card")
        goto(page, "")
        scroll_to_text(page, "compliant requests", 200)
        shot(page, out, "03_inbox_batch")
        if click_button(page, "Approve all 9") or click_button(page, "Approve all"):
            page.evaluate("() => document.querySelector('[data-testid=\"stMain\"]').scrollTo(0,0)")
            time.sleep(0.6)
            shot(page, out, "04_inbox_after_approve")

        # Filings and payroll
        goto(page, "deadlines_view")
        shot(page, out, "05_deadlines")
        goto(page, "payroll_view")
        shot(page, out, "06_payroll")

        # Schedule: Ouargla, then Ramadan mode
        goto(page, "schedule_view")
        sel = page.locator('[data-testid="stSelectbox"]').first
        sel.click()
        time.sleep(0.6)
        opt = page.get_by_role("option").filter(has_text="Ouargla")
        if opt.count():
            opt.first.click()
            settle(page)
        click_button(page, "Generate")
        time.sleep(1.0)
        shot(page, out, "07_schedule")
        scroll_to_text(page, "Employee", 160)
        shot(page, out, "08_schedule_grid")
        page.evaluate("() => document.querySelector('[data-testid=\"stMain\"]').scrollTo(0,0)")
        tog = page.get_by_text("Ramadan hours").first
        if tog.count():
            tog.click()
            settle(page)
            click_button(page, "Generate")
            shot(page, out, "09_schedule_ramadan")

        # Employee desk: a Darija request
        goto(page, "self_service")
        chat = page.locator('[data-testid="stChatInputTextArea"]').first
        if chat.count():
            chat.fill("salam, 3tini attestation de travail svp")
            chat.press("Enter")
            time.sleep(2.0)
            settle(page)
            shot(page, out, "10_desk_answer")
            exp = page.get_by_text("View the certificate").first
            if exp.count():
                exp.click()
                time.sleep(1.0)
            scroll_to_text(page, "View the certificate", 260)
            shot(page, out, "11_desk_doc")

        # Hiring
        goto(page, "job_post_view")
        ta = page.locator("textarea").first
        ta.fill("I need 3 sorters for the Algiers hub, reliable and available for "
                "shifts, on a 12-month CDD, able to work Fridays.")
        click_button(page, "Write the post")
        time.sleep(1.0)
        shot(page, out, "12_jobpost")
        scroll_to_text(page, "ready to publish", 160)
        shot(page, out, "13_jobpost_result")
        goto(page, "talent_pool")
        shot(page, out, "14_candidates")
        scroll_to_text(page, "four-fifths", 260)
        shot(page, out, "15_bias")

        # Trust
        goto(page, "privacy_view")
        shot(page, out, "16_privacy")
        goto(page, "people")
        shot(page, out, "17_people")
        goto(page, "anomalies_view")
        shot(page, out, "18_anomalies")

        browser.close()


if __name__ == "__main__":
    main()
