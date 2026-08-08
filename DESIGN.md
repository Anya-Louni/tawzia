# Design

<!-- impeccable:design-schema 1 -->

## Visual world

**Le registre public algérien.** Not a SaaS dashboard, not a startup deck: the
visual language of an official register that a labour inspector, a DRH and a
finance director can all read without asking what a colour means. A deep navy
command bar sits above a white worksheet on a slate ground. Everything is
squared off, ruled, and legible at projector distance, because this app is shown
in meeting rooms as often as it is used at a desk.

The refused arrangement: the indigo-to-violet gradient SaaS look this app used
before. Gradients read as decoration, and decoration is exactly what an audience
evaluating a compliance and payroll claim discounts.

## Mode

**Operate.** Operations and HR managers completing a task: forecast, roster,
pay, check risk, source. Scanability, state, and familiar affordances outrank
expression. Brand lives in the ruling, the type scale, and one blue.

## Color

Strategy: **restrained** , slate ground, white surfaces, one blue that always
means "action or active", plus a semantic set that only ever means status.

| Role | Value | Use |
|---|---|---|
| Navy | `#0A2540` | Command bar, h1/h2, metric values |
| Blue | `#1355C4` | Primary buttons, links, active nav, focus ring |
| Blue dark | `#0E42A0` | Hover and pressed |
| Blue soft | `#E8F0FC` | Active/selected background tint only |
| Ground | `#F1F5F9` | Page background , makes white surfaces read as cards |
| Surface | `#FFFFFF` | Cards, tables, inputs |
| Line | `#CBD5E1` | Every border, 1px, always visible |
| Text | `#0F172A` | Body |
| Muted | `#475569` | Secondary text (7:1 on white; never a light gray) |
| Green / Orange / Red | `#047857` / `#B45309` / `#B91C1C` | Status only, never brand |

**Contrast is the design.** The ground is slate, not white, so a white card is a
real object with a visible edge. That single decision replaces every shadow the
old theme used to fake depth with.

## Prohibitions

These bind because the world is a printed register, which has none of them:

- **No gradients anywhere** , not in text, buttons, backgrounds, accents or
  rails. Emphasis comes from weight, size and the navy.
- No glass, blur, or coloured halo shadows. Depth is a 1px line and, at most, a
  small offset shadow with real blur.
- No coloured `border-left` above 1px on cards or alerts.
- No decorative icon-plus-heading card grids used as page structure.

## Type

Inter throughout (UI workhorse, correct for Operate; carries French accents and
the Arabic-adjacent Latin set cleanly). Scale is wide and obviously stepped so
hierarchy survives a projector: h1 32px/800 navy, h2 22px/700, h3 17px/700,
body 15px/400, caption 13px. Numbers in metrics are 800 weight navy , the
figure is the content.

## Layout

**Navy command bar, no sidebar.** The seven sections sit in the bar as seven
equal buttons, always visible, always the same box (58px). A cramped bar that
hides features makes a prospect believe they do not exist, which is the one
visual failure that costs money.

**Choosing a feature dims everything else.** Clicking a section opens
`st.dialog`, which lays a navy veil (`rgba(10,37,64,.62)`) over the app and
leaves one decision on screen: which of that section's features to open. Each
entry is an equal-height card carrying a benefit sentence, not a feature name.
Section metadata lives in `core/nav.py`.

Navigation is hand-built on `st.page_link` / `st.switch_page` with
`st.navigation(position="hidden")`. Streamlit's native top navigation collapses
every section into an empty "N more" overflow when it cannot measure its items,
which is unacceptable on a projected demo.

## Sizing contract

One box per control class, enforced globally rather than per page, because
inconsistent sizing was the most visible defect:

| Element | Size |
|---|---|
| Section buttons (navy bar) | 58px tall, equal widths |
| Every other button, anywhere including dialogs | 42px tall, 7px radius |
| Inputs and selects | 42px tall, matching buttons |
| Metric tiles | 96px minimum, so one- and two-line labels align |

Rhythm: cards are bordered white blocks with generous inner padding, separated
by clear gutters, more space above a heading than below it.

## Motion

Restrained and uniform: 130-160ms ease transitions, a 1-2px lift on hover for
buttons, metric tiles and picker cards, returning to rest on `:active`. No
entrance animations, no scroll effects. The onboarding tour (driver.js,
`core/tour.py`) is the one authored motion moment.

## Conventions

- Every page opens `appdata.sidebar_controls()` , retained name, now renders the
  top context strip and injects the theme.
- Status is carried by the semantic colours plus a word, never colour alone.
- Provenance line (`appdata.data_badge()`) closes every page: the honesty
  commitment is part of the layout, not a footnote.
