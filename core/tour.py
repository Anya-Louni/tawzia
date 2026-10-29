"""
core/tour.py
------------
The product's guided tour, on first launch.

Why it exists
=============
A platform with many screens loses the person who opens it for the first time,
and a lost person does not buy. The tour says in five steps what the tool does,
where to click and what it earns, then disappears and never comes back unless
asked.

How it is wired
===============
`driver.js` (MIT, bundled in `assets/vendor/`, never loaded from a CDN: the demo
must work without a network) is mounted in a **Custom Components v2**
component. CCv2 does not put the component in an iframe: the script runs in the
app's document, so it can highlight the real interface elements (the band, the
spaces, the settings), not a copy in an isolated frame.

`isolate_styles=False` is required: driver.js draws its overlay and popover on
`document.body`, outside the shadow root, so its stylesheet must be global.

The selectors are our own named containers (`st-key-*`), never
`st-emotion-cache-*` classes, which change with every Streamlit version.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

_VENDOR = Path(__file__).resolve().parent.parent / "assets" / "vendor"

_SEEN_KEY = "_tour_seen"
_REPLAY_KEY = "_tour_replay"


def _read(name: str) -> str:
    try:
        return (_VENDOR / name).read_text(encoding="utf-8")
    except OSError:
        return ""


# driver.js ships as an IIFE that sets `this.driver`; in an ES module `this` is
# undefined at top level, so it runs with `window` as `this`.
_DRIVER_SRC = _read("driver.iife.js")
_DRIVER_CSS = _read("driver.css")

_JS = """
(function () {
%s
}).call(window);

export default function (component) {
  const { data, setTriggerValue } = component;
  if (!data || !data.run) return;

  const factory = window.driver && window.driver.js && window.driver.js.driver;
  if (typeof factory !== "function") return;

  // One tour at a time, even if Streamlit remounts the component.
  if (window.__wfTourRunning) return;
  window.__wfTourRunning = true;

  const steps = (data.steps || [])
    .filter(function (s) { return !s.element || document.querySelector(s.element); })
    .map(function (s) {
      return {
        element: s.element || undefined,
        popover: {
          title: s.title,
          description: s.text,
          side: s.side || "bottom",
          align: s.align || "start",
        },
      };
    });

  if (!steps.length) { window.__wfTourRunning = false; return; }

  const finish = function () {
    window.__wfTourRunning = false;
    setTriggerValue("finished", true);
  };

  const tour = factory({
    showProgress: true,
    allowClose: true,
    overlayColor: "#0A2540",
    overlayOpacity: 0.68,
    stagePadding: 6,
    stageRadius: 8,
    popoverClass: "wf-tour",
    nextBtnText: (data.labels || {}).next || "Next",
    prevBtnText: (data.labels || {}).back || "Back",
    doneBtnText: (data.labels || {}).done || "Get started",
    progressText: "{{current}} / {{total}}",
    steps: steps,
    onDestroyed: finish,
  });

  // Let Streamlit finish painting the page before measuring the targets.
  // `setTimeout`, not `requestAnimationFrame`: rAF does not fire in a hidden
  // tab, and the tour would then hang.
  setTimeout(function () {
    try {
      tour.drive();
    } catch (err) {
      window.__wfTourRunning = false;
      console.error("Tawzia guided tour:", err);
    }
  }, 300);
}
""" % _DRIVER_SRC

_CSS = _DRIVER_CSS + """
/* The popover speaks the product's visual language: navy, action blue,
   square corners, no gradient. */
.driver-popover.wf-tour {
  background:#FFFFFF; border:1px solid #CBD5E1; border-radius:10px;
  box-shadow:0 24px 60px -20px rgba(10,37,64,.6);
  font-family:'Inter', system-ui, sans-serif; max-width:360px;
}
.driver-popover.wf-tour .driver-popover-title {
  font-size:16px; font-weight:800; color:#0A2540; letter-spacing:-.015em;
}
.driver-popover.wf-tour .driver-popover-description {
  font-size:13.5px; line-height:1.55; color:#334155;
}
.driver-popover.wf-tour .driver-popover-progress-text {
  font-size:12px; color:#475569; font-weight:600;
}
.driver-popover.wf-tour button {
  background:#FFFFFF; color:#0A2540; border:1px solid #CBD5E1;
  border-radius:6px; padding:6px 14px; font-size:13px; font-weight:600;
  text-shadow:none; transition:background .13s ease, border-color .13s ease;
}
.driver-popover.wf-tour button:hover {
  background:#E8F0FC; border-color:#1355C4; color:#0E42A0;
}
.driver-popover.wf-tour .driver-popover-next-btn {
  background:#1355C4; border-color:#1355C4; color:#FFFFFF;
}
.driver-popover.wf-tour .driver-popover-next-btn:hover {
  background:#0E42A0; border-color:#0E42A0; color:#FFFFFF;
}
.driver-popover.wf-tour .driver-popover-close-btn {
  background:transparent; border:0; padding:0; width:28px; height:28px;
  font-size:20px; color:#64748B; top:8px; right:8px;
}
.driver-popover.wf-tour .driver-popover-close-btn:hover { background:#EEF2F7; color:#0A2540; }
.driver-popover.wf-tour .driver-popover-arrow { border-color:#FFFFFF; }
"""

# The steps: what the tool does, where to click, what it earns.
# (selector, title key, text key, side, align). Keys live in core/i18n.py so the
# tour speaks the chosen language. Steps whose target is absent are skipped.
_STEPS = [
    (".st-key-wf_topbar", "tour_1_t", "tour_1_x", "bottom", "start"),
    (".tz-today", "tour_2_t", "tour_2_x", "bottom", "start"),
    ("[data-testid='stMain'] [data-testid='stVerticalBlock']:has(> [data-testid='stElementContainer'] .tz-card-top)", "tour_3_t", "tour_3_x", "bottom", "start"),
    (".st-key-wf_ask", "tour_4_t", "tour_4_x", "bottom", "start"),
    (".st-key-wf_sections", "tour_5_t", "tour_5_x", "bottom", "start"),
    (".st-key-wf_controls", "tour_6_t", "tour_6_x", "bottom", "end"),
]


def steps() -> list:
    from .i18n import t
    return [{"element": el, "title": t(tk), "text": t(xk), "side": side, "align": align}
            for el, tk, xk, side, align in _STEPS]


_COMPONENT = st.components.v2.component(
    "wf_onboarding_tour",
    html="<div hidden></div>",
    css=_CSS,
    js=_JS,
    # driver.js draws its overlay on document.body, outside the shadow root,
    # so its stylesheet must be global.
    isolate_styles=False,
)


def available() -> bool:
    """The tour is only possible if driver.js was bundled."""
    return bool(_DRIVER_SRC)


def maybe_run(current) -> None:
    from .i18n import t
    """
    Run the tour on the session's first display, or on request.

    Called after the page renders, so the targets already exist in the
    document when driver.js measures them.
    """
    if not available():
        return

    replay = st.session_state.pop(_REPLAY_KEY, False)
    first_time = not st.session_state.get(_SEEN_KEY, False)

    # On first launch the tour runs on the home page only.
    on_home = getattr(current, "url_path", "") in ("", "autopilot")
    run = replay or (first_time and on_home)

    if run:
        st.session_state[_SEEN_KEY] = True

    _COMPONENT(
        key="wf_tour",
        data={"run": bool(run), "steps": steps(),
              "labels": {k: t(f"tour_{k}") for k in ("next", "back", "done")}},
        on_finished_change=lambda: None,
    )
