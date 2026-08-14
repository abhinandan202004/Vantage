# Stock Screener — Backend MVP

A screener.in-style app that scores stocks on two **independent** axes —
Technical (10 chart-based conditions) and Fundamental (10 business-quality
conditions) — matching the checklist you designed.

## What's working right now (tested in this session)

- ✅ FastAPI app boots, `/health` responds, OpenAPI docs at `/docs`
- ✅ SQLAlchemy models for stocks, OHLCV, fundamentals, shareholding, scores
  — schema verified to create cleanly
- ✅ Technical indicator engine (EMA20/50/200, RSI14, ADX14, volume ratio,
  naive resistance detection, consolidation detection) — verified against
  synthetic OHLCV data
- ✅ Technical scoring (10 conditions → 0-100 score + per-condition breakdown)
  — verified end-to-end
- ✅ Fundamental scoring (10 conditions → 0-100 score + breakdown) — verified
  end-to-end with sample data
- ✅ **Smart Money scoring** (`app/scoring/smart_money_score.py`) — a THIRD,
  independent axis from the Smart Money Trail checklist. Unlike the flat
  10-points-per-condition Technical/Fundamental scores, this one is
  **weighted** (FII Increasing 15, Promoter Buying 15, DII/Mutual Fund/
  Delivery Volume/Relative Strength/Breakout/Earnings Growth 10 each,
  ROCE/Low Debt 5 each — matching the poster's weight table), and comes
  with an interpretation label per the score bands (85-100 "Strong
  institutional accumulation" down to <50 "Limited evidence"). Verified
  end-to-end across a strong-signal case, a mixed/partial-data case, and
  an all-unknown edge case.
- ✅ `/stock/{symbol}/ohlcv` and `/stock/{symbol}/score` endpoints wired up
  — the score endpoint now returns `technical`, `fundamental`, AND
  `smart_money` sections together, verified with a mocked end-to-end
  request through FastAPI's TestClient

## What's stubbed / needs your machine to verify

I can't reach Yahoo Finance, NSE, or BSE from this sandbox (network is
locked down to package registries only), so the following are
**code-complete but untested against live data**:

- `app/data_ingestion/yfinance_client.py` — OHLCV fetch via yfinance
- `app/data_ingestion/nse_client.py` — quote + shareholding via nsepython
- `app/data_ingestion/bhavcopy.py` — BSE bhavcopy download. **Double-check
  the URL pattern** (`BHAVCOPY_URL_TEMPLATE`) against BSE's current bhavcopy
  page before relying on it — exchanges change these URLs without notice
  and I couldn't verify it live.
- The `/stock/{symbol}/score` endpoint's fundamental side currently passes
  an empty dict — real fundamentals need a DB-backed ingestion job (pull
  from NSE/bhavcopy/paid API → populate `fundamentals` + `shareholding`
  tables → query in the route) which isn't built yet.
- Sector-relative-strength scoring needs a stock→sector-index mapping
  table populated (the `Stock.sector_index_symbol` column exists but
  nothing populates it yet).
- Smart Money score: 8 of 10 factors are currently `None` (undetermined)
  in the live endpoint — only `breakout_with_volume` and
  `strong_relative_strength` are wired up today, reusing signals already
  computed on the technical side. The rest need:
  - `fii_increasing` / `dii_increasing` / `promoter_buying` — a query over
    2-4 consecutive `shareholding` rows per stock (schema already supports
    this, no migration needed — just needs the ingestion job to populate
    `Shareholding` rows first, then a trend-detection function)
  - `mutual_fund_buying` — needs a new data source (monthly MF portfolio
    disclosures aren't covered by NSE/yfinance/bhavcopy; likely needs AMFI
    data or a paid provider)
  - `high_delivery_volume` — needs NSE's delivery-percentage field (available
    via `nse_client.py`'s quote endpoint, not yet parsed out)
  - `earnings_growth` / `roce_above_20` / `low_debt` — same fundamentals
    ingestion job as the Fundamental score depends on

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with your local Postgres credentials

# create a Postgres DB first (via psql or a GUI), then:
python -m scripts.init_db

# run the API
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive API docs.

Quick manual test of the data layer (once you have network access to
Yahoo/NSE from your machine):
```bash
python -m app.data_ingestion.yfinance_client RELIANCE
python -m app.data_ingestion.nse_client RELIANCE
python -m app.data_ingestion.bhavcopy 2026-07-29
```

## Project layout

```
backend/
  app/
    main.py                 # FastAPI app + CORS
    config.py                # settings (DB url, defaults)
    db.py                     # SQLAlchemy engine/session
    schemas.py                # Pydantic response models
    models/tables.py          # ORM models: Stock, OHLCV, Fundamental, Shareholding, Score
    data_ingestion/
      yfinance_client.py       # OHLCV via Yahoo Finance
      nse_client.py             # quotes + shareholding via NSE public endpoints
      bhavcopy.py                # BSE daily bulk file downloader
    indicators/
      technical.py              # EMA/RSI/ADX/volume/resistance/consolidation calcs
    scoring/
      technical_score.py         # 10-condition technical score
      fundamental_score.py       # 10-condition fundamental score
      smart_money_score.py       # weighted 10-factor smart money score
    routers/
      stock.py                    # /stock/{symbol}/ohlcv, /stock/{symbol}/score
  scripts/
    init_db.py                    # creates all tables
```

## Next steps (not built yet)

1. **Fundamentals ingestion job** — nightly/quarterly script pulling from
   NSE/paid API into the `fundamentals` + `shareholding` tables, so
   `/stock/{symbol}/score` can compute a real fundamental score instead
   of an empty one.
2. **Sector index mapping** — populate `Stock.sector_index_symbol` for
   each stock (e.g. RELIANCE → NIFTY ENERGY) so the "sector outperforming
   Nifty" condition can be scored.
3. **Frontend** — React + TypeScript, `lightweight-charts` for the
   candlestick view, TanStack Table for financial statement grids
   (Quarterly Results, P&L, Balance Sheet, Cash Flow, Ratios, Shareholding),
   and a peer-comparison table.
4. **Scheduled scoring** — APScheduler job to compute + persist scores
   for your whole watchlist nightly, instead of computing on each request.
