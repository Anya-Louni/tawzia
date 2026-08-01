# WorkForce.dz

**Shift-labour intelligence for Algerian operations.**

Forecast Algerian demand properly — on the real Algerian calendar and real
weather — and turn it into a legal, cost-optimal shift roster.

> **The pitch, the market sizing and the honest caveats are in
> [`PITCH.md`](PITCH.md). Every number's provenance is in
> [`SOURCES.md`](SOURCES.md).**

---

## Why this exists

Global workforce-management tools are built for a Gregorian, Saturday–Sunday,
temperate market. In Algeria they are structurally wrong: the weekend is
**Friday–Saturday**, the two largest demand events (Ramadan and the Aïds) move
~11 days earlier each year on the **Hijri calendar**, and summer is the
**diaspora-return peak**, not a lull. WorkForce.dz builds those in as
first-class features — and the app measures how much that's worth against the
same algorithm without them.

## What's in the app

| Page | What it shows |
|---|---|
| **Command centre** | The forecast, the recommended roster, its cost, and what's driving the next few weeks. |
| **Demand forecast** | The forecast with prediction intervals, by shift, with the real weather over the horizon and a plain-language reason for each day. |
| **Roster & cost** | The full schedule, crew mix, and the labour-cost stack derived from Algerian statute. |
| **Airport ops AI** | The aviation module for Air Algérie / Aéroport d'Alger: passenger-flow forecast → terminal staffing, a **delay-cascade predictor** (names the one flight to protect to break a cascade), and a turnaround-risk board. Built on the real ALG network. |
| **Evidence** | Walk-forward backtest vs a generic international model and naive baselines; the out-of-sample money comparison; feature importance. **The credibility page.** |
| **Algerian calendar** | Why a foreign tool mis-forecasts here — the weekend, the moving year, the seasonal drivers — with a live check against the reference calendar. |
| **Business case** | Bottom-up market sizing and unit economics, with pricing derived from the measured saving. |
| **Sources & assumptions** | Every external number and every assumption, cited. |
| **Ops assistant** | Plain-language Q&A over the current plan (needs a free Groq key). |

> **Operational volumes are simulated** — no real Algerian operator's ledger is
> public. The calendar and weather they respond to are real. The app says so on
> every page.

---

## Setup

### 1. Prerequisites
- **Python 3.10+** — check with `python --version`

### 2. Virtual environment + dependencies

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

**Mac / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

> If PowerShell blocks activation: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`, then retry.

### 3. Run

```bash
streamlit run dashboard.py
```

Opens at `http://localhost:8501`. The first load fetches real weather and runs
a backtest (~1–2 min); after that everything is cached and instant. No API key
is needed for any page except the Ops assistant.

### 4. (Optional) Ops assistant

The assistant uses [Groq](https://console.groq.com) (free tier, no card).
Create a `.env` in the project root:

```
GROQ_API_KEY=gsk_your_key_here
```

`.env` is gitignored. Every other page works without it.

### Offline / unreliable-wifi demos

Open the app once with a connection so the caches populate, then toggle **Data
source → Allow live API calls** off in the sidebar. The whole app runs from
`data/cache/`.

---

## Project structure

```
.
├── dashboard.py              # Entry point — st.navigation over the pages
├── app_pages/                # One file per page
│   ├── command_centre.py
│   ├── forecast_view.py
│   ├── roster_view.py
│   ├── airport_ops.py        # Aviation module (Air Algérie / ALG)
│   ├── evidence.py
│   ├── calendar_view.py
│   ├── business_case.py
│   ├── sources_view.py
│   └── assistant.py
├── core/                     # The engine (each module self-tests via __main__)
│   ├── sources.py            # Single registry of every cited number + assumption
│   ├── calendar_dz.py        # Hijri conversion, Algerian holidays, seasonal drivers
│   ├── weather_dz.py         # Open-Meteo per wilaya (+ offline fallback)
│   ├── macro_dz.py           # World Bank Algeria indicators
│   ├── labour_dz.py          # SNMG/CNAS labour cost stack, roles, shifts
│   ├── demand.py             # Simulated volumes on the real calendar + weather
│   ├── forecast.py           # Walk-forward backtest, gradient-boosted forecaster
│   ├── staffing.py           # LP roster optimiser + fair baseline comparison
│   ├── pipeline.py           # End-to-end out-of-sample evidence run
│   ├── aviation.py           # ALG flight network + rotation-aware schedule
│   ├── delay_cascade.py      # Delay-propagation model + keystone attribution
│   ├── pax_flow.py           # Passenger flow → terminal staffing
│   ├── market.py             # Sizing, pricing, unit economics
│   └── appdata.py            # Cached loaders + shared UI shared by the pages
├── PITCH.md                  # Investor/jury narrative
├── SOURCES.md                # Provenance of every number
├── data/cache/               # API responses cached here (gitignored)
└── .streamlit/config.toml    # Theme
```

### Verifying the engine

Each core module runs its own self-check:

```bash
python -m core.calendar_dz     # Hijri round-trip + weekend check
python -m core.labour_dz       # cost stack (derives 138.46 DZD/h floor)
python -m core.forecast        # walk-forward backtest vs baselines
python -m core.pipeline        # end-to-end saving, out of sample
```

---

## Troubleshooting

**First load is slow.** It's fetching real weather and running a 30+ origin
backtest. Cached afterwards — subsequent loads are instant.

**`ModuleNotFoundError`.** The venv isn't active, or deps aren't installed. See
Setup step 2.

**Ops assistant warns about `GROQ_API_KEY`.** Expected without a key — every
other page works. See Setup step 4.

**Port 8501 in use.** `streamlit run dashboard.py --server.port 8502`

**A weather/macro value shows "offline fallback".** The live API was
unreachable and nothing was cached yet. Connect once and reload.
