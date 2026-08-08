# Sources & assumptions

Every externally-sourced number in WorkForce.dz, and every modelling
assumption, in one place. The app renders the same information on its
**Sources & assumptions** page, pulled from the single registry in
[`core/sources.py`](core/sources.py).

The rule: a figure is either **measured** (published, cited), **live**
(fetched at runtime from a public API), or an **assumption** (our modelling
choice, labelled as one). Nothing is dressed up as more certain than it is.

---

## What is real, and what is simulated

| Layer | Status |
|---|---|
| **Algerian calendar** (Ramadan, the two Aïds, Yennayer, gazetted holidays, Friday–Saturday weekend) | **Real.** Computed locally from the tabular Islamic calendar; round-trip verified over 60 Hijri years; key dates cross-checked live against api.aladhan.com. |
| **Weather** (temperature, rainfall, heat stress per wilaya) | **Real.** ERA5 reanalysis archive + operational forecast, via Open-Meteo. |
| **Macroeconomics** (population, labour force, CPI, unemployment) | **Real.** World Bank Open Data, fetched live. |
| **Labour costs** (SNMG, CNAS, statutory premiums/caps) | **Real.** Derived from published Algerian rates and the labour code. |
| **Operational volumes** (parcels/passengers/cases per shift) | **Simulated.** No real Algerian operator's ledger is public. The volumes are synthetic; the calendar and weather they respond to are real. |
| **Company staff & attendance** (the new AI features run on this) | **Real when imported.** A company uploads its own staff/attendance CSV (page "Données de l'entreprise"); everything then reads its real figures. Without an import, a clearly-labelled demo is used. Source is always shown on-screen. |
| **CV/poste matching** (appariement) | **Real, local.** TF-IDF embeddings (word + char n-grams, scikit-learn) computed on-device — no key, offline, reproducible. |
| **Payroll/attendance anomalies** | **Real.** Cited Algerian rules (SNMG/IRG/CNAS) + an unsupervised IsolationForest fitted on the company's own data. |
| **KPI, scenario simulator, decision copilot** | **Real derivations.** Aggregations of the above on the real SNMG+CNAS+IRG stack. The copilot's language layer (Groq) only narrates the locally-computed figures; it invents no numbers. |
| **Recruitment channel directory** (sourcing) | **Real institutions.** USTHB, ESI, ENP, ESC Alger, the regional universities, the CFPA/INSFP network, ANEM, Emploitic and the rest exist and are verifiable. Their **volumes, costs and lead times are assumptions** (see below): no Algerian operator publishes its cost per hire. |
| **Partner and influencer lists** | **Not generated.** The app returns partner *profiles* with verifiable selection criteria, never names. A language model asked to "find influencers" invents plausible false ones, which is the worst possible output in front of someone who knows the local scene. |
| **Digit-reading model** (document check) | **Trained on real data.** The UCI/NIST *Optical Recognition of Handwritten Digits* set, 1797 digits written by 43 real people, a quarter held out. Printed digits are added to training and are **rendered by us** from the server's fonts; the two accuracies are reported separately and recomputed at every start. |
| **Forgery / tampering detection** | **Not shipped.** Implemented with error-level analysis and noise inconsistency, then measured: it flagged clean payslips as retouched and did not separate clean from spliced. Removed. Only file metadata (a fact) and a human-read ELA image remain. |
| **Skills reference and employee skill profiles** | **Modelling choice.** The per-role skill requirements are ours and are the first thing a customer replaces with their own grid. Demo profiles are derived deterministically from the synthetic workforce; in deployment they come from the annual review or the imported HR file. |
| **Savings figure** | **Out-of-sample, on simulated volumes.** Validates the method, not the market magnitude. |

---

## Live data APIs (no key required)

| Source | Used for | Endpoint |
|---|---|---|
| **Open-Meteo** | Real daily weather per wilaya — ERA5 archive (observed history) and operational forecast | `archive-api.open-meteo.com`, `api.open-meteo.com` |
| **World Bank Open Data** | Algeria population, labour force, CPI inflation, unemployment | `api.worldbank.org/v2/country/DZA` |
| **Aladhan** | Cross-check of the local Hijri calendar on Ramadan/Aïd dates | `api.aladhan.com/v1/gToH` |

All responses cache to `data/cache/` on first fetch, so the app runs fully
offline afterwards. Turn off "Autoriser les appels API en direct" under
**Données** in the top bar to force cache-only mode.

---

## Cited measurements

### Labour & cost
| Figure | Value | Source |
|---|---|---|
| SNMG (minimum wage) | 24,000 DZD/month | Conseil des ministres / APS — in force Jan 2026 |
| Legal monthly hours | 173.33 h | Algerian labour code (40h week) |
| CNAS employer contribution | 26% of gross | CNAS schedule |
| CNAS employee contribution | 9% of gross | CNAS schedule |
| Derived statutory hourly floor | **138.46 DZD/h** | Computed — reproduces the officially published figure exactly |

### Market
| Figure | Value | Source |
|---|---|---|
| Algerian e-commerce market | ~$2bn/year | EasySell market analysis |
| COD share of orders | ~95% | EasySell / dz-ecom |
| COD return rate (MENA) | ~19% | dz-ecom carrier benchmark |
| Largest carrier network | 160+ branches, all 58 wilayas | Yalidine |
| Port demurrage (congestion) | $5,000/day/vessel | Recovery Advisers market alert |
| Vessel wait, Port of Algiers | >7 days | GoComet port monitoring |

### Startup / funding
| Figure | Value | Source |
|---|---|---|
| Algerian Startup Fund capital | 2.4bn DZD | asf.dz |
| Startup-label tax exemption | 4 years (IBS/TAP/IRG) + 0% VAT on equipment | startup.dz |

Full URLs are in [`core/sources.py`](core/sources.py) and on the app's Sources page.

---

## Assumptions (replace these in a pilot)

These are modelling choices, not findings. A pilot customer replaces each with
a measured value from their own operation on day one.

| Assumption | Value | Why it's an assumption |
|---|---|---|
| Parcels sorted per worker per hour | 45 | Depends on the site's process and equipment — the first thing a pilot measures. The whole cost model scales off it, so it's a slider in the app. |
| Overtime premium | +50% | Statutory floor; a given collective agreement may sit above it. |
| Temp-agency markup | +35% | Varies by wilaya and by how late the request is made. |
| Understaffing penalty multiple | 2.4× | The cost of an uncovered hour vs a covered one, capturing the failed COD delivery, the return leg and lost customer value. The single most challengeable number — exposed as a slider. |
| Applicants needed per hire | 8 | Funnel ratio used to size a sourcing campaign. Varies hugely by channel and role; the first number a pilot replaces with a measured one. |
| Share of applicants shortlisted | 22% | Combined with each channel's own quality to give expected hires per campaign. The per-channel volumes, costs and lead times in the directory are the same kind of framing estimate. |
| Direct training cost per person-day | 3,500 DZD | Trainer amortised plus materials, excluding the trainee's own wage. Drives the training plan and the train-or-recruit arbitrage. A customer grid or a CFPA agreement replaces it. |
| External recruitment cost | 45,000 DZD | Sourcing and selection, excluding salary and excluding the two-month ramp-up counted separately. Used as the comparison term against internal mobility. |

---

## What was removed from the earlier prototype

- **A rigged baseline** — the old comparison charged only the "naive" strategy
  a 1.3× rush surcharge. Both strategies now face identical cost and penalty
  structures.
- **Circular validation** — the old model was trained and scored on the same
  fixed-seed formula. Now: walk-forward backtest against held-out periods,
  with unforecastable shocks left in.
- **The wrong weekend** — the original weekly pattern treated Saturday/Sunday
  as the low days. Algeria's weekend is Friday–Saturday.
- **Invented labour costs** — "3,000 DZD/shift" with no derivation, replaced by
  a build-up from SNMG and the CNAS schedule.
- **A decorative flight board** — a synthetic feed that drove nothing.
