# How the AI works (in plain words)

This is the honest, simple explanation of every "AI" piece in WorkForce.dz, so
anyone on the team can answer a jury or a customer without hand-waving.

There is no single magic model. "AI" here is **four different things**, and it
helps to keep them separate:

1. A **forecasting model** (machine learning) that predicts how busy each day/shift will be.
2. An **optimiser** (planning math) that turns that forecast into the cheapest legal roster.
3. Small **prediction models** for HR (who might quit, ranking CVs).
4. A **language model assistant** (a chatbot) we *call*, not one we built.

Below, each one, what data it uses, and what "training" actually means for it.

---

## The most important honesty point

We do **not** own a real Algerian company's historical sales/orders ledger,
because no such data is public. So the day-to-day **volumes are simulated** but
they are driven by **real signals**: the real Algerian calendar (including the
Hijri/Muslim calendar, Ramadan and the two Aids), the real Friday-Saturday
weekend, real paydays, and **real weather** pulled from a public weather API.

So the *shape* of demand the model learns (busy before Aid, quiet on the rest
day, summer diaspora peak, weather effects) is real. Only the exact counts are
synthetic. On a paying customer we retrain on their real numbers and the method
is identical. The app says this on every page. Never hide it, it is a strength:
it means our results are not a rigged number.

---

## 1. The demand forecast (the main machine-learning part)

**The job:** given a future date, predict how many orders (or passengers) to
expect, per shift.

**What "training" means here:** we show the model thousands of past days. For
each past day it sees the *inputs* (below) and the *actual* volume, and it
slowly learns the relationship "these conditions -> roughly this many orders".
In code this is literally one line: `model.fit(X, y)` where `X` is the table of
inputs and `y` is the actual volumes. It runs on a normal laptop in seconds. No
GPU, no giant dataset, no month of training.

**The inputs (called "features") the model looks at:**
- Day of week, and whether it is the Algerian weekend (Friday/Saturday).
- Month and season.
- Where we are on the **Hijri calendar**: which Hijri month, how many days until
  Ramadan, how many days until/after each Aid.
- Public holidays.
- **Real weather**: temperature and rain over the coming days.
- Payday proximity (people order more right after payday).
- The recent trend (the last few days' volumes, so it knows the current level).

**The model itself:** a *gradient-boosted decision tree*
(`HistGradientBoostingRegressor` from the scikit-learn library). Simple picture:
it builds many tiny "yes/no" decision trees one after another, and each new tree
focuses on fixing the mistakes of the ones before it. Add them all up and you
get a good predictor. We chose it because it is accurate, fast, and handles this
kind of mixed calendar+weather data well.

**How we test it honestly (walk-forward):** we never let the model see the
future. We train it on, say, the first 12 months, ask it to predict the next
block, write down the error, then slide the window forward and repeat. This is
called a *walk-forward backtest*, and it mimics how it would really run in
production. The numbers we quote (about **50% less error**, **6-8% labour cost
saved**) come from these *out-of-sample* tests, not from the data it trained on.

**Two accuracy fixes worth knowing (in case someone asks):**
- We predict on a log scale and correct it back with a factor (*Duan smearing*)
  so the totals are not biased too low or too high.
- We feed the recent level in as a feature ("lag anchor") so the model stays
  glued to reality instead of drifting.

**Why it is defensible:** we compare our forecast against (a) the **same
algorithm with the Algerian calendar features removed** (this stands in for a
generic international tool) and (b) naive baselines like "same as last week". The
improvement is the *value of knowing Algeria*. We also **show the weeks where we
lose** to the baseline, on purpose, so it is clearly not cherry-picked.

Run it yourself: `python -m core.forecast` (backtest) and `python -m core.pipeline`
(the full out-of-sample money comparison).

---

## 2. The roster optimiser (planning, not machine learning)

**The job:** now that we know how many people we need per shift, decide exactly
who works when, for the **lowest cost that still obeys the law**.

This is not machine learning, it is **linear programming** (using
`scipy.optimize.linprog`). Think of it as a very fast, exact "what is the cheapest
combination" solver:
- **Decisions:** how many of each role on each shift.
- **Goal:** minimise total labour cost, using the **real Algerian cost rates**.
- **Rules it must respect:** cover the forecasted demand, stay under the overtime
  cap, give the weekly rest day, meet minimum staffing.

The solver returns the cheapest schedule that breaks no rule. This is the
"decision AI": the forecast says *how much work*, the optimiser says *who covers
it and for how much*.

Run it: it is exercised in `core/staffing.py` and inside `core/pipeline.py`.

---

## 3. The labour-cost engine (real law, no AI)

Not AI at all, but it is what makes everything credible. It encodes the actual
Algerian statute: the minimum wage (SNMG), the social charges (CNAS, 26% employer
+ 9% employee), and income tax (IRG brackets). From these it derives the exact
legal hourly floor of **138.46 DZD/hour**. It is plain arithmetic, so it is
exact and checkable. Run: `python -m core.labour_dz`.

---

## 4. The HR prediction models

**Attrition ("who might quit"):** a *logistic regression* - one of the simplest,
most transparent models there is. It takes inputs like tenure, pay versus the
market, lateness, contract type and leave patterns, and outputs a quit-risk
percentage plus the top reasons. We are honest that it is **illustrative**: it is
not trained on a real company's resignation records (we do not have those). On a
pilot we refit it on the customer's own history and it becomes real.

**CV screening:** see the language-model section, plus a deterministic scoring
step. The AI reads the CV; our own code does the scoring, so the ranking is
transparent and explainable.

---

## 5. The language-model assistant (the chatbot / CV reader)

This is the part people usually mean by "AI" today, and it is important to be
clear: **we did not train a language model.** That costs millions and is not what
we do. Instead we **call a ready-made hosted model through its API**, the same way
an app calls a payment or maps service.

- It uses **Groq** (Llama 3.3, free tier, no card) as the natural-language layer.
- With no key at all, it falls back to simple rules so nothing crashes.
- The language model is only the thin translation/narration layer. The real
  intelligence is the owned models (forecast, roster optimiser, attrition,
  anomaly detection, CV matching), which run locally with no key.
  (All of this lives in `core/ai.py`.)

**How we use it (this is the clever part, not the model itself):**
- **CV screener:** we send the CV text with a strict instruction: "pull out these
  Algeria-specific fields (formation LMD, service national, langues, wilaya,
  permis, experience) and return them as clean data." The model does the
  *reading and understanding*; our code does the *scoring and ranking*.
- **HR copilot / Ops assistant:** we hand the model the current real numbers
  (the roster, the payslips, the labour-law facts) as context, then let it answer
  questions in plain French or English. Because it is "grounded" on our own data,
  it answers from the facts instead of making things up.

So our value in this part is not the model, it is: the Algeria-specific prompts,
the structured extraction, the grounding on real law, and the free-fallback
plumbing.

---

## One-paragraph version (for a pitch)

"We forecast demand with a gradient-boosted model trained on the real Algerian
calendar, the Friday-Saturday weekend and real weather, and we prove it out of
sample against a generic tool (about half the error). A linear-programming
optimiser turns that forecast into the cheapest roster that still respects the
Algerian labour code. On top, smaller transparent models flag who might quit and
rank CVs, and a hosted language model powers a plain-language HR assistant and CV
reader. The operational volumes in the demo are simulated on real signals and we
say so, because on a customer we retrain on their real data and the method is
unchanged."

---

## How to reproduce / verify (copy-paste)

```bash
python -m core.calendar_dz     # Hijri calendar round-trip + weekend check
python -m core.labour_dz       # derives the 138.46 DZD/h legal floor
python -m core.forecast        # walk-forward backtest vs baselines
python -m core.pipeline        # end-to-end saving, out of sample
```

Each core module self-checks when run this way, so you can show a skeptic the
numbers being produced live.

---

## New AI features (v2)

Three additions that lean harder on AI, each grounded on the deterministic engine
so nothing is hallucinated.

**Inspection simulator (`core/inspector.py`).** A dry run of the labour
inspection. It runs the rule-based compliance checks (real facts: overtime cap,
CDD over 24 months, pay below SNMG, coverage, leave), attaches to each an
article, an indicative fine band and a catch-likelihood, then an LLM writes the
inspector's report and the cheapest fix order. The findings are code; only the
narrative is AI. Fine bands are labelled indicative, not legal advice.

**Journal Officiel watch (`core/regwatch.py`).** Keeps a register of the labour
and payroll rules we enforce, checks whether the live configuration still matches
the current legal value, and lets you simulate a rule change (for example a new
SNMG) to see exactly who is affected and what it costs across the real workforce,
with an AI-drafted compliance notice. In the demo the register is a curated
summary; in production it is fed by automatic ingestion of the Journal Officiel.

**Retention negotiator (`core/retention.py`).** For a flight-risk employee it
takes each retention lever (raise, CDD to CDI, overdue leave, attendance
conversation, onboarding), runs a counterfactual through the same attrition model
(change the driver the lever targets, re-score the risk), and turns the drop in
risk into money saved. The best net-value lever wins, and an LLM writes the
manager's one-to-one script. The model-based counterfactual is the real method;
the money figures are directional until the model is re-fit on a pilot.

**Odoo (`core/odoo_bridge.py`).** Reads employees and contracts from a live Odoo
over its XML-RPC API and maps them into our model, so all of the above runs on a
customer's existing Odoo data. See [ODOO.md](ODOO.md).
