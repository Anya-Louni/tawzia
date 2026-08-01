# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: operations managers and founders at Algerian shift-labour businesses —
e-commerce fulfilment/parcel hubs (Yalidine-class carriers), retail & FMCG
distribution centres, and airport ground handling (Air Algérie / Aéroport
d'Alger). They plan shifts days ahead from dispatch offices, warehouse
mezzanines and ops-control rooms, mostly in French/Arabic, often from
spreadsheets and delivery-app dashboards.

Secondary (for this marketing surface specifically): a startup-competition jury
and early investors in Algeria who must be convinced the product is rigorous,
locally rooted, and fundable.

## Product Purpose

Tell an Algerian operator exactly how many workers to schedule on each shift, so
they stop losing money guessing — too few staff means failed deliveries (paid
twice in a 95% cash-on-delivery market), too many means idle wages. The engine
forecasts demand, then produces the cheapest legally-compliant roster, and
proves the saving out-of-sample.

## Positioning

The mechanism a foreign competitor cannot truthfully copy: WorkForce.dz models
the **real Algerian operating calendar** as a first-class input — the
Friday–Saturday weekend, the Hijri calendar (Ramadan and the two Aïds, which
move ~11 days earlier each year and reshape the day), the diaspora summer peak,
the rentrée and the end-of-month payday cycle — plus real observed weather and
the real Algerian labour-cost stack (SNMG, CNAS). Global workforce tools
(Quinyx, UKG, Legion) are built for a Gregorian, Saturday–Sunday, temperate
market and have no way to express these. A second, aviation-specific mechanism:
a rotation-aware delay-cascade predictor that names the single flight to protect
to break a cascade.

## Operating Context

The artifacts of this world: shift rosters and crew load-sheets; airport
departure boards (FIDS); the dual Hijri/Gregorian almanac and prayer-time
calendars that govern the Algerian year; delivery-app dispatch dashboards;
customs/labour bureaucracy; wilaya road signage (French/Arabic/Tifinagh); the
Saharan and Mediterranean climate that drives labour capacity. Demand events
that matter: Ramadan, Aïd el-Fitr, Aïd el-Adha, the mid-June–September diaspora
return, the rentrée scolaire, payday.

## Capabilities and Constraints

- Demand forecasting (gradient-boosted, walk-forward backtested) on real
  calendar + real ERA5 weather per wilaya.
- Legal roster optimisation (LP) honouring the statutory overtime cap and
  weekly rest, costed on SNMG 24,000 DZD + 26% CNAS employer charge; derived
  hourly floor 138.46 DZD reproduces the official figure exactly.
- Out-of-sample evidence: ~50% lower forecast error than a generic
  international model; 5.7–7.9% cost saving; +12pp service level; wins 69–81%
  of windows (and honestly shows the losses).
- Aviation module on the real ALG route network: hourly passenger-flow →
  terminal staffing; delay-cascade prediction (reproduces the ~45% industry
  reactionary-delay share); turnaround-risk scoring.
- The working product is a Python/Streamlit multi-page app (the live demo).
- Verticals live today: e-commerce hub, retail DC, airport ground handling.

## Brand Commitments

- Name: **WorkForce.dz** (the `.dz` — Algeria's ccTLD — is load-bearing; this
  is deliberately, unmistakably Algerian).
- Voice: rigorous, plain-spoken, radically honest — it states its own caveats
  rather than hiding them.
- No prior binding visual identity worth preserving. The earlier Air-Algérie-red
  instrument-panel look is being replaced and is anti-reference, not authority.

## Evidence on Hand

- Real, citable inputs and a full source registry (core/sources.py): SNMG/CNAS,
  Yalidine network, COD share/return rates, Air Algérie 8.8M→10M passenger goal
  + ~60 aircraft, ALG 9.15M pax 2024, port demurrage, ASF/startup-label funding.
- Live public-data integrations: Open-Meteo (ERA5 weather), World Bank (macro),
  Aladhan (Hijri cross-check).
- The working app itself is the primary demonstration.
- **Must not fabricate:** the operational *volumes* in the demo are simulated
  (no Algerian operator's ledger is public) — the calendar, weather and labour
  law driving them are real. No real signed customers, no real revenue, no real
  testimonials yet. Pricing tiers (Free / Pro 39,000 DZD / Enterprise) are the
  intended model, not booked deals.

## Product Principles

1. Local truth is the moat — model Algeria as it actually runs, not as a
   translated Western template.
2. Defensible over impressive — a 6% saving that survives diligence beats a 30%
   one that doesn't; show the caveats and the losses.
3. Every number traceable to a real source or labelled as an assumption.
4. The right AI for each job (forecasting model, optimiser, cascade-propagation
   model, LLM copilot) — not one chatbot dressed as everything.
5. Two verticals, one engine: parcels and passengers are the same problem.
