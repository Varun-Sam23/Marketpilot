# MarketPilot

A free, Chromebook-friendly Indian-market intelligence command center.

## Design

MarketPilot is built around a simple workflow:

**Before the market opens** → build evidence from previous sessions + global cues + overnight news → generate a structured AI thesis.

**During market hours** → refresh market snapshots and live news while the dashboard is open.

**After the market** → preserve the morning thesis in a journal so future versions can score thesis vs. outcome.

## Dashboard

### Morning Intelligence
- AI bias and market regime
- Confidence
- Bull / Base / Bear cases
- Key levels and invalidation
- Drivers and risks
- Technical snapshot
- Sector pulse
- Overnight / pre-market headlines

### Live Market
- NIFTY 50, BANK NIFTY, SENSEX, India VIX
- Watchlist
- Live-news feed
- 60-second refresh while the browser tab is open

### Performance
- Morning thesis journal
- Date, rule bias, AI bias, regime and confidence
- Outcome scoring is planned for the next iteration

## Automation

GitHub Actions prepares the morning report on weekdays around 09:00 IST. The engine checks the NSE trading calendar and produces a `MARKET CLOSED` report on weekends or NSE holidays.

The repository stores the latest report in `data/latest.json` and the morning thesis history in `data/history.json`.

## AI

The AI layer uses Google's stable `gemini-2.5-flash` model when `GEMINI_API_KEY` is available. The key must be stored as a GitHub Actions secret, never in source code.

## Free-data caveat

Free/public market feeds are useful for research but are not guaranteed exchange-grade or tick-by-tick. Data can be delayed, incomplete, rate-limited or temporarily unavailable. MarketPilot is decision support only and never places orders.

## Planned upgrades

- FII/DII activity
- NIFTY and BANK NIFTY option-chain/OI analysis
- PCR and major strike levels
- richer sector/index coverage
- opening-range and VWAP analysis
- end-of-day thesis evaluator
- historical accuracy and calibration
- configurable watchlists and alerts
