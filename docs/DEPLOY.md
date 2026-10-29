# Ship it: public link in ~3 minutes

The fastest way to get a shareable link you can paste into outreach emails is
**Streamlit Community Cloud** (free, no card).

## Deploy

1. Go to **https://share.streamlit.io** and sign in with the GitHub account that
   owns the repo (Anya-Louni). When asked, grant access to **private** repos -
   the repo can stay private, Streamlit still builds it.
2. Click **New app** -> **Deploy from GitHub**.
3. Fill in:
   - Repository: `Anya-Louni/AI-Forge`
   - Branch: `main`
   - Main file path: `dashboard.py`
4. Click **Deploy**. The first load runs the walk-forward backtest and fetches
   real weather (about 1 to 2 minutes); after that everything is cached and
   instant.

You now have a URL like `https://ai-forge-xxxx.streamlit.app`.

### Repo private, app shareable

Repo visibility and app visibility are two different settings:

- **Repo** (your code): keep it **private**. Deployment still works.
- **App** (who can open the link): after deploy, in **Settings -> Sharing** choose
  either **public by link** (anyone with the URL, best for pasting into cold
  emails, nothing is indexed) or **restricted to specific emails** (only invited
  prospects, but they must sign in). For outreach, public-by-link is the low-
  friction choice.

## Turn on the AI copilots (optional)

The owned models (forecasting, roster, inspection, Journal Officiel watch,
retention, anomaly detection, CV matching) all work with no key. To enable the
natural-language layer (decision copilot, plain-language answers, the
inspector's report, the retention script), add the Groq key in the app's
**Settings -> Secrets**:

```
GROQ_API_KEY = "gsk_..."        # free, no card - console.groq.com
```

Never commit this key to the repo. It lives only in the Streamlit Cloud Secrets
panel (deployed) or in a gitignored .streamlit/secrets.toml (local). Everything
else keeps working without it.

## Tailored demo links (industry mode)

The same app tailors itself per prospect from a query parameter. Send each
company the link that speaks their language - it sets their vertical, tailors the
copy, and hides the modules that do not apply:

| Prospect | Link |
|---|---|
| E-commerce / delivery | `https://<your-url>/?industry=delivery` |
| Hotel | `https://<your-url>/?industry=hotel` |
| Transport / fleet | `https://<your-url>/?industry=transport` |
| Retail / distribution | `https://<your-url>/?industry=retail` |
| Airport / ground ops | `https://<your-url>/?industry=airport` |
| Full platform (all) | `https://<your-url>/` |

Replace `<your-url>` with the Streamlit URL from the deploy step.

## Offline / unreliable-wifi demos

Open the app once with a connection so the caches fill, then in the top bar under
**Data source** turn off **Allow live API calls**. The whole app then runs from
`data/cache/`, which is handy for a pitch on venue wifi.
