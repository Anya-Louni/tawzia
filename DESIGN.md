# Design

<!-- impeccable:design-schema 1 -->

## Visual world — Solari split-flap departure board

The marketing surface **is** an airport split-flap board (Solari di Udine): a
living schedule that flips from noise into signal. This is a deliberately
committed single world — slate board chrome + bone "boarding-pass" tickets for
readable prose — held in both OS themes (a departure board is illuminated
slate; that is the use-scene, not a dark-by-default reflex). It replaces the
prior Air-Algérie-red instrument-panel look, which is anti-reference.

The atomic component is the **flap**: a fixed-width character cell / tile with a
hard horizontal center seam and side sprocket notches. Headlines, nav, buttons,
status pills and data rows are all built from flaps or board rows — never
generic cards.

## Two surfaces

- **BOARD** — slate flap tiles, sodium-amber active text. Chrome, headlines,
  nav, buttons, data rows, status. Uppercase, tabular, fixed cells.
- **TICKET** — warm bone boarding-pass paper, ink text, perforated edges,
  monospace ticket data. Carries all readable prose (feature copy, pricing
  detail) at a 62–72ch measure. Board and boarding pass are one world.

## Palette (roles, not accents scattered on neutral)

- `--slate` #1C2026 board ground · `--slate-2` #262B33 flap face · `--slate-3`
  #31373F raised · `--seam` rgba(0,0,0,.55) flap hinge line
- `--bone` #ECE7DA ticket paper · `--bone-2` #E2DCCB · `--ink` #23201A ticket text
- `--amber` #E9B24C — live/active/primary (the sodium-lamp accent; owns board text)
- `--red` #D8452F — delay / protect / alarm (semantic only)
- `--green` #8FB65A — on-time (semantic only) · `--dim` #79818D — inactive/greyed

Amber and bone-on-slate and ink-on-bone all clear 4.5:1. Red and green are
semantic status colors, never the accent.

## Type

Display POV comes from the **flap treatment** (fixed cells, seams, uppercase,
amber), not a novelty family — CSP blocks webfonts, so no font is linked.
- Board/display: condensed grotesque stack — `"Arial Narrow","Roboto Condensed",
  "Helvetica Neue",system-ui,sans-serif`, uppercase, rendered in fixed cells.
- Board/ticket data: `ui-monospace, "SF Mono","IBM Plex Mono",Menlo,monospace`
  — legitimate: this is board/ticket measurement data, not a "technical" costume.
- Ticket prose: system humanist sans, 62–72ch, for actual reading.

## Signature motion — the split-flap reveal

The ONE authored moment: characters cycle and flip to land on target, staggered
left→right and top→bottom so a board resolves like the real thing. Triggered on
load (hero) and on scroll-into-view (each board), via IntersectionObserver.
Buttons are flap tiles that flip on hover and press. `prefers-reduced-motion`
renders final text immediately with no flipping. Bound the char-cycling; only
animate visible boards.

## Bans specific to this world

- No generic SaaS cards, no hero-metric template, no gradient text, no glass
  decoration, no colored left-border rails. Structure is the board and the
  ticket.
- Section numbers only where a real sequence exists (the FORECAST→ROSTER→SAVE
  itinerary legs). Status color is semantic, never decoration.

## Content truth

Operational volumes shown on the board are illustrative/simulated (labelled);
calendar, weather and labour-law inputs are real. No invented customers,
revenue, or testimonials. Pricing (Free / Pro 39,000 DZD / Enterprise) is the
intended model. Demo link is a placeholder until the Streamlit app is deployed.
