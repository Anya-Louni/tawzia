---
name: Tawzia
description: The AI HR platform built for Algeria. An approval desk you can feel.
colors:
  tawzia-blue: "#0B57A8"
  tawzia-blue-deep: "#084684"
  sky: "#6CBEF5"
  blue-mid: "#4E98E0"
  blue-wash: "#E7F1FC"
  clay-ground: "#E6ECF5"
  clay: "#EEF3F9"
  clay-high: "#F6F9FC"
  ink: "#0F1B2D"
  muted-ink: "#475870"
  line: "#D5DEEA"
  table-head: "#E9EFF7"
  status-green: "#0F6E4C"
  status-green-bg: "#DDF5EA"
  status-orange: "#8A5200"
  status-orange-bg: "#FDF0DA"
  status-red: "#B3261E"
  status-red-text: "#A32019"
  status-red-bg: "#FDECEC"
typography:
  display:
    fontFamily: "Manrope, Noto Sans Arabic, Segoe UI, system-ui, sans-serif"
    fontSize: "32px"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.035em"
  figure:
    fontFamily: "Manrope, Noto Sans Arabic, sans-serif"
    fontSize: "34px"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.035em"
    fontFeature: "tnum"
  headline:
    fontFamily: "Manrope, Noto Sans Arabic, sans-serif"
    fontSize: "21px"
    fontWeight: 800
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Manrope, Noto Sans Arabic, sans-serif"
    fontSize: "16px"
    fontWeight: 800
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Manrope, Noto Sans Arabic, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Manrope, Noto Sans Arabic, sans-serif"
    fontSize: "13.5px"
    fontWeight: 700
  caption:
    fontFamily: "Manrope, Noto Sans Arabic, sans-serif"
    fontSize: "12px"
    fontWeight: 400
  code:
    fontFamily: "JetBrains Mono, monospace"
rounded:
  slab: "28px"
  card: "24px"
  tile: "22px"
  well: "18px"
  ctrl: "16px"
  field: "14px"
  chip: "999px"
spacing:
  card-pad: "20px 22px"
  tile-pad: "18px 20px 16px"
  topbar-pad: "14px 18px"
  track-pad: "6px"
  gap-sm: "6px"
components:
  button-primary:
    backgroundColor: "{colors.tawzia-blue}"
    textColor: "#FFFFFF"
    rounded: "{rounded.ctrl}"
    padding: "0 20px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.tawzia-blue-deep}"
  button-secondary:
    backgroundColor: "{colors.clay}"
    textColor: "{colors.ink}"
    rounded: "{rounded.ctrl}"
    padding: "0 20px"
    height: "44px"
  button-secondary-hover:
    backgroundColor: "{colors.clay-high}"
    textColor: "{colors.tawzia-blue}"
  card:
    backgroundColor: "{colors.clay}"
    rounded: "{rounded.card}"
    padding: "{spacing.card-pad}"
  stat-tile:
    backgroundColor: "{colors.clay}"
    rounded: "{rounded.tile}"
    padding: "{spacing.tile-pad}"
  field:
    backgroundColor: "{colors.clay-ground}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    height: "44px"
  ask-well:
    backgroundColor: "{colors.clay-ground}"
    rounded: "{rounded.well}"
    height: "48px"
  nav-track:
    backgroundColor: "{colors.clay-ground}"
    rounded: "{rounded.tile}"
    padding: "{spacing.track-pad}"
  nav-section-active:
    backgroundColor: "{colors.tawzia-blue}"
    textColor: "#FFFFFF"
    rounded: "{rounded.ctrl}"
    height: "48px"
  subnav-pill-current:
    backgroundColor: "{colors.clay-ground}"
    textColor: "{colors.tawzia-blue}"
    rounded: "{rounded.chip}"
    padding: "7px 15px"
---

# Design

<!-- impeccable:design-schema 1 -->

Recorded from the shipped build: `core/appdata.py` (`_ROOT_VARS`, `inject_theme`),
`.streamlit/config.toml`, `core/nav.py`, `dashboard.py`, `core/i18n.py`, and the
review captures in `.impeccable/review/`. The frontmatter is normative; the
prose says where and why. Extensions (shadows, motion, breakpoints, component
snippets) live in `.impeccable/design.json`.

## Visual world

**The approval desk you can feel.** Tawzia is clay on a soft neumorphic desk.
The ground and every surface share one cool hue; nothing is separated by a
white card or a hard rule, only by light. Agent cards are clay tiles raised off
the desk, fields and tracks are wells pressed into it, and approving presses the
tile's button into the surface. It refuses the flat white-card SaaS dashboard
and the KPI wall.

### The light rule

**The Top-Left Light Rule.** One light for the whole app, from the top left.
Anything raised carries a white highlight up-left and an ink-blue shade
down-right (`rgba(30,58,105,…)`), plus a 1px inner top light. Anything inset
reverses both. A shadow that falls any other way is a bug.

### Raised vs inset vocabulary

Depth is a vocabulary of two words, and every element speaks one of them:

| Raised (clay, `--tz-raise*`) | Inset (well, `--tz-inset*`) |
|---|---|
| Top slab, cards, stat tiles, native metrics | Ask Tawzia command bar, every input, select, textarea, chat input |
| Secondary buttons, context controls, popover triggers | The section track, segmented controls and tab lists |
| Selected segment or tab (small raise inside its well) | The current sub-screen pill, the card-head meta pill |
| Chips, avatars, alerts, tables, chat messages | Expanders, a card nested in a card, the meter groove, disabled buttons |

Three raise sizes: `raise` (slab, cards, tiles), `raise-sm` (buttons, controls),
`raise-xs` (chips, hover states, selected segments). Two inset sizes: `inset`
(command bar, section track, chat input) and `inset-sm` (fields, pills, wells).

**The Nested Well Rule.** A card inside a card is not another tile: it becomes a
well (ground fill, `inset-sm`, 18px radius). Raised never stacks on raised.

### The signature: press to sign

**The Press-to-Sign Rule.** A button goes from raised to inset when pressed:
`:active` swaps its shadow for `--tz-press` and moves it `translateY(1px)
scale(.985)`. Every active or selected state reads pressed in or set apart by
light, never by a new colour alone. Approve is the gesture the whole product
is built around, so the press is the one tactile moment that must always work.

## Mode

**Operate.** HR managers and DRH at a desk in daylight, and a jury at a
projector. The task is to clear the decision inbox, then look under the hood
only when needed. Scanability, state and familiar Streamlit affordances outrank
expression; the brand lives in the clay, the light, and one blue.

## Color

Strategy: **restrained, monochrome clay plus one action blue.** Ground and
surfaces are the same cool hue a few steps apart; Tawzia blue is the only
filled colour on a card; the semantic set only ever means status.

| Role | Token | Use |
|---|---|---|
| Tawzia blue | `tawzia-blue` | The primary button (convex blue clay), the active section, links, page links, caret, current sub-screen text, emphasis inside the hero sentence |
| Blue deep | `tawzia-blue-deep` | Primary hover |
| Sky | `sky` | Text selection only (`rgba(108,190,245,.45)`). Focus is a 3px Tawzia-blue ring, 3px offset (6:1 on the ground), on every control |
| Blue mid, blue wash | `blue-mid`, `blue-wash` | Chart series and the rising chip tint; never a surface |
| Clay ground | `clay-ground` | Page background, and the fill of every well |
| Clay | `clay` | Every raised surface: slab, cards, tiles, secondary buttons, dialogs |
| Clay high | `clay-high` | Hover on clay, avatars, chat bubbles, focused command bar |
| Ink | `ink` | Titles, figures, body |
| Muted ink | `muted-ink` | Labels, captions, inactive nav (about 6.6:1 on clay) |
| Line | `line` | Native widget borders and dataframe borders; depth itself comes from light |
| Status green / orange / red | `status-*` | Status only, as native badges and alerts, always with a word |

Charts: categorical series start with the brand blue family (`#0B57A8`,
`#4E98E0`, `#6CBEF5`) then the semantic set; the sequential ramp runs
`#F0F7FE` to `#062F58` (config.toml).

**The One Blue Rule.** Blue clay is the single primary per card. A card offers
one filled blue button (Approve, Approuver les 9); everything else on it is
secondary clay, a page link, or an expander.

**The Word Rule.** Status is colour plus a word (`:red-badge[Urgent]`,
`:green-badge[+12 M DZD]`, the chip "5 urgentes"). Colour alone never carries
meaning.

## Prohibitions

Each binds because the clay world has none of it; each was checked against what
the world itself uses:

- No flat white cards (`#FFFFFF` surfaces). White exists only as highlight
  light and as text on blue clay.
- No hard offset shadows, and no shadow that contradicts the top-left light.
  Shadows are always soft, paired, and blue-ink tinted, never neutral black.
- No gradients on surfaces, text or buttons; convexity comes from paired inner
  highlight and inner base shade, not from a gradient fill.
- No glass, blur or backdrop-filter. Clay is opaque.
- No coloured `border-left` stripes on cards or alerts.
- No second filled colour on a card, and no KPI wall: stat tiles sit three
  across at the top of a screen, not as the screen.

## Type

**Manrope** 400 to 800 for everything (config.toml `font` and `headingFont`),
**Noto Sans Arabic** 400 to 800 as the Arabic face, **JetBrains Mono** for code.
CSS stack: `'Manrope','Noto Sans Arabic','Segoe UI',system-ui,sans-serif`, set on
`html, body, stApp` only (never a universal selector, it would break the
Material icon font).

| Role | Size / weight | Where |
|---|---|---|
| Screen title (hero) | 32px / 800, -0.035em, 1.1 (26px under 760px) | One per screen, no box around it |
| Hero sentence | 15px muted, 1.55, max 72ch, `<b>` in blue 800 | One sentence under the title |
| Figure | 34px / 800, -0.035em, tabular (28px under 760px) | Stat tiles; native metrics 800 |
| Native headings | 30 / 21 / 17 / 15 / 14 / 13px, weights 800 / 800 / 750 / 600 / 600 / 600 | Markdown headings in pages |
| Card title | 16px / 800, -0.015em | `appdata.card_head()` |
| Label | 13 to 13.5px / 700 muted | Tile and metric labels, nav, sub-screen pills |
| Caption | 12px muted | Tile captions, list subtitles, provenance line |
| Chip | 11.5px / 800 | Delta and meta chips |

**The Tabular Figure Rule.** Metric values, tile figures, list values and
dataframes use `font-variant-numeric: tabular-nums`. The figure is the content
of a tile.

**The One Family per URL Rule (Streamlit gotcha).** A `font` / `headingFont`
URL in config.toml must hold exactly one family. Streamlit maps the URL to the
single name before the colon; a second family in the same URL is never applied.
That is why the Arabic face is `@import`ed at the top of `_ROOT_VARS` instead.

**Direction.** FR / EN / ع switch (`core/i18n.LANGS`). In Arabic, `i18n.rtl_css()`
turns the main area `direction: rtl` and keeps dataframes LTR. Spacing uses
logical properties (`margin-inline-start`, `margin-inline-end`, `text-align:end`)
so lists mirror cleanly; new CSS must do the same.

## Layout

**One raised top slab, no sidebar.** The sidebar is hidden. `nav.page_header()`
renders a sticky clay slab (top .5rem, 28px radius) holding, left to right: the
logo lockup (with a short sector mention only for a tailored edition), the
**Demander à Tawzia** command bar as an inset well in the centre, and the
context controls (activity, forecast, data, language) as small clay pieces on
the right.

**Five screens plus Settings in one inset track.** Under the brand row:
Décisions, Personnel, Planning, Recrutement, Paie & déclarations, Réglages as
equal buttons in one well. The open space is raised in blue clay; the others are
transparent muted text that rises to `raise-xs` on hover. A click opens that
space's first screen.

**Sub-screens as pills.** The open space's screens sit under the track as small
pills. The current one is not a link (there is nowhere to go): it is an inset
pill in blue 800. The others are transparent page links that rise on hover.

Navigation is hand-built on `st.button` / `st.page_link` / `st.switch_page` with
`st.navigation(pages, position="hidden")`; section metadata, icons and benefit
notes live in `core/nav.py`. Streamlit's native top nav collapses sections into
an empty "N more" overflow on a projector, so it stays off.

**Screen body.** Main column max 1320px, top padding 1.4rem. Title and one
sentence, then three stat tiles, then the work column of cards with a quieter
side column (the inbox: decisions left, director summary and agent log right).

**Under 760px.** The slab stops being sticky (22px radius, 12px padding), the
hero and figures step down, and the section track is meant to wrap into a 3 x 2
grid at 12px.

## Sizing

| Element | Size |
|---|---|
| Every button (main, dialog, download, popover, form submit) | min 44px tall, 0 20px padding, 16px radius, 14px / 700 |
| Section buttons in the track | 48px tall, 16px radius, 13.5px / 700 |
| Ask Tawzia well | min 48px, 18px radius |
| Inputs, selects, textareas | min 44px, 14px radius |
| Context controls | min 44px, 14px radius, 12.5px / 700 |
| Segmented control and tab segments | 36px inside a 16px well with 4px padding, 12px radius |
| Cards | 24px radius, 20px 22px padding |
| Stat tiles / native metrics | 22px radius, min 118px / 108px, 18px 20px 16px padding |
| Top slab, dialog | 28px radius |
| Nested well, alert, table | 18px radius |
| Chips, pills, avatars, meter | full round; avatars 36px |

## Motion

Two authored moments and short state transitions, nothing else.

- **Rise:** cards, tiles and metrics enter with `tz-rise` (8px up, fade, .34s
  `cubic-bezier(.16,1,.3,1)`). The meter fills once in .7s on the same curve.
- **Press:** the press-to-sign swap above. Hover lifts buttons 1px.
- State transitions 140 to 220ms (`ease`, transforms on `cubic-bezier(.2,.8,.3,1)`).
- `prefers-reduced-motion` collapses every animation and transition.
- No scroll effects, no looping motion.

## Conventions

- Every page opens with `appdata.sidebar_controls()` (retained name: it injects
  the theme and guarantees the header state).
- `appdata.data_badge()` closes every page: the provenance line, including
  "Les volumes opérationnels sont simulés", is part of the layout.
- Status is colour plus a word, never colour alone.
- Never target `st-emotion-cache-*` classes; they change every Streamlit
  release. Style through `data-testid`, `data-baseweb`, `kind` attributes and
  `st-key-*` container keys.
- `st.navigation(position="hidden")` with the hand-built header.
- Colours enter the stylesheet only through `var(--tz-*)` from `_ROOT_VARS`;
  native widgets get theirs from config.toml.
- Use the house helpers before new markup: `stat_card`, `card_head`,
  `list_rows`, `legend`, `.tz-hero`, `.tz-meter`. Cards are
  `st.container(border=True)`; the theme makes them clay.
