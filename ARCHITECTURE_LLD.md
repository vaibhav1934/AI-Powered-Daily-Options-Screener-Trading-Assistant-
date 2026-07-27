# StockGlass AI — Low-Level Design (LLD) & End-to-End Workflows

This document provides a comprehensive Low-Level Design (LLD) and workflow guide for **StockGlass AI**, detailing the architecture, data flows, factor engine mechanics, AI synthesis pipeline, and real-time streaming protocols.

---

## 1. Executive Summary & System Architecture

StockGlass AI is a screening-grade trading assistant built on a **10-Layer / 50-Factor Evaluation Engine**, real-time **Finnhub market data integration**, an **AI Synthesis & Compliance Layer**, and **Server-Side Paper Trading**. To ensure institutional reliability and compliance, the system operates under two strict global rules:
1. **Zero Mock / Fallback Data:** If live market data or database scans are unavailable, endpoints return error states (`503/404`) or empty structures (`[]` / `0.0`) rather than generating simulated numbers.
2. **Zero Buy/Sell Advisory Language:** All user-facing explanations synthesized by the LLM must pass a strict rules-based compliance filter that prohibits direct trading advice.

### High-Level System Architecture

```mermaid
graph TB
    subgraph External [External Services & Data Sources]
        FH[Finnhub API<br>Live Quotes & News]
        PG[(Supabase PostgreSQL<br>Scans, Logs, Positions)]
        LLM[LLM Provider<br>Anthropic Sonnet / Gemini Pro]
    end

    subgraph Backend [FastAPI Backend Engine /v1]
        API[Central API Router<br>/v1/stocks, /v1/positions, /v1/indices]
        WS[WebSocket Engine<br>/v1/stream & /v1/ws]
        SCAN[Scan Service & Cron<br>Daily Pipeline Engine]
        SYN[AI Synthesis Service<br>LLM Call + Compliance Filter]
        PAPER[Paper Trading Service<br>Server-Side P&L Engine]
        FENG[Factor Engine Registry<br>10 Layers / 50 Factors F1-F50]
    end

    subgraph Frontend [Next.js 15 / React 19 Client]
        UI[Screener Table & Watchlist]
        MODAL[Stock Detail & Factor Breakdown Modal]
        PORT[Paper Trading & Portfolio UI]
    end

    UI <-->|HTTP REST JSON| API
    MODAL <-->|HTTP REST JSON| API
    PORT <-->|HTTP REST JSON| API
    UI <-->|WebSocket wss:// 5s Throttle| WS

    API --> SCAN
    API --> SYN
    API --> PAPER
    WS -->|Batch Quote Fetch| FH
    SCAN -->|Market Data & Candles| FH
    SCAN <-->|Persist Scans & FactorLogs| PG
    SCAN --> FENG
    SYN -->|Fetch News| FH
    SYN <-->|Synthesis Call| LLM
    PAPER <-->|Live Price Validation| FH
    PAPER <-->|Persist Positions| PG
```

---

## 2. End-to-End Workflow Sequence Diagrams

### Workflow 1: Daily Screener Pipeline & Factor Evaluation Engine
This workflow executes daily (via cron or on-demand scan trigger) to evaluate tickers against the 50-factor framework.

```mermaid
sequenceDiagram
    autonumber
    actor Cron as Cron Scheduler / Admin
    participant Scan as Scan Service (`scan_service.py`)
    participant FH as Finnhub Client (`finnhub.py`)
    participant Reg as Factor Registry (`registry.py`)
    participant Engine as Factor Layers 1-10 (`f1_to_f50`)
    participant DB as PostgreSQL (`DailyScan` & `FactorLog`)

    Cron->>Scan: Trigger Daily Scan (e.g., date=2026-07-26)
    Scan->>FH: Fetch Universe Candles, Quotes & Earnings Calendar
    FH-->>Scan: Return Market Data Batch
    
    loop For each Ticker in Universe
        Scan->>Reg: Initialize ScanContext(ticker, price, earnings, ...)
        Scan->>Engine: Evaluate Layers 1 to 10 (F1 through F50)
        Engine-->>Scan: Return 50 FactorResults (triggered, vetoed, detail, metadata)
        
        Note over Scan,Engine: Veto Protocol: If any Named Rule (F40-F50) returns vetoed=True,<br>setup is flagged and hardFlags are populated.
        
        Scan->>Scan: Compute Overall Score (1.0 to 10.0) & Assign Risk Bucket
        Scan->>DB: INSERT INTO daily_scans (ticker, score, risk_bucket, veto_reason)
        Scan->>DB: INSERT INTO factor_logs (factor_id, triggered, vetoed, result_detail_json)
    end
    
    DB-->>Scan: Commit Transaction
    Scan-->>Cron: Return Scan Completion Audit Log
```

---

### Workflow 1B: Screener Pagination & Universe Supplementation (`GET /v1/stocks`)
When the frontend dashboard requests screener setups, the backend combines evaluated DailyScan results with the full 10,419-stock database universe (`StockUniverse`), applying server-side pagination (`page`, `pageSize`) and exact filtering.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Next.js Screener Table UI
    participant API as StockGlass Router (`stockglass.py`)
    participant Svc as StockGlass Service (`stockglass_service.py`)
    participant DB as PostgreSQL (`DailyScan` & `StockUniverse`)

    Client->>API: GET /v1/stocks?list=all&page=1&pageSize=10&q=
    API->>Svc: get_stock_list(page=1, page_size=10, filters...)
    Svc->>DB: SELECT * FROM daily_scans WHERE scan_date >= today ORDER BY score DESC
    DB-->>Svc: Return Scanned Results (Evaluated Setups)
    
    alt If no strict evaluation filters (direction, earnings, risk_bucket)
        Svc->>DB: SELECT * FROM stocks WHERE is_active=True AND match(sector, query)
        DB-->>Svc: Return Matching Universe Tickers
        Svc->>Svc: Merge & Deduplicate (Scanned first, then Universe with baseline score 5.0)
    end

    Svc->>Svc: Calculate Total Count & Slice Page (start_idx to end_idx)
    Svc-->>API: Return StockListResponseSchema(count=10, total=5210, page=1, total_pages=521, results)
    API-->>Client: HTTP 200 JSON (Paginated Table Rows & Footer Metadata)
```

---

### Workflow 2: On-Demand Stock Detail & AI Synthesis Pipeline (`GET /v1/stocks/{symbol}`)
When a user selects a ticker, the backend synthesizes real-time news and deterministic factor logs into compliant natural language copy.

```mermaid
sequenceDiagram
    autonumber
    actor User as Frontend Client UI
    participant API as StockGlass Router (`stockglass.py`)
    participant Svc as StockGlass Service (`stockglass_service.py`)
    participant DB as PostgreSQL (`DailyScan` & `FactorLog`)
    participant FH as Finnhub Client (`finnhub.py`)
    participant Syn as Synthesis Service (`synthesis_service.py`)
    participant LLM as LLM Client (Anthropic / Gemini)

    User->>API: GET /v1/stocks/NVDA
    API->>Svc: get_stock_detail("NVDA")
    
    par Parallel Data Fetch
        Svc->>DB: SELECT latest scan & factor_logs for NVDA
        Svc->>FH: Fetch live real-time quote (price, chg, pct)
        Svc->>FH: Fetch company news (last 7 days)
        alt If sector is 'Unknown' or 'US Equities'
            Svc->>FH: Fetch company profile (get_company_profile)
            FH-->>Svc: Return real sector (e.g. 'Semiconductors' or 'Technology') & name
            Svc->>DB: UPDATE stocks SET sector=real_sector, name=real_name WHERE ticker='NVDA'
        end
    end
    
    DB-->>Svc: Return DailyScan + 50 FactorLogs + StockUniverse Enrichment
    FH-->>Svc: Return Live Quote + News Headlines + Profile
    
    Svc->>Syn: synthesize_reasons("NVDA", score, factor_logs, news)
    Syn->>Syn: Filter active factors (triggered or vetoed)
    Syn->>LLM: Complete System Prompt (Compliance Rules) + User Prompt (Score, Factors, News)
    LLM-->>Syn: Return Raw JSON String `[{"type":"bull","code":"F44","text":"..."}]`
    
    loop For each synthesized reason text
        Syn->>Syn: check_compliance(text) -> Scan regex for "buy", "sell", "target price", "recommend"
        alt Compliance Check Passed
            Syn->>Syn: Keep AI-generated informational explanation
        else Compliance Violation Detected / LLM Offline
            Syn->>Syn: Fallback to safe deterministic factor description (Zero mock data)
        end
    end
    
    Syn-->>Svc: Return List[ReasonItem]
    Svc-->>API: Return StockDetailSchema (Drop-in v1 Contract)
    API-->>User: HTTP 200 JSON Response
    User->>User: Synchronize live quote (price, chg, pct) & enriched sector into active Screener Table row
```

---

### Workflow 2B: On-Demand Live Factor Evaluation & Same-Day Caching (`GET /v1/stocks/{symbol}/live`)
To prevent unnecessary re-execution of heavy EDGAR SEC lookups and Finnhub API calls when a user views a stock multiple times in the same day, the system implements a **Same-Day Database Caching Protocol**.

```mermaid
sequenceDiagram
    autonumber
    actor User as Frontend Client UI
    participant API as StockGlass Router (`stockglass.py`)
    participant Svc as StockGlass Service (`stockglass_service.py`)
    participant DB as PostgreSQL (`DailyScan` & `StockUniverse`)
    participant EDGAR as SEC EDGAR Client (`F46EDGARShelfCheck`)

    User->>API: GET /v1/stocks/NVDA
    API->>Svc: get_stock_detail("NVDA") -> checks cache & evaluates on-demand if needed
    Svc->>DB: SELECT * FROM daily_scans WHERE ticker='NVDA' AND scan_date=today
    
    alt Same-Day Cache Hit (live_evaluated_at == today)
        Note over Svc,DB: Factor evaluation already completed today.<br>Skip EDGAR & Finnhub calls.
        DB-->>Svc: Return Cached DailyScan & FactorLogs
        Svc-->>API: Return StockDetailSchema (Instant Response)
    else Cache Miss (live_evaluated_at is NULL or older date)
        Note over Svc,EDGAR: On-demand live factor evaluation triggered.
        Svc->>DB: SELECT * FROM stocks WHERE symbol='NVDA'
        DB-->>Svc: Return StockUniverse (cik='0001045810')
        Svc->>EDGAR: F46EDGARShelfCheck.evaluate(ctx) -> Fetch live SEC submissions
        EDGAR-->>Svc: Return FactorResult (status='live', action='VETO', detail='...')
        Svc->>DB: UPDATE daily_scans SET live_evaluated_at=now(), factor_results_json=...
        Svc->>DB: UPDATE factor_logs SET triggered=..., vetoed=..., result_detail_json=...
        DB-->>Svc: Commit Transaction
        Svc-->>API: Return Updated StockDetailSchema
    end
    API-->>User: HTTP 200 JSON Response
```

---

### Workflow 3: Real-Time WebSocket Quote Streaming (`/v1/stream` & `/v1/ws`)
Delivers screening-grade live quote updates throttled at 5-second intervals without generating fake data if feeds disconnect.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Frontend Screener / Watchlist UI
    participant WS as WebSocket Router (`/v1/stream`)
    participant Task as Async Background Task (`send_quote_updates`)
    participant FH as Finnhub Client (`finnhub.py`)

    Client->>WS: Connect wss://api.stockglass.ai/v1/stream?symbols=NVDA,AVGO&token=<jwt>
    WS->>WS: Validate Authentication Token & Scopes
    WS->>WS: Add NVDA, AVGO to `subscribed_symbols` pool
    WS-->>Client: Accept WebSocket Connection (HTTP 101 Switching Protocols)
    
    Note over Client,WS: Client can also send dynamic JSON messages:<br>`{"type": "subscribe", "symbols": ["HOOD"]}`
    
    loop Every 5 Seconds (Section 6/7 Throttle Rule)
        Task->>Task: Check if `subscribed_symbols` is non-empty
        Task->>FH: get_quotes_batch(["NVDA", "AVGO", "HOOD"])
        
        alt Live Quotes Successfully Fetched (price > 0)
            FH-->>Task: Return List[StockQuote]
            Task->>Client: Send Flat JSON `{"symbol":"NVDA", "price":178.55, "ts":"2026-07-26T10:25:00Z"}`
        else Finnhub Unavailable / API Rate Limited
            FH-->>Task: Raise Exception or Return 0.0
            Task->>Task: Log warning & Suppress output (Zero Mock Fallback Enforced)
        end
    end
    
    Client->>WS: Disconnect / Close Window
    WS->>Task: Cancel Background Sender Task & Clean Pool
```

---

### Workflow 4: Server-Side Paper Trading Execution (`POST /v1/positions` & `GET /v1/positions`)
Prevents client-side win-rate drift by forcing all execution prices and P&L calculations to be validated server-side against live quotes.

```mermaid
sequenceDiagram
    autonumber
    actor Trader as Frontend Portfolio UI
    participant API as Portfolio Router (`portfolio.py`)
    participant Svc as Paper Trading Service (`paper_trading_service.py`)
    participant FH as Finnhub Client (`finnhub.py`)
    participant DB as PostgreSQL (`Position` table)

    Trader->>API: POST /v1/positions `{"symbol":"NVDA", "qty":10, "entryPrice":178.42}`
    API->>Svc: create_position(data)
    Svc->>DB: INSERT INTO positions (symbol, qty, entry_price, status='open', opened_at=NOW())
    DB-->>Svc: Return Position (id='pos_8f2a1')
    Svc-->>API: Return HTTP 201 PositionItemSchema
    API-->>Trader: UI confirms open position
    
    Note over Trader,API: User views active positions tab
    
    Trader->>API: GET /v1/positions?status=open
    API->>Svc: get_positions(status_filter="open")
    Svc->>DB: SELECT * FROM positions WHERE status = 'open'
    DB-->>Svc: Return List[Position]
    
    Svc->>FH: get_quotes_batch(["NVDA", ...]) (Fetch live market prices)
    FH-->>Svc: Return Live Quotes (e.g., NVDA current_price = 181.10)
    
    loop For each open position
        Svc->>Svc: Calculate server-side unrealizedPnl = (current_price - entry_price) * qty
        Svc->>Svc: Populate `currentPrice` and `unrealizedPnl` fields
    end
    
    Svc-->>API: Return PositionListResponseSchema
    API-->>Trader: UI renders live profit/loss without mock drift
```

---

## 3. The 10-Layer / 50-Factor Evaluation Engine

The factor evaluation engine evaluates 50 technical, fundamental, macro, and sentiment conditions grouped into 10 logical layers. Each layer contains 5 factors.

### Standing Checks vs. Named Error-Correction Rules
* **Standing Factors (F1–F39):** Represent foundational market structure checks (e.g., moving average stacks, volume momentum, sector breadth). Currently implemented as clean, unconfigured stubs returning `neutral` status until customized.
* **Named Rules / Error-Correction Log (F40–F50):** Hardcoded institutional trading rules derived from historical trading mistakes. These are fully live, executable implementations that actively evaluate market conditions and enforce hard constraints.

### The Veto Protocol
Named rules act as circuit breakers. When a risk rule triggers a **Veto Action** (e.g., F47 detecting an earnings announcement within 5 days of entry), the system immediately:
1. Sets `vetoed = True` on the `FactorLog`.
2. Appends the rule name to the stock's `hardFlags` array in the API response.
3. Restricts the setup from being classified as a clean actionable buy, regardless of how high the overall numeric score (1.0–10.0) is.

### Factor & Layer Allocation Matrix

| Layer # | Layer Name | Factor IDs | Description | Live Named Rules in Layer |
| :---: | :--- | :---: | :--- | :--- |
| **L1** | **Price Action** | F01 – F05 | Trend structure, MA stacks, breakout confirmation | — *(Standing checks)* |
| **L2** | **Volume / Flow** | F06 – F10 | Relative volume, institutional accumulation, VWAP | — *(Standing checks)* |
| **L3** | **Volatility** | F11 – F15 | ATR expansion, Bollinger band squeeze, IV rank | **F49** (BOJ/KOSPI Rule)<br>**F50** (War Tape Rule) |
| **L4** | **Earnings Calendar** | F16 – F20 | Proximity to reporting dates, historical surprise rates | **F48** (Gap-Hold Protocol) |
| **L5** | **Analyst / Sentiment** | F21 – F25 | Rating consensus, target revisions, short interest | **F43** (ATH Record Earnings)<br>**F47** (Pre-Earnings Binary Exit) |
| **L6** | **Macro / Rates** | F26 – F30 | Treasury yield correlation, Fed policy headwinds | **F46** (EDGAR Shelf Check) |
| **L7** | **Sector Rotation** | F31 – F35 | Industry relative strength, capital flow leadership | **F42** (Entry Cutoff)<br>**F45** (FOMC Reduction) |
| **L8** | **News / Catalyst** | F36 – F40 | SEC filings, press release sentiment, catalyst velocity | **F41** (Bear Case First)<br>**F44** (Analyst Tier Weighting) |
| **L9** | **Risk Rules** | F41 – F45 | Position sizing gates, liquidity floors, stop constraints | **F40** (No Clean Setup) |
| **L10** | **Position Fit** | F46 – F50 | Portfolio correlation, margin impact, account exposure | — *(Standing checks)* |

> [!NOTE]
> **Layer Boundary Mapping:** As permitted by the Section 0 specification note, internal engine numbering assigns named rules (F40–F50) to their functional domain layers (e.g., F47 in Layer 5 "Binary/Earnings", F49/F50 in Layer 3 "Macro/Vol"). When assembling REST API responses, `stockglass_service.py` sorts and maps all factors into the exact 10 layer groupings expected by the frontend contract.

---

## 4. Data Models & Database Schema (LLD Layer)

The backend uses **SQLAlchemy 2.0 (Async)** with PostgreSQL / Supabase, mapped directly onto Pydantic v1 contract schemas.

### Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    STOCK_UNIVERSE ||--o{ DAILY_SCANS : "1-to-many (ticker)"
    DAILY_SCANS ||--o{ FACTOR_LOGS : "1-to-many (scan_id)"
    
    STOCK_UNIVERSE {
        string symbol PK
        string company_name
        string exchange
        string cik
        string sector
        string industry
        datetime created_at
        datetime updated_at
    }

    DAILY_SCANS {
        int id PK
        string ticker FK
        date scan_date
        float score
        string risk_bucket
        string veto_reason
        date live_evaluated_at
        jsonb factor_results_json
        datetime created_at
    }
    
    FACTOR_LOGS {
        int id PK
        int scan_id FK
        string factor_id
        string factor_name
        int layer_number
        bool triggered
        bool vetoed
        bool stubbed
        jsonb result_detail_json
    }
    
    POSITIONS {
        string id PK
        string symbol
        float qty
        float entry_price
        float exit_price
        string status
        datetime opened_at
        datetime closed_at
    }
    
    WATCHLIST_ITEMS {
        int id PK
        string ticker
        string custom_label
        datetime added_at
    }
```

### The Same-Day Database Caching Protocol (`live_evaluated_at`)
To optimize API latency and rate-limit consumption for heavy institutional checks (such as SEC EDGAR F46 dilution checks):
1. **Initial Seed & Morning Scan:** Tickers are loaded from `stocks` (StockUniverse) and scanned daily. During the initial morning batch scan, `live_evaluated_at` is set to `NULL` for on-demand factors.
2. **First User View (Cache Miss):** When `GET /v1/stocks/{symbol}/live` is invoked, the service checks if `live_evaluated_at` matches today's UTC date. If not, it executes real-time EDGAR lookups using the CIK from `stocks`, updates `FactorLog` records, and sets `live_evaluated_at = today`.
3. **Subsequent Views (Cache Hit):** Any subsequent requests for the same ticker on the same day detect `live_evaluated_at == today` and immediately return the cached factor evaluations without external API calls.

### Runtime Detail JSONB (`result_detail_json`)
To support rich hover tooltips in the frontend factor modal without hardcoding static strings, `FactorLog` stores a JSONB blob containing runtime metrics evaluated during the scan:
```json
{
  "factor_id": "F47",
  "factor_name": "Pre-Earnings Binary Exit",
  "layer_number": 5,
  "status": "live",
  "triggered": true,
  "vetoed": true,
  "detail": "NVDA has earnings within the holding window (3 days until Q2 report). Framework rule: exit before binary event — no holding through earnings.",
  "metadata": {
    "earnings_within_window": true,
    "days_until_earnings": 3,
    "rule": "No holding through earnings"
  }
}
```
When `GET /v1/stocks/{symbol}/factors` is called, `stockglass_service.py` extracts the `detail` string from this blob, ensuring user explanations reflect exact market conditions at the time of the scan.

---

## 5. Security, Compliance & Resilience Protocols

### 1. Strict Zero-Fallback / Zero-Mock Data Policy
To guarantee that traders never make decisions based on artificial data, all service layers enforce strict fallback prohibitions:
* **REST API Endpoints:** If Supabase database queries fail or return empty sets, endpoints return `[]` (empty list) or `0.0`. No random scores or simulated tickers are generated.
* **Live Price Calculations:** In paper trading (`GET /v1/positions`), if Finnhub fails to return a live quote for an open symbol, `currentPrice` falls back to `entry_price` with `unrealizedPnl = 0.0` and logs an error, rather than inventing a price.
* **WebSocket Streaming:** In `/v1/stream`, if market data batch queries fail or rate limits are hit, the background task suppresses emission for that cycle rather than sending synthetic numbers.

### 2. Rules-Based AI Compliance Filter
The AI Synthesis Agent (`synthesis_service.py`) is restricted to informational scoring commentary. Before any LLM output is delivered to the frontend, it passes through `check_compliance(text)`:
```python
FORBIDDEN_ADVISORY_PATTERNS = [
    r"\bbuy\b", r"\bsell\b", r"\bstrong buy\b", r"\bstrong sell\b",
    r"\btarget price\b", r"\brecommend(ation|ed|ing)?\b",
    r"\binvest(ment|ing|ors)?\b", r"\btake position\b", r"\benter (long|short)\b",
]
```
* **Pass:** *"Setup structure is supported by positive volume accumulation and upward MA alignment."*
* **Rejection:** *"Strong buy recommended before earnings with a target price of $150."* -> **Action:** The system discards the LLM text and substitutes a safe, deterministic rule description from the factor database log.

### 3. Database Resilience & Connection Sizing
* **Global 503 Exception Handler:** In `app/main.py`, SQLAlchemy operational errors and database disconnects are intercepted globally, returning a clean `503 Service Unavailable` JSON response with code `DATABASE_UNAVAILABLE` rather than crashing or leaking stack traces.
* **Connection Pooling:** Configured in `app/db/session.py` with `pool_size=5`, `max_overflow=10`, and `pool_pre_ping=True` to handle transient network drops gracefully in serverless/cloud environments.

### 4. Streamlined Scan Status Lifecycle & Immediate Execution Accessibility
To provide a frictionless user experience for institutional traders and eliminate unnecessary speed bumps (FR-7 / FR-16 streamlining):
* **Auto-Confirmation of Valid Scans:** Any stock that successfully passes the 50-factor deterministic evaluation without triggering a mandatory veto rule initializes directly in `CONFIRMED` status (rather than requiring a manual TradingView screenshot upload to transition from `PENDING_CONFIRMATION`).
* **Immediate Execution Details:** Because valid setups initialize as `CONFIRMED`, execution details (`entry_price`, `strike_price`, `stop_loss`) are immediately accessible to the user in the UI dashboard and authorized for explanation by the AI Assistant in the chat panel.
* **Veto / Cutoff Locking:** If a setup triggers an active veto rule (e.g., F40 No Clean Setup or F46 Dilution) or is evaluated after the institutional entry cutoff time, its status is strictly set to `LOCKED`, withholding execution details and preventing actionable trades.

### 5. Complete AI Context Injection & Automated Options Contract Selection
To ensure institutional-grade explanations and strict compliance with the Zero-Mock Data policy:
* **Automated Options Contract Selector (`options_service.py`):** In strict adherence to the prohibition against simulated data, strike prices are never calculated using arbitrary percentage multipliers (e.g., flat 5% OTM heuristics). `options_service.py` integrates with `yfinance` to automatically query real exchange option chains and select institutional Call/Put contracts matching target Delta (~0.30 to 0.45) and expiration windows (30–45 DTE). When a live options chain feed is unavailable, `strike_price` evaluates to `NULL` (`None`) and renders as `"N/A - Requires Live Options Chain Feed"`.
* **Local Vectorized Technical Indicator Engine (`technicals.py`):** Technical indicators (RSI, SMA 50/200) are computed locally using vectorized `pandas`/`numpy` math on daily OHLCV bars fetched via `yfinance` and Finnhub, eliminating external indicator rate limits while ensuring precision and reproducibility.

### 6. AI News Catalyst Synthesis & Zero-Mock News Policy
To provide traders with institutional clarity on market narratives without risking simulated or advisory content:
* **Concurrent Catalyst Synthesis:** When a user opens the Stock Detail view (`GET /v1/stocks/{symbol}`), the backend concurrently executes `synthesize_reasons` (for score bullets) and `synthesize_news_summary` (for full narrative summary) via `asyncio.gather`.
* **Institutional Catalyst Summary:** `synthesize_news_summary` feeds up to 5 recent news articles (headlines, summaries, sources) from Finnhub directly to the LLM to generate an objective, 2-sentence institutional summary of the market narrative, fundamental catalyst, or macroeconomic impact. `NewsItemSchema` explicitly includes `summary: Optional[str]` to guarantee end-to-end data integrity.
* **Strict Compliance & Zero-Mock Fallback:** All generated summaries must pass `check_compliance(text)`. If an article feed is empty, the LLM is offline, or compliance rejects the text, `newsSummary` evaluates to `null` (`None`) without generating simulated summaries or mock market stories. The UI displays an italicized notification or hides the box cleanly.


