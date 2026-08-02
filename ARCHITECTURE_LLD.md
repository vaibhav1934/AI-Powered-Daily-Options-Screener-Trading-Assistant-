# StockGlass AI — Low-Level Design (LLD) & End-to-End Workflows

This document provides a comprehensive Low-Level Design (LLD) and workflow guide for **StockGlass AI**, detailing the architecture, data flows, factor engine mechanics, AI synthesis pipeline, and real-time streaming protocols.

---

## 1. Executive Summary & System Architecture

StockGlass AI is a screening-grade trading assistant built on a **10-Layer / 50-Factor Evaluation Engine**, real-time **Finnhub market data integration**, an **AI Synthesis & Compliance Layer**, and **Server-Side Paper Trading**. To ensure institutional reliability and compliance, the system operates under two strict global rules:
1. **Zero Mock / Fallback Data:** If live market data or database scans are unavailable, endpoints return error states (`503/404`) or empty structures (`[]` / `0.0`) rather than generating simulated numbers.
2. **Zero Buy/Sell Advisory Language:** All user-facing explanations synthesized by the LLM must pass a strict rules-based compliance filter that prohibits direct trading advice.

### Implementation Update (2026-08-02): Missing Factor Inputs Wired

The scan pipeline now forwards the following previously-missing fields directly into `ScanContext` for factor evaluation:
1. **Earnings fields** (`eps_estimate`, `eps_actual`, `revenue_estimate`, `revenue_actual`, `is_after_hours_beat`) from Finnhub earnings calendar entries.
2. **Earnings window field** (`earnings_within_window`) computed from report date proximity (`0..5` days).
3. **Gap structure fields** (`gap_present`, `gap_hold_valid`) computed from live daily bars (today open vs previous close) plus current-price hold validation.
4. **Analyst action fields** (`analyst_rating_change`, `analyst_firm_tier`) from Finnhub upgrade/downgrade actions with conservative tier classification.
5. **EDGAR filing fields** (`near_ath_proximity`, `edgar_check_status`, `has_recent_shelf_filing`, `shelf_filing_date`, `shelf_form_type`) now enriched during main batch scan for near-ATH names instead of only lazy detail evaluation.
6. **Ecosystem proxy field** (`ecosystem_partner_10pct_move`) now populated from same-sector +10% mover cohort detection in the active scan set.

Residual limitation:
1. Ecosystem relationship quality remains a free-data proxy (sector-cohort based) and is not yet a true supply-chain graph.

### Implementation Update (2026-08-02): Full 50-Factor Audit JSON Export

The stock detail click workflow now supports a full audit export for every evaluated ticker:
1. New endpoint `GET /v1/stocks/{symbol}/factor-audit` returns factor-by-factor runtime evidence for `F1` through `F50`.
2. Endpoint contract parameters:
    - `forceLive` (boolean): if `true`, backend re-runs on-demand live evaluation before export.
    - `requireAllLive` (boolean): if `true`, backend returns `409` when any factor is non-live/stubbed; if `false`, payload includes `liveValidation.nonLiveFactors`.
3. Payload sections:
    - `scanApiCalls`: live provider call list and output snapshots used by the run.
    - `scanInputs`: normalized runtime input context used by the factor engine.
    - `factors[]`: layer mapping (`layer`, `layerRange`), factor identity (`factorCode`, `factorName`), and final decision block (`status`, `triggered`, `vetoed`, `action`, `evaluationStatus`, `stubbed`, `detail`, `metadata`).
4. Frontend download gating via environment key:
    - `NEXT_PUBLIC_DOWNLOAD_OUTPUT=true` enables browser auto-download of the audit JSON on stock click.
    - Missing/invalid values default to disabled (`false`).
5. Validation/error behavior:
    - `503` when live evaluation cannot be completed.
    - `404` when no scan data exists for the symbol.
    - `409` when `requireAllLive=true` and one or more factors are not in `LIVE` status.

### Implementation Update (2026-08-02): Production API URL + Portfolio Auth Guardrails

Frontend runtime configuration and auth handling were tightened to prevent silent production failures:
1. `NEXT_PUBLIC_API_URL` is now mandatory in production runtime. The frontend no longer silently defaults to localhost in production when the key is missing.
2. Missing production API URL now surfaces an explicit configuration error message to the UI call sites instead of returning ambiguous empty lists/404s.
3. Home dashboard portfolio summary calls are auth-gated: portfolio fetches are skipped when the user is not logged in, returning a clear `Login required for portfolio analytics` state.
4. Error diagnostics were expanded for:
    - `/v1/stocks/dual-horizon`
    - `/v1/portfolio/score`
    - `/v1/portfolio/optimize`
    with explicit differentiation for `401/403` authentication issues versus `404` endpoint/base-URL mismatches.
5. Auth client (`/v1/auth/login`, `/v1/auth/register`, `/v1/auth/refresh`, `/v1/auth/me`) now enforces configured API base URL in production using the same runtime guard as data APIs; auth requests no longer silently fall back to relative frontend paths.
6. Portfolio UI cards now propagate fetch failures consistently across score, weakest-components, and optimizer-actions panels, avoiding false empty-state messaging when backend/API connectivity fails.

### Implementation Update (2026-08-02): Portfolio DB Outage Transparency + Position Entry Availability

Portfolio and paper-trading UX behavior was tightened for runtime outages where backend routes are healthy but database connectivity is down:
1. Portfolio client calls now parse backend JSON error payloads and surface explicit DB outage messages when backend returns `Database connection failed` semantics (for `/v1/portfolio/score`, `/v1/portfolio/optimize`, `/v1/positions`, and `POST /v1/positions`).
2. The portfolio overview no longer hides the `Open Paper Position` form when score fetch fails; users can still see and interact with the position-entry workflow while receiving truthful backend error messages.
3. Position mutation/read failures now return operation-specific UI errors (`cannot create/load/close positions until DB connectivity is restored`) instead of a generic fetch failure string.
4. Operational dependency made explicit: paper trading is fully backend-persisted and requires healthy Postgres DNS/network connectivity at runtime.
5. Backend DB engine now applies Supabase-pooler-safe defaults when host matches `*.pooler.supabase.com`: effective SQLAlchemy pool is capped (`pool_size<=5`, `max_overflow=0`) and SSL is enforced via connect args, reducing `EMAXCONNSESSION` session-limit failures during portfolio operations.
6. Portfolio page now auto-refreshes authenticated workspace data every 15 seconds while the browser tab is visible, enabling near-live paper-trading score/P&L/positions updates without requiring manual refresh.
7. Paper-trading entry workflow moved to screener-first UX: users open positions directly from screener stock rows (`+ Paper`) using live row price and selected quantity; portfolio overview now serves analytics/status context rather than manual symbol/price entry.
8. Backend exception responses now explicitly attach localhost CORS headers for handled error paths (`AppError`, DB connectivity errors, generic 500), preventing browser-side false `No Access-Control-Allow-Origin` blocks when upstream errors occur.
9. Finnhub analyst action endpoint (`/stock/upgrade-downgrade`) now treats HTTP `401/403` as provider-tier unavailability and degrades to empty analyst-action signal instead of noisy hard-failure propagation.
10. Backend lifecycle now disposes SQLAlchemy engine on shutdown, and Supabase pooler defaults are capped to low-concurrency mode (`pool_size<=3`, `max_overflow=0`, `ssl=require`) to reduce `EMAXCONNSESSION` pressure.
11. Asyncpg PgBouncer compatibility: for Supabase pooler hosts, backend runtime and Alembic migration engine disable async prepared statement cache (`statement_cache_size=0`) to prevent `DuplicatePreparedStatementError` in transaction-pool mode.

### Implementation Update (2026-08-02): Option Contract Paper Trading Support

Paper trading position creation was updated to support both underlying stocks and specific Option Contracts:
1. **Option contract symbol formatting:** The Detail Panel execution card now formats OCC-compliant option symbols (e.g. `NVDA250117C00150000`) for AI target strikes (Call/Put at ~35 DTE).
2. **Dual-button execution:** Detail Panel surfaces both `+ Paper Stock` (underlying stock at live price) and `+ Paper Option` (option contract at target strike price).
3. **Portfolio Greeks integration:** When an OCC-formatted option position is created, the backend `portfolio_management_service` parses the symbol root, expiration, call/put type, and strike, automatically computing Black-Scholes **Delta**, **Theta**, and **Vega** for Component 5 (*Options Greek Exposure*) of the Portfolio Score.

### Multi-User Privacy Isolation (JWT-Scoped)

StockGlass AI now enforces user-scoped privacy boundaries for portfolio and chat data paths:
1. **Portfolio isolation:** All paper-trading positions and derived portfolio analytics are scoped by authenticated user identity (`users.id`).
2. **Chat isolation:** GenAI conversation memory is namespaced by authenticated user identity and conversation id, preventing cross-user history leakage.
3. **JWT-required privacy routes:** Privacy-sensitive routes (`/v1/positions*`, `/v1/portfolio/score`, `/v1/portfolio/optimize`, `/v1/chat*`) require bearer-authenticated users and do not permit API-key-only access.
4. **Legacy unowned positions:** Pre-migration rows without ownership are excluded from user-scoped reads and do not appear in any authenticated user's portfolio views.

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

---

## 10. Agentic AI Architecture — Chat Agent & Autonomous Scan Triggering

### Overview
StockGlass AI uses a **Single-Node Agentic Architecture** built natively on the Anthropic/Gemini SDK (no LangChain, no CrewAI). The Chat Agent operates on a **ReAct (Reason + Act) loop**: it receives a user query, decides if it needs live data, autonomously triggers Python Tool functions, reads the results, and formulates the final response.

### Agent Tools (Function Calling)
The agent (`app/agents/chat_agent.py`) has access to the following tools:

| Tool | Purpose |
|---|---|
| `get_scan_results` | Fetch today's scanned tickers from DB filtered by status / risk bucket |
| `explain_ticker` | Deep-explain why a ticker was ranked or vetoed by specific framework rules |
| `apply_ui_filter` | Apply real-time filter on the screener table (e.g., "show only LOW risk") |
| `trigger_scan` | **Autonomously trigger the full 50-factor / 10-layer scan for today** |

### Proactive Scan Trigger Behaviour
When the agent detects that today's scan dataset is **empty** (`scan_empty=True`):
1. The agent proactively informs the user: *"No scan data found for today. Would you like me to trigger the full 50-factor scan now?"*
2. The agent **never** triggers the scan automatically — it always asks for explicit user confirmation first.
3. When the user confirms (e.g., *"yes", "run it", "go ahead"*), the agent calls `trigger_scan(confirmed=True)`.
4. The agent streams real-time feedback: ⚙️ starting → ✅ complete with ticker counts.
5. The user is instructed to refresh the screener table to see the newly populated results.

### Why No Automatic Scheduler?
The backend is hosted on **Hugging Face Spaces free tier (CPU basic)**, which sleeps after ~15 minutes of inactivity. An internal `APScheduler` set to 6:30 AM CST would be unreliable because the Space will likely be sleeping at that time. The Agentic "on-demand with confirmation" model is the correct, reliable solution for free-tier cloud deployments.

### GenAI Components
| Component | File | Model | Purpose |
|---|---|---|---|
| Chat Agent Orchestrator | `app/agents/chat_agent.py` | Gemini / Claude | ReAct loop, tool calling, streaming responses |
| News Synthesis Agent | `app/services/synthesis_service.py` | Gemini / Claude | Unstructured news → structured Bull/Bear bullets |
| Vision AI Options Extractor | `app/api/screenshots.py` | Gemini Vision / Claude Vision | Screenshot → structured options chain JSON |

---

## 11. Deployment Architecture

### Cloud Stack
| Layer | Platform | Notes |
|---|---|---|
| **Backend** | Hugging Face Spaces (CPU Basic) | Dockerized FastAPI on port 7860, public access required |
| **Frontend** | Vercel (Next.js) | Edge-deployed; `NEXT_PUBLIC_API_URL` env var must be set to HF URL |
| **Database** | Supabase (PostgreSQL) | `DATABASE_URL` secret set in HF Spaces Variables |

### Critical Deployment Notes
* **HF Space must be PUBLIC:** The frontend (Vercel) makes direct browser `fetch()` calls to the HF backend. If the Space is Private, HF intercepts all unauthenticated requests and returns an HTML 404 page, breaking the API.
* **API_SECRET_KEY must be set in HF Secrets:** The frontend sends `X-API-Key: dev_key` on every request. The backend validates this against `API_SECRET_KEY` from environment. If missing, the backend falls back to `"change-me-in-production"` which causes 401 errors.
* **Trailing newlines in HF secrets:** Pasting secrets manually in the HF UI often appends `\n`. The `DATABASE_URL` field validator in `config.py` strips these automatically using `@field_validator`.
* **`/chat` POST trailing slash:** FastAPI's trailing-slash redirect (307) on `POST /chat/` converts POST to GET, breaking the SSE stream. Both `@router.post("")` and `@router.post("/")` are registered to prevent this.
* **Multi-user auth model:** The app now supports public self-registration via `POST /v1/auth/register`, followed by JWT access/refresh token usage for authenticated app access. Existing API-key access remains available as a compatibility/admin path.
* **Versioned API namespace:** All production REST endpoints are exposed under `/v1/...` only.
    Root fallback aliases (such as `/stocks`, `/chat`, `/watchlist`, `/debug`, `/auth`) are intentionally disabled to enforce a single stable contract.
* **CORS:** `allow_origin_regex` covers `*.vercel.app` and `*.hf.space` wildcard domains, plus local development origins `http://localhost(:port)` and `http://127.0.0.1(:port)`.
* **Long-term fundamentals sourcing:** The long-term dual-horizon model now merges SEC EDGAR Company Facts (`/api/xbrl/companyfacts/CIK...json`) with market-data fundamentals. Accounting fields (including `interest_coverage`) are filled from SEC XBRL when market provider fields are null, while valuation fields (`trailing_pe`, `forward_pe`, `peg_ratio`) remain market-provider sourced.
* **Pre-scoring market-cap gate:** Candidate eligibility now enforces `market_cap_usd >= 1,000,000,000` before entering the 50-factor / 10-layer engine. This gate is applied in both batch scan ingestion and on-demand single-ticker evaluation paths. Inputs support numeric caps and `T/B/M` suffixed strings via deterministic parsing, and filtered counts are surfaced in scan trigger responses as `tickers_filtered_market_cap`.

### Required Hugging Face Secrets
| Secret Name | Value | Required? |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` from Supabase | ✅ Yes |
| `API_SECRET_KEY` | `dev_key` (match frontend `X-API-Key`) | ✅ Yes |
| `GEMINI_API_KEY` | Google Gemini API key | ✅ For GenAI features |
| `FINNHUB_API_KEY` | Finnhub API key | ✅ For market data |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage key | ✅ For technicals |
| `FRED_API_KEY` | FRED API key | Recommended for official keyed macro/rates access |

---

## 12. Scan Pipeline — Design & Fixes (2026-07-28)

### How the Scan Pipeline Works

1. **Trigger**: `POST /v1/scans/trigger` (or via AI chat tool `trigger_scan`) calls `scan_service.trigger_scan()`.
2. **Earnings Calendar**: Fetches today's earnings list from Finnhub (`/calendar/earnings?from=DATE&to=DATE`).
3. **Rolling Offset / Pagination**: Before slicing, the service queries the `daily_scans` table to find which tickers have already been scanned today. It skips those and takes the **next `batch_size` (default 20)** unseen tickers.
4. **Concurrent Fetch**: For each ticker in the batch, it concurrently fetches quote, technicals, and company profile (5-at-a-time semaphore to respect free-tier rate limits).
5. **Safety Guard**: If Finnhub returns 0 tickers (API error / no data), the scan **aborts early** and returns `status: ABORTED_NO_DATA` — it never wipes existing database records.
6. **Scoring**: `run_full_scan()` evaluates all 50 factors across 10 layers for each ticker.
7. **Incremental Persist**: Only the new batch's tickers are deleted and re-inserted — not the entire day's data.
8. **Commit**: `session.commit()` is called at the end to permanently save all rows to Supabase.
9. **All Done**: When all tickers in the calendar are scanned, returns `status: ALL_SCANNED`.

### Key Files
| File | Role |
|---|---|
| `backend/app/services/scan_service.py` | Core scan pipeline, offset pagination, DB persistence |
| `backend/app/api/scans.py` | REST endpoints (`POST /trigger`, `GET /{date}`) |
| `backend/app/agents/chat_agent.py` | AI tool executor — triggers scan via chat, offloads to `asyncio.create_task` |

### Bug Fixes Applied
| Bug | Symptom | Fix |
|---|---|---|
| `session.flush()` instead of `session.commit()` | Scan ran successfully but no rows saved to DB | Changed final flush to `session.commit()` |
| Gemini tool args not saved to `current_tool_name` | Tool call detected by frontend but silently never executed | Fixed Gemini streaming branch to always set `current_tool_name` before yielding |
| `confirmed is True` strict bool check | Gemini passes `"true"` string; scan was silently cancelled | Relaxed to check `str(val).lower() in ["true","yes","1"]` |
| `asyncio.create_task()` GC'd immediately | Background scan task destroyed before running | Added module-level `_bg_tasks` set to hold strong reference |
| Full `DELETE` before incremental insert | Re-running scan wiped all existing data for the day | Changed to `DELETE WHERE ticker IN (batch)` |
| Always scanning first 20 tickers | Repeated scans scanned same stocks over and over | Implemented offset from DB — each run skips already-scanned tickers |
| `UnboundLocalError: scan_empty` | Hard crash in SSE stream | Moved variable initialization outside `for` loop |
| SQL date boundary bug (days 28–31) | `get_scan_results` returned empty for late-month dates | Replaced hardcoded day math with `timedelta(days=1)` |
| `ConnectionDoesNotExistError` (asyncpg) | Scan crashed mid-write after 30–90s of Finnhub API calls | Refactored to use three short-lived sessions: (1) quick read at start, (2) no session held during Finnhub work, (3) fresh write session at end |

---

## 13. Dual-Horizon Selection Framework (2026-08-01)

### Objective
The scan pipeline now computes two independent selection outputs from the same live data snapshot:
1. **30-Day Tactical Engine** (catalyst + setup + options mechanics, gated by macro regime checks).
2. **Long-Term Investment Engine** (business quality + valuation readiness with strict data availability checks).

This design prevents short-term catalyst positioning from contaminating long-term conviction sizing.

### Implementation Files
| File | Change |
|---|---|
| `backend/app/framework/dual_horizon.py` | Added tactical and long-term evaluators and output contract builders |
| `backend/app/services/fundamentals_service.py` | Added live fundamentals ingestion (`yfinance`) for long-term engine inputs |
| `backend/app/framework/factors/base.py` | Extended `ScanContext` with typed fundamentals fields plus tactical enrichment fields (`mtf_trend_aligned`, `relative_volume`, catalyst booleans, options mechanics metrics) |
| `backend/app/framework/engine.py` | Mapped enriched tactical + long-term fields from ticker payload into `ScanContext` |
| `backend/app/core/market_data/technicals.py` | Added live 60m trend-alignment check and relative-volume computation from real bars |
| `backend/app/services/options_service.py` | Added live options mechanics metrics (`iv_rank_1y`, `iv_crush_risk`, `put_call_oi_ratio`, `skew_signal`) to selected contract payload |
| `backend/app/services/scan_service.py` | Persisted dual-horizon payload into `daily_scans.factor_results_json.dual_horizon` |
| `backend/app/services/stockglass_service.py` | Exposed dual-horizon payload in stock list/detail and built dedicated dual-list response |
| `backend/app/api/stockglass.py` | Added route: `GET /v1/stocks/dual-horizon` |
| `backend/app/db/schemas.py` | Added dual-horizon API schemas |

### New API Route
`GET /v1/stocks/dual-horizon`

Response model: `DualHorizonListResponseSchema`

```json
{
    "scanDate": "2026-08-01",
    "tacticalCount": 27,
    "longTermCount": 11,
    "tactical": [
        {
            "symbol": "NVDA",
            "name": "NVIDIA Corporation",
            "sector": "Semiconductors",
            "score": 8.1,
            "sizingCap": "100%",
            "regimeGate": "PASS"
        }
    ],
    "longTerm": [
        {
            "symbol": "MSFT",
            "name": "Microsoft Corporation",
            "sector": "Technology",
            "score": 7.4,
            "sizingCap": null,
            "regimeGate": null
        }
    ]
}
```

### Persisted Runtime Schema (`daily_scans.factor_results_json.dual_horizon`)
```json
{
    "tactical": {
        "score": 7.3,
        "regime_gate_pass": true,
        "regime_fail_reasons": [],
        "catalyst_signals": ["EARNINGS_WINDOW"],
        "technical_signals": ["PRICE_ABOVE_SMA50"],
        "options_signals": ["OPTION_CONTRACT_AVAILABLE"],
        "conviction_tier": "FULL_SIZE",
        "sizing_cap": "100%",
        "entry_cutoff": "11:00 AM CST (10:30 AM CST Fridays)",
        "binary_event_exit": "EXIT_BEFORE_EARNINGS_UNLESS_EXPLICIT_OVERRIDE",
        "invalidation_rule": "SET_AT_ENTRY_NO_EMOTIONAL_OVERRIDE"
    },
    "long_term": {
        "status": "SCORED",
        "score": 6.9,
        "thesis_strength_score": 7.2,
        "entry_timing_score": 6.0,
        "portfolio_fit_score": 6.0,
        "missing_inputs": [],
        "thesis_break_condition": "FUNDAMENTAL_THESIS_BREAK_ONLY"
    }
}
```

### Validation & Error Behavior
1. **No synthetic fundamentals:** If fundamentals are missing from live feed, each missing field is explicitly listed in `long_term.missing_inputs`.
2. **Long-term score suppression:** If required long-term inputs are incomplete, status is `DATA_NOT_AVAILABLE` and long-term score is `null`.
3. **Regime hard gate:** Tactical candidates with triggered `F45`, `F49`, `F50`, or post-cutoff state fail regime gate and are excluded from tactical list output.
4. **Legacy list compatibility:** `daily_scans.list_type` remains populated for compatibility; dual-horizon list consumption should use `GET /v1/stocks/dual-horizon` as source of truth.

### Tactical Enrichment Update (2026-08-02)
1. **Catalyst expansion:** Tactical scoring now ingests additional live catalyst classes from ticker/general news parsing: analyst day, product launch, FDA/regulatory events, index reconstitution, and sector macro events (including OPEC or macro data print context).
2. **Technical setup expansion:** Tactical scoring now uses multi-timeframe alignment (daily trend plus 60m trend check) and relative-volume confirmation sourced from real bars.
3. **Options mechanics expansion:** Tactical scoring now uses live options mechanics signals from selected chain data: IV rank proxy, IV crush risk tier, put/call OI ratio, and skew classification.
4. **API output extension:** `dualFramework.tactical` now includes `catalyst_signals`, `technical_signals`, `options_signals`, `entry_cutoff`, `binary_event_exit`, and `invalidation_rule` in stock detail responses.

### Long-Term Completion Update (2026-08-02)
1. **Long-term layer expansion:** The long-term evaluator now emits additional structured outputs for remaining framework sections:
    - `moat_signals` (quality/moat proxies from margin and return profile)
    - `secular_signals` (structural growth and sector-tailwind mapping)
    - `management_signals` (ownership/capital discipline signals)
    - `target_valuation_band` (forward-PE valuation band output)
2. **Portfolio-fit integration:** Portfolio-fit now consumes real open-position exposure by sector from `positions` + `stocks`, and applies exposure-aware scoring without synthetic state.
3. **Thesis-change flagging:** Long-term payload now emits `thesis_change_event_detected` based on live fundamentals deterioration conditions (negative growth/margin pressure/leverage stress).
4. **Cadence automation:** Stock detail read path enforces long-term refresh logic:
    - monthly refresh when persisted scan month differs from current month;
    - immediate refresh when `thesis_change_event_detected=true` in the last persisted long-term payload.
5. **Extended API contract:** `dualFramework.long_term` now includes `target_valuation_band`, `moat_signals`, `secular_signals`, `management_signals`, `thesis_change_event_detected`, and `thesis_break_condition`.

### Routing Note (2026-08-01)
`/v1/scans/trigger` is the canonical and only supported scan trigger route.
The root alias `/scans/trigger` was removed to prevent duplicate endpoint exposure.

### 50-Factor Compliance Status (2026-08-02)
1. **Canonical mapping enforced:** Factor IDs `F01..F39` are now mapped to the user-defined 10-layer taxonomy labels (macro → global structure → earnings/catalyst → sector/correlation → technical → options mechanics → liquidity/microstructure → sentiment/positioning).
2. **Truthful implementation signaling:** Any factor whose required live inputs are not yet wired returns `status=UNCONFIGURED` with `stubbed=true` at evaluation time. These factors are included in audit output and are never silently treated as implemented.
3. **Core live coverage retained:** `F40..F50` remain dedicated live rule implementations.
4. **Coverage contract:** Scan responses continue exposing factor coverage (`total`, `live_count`, `stubbed_count`, IDs) so implementation gaps are visible. Current measured state: `total=50`, `live_count=43`, `stubbed_count=7`.
5. **EDGAR enforcement tightened:** `F46` now fails closed when EDGAR availability checks fail. If SEC check is unavailable, entry is vetoed instead of passing.
6. **Free public-source expansion:** The following spec factors are now backed by free public data and wired live into scan evaluation:
    - `F03` via free dollar-index history (`DX-Y.NYB`)
    - `F04` via free FRED Treasury yield series (`DGS2`, `DGS10`)
    - `F05` via free ETF/volatility series (`HYG`, `LQD`, `GLD`, `^VIX`)
    - `F09` via free overnight futures intraday history (`ES=F`)
    - `F07` via free European index history (`^GDAXI`, `^FTSE`)
    - `F10` via free VIX term proxies (`^VIX`, `^VIX9D`, `^VIX3M`)
    - `F16`, `F18`, `F19` via free ticker/sector/SPX history and sector ETF mapping
    - `F23` via free intraday volume-profile node calculation from `yfinance` bars
    - `F28`, `F29` via free option-chain Greeks estimated from `yfinance` chain data
    - `F37` via free short-interest fields exposed in `yfinance` fundamentals (`shortRatio`, `shortPercentOfFloat`)
    - `F01` via free Fed-path proxy synthesized from FRED rates/curve + DXY/VIX context (`fed_policy_prob_proxy`)
    - `F08` via free central-bank surprise proxy from live macro-news keyword scoring (`central_bank_surprise_proxy`)
    - `F12` via free whisper proxy from pre-earnings options crowding + analyst/reaction sentiment (`whisper_eps_gap_proxy`)
    - `F13` via free guidance-trend proxy from quarterly earnings surprise trajectory (`guidance_revision_trend_4q`)
    - `F33` via free options activity proxy (`option_volume_oi_ratio = selected_contract_volume / selected_contract_oi`)
    - `F35` via free dealer-gamma regime proxy inferred from put/call OI ratio + IV rank + skew (`dealer_gamma_regime_proxy`)
    - `F38` via free retail sentiment proxy from ticker news tone scoring (`retail_sentiment_score`)
7. **Proxy transparency contract:** For these factors, outputs include `metadata.source_tier="FREE_PROXY"` to make non-institutional quality explicit in audit logs.

### Remaining Gaps to Reach Full 1:1 Spec Parity
1. **Data-source parity gaps:** `F01`, `F08`, `F12`, `F13`, `F33`, `F35`, and `F38` are now live via free proxies, but still require institutional datasets for strict parity (FedWatch probabilities, structured central-bank surprise feeds, whisper/guidance databases, full historical options-flow panels, dealer positioning models, and dedicated retail-flow datasets).
2. **Execution-policy parity gaps:** Some non-factor risk policies (for example explicit no-averaging-down enforcement and 25% FOMC-week cap as hard execution controls) are documented but not yet fully enforced as server-side order-policy gates.
3. **No-skip interpretation:** `F11` is implemented as earnings-presence detection at ticker level; strict "every name no skip" guarantees still depend on upstream universe ingestion/scheduling and operational availability.

---

## 14. Portfolio Scoring & Optimization (Paper Trading)

### Objective
Provide deterministic, auditable portfolio management outputs for paper-trading positions:
1. **Portfolio Score (0-100 composite)** from weighted component scores.
2. **Portfolio Optimization Advisory** with ranked, trigger-linked actions.

### API Routes
1. `GET /v1/portfolio/score`
2. `GET /v1/portfolio/optimize?cadence=weekly|regime_shift`

Both endpoints also support optional per-request weight overrides via query params:
`w_concentration`, `w_risk_adjusted_return`, `w_diversification`, `w_drawdown`, `w_greeks`, `w_liquidity`, `w_conviction`, `w_tax_efficiency`.
Validation rules:
1. Every provided weight must be non-negative.
2. Effective full weight set must sum exactly to 1.0.
3. Invalid sets fail fast with explicit error.

### Frontend Routing
1. Main screener route: `/`
    Displays only a compact portfolio summary strip (composite score, top watch items, CTA).
2. Dedicated portfolio workspace route: `/portfolio`
    Hosts the full paper-trading portfolio management UI: score workspace, optimizer queue, position-entry form, and open-positions table.

Frontend polling policy (implemented):
1. Visibility-aware background polling refreshes score and open positions on `/portfolio`.
2. Full optimization payload is loaded via weekly cadence path and served from backend cadence control.

This route split keeps ticker-level discovery and book-level management as separate user workflows.

### Weighted Score Components
1. Concentration Risk — 15%
2. Risk-Adjusted Return — 15%
3. Diversification/Correlation — 12%
4. Drawdown Exposure — 12%
5. Options Greek Exposure — 12%
6. Liquidity Score — 10%
7. Conviction Alignment — 12%
8. Tax Efficiency — 12%

Final score is the weighted blend of available component scores. If a component cannot be computed from available live/runtime data, it is surfaced as `DATA_NOT_AVAILABLE` and listed in `missingComponents`.

Default weights are runtime-configurable through app settings (`AppConfig`), and can be overridden per call on the portfolio scoring/optimization endpoints.

### Optimization Pass (Advisory-Only)
The optimizer emits a ranked action list with explicit trigger causes, aligned to these deterministic steps:
1. Concentration rebalance (`single_name_over_10pct`, `sector_over_30pct`)
2. Correlation de-clustering (`top5_avg_corr_gt_0_75`) plus concrete replacement generation (`uncorrelated_replacement_candidate`) from the latest scan universe, excluding current holdings and dominant-sector crowding.
3. Tax-loss harvest (`loss_gt_30d_no_near_catalyst`) with explicit near-term catalyst gate from dual-horizon tactical payload.
4. Greek rebalance (`greek_band_exceeded`)
5. Conviction sizing correction (`position_weight_vs_conviction_cap`)
6. Liquidity sweep (`liquidity_score_below_70`) plus option-chain one-day-exit validation (`option_oi_volume_one_day_exit_failed`) using live open interest and volume checks on held OCC contracts.
7. Macro regime cap (`regime_shift_f45_f49_f50`)
8. Ranked output (`actions[]` with `priority`, `action`, `trigger`, `reason`, `metrics`)

Cadence and output semantics (implemented):
1. `cadence=weekly` returns a deterministic cached optimization payload keyed by `(user_id, ISO week)` to avoid recomputation on high-frequency UI refresh.
2. `cadence=regime_shift` bypasses the weekly cache and executes a fresh optimization pass.
3. Unknown cadence values are normalized to `weekly`.
4. Holdings that trigger no rebalance rule are emitted as explicit `HOLD` actions (`trigger=no_rebalance_trigger`) so each open holding has a deterministic optimization classification.

Liquidity scoring semantics (implemented):
1. Component 6 now blends equity exit-liquidity and held-options liquidity checks directly in score computation.
2. Option liquidity contributes using open-interest/volume availability and contract-size-vs-OI threshold checks.
3. Score metrics now include `option_liquid_positions` and `option_illiquid_positions`.

### Data Sources & Integrity
1. Positions source: `positions` table (`status=open`) with server-side notional and P&L context.
2. Market prices: live quotes via Finnhub for current pricing.
3. Return/correlation/drawdown series: yfinance daily close history.
4. Conviction alignment: latest scan conviction context from `daily_scans.factor_results_json.dual_horizon`.
5. Macro override: latest factor triggers (`F45`, `F49`, `F50`) from `factor_logs`.

### Error Handling
1. If no open positions exist, score returns `DATA_NOT_AVAILABLE` with `missingComponents=["No open positions"]`.
2. If required live quote data is missing for held symbols, scoring fails explicitly rather than fabricating values.
3. Optimization remains advisory-only and never auto-executes trades.

### Scheduled Execution Policy
Portfolio maintenance jobs are scheduled server-side (CST timezone):
1. Daily scoring run (all active users) at configured `portfolio_daily_score_hour` / `portfolio_daily_score_minute`.
2. Weekly optimization run (all active users, cadence=`weekly`) at configured `portfolio_weekly_optimize_day_of_week`, `portfolio_weekly_optimize_hour`, and `portfolio_weekly_optimize_minute`.
3. Scheduler can be disabled with `portfolio_scheduler_enabled=false`.
4. Job execution is deterministic, logs per-user failures, and never auto-executes trades.

---

## 15. Multi-User Registration & Session Access (2026-08-02)

### Objective
Evolve the app from a single hardcoded developer user path into a real multi-user flow where end users can register, log in, and use the application with JWT-backed sessions.

### Auth Routes
1. `POST /v1/auth/register`
2. `POST /v1/auth/login`
3. `POST /v1/auth/refresh`
4. `GET /v1/auth/me`

### Session Model
1. Registration issues an access token and refresh token immediately on success.
2. Frontend stores JWT session tokens locally and uses Bearer authentication for protected app requests.
3. API-key access remains supported as a compatibility path for local development/admin automation.

### Protected Route Behavior
1. StockGlass contract routes already accept Bearer token or API key.
2. Internal authenticated routes now also accept Bearer token or API key, enabling registered users to access scans, uploads, watchlists, chat, and portfolio workflows without the single shared API-key path.

### Frontend UX
1. The login modal now supports both `Log In` and `Register` modes.
2. Registration validates password confirmation client-side before attempting account creation.
3. After registration, the user is automatically treated as logged in and the app continues under the issued JWT session.


