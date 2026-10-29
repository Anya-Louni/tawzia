# Tawzia

**Shift-labour intelligence for Algerian operations.**

---

## The one-sentence version

Algerian logistics and retail operators lose money every week rostering
against a calendar their software doesn't understand — we forecast Algerian
demand properly and turn it into a legal, cost-optimal shift plan.

---

## 1. The problem, concretely

An Algerian parcel hub, distribution centre or ground-handling operation has
to decide, days ahead, how many people to put on each shift. Get it wrong in
either direction and it costs:

- **Too few** → parcels miss their delivery window. In a market where
  **95% of e-commerce orders are cash on delivery**, a missed attempt isn't a
  reschedule — the customer refuses the package and the merchant pays for the
  outbound *and* return legs. COD return rates run **19% regionally**, and in
  Algeria swing between roughly 15% and 25% depending on delivery reliability.
- **Too many** → idle wages, at a loaded cost most operators under-estimate by
  about a quarter because they plan against gross wage and forget the **26%
  CNAS employer charge**.

Today most operators run a **fixed weekly roster** sized on a rolling average.
It cannot see the day coming.

## 2. Why existing software doesn't fix it

Global tawzia-management tools — Quinyx, UKG, Legion, Deputy — are built
for a Gregorian, Saturday–Sunday, temperate market. In Algeria they are wrong
in four structural ways:

| What they assume | What's actually true in Algeria |
|---|---|
| Weekend is Saturday–Sunday | Weekend is **Friday–Saturday** |
| The year is Gregorian | **Ramadan and the two Eids move ~11 days earlier each year** and reshape the day, not just its volume |
| Summer is a demand trough | Summer is the **annual peak** — the diaspora return, mid-June to early September |
| Demand is smooth within a month | Salaries are paid **end of month**; demand spikes in the first days of the next |

These aren't tuning problems. A tool with no Hijri calendar in its feature set
has **no way to express the right answer**, however much data you give it.

> We know this failure mode intimately: the first version of this project had
> the Algerian weekend backwards in its own demand model. We found it while
> rebuilding on real data.

## 3. What we built

A forecasting and rostering engine with Algeria as a first-class citizen:

- **A real Algerian calendar engine.** Hijri conversion computed locally
  (verified round-trip across 60 Hijri years; Eid al-Fitr 1445 resolves to
  10 April 2024, the actual date), plus gazetted civil holidays including
  Yennayer, the Friday–Saturday weekend, back to school, the diaspora
  season and the payday cycle.
- **Real weather.** ERA5 observed history and operational forecast per wilaya
  via Open-Meteo. Ouargla recorded **84 days above 38°C in summer 2024** —
  heat that measurably cuts effective labour capacity.
- **A cost model built from Algerian statute.** SNMG 24,000 DZD/month over
  173.33 legal hours, CNAS employer charges, statutory night, rest-day and
  holiday premiums. Our derived floor rate of **138.46 DZD/hour reproduces the
  officially published figure exactly**.
- **A legal optimiser.** Overtime capped at 20% of legal working time and the
  weekly rest day are encoded as **hard constraints** — a plan that breaks them
  is infeasible, not merely expensive.

Since then it has become a full HR platform rather than a scheduling tool. 29
screens across seven sections, covering the employee from before they apply to
the day they leave:

- **Sourcing.** A directory of real Algerian recruitment channels — the
  universities and national schools, the CFPA/INSFP network, ANEM, the job
  boards, internal referral — ranked for a given role and wilaya and turned into
  a costed plan. It penalises over-qualification, because a graduate hired into
  an operational post leaves and you pay the turnover twice.
- **Screening that resists manipulation.** CV evaluation and batch matching on
  local embeddings, plus detection of candidates who hide instructions in a PDF
  to inflate their own score. Most tools on the market simply obey them.
- **Skills and internal mobility.** Who already covers most of a vacancy, what
  they are missing, and the arbitrage between training them and recruiting
  outside, with both costs and both timelines.
- **Payroll, compliance and document control.** CNAS/IRG payroll, anomaly
  detection, an inspection dry run, and a trained vision model that reads
  amounts off a payslip and checks them against the SNMG and the CNAS rate.
- **A decision layer.** KPIs, a scenario simulator, and copilots that narrate
  figures the engine computed rather than inventing their own.

## 4. The evidence

Walk-forward backtest, 25+ independent forecast origins, no model ever seeing
the data it's scored on:

| Model | MAPE |
|---|---|
| **Tawzia** | **~15%** |
| Generic international model *(same algorithm, blind to Algeria)* | ~31% |
| Seasonal naive | ~30% |
| Trailing mean | ~38% |

**~50% lower forecast error than the identical algorithm without the Algerian
feature set.** That gap is the product.

Turned into money — both rosters built blind, both scored against the same
realised demand, both paying identical wages, premiums and shortfall penalties:

- **5.7%–7.9% lower total cost**
- **+12 percentage points service level**
- Wins on **69–81% of windows** — and loses up to 9% on the rest

That last line matters. A comparison that never loses is a comparison that has
been rigged.

## 5. The honest caveat

**We do not have a real Algerian operator's volume ledger.** Nobody outside
those companies does. The operational *volumes* in the demo are simulated.

What is real is everything they respond to: the actual Algerian calendar and
the actual observed weather. So the results validate **the method, not the
market**. The magnitude needs a pilot to confirm — and the app says so on
every page.

We'd rather defend a 6% saving that survives diligence than pitch a 30% one
that doesn't.

## 6. Market

Bottom-up, priced at 20% of measured value delivered (~47,000 DZD/site/month):

| Segment | Sites | Confidence |
|---|---|---|
| E-commerce parcel & delivery branches | ~600 | Anchored — Yalidine alone has 160+ across all 58 wilayas |
| Retail & FMCG distribution centres | ~180 | Estimated |
| Food & beverage manufacturing | ~320 | Estimated |
| Port, bonded warehouse & clearance | ~45 | Estimated |
| Airport ground handling | ~16 | Anchored |

- **TAM** ≈ 655M DZD/year (~$4.9M)
- **SAM** ≈ 646M DZD/year — excludes airports, which are state-operated and buy
  through multi-year public tender
- **SOM** ≈ 26M DZD/year — 46 sites, 4% of SAM in 3 years

**Say this plainly:** Algeria alone is a ~$4.8M/year serviceable market. That's
a good, profitable business — **not, on its own, a venture-scale one**. Anyone
who claims otherwise loses the room at diligence.

The regional case is what justifies a second cheque. The Hijri calendar engine
— the expensive, reusable part — applies identically in Morocco, Tunisia,
Egypt, Saudi Arabia and Jordan. Population-scaled, that's roughly **$26M/year**.
(The Friday–Saturday weekend does *not* generalise — three of those six markets
run Saturday–Sunday. That's per-country configuration, which is exactly why the
engine is parameterised by market.)

## 6b. The aviation module — for the Air Algérie / Aéroport d'Alger conversation

The same forecast-and-optimise engine extends into an **Airport Operations AI**
module, built for the customer you plan to approach. It's grounded in the real
ALG route network and the real Algerian calendar (flight schedules and delays
are simulated, and the app says so).

**Why now:** Air Algérie is scaling from ~8.8M passengers (2025) toward ~10M
(2026) and taking **~60 new aircraft** onto a hub that already congests at
peak, with a documented "chaotic day" of cascading delays. Three features hit
that directly:

1. **Passenger-flow forecaster → terminal staffing.** Predicts the crowd
   physically at check-in / security / boarding *each hour* — driven by the
   flight schedule *and* the diaspora-summer / Ramadan / Eid calendar — and
   turns it into desk and agent counts. The peak (not the daily total) is what
   jams ALG in July, and it's invisible to a Western-calendar tool.

2. **Delay-cascade predictor (the flagship).** Aircraft fly chains; a late
   inbound eats its turnaround and pushes every subsequent flight. The model
   predicts the whole chain *before it happens* and names the **one flight to
   protect to break it** — e.g. "protect AH1402, and you spare 5 downstream
   flights and 741 passengers." It reproduces the ~45% reactionary-delay share
   the industry sees, from first principles — a built-in validity check.

3. **Turnaround-risk board.** Per aircraft, how tight the ground time is versus
   the minimum turnaround — Boeing's own turnaround-optimisation use case, on
   the ALG schedule.

This is what makes the Air Algérie conversation concrete rather than "we could
help." It also shows the engine generalises from parcels to passengers — one
platform, multiple verticals.

**The honest line for this module too:** we don't have Air Algérie's live
rotation feed or delay log, so those are modelled. The *computations* are the
real ones — deploying on their AODB/FIDS feed is a data-connection, not a
rebuild. And we will **not** claim Boeing-style sensor predictive maintenance;
we don't have the telemetry, and faking it fails diligence.

## 7. Go to market

**Beachhead: private e-commerce delivery operators.** Not Air Algérie.

The earlier version of this project pitched Air Algérie as the customer. It's
the wrong first customer for a startup: state-owned, procured through public
tender, multi-year sales cycle. It stays on the roadmap as a credibility anchor
— it is not something to build a three-year plan on.

Delivery operators are the opposite: privately owned, fast-moving, already
running digital order systems we can integrate with, and with a direct,
countable line from a mis-staffed shift to a failed COD delivery.

**Sequence:** 2–3 unpaid pilots in Algiers and Oran to replace our assumptions
with measured throughput → published case study with real numbers → paid
rollout across each operator's branch network (a multi-site expansion, not a
one-off sale) → adjacent verticals → Maghreb.

## 8. Funding context

- **Algerian Startup Fund** — 2.4bn DZD with six public banks, 100+ startups
  funded from 350+ applications. A realistic first cheque.
- **Label Startup** — 4 years' exemption from IBS, TAP and founder income tax,
  plus 0% VAT on imported equipment. Materially extends runway.
- **Algérie Télécom's 1.5bn DZD (~$11M) fund** targets AI specifically — this
  qualifies.
- Partech, Orange Ventures and Flat6Labs completed ~8 Algerian deals in
  2024–25, so a follow-on has precedent.

## 9. What we'd do with a first cheque

1. **Three paid pilots.** Replace every assumption in `core/sources.py` with
   measured values from real operations. This is the single highest-value
   thing we can do.
2. **Bring onboarding cost to near zero.** Today it's engineer-weeks per
   customer to ingest history and fit productivity constants. That number
   decides whether this scales.
3. **Sync the calendar to the official announcement.** Ramadan and Eid dates
   are set by the Commission Nationale d'Observation du Croissant Lunaire; our
   local calendar is accurate to within a day or two and flags the days where
   that ambiguity bites.
4. **Second vertical.** Retail distribution — the same engine, and it shows the
   sharpest Ramadan response of anything we modelled (1.68× ordinary volume).

## 10. The questions we expect, and our answers

**"Your savings number is from simulated data."**
Correct, and we say so before you ask. The method is out-of-sample and the
harness transfers unchanged to real data. Give us a pilot and we'll replace the
number.

**"Why won't Yalidine just build this in-house?"**
They might. But the calendar engine is the hard part, it's reusable across
their competitors, and their engineering priority is network coverage, not
labour optimisation. If they build it, that validates the category — and we're
already selling to the other 400 branches.

**"Why is your LTV:CAC 13×?"**
Because the churn assumption is generous and unevidenced. Treat it as a
placeholder until there's cohort data. We flag it in the app.

**"Is a $5M TAM investable?"**
Not on its own. Algeria is the beachhead and the proof. The regional case is
the investable one.

**"Is the AI real, or is it a chatbot with a dashboard around it?"**
Two models are trained by us and both report their accuracy on data they never
saw. The demand forecaster is backtested walk-forward against a generic
international model. The digit reader in the document-control screen trains at
startup on a public dataset of real handwritten digits and prints its held-out
accuracy on screen, alongside a list of what it cannot do. Everything else is
either planning maths, Algerian statute, or a hosted language model that
narrates figures our engine computed. We keep those four categories separate on
purpose.

**"Do you detect forged documents?"**
No, and the reason matters more than the answer. We built the standard detector
(error-level analysis, noise inconsistency), measured it, and found it labelled
clean payslips as retouched while failing to separate clean from spliced. We
removed it. What we kept is opposable: what the file's metadata declares, and
the amounts checked against the SNMG and the CNAS rate. A fraud detector that
accuses an honest document costs a customer more than no detector at all.

---

## Running it

```bash
streamlit run dashboard.py
```

See `README.md` for setup. `SOURCES.md` lists every external number and every
assumption.
