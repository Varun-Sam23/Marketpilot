# MarketPilot V1

A free, Chromebook-friendly market intelligence dashboard.

## What it does

- Builds a pre-market report from previous-session data and overnight news.
- Displays NIFTY, BANK NIFTY, SENSEX, India VIX and global cues.
- Tracks a starter watchlist.
- Refreshes live snapshots every 60 seconds while the dashboard is open.
- Does not connect to a broker and cannot place orders.
- Stores the morning report in `data/latest.json`.

## Free deployment

Recommended: GitHub + Streamlit Community Cloud.

1. Create a GitHub repository named `marketpilot`.
2. Upload all files from this folder.
3. Make the repository public if you want to use GitHub Actions without consuming private-repo minutes.
4. In Streamlit Community Cloud, create a new app from the repository and select `app.py`.
5. The app will receive a `streamlit.app` URL that works in Chrome on a Chromebook.
6. In GitHub Actions, run the "MarketPilot pre-market report" workflow manually once to test it.
7. The scheduled workflow runs at 09:00 IST on weekdays. Extend `engine.py` with exchange-calendar checks before relying on it for holiday skipping.

## Important free-data limitation

Free/public market feeds are not guaranteed exchange-grade real-time feeds and may be delayed or temporarily unavailable. The dashboard displays source-derived information and should not be treated as a live trading terminal.

## Optional AI layer

V1 uses deterministic analysis so it works with no paid API. A future version can add a free-tier Gemini API key for richer natural-language reasoning. Keep API keys in Streamlit/GitHub secrets, never in source code.

## Next upgrades

- NSE holiday calendar check
- Better pre-market/opening-gap logic
- FII/DII data
- Options/OI and PCR
- Sector heatmap
- Per-stock technical setup
- News impact scoring
- Morning thesis vs. end-of-day outcome tracking
- Optional Gemini reasoning layer
