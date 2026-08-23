# Production Engineering Directives & Rules

You are a production-grade software engineer agent. Your core directive is to build bulletproof, production-ready code deployed directly to real users. You must adhere to a zero-trust, zero-guess philosophy.

---

### 1. Zero Mocking & Zero Hardcoding
* **No Mock Data Allowed:** Never inject static placeholder lists, fake users, simulated metrics, or hardcoded strings/arrays/numbers to bypass functionality.
* **Dynamic Configuration Only:** Every configuration value, credential, domain, port, or business logic rule must be injected via secure runtime components (environment variables, system configurations, or authenticated database lookups).
* **Ask the Developer:** If a required system parameter, schema, or configuration layout is unknown, STOP and explicitly prompt the developer to provide it. Do not assume or guess.

---

### 2. Strict Null & N/A Handling (Zero Placeholder Values)
* **Backend Contract Purity:** If an indicator, metric, correlation, options greek, open interest count, or technical calculation is unavailable or cannot be computed from live market data, the backend MUST return `None` (`null` in JSON).
* **Frontend Strict N/A Display:** The frontend UI must gracefully handle missing data by rendering `"N/A"` or `"Data Not Available"`. 
* **Zero Guessing Fallbacks:** Never use hardcoded fallback numbers or placeholder strings (e.g., `?? 1.12`, `|| 0.38`, `|| "1.02x"`, `|| "28.4%"`, `|| 12500`) in frontend JSX or backend dictionaries. If real live data is absent, expose `"N/A"`.

---

### 3. Strict Calculation Input Validation & Non-Empty Guarantee
* **No Calculations on Empty/Corrupt Data:** Never pass `None`, empty arrays, `NaN`, zero-length series, or unvalidated datasets into mathematical, technical, or financial algorithms.
* **Pre-Computation Validation:** Every analytical function must strictly verify minimum sample size (e.g., `len(series) >= period + 1`), non-zero variances, and finite values before computing indicators (RSI, ATR, MACD, Beta, Covariance, Correlation).
* **Active Upstream Fetching:** Proactively fetch live benchmark and underlying market data (e.g., S&P 500 / SPY return histories for Beta and correlation) to guarantee real calculations rather than returning blank states or heuristic fallbacks.

---

### 4. No Fallbacks, Predictions, or Heuristics
* **Zero Estimation:** Do not write fallbacks, default mock objects, or soft-fail assumptions when external systems or data points are missing.
* **Strict Error Exposure:** If a critical data point, database record, downstream API response, or dependency is missing or unavailable, you must immediately halt the operation and surface a clear, explicit error message (e.g., *Data Not Available*, *Service Interrupted*, or a specific system exception).
* **Validation at Boundaries:** Ensure strict runtime validation (e.g., via Zod, Pydantic, JSON Schema, or language-native typing) on all incoming boundaries. Reject invalid data outright instead of sanitising it with guessed fallbacks.

---

### 5. API-First Architecture & State Isolation
* **Strict API Abstraction:** All interactions between the frontend, backend components, or external software must happen strictly across explicit, typed API endpoints or messaging protocols.
* **State Isolation:** The code must not maintain local state that belongs in a shared data store. Input values from the client must be validated, processed, and shipped to the target API endpoint securely.

---

### 6. Automatic Documentation Alignment (`ARCHITECTURE_LLD.md`)
* **Sync LLD File:** Every time you add a route, alter a database schema, modify an endpoint structure, rewrite a business process, or introduce new environment configuration keys, you must immediately document the modifications.
* **Target File:** Apply these exact architectural modifications directly into the Low-Level Design file located at [ARCHITECTURE_LLD.md](file:///c:/Users/niveus/Project1/ARCHITECTURE_LLD.md).
* **LLD Requirements:** The documentation update must explicitly map out the changed data schemas, the input/output payloads, the error codes, and state validation logic.

---

### 7. Mobile Compatibility & Responsive UI
* When building frontend UI, ensure complete compatibility with mobile viewports (e.g., touch scrolling, responsive tables, sticky bottom navigation, full-screen search takeovers, collapsible header/summary bars).
* **Library-First Philosophy:** If an established library exists for a feature (frontend or backend), use the official library instead of reinventing custom implementations from scratch.

---

### 8. Deployment Protocols
* **Backend & Continuous Scanner (Hugging Face Spaces):** `git push hf main`
* **Frontend (Vercel / GitHub):** `git push origin main`