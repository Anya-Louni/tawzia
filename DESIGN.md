# Design

<!-- impeccable:design-schema 1 -->

## Visual world

**Sharp, high contrast, action first.** A navy command band carries the brand and
the navigation; below it, white worksheets with a visible edge sit on a cool grey
ground. Corners are square. Each agent owns one colour and one drawn icon, so a
card's origin reads before its text. The screen should look like work is
happening: the inbox headline is the day's count, a progress bar fills as cards are
cleared, and a navy panel charts what each agent prepared.

Refused: the earlier soft clay and neumorphic look (too low in contrast, read as an
empty product), the flat "public register" look before it, and any glass,
gradient or decorative halo.

## Mode

**Operate.** HR managers clearing decisions at a desk in daylight, and a jury on a
projector. Familiar controls, strong hierarchy, one primary action per card.

## Color

Strategy: **committed shell, restrained work area.** Navy owns the band; blue is the
only action colour; agent colours identify, status colours warn, and both always
come with a word.

| Role | Value | Use |
|---|---|---|
| Navy | `#0A2540` | Command band, agent chart panel, phone frame |
| Navy 2 | `#173B66` | Hover inside the band |
| Ink | `#0A1628` | Text, figures, secondary buttons (outlined), selected segment |
| Muted | `#3E4C60` | Secondary text (9:1 on white) |
| Ground | `#EDF1F6` | Page background |
| Surface | `#FFFFFF` | Cards, fields, tables |
| Line | `#C5D0DE` / `#9AABC2` | Card edges / field edges and hover |
| Blue | `#0B57A8` | The primary action, links, focus ring (6:1) |
| Sky | `#6CBEF5` | Active underline in the band, selection, focus inside the band |
| Agents | attendance `#0B57A8`, payroll `#6D28D9`, filings `#B45309`, compliance `#B91C1C`, retention `#15803D`, hiring `#0F766E`, desk `#334155`, onboarding `#4338CA`, planning `#0E7490` | Icon tiles, chart bars, progress segments |
| Status | ok `#15803D`, warn `#B45309`, danger `#B91C1C` on their washes | Tags and deadline panel, always with a word |

## Shape and depth

- Radius: 3px for buttons, fields, tags; 8px for cards. Nothing pill-shaped.
- Cards: 1px edge plus one soft lift (`0 1px 2px` + `0 10px 26px -14px`), stronger on hover.
- Primary button: solid blue, white text. Secondary: white with a 1.5px ink outline,
  inverting to ink on hover. On press, every button sinks (inset shadow, 1px down,
  no transition): the "press to sign" moment.

## Type

Manrope 400 to 800 (config.toml, one family per URL: Streamlit drops the whole theme
otherwise), Noto Sans Arabic `@import`ed in CSS for the Arabic interface. Inbox
headline 34/800, page titles 32/800, card titles 15.5/800, stat labels 13/800
uppercase, body 15, captions 12.5. Tabular numerals on every figure.

## Layout

- Navy band: logo, the white "Ask Tawzia" field (the brightest element), context
  controls and language switch; under a hairline, the six spaces as tabs, the open
  one a white slab with a sky underline; sub-screens as small tabs below.
- Inbox: a two-part "today" panel (count, sentence, segmented progress bar | agent
  chart), then a filter bar (All, Urgent, one per agent), then cards; a side column
  with the next legal deadline, the management summary and the action log.
- Card anatomy: agent tile, tags, title, why, law, "what approval triggers"
  (expandable), then Approve (primary) · Edit (link) · Reject (secondary).
- Mobile: the band stops sticking, spaces and controls wrap two per row, the today
  panel stacks.

## Motion

Cards rise 6px on first appearance; progress and chart bars grow from the left once.
Buttons react in 140ms, press instantly. Everything stops under
`prefers-reduced-motion`.

## Conventions

- Tokens live only in `core/appdata._ROOT_VARS`; the sheet uses `var(--tz-*)`.
- Every page calls `appdata.sidebar_controls()` and ends with `appdata.data_badge()`.
- Never target `st-emotion-cache-*` classes; use `data-testid` hooks and
  `st.container(key=...)` (`.st-key-*`). Never a universal `*` font selector (it
  kills the icon font).
- Navigation is hand-built (`core/nav.py`) with `st.navigation(position="hidden")`.
- English by default (`core/i18n.py`), French and Arabic as switches; Arabic sets the
  page right to left.
