"""
Test Suite for StockGlass AI API Contract (v1)
================================================
Verifies compliance with drop-in replacement requirements across all 7 sections.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db
from app.db.models import Position, PositionStatus, DailyScan, FactorLog, RiskBucket, ScanStatus


# --- In-Memory Mock Session for deterministic testing ---

class MockResult:
    def __init__(self, items=None, scalar_val=None):
        self._items = items or []
        self._scalar_val = scalar_val

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._scalar_val

    def scalar(self):
        return self._scalar_val


class MockSession:
    def __init__(self):
        self.positions = {}
        self.test_scan = DailyScan(
            id=1,
            scan_date=datetime.now(timezone.utc),
            ticker="NVDA",
            score=8.2,
            risk_bucket=RiskBucket.MODERATE,
            status=ScanStatus.CONFIRMED,
            entry_price=178.42,
            factor_logs=[
                FactorLog(id=i+1, factor_id=f"F{i+1:02d}", factor_name=f"Factor {i+1}", layer_number=(i//5)+1, triggered=(i in (0, 46)), vetoed=(i == 39))
                for i in range(50)
            ],
            factor_results_json={"market_data": {"name": "NVIDIA Corp", "sector": "Semiconductors"}},
        )

    async def execute(self, stmt):
        stmt_str = str(stmt).lower()
        if "position" in stmt_str:
            params = {}
            try:
                params = stmt.compile().params
            except Exception:
                pass
                
            # Check if an ID parameter was passed for position lookup/close
            for k, val in params.items():
                if str(val).startswith("pos_"):
                    pos_obj = self.positions.get(val)
                    return MockResult(scalar_val=pos_obj, items=[pos_obj] if pos_obj else [])
                    
            # Otherwise return all positions matching status filter if present
            items = [p for p in self.positions.values() if isinstance(p, Position)]
            for k, val in params.items():
                stat_str = str(val.value).lower() if hasattr(val, "value") else str(val).lower()
                if stat_str in ("open", "closed"):
                    items = [p for p in items if p.status.value.lower() == stat_str]
                    
            return MockResult(items=items, scalar_val=items[0] if items else None)
        # Return test scan data for screener and detail tests
        if "scan" in stmt_str:
            return MockResult(items=[self.test_scan], scalar_val=self.test_scan)
        return MockResult(items=[], scalar_val=None)

    async def scalar(self, stmt):
        return None

    def add(self, obj):
        if isinstance(obj, Position):
            self.positions[obj.id] = obj

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def close(self):
        pass


mock_session_instance = MockSession()

async def override_get_db():
    yield mock_session_instance


from app.core.rate_limiter import init_rate_limiters
init_rate_limiters()

@pytest.fixture(autouse=True)
def setup_stockglass_db_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]

client = TestClient(app)

VALID_HEADERS = {"Authorization": "Bearer test_token_123"}


def test_get_indices():
    """Verify Section 1 indices strip endpoint returns S&P 500, Nasdaq, Dow Jones."""
    resp = client.get("/v1/indices", headers=VALID_HEADERS)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 3
    names = {item["name"] for item in data}
    assert names == {"S&P 500", "Nasdaq", "Dow Jones"}
    for item in data:
        assert "value" in item
        assert "chg" in item
        assert "pct" in item


def test_get_stock_list():
    """Verify Section 2 screener table returns drop-in compliant structure."""
    resp = client.get("/v1/stocks?list=list1&q=NVDA", headers=VALID_HEADERS)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "count" in data
    assert "total" in data
    assert "results" in data
    assert len(data["results"]) > 0
    first_stock = data["results"][0]
    assert first_stock["symbol"] == "NVDA"
    assert "price" in first_stock
    assert "chg" in first_stock
    assert "pct" in first_stock
    assert "volume" in first_stock
    assert "score" in first_stock
    assert "earningsSoon" in first_stock
    assert "hardFlags" in first_stock
    assert "sparkline" in first_stock
    assert "levels" in first_stock
    assert "support" in first_stock["levels"]
    assert "resistance" in first_stock["levels"]


def test_get_stock_detail():
    """Verify Section 3 right-hand panel returns 10-layer scores and reasons."""
    resp = client.get("/v1/stocks/NVDA", headers=VALID_HEADERS)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["symbol"] == "NVDA"
    assert data["name"] == "NVIDIA Corp"
    assert "layerScores" in data
    assert len(data["layerScores"]) == 10
    assert "reasons" in data
    assert len(data["reasons"]) > 0
    assert "news" in data
    assert isinstance(data["news"], list)


def test_get_stock_factors():
    """Verify Section 4 modal returns 50-factor breakdown across 10 layers."""
    resp = client.get("/v1/stocks/NVDA/factors", headers=VALID_HEADERS)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["symbol"] == "NVDA"
    assert "summary" in data
    assert "pass" in data["summary"]
    assert "neutral" in data["summary"]
    assert "fail" in data["summary"]
    assert "layers" in data
    assert len(data["layers"]) == 10
    total_factors = sum(len(layer["factors"]) for layer in data["layers"])
    assert total_factors == 50


def test_paper_trading_crud():
    """Verify Section 5 paper trading position lifecycle and server-side tracking."""
    # Create position
    create_payload = {"symbol": "AAPL", "qty": 15.0, "entryPrice": 224.15}
    resp_create = client.post("/v1/positions", json=create_payload, headers=VALID_HEADERS)
    assert resp_create.status_code == 201, resp_create.text
    created = resp_create.json()
    assert created["id"].startswith("pos_")
    assert created["symbol"] == "AAPL"
    assert created["status"] == "open"
    pos_id = created["id"]

    # Get positions
    resp_get = client.get("/v1/positions?status=open", headers=VALID_HEADERS)
    assert resp_get.status_code == 200, resp_get.text
    data_get = resp_get.json()
    assert any(item["id"] == pos_id for item in data_get["results"])

    # Close position
    resp_close = client.delete(f"/v1/positions/{pos_id}", headers=VALID_HEADERS)
    assert resp_close.status_code == 200, resp_close.text
    closed = resp_close.json()
    assert closed["id"] == pos_id
    assert closed["status"] == "closed"
    assert "exitPrice" in closed
    assert "realizedPnl" in closed

    # Close non-existent position
    resp_not_found = client.delete("/v1/positions/pos_nonexistent_999", headers=VALID_HEADERS)
    assert resp_not_found.status_code == 404
    err_data = resp_not_found.json()
    assert err_data["error"]["code"] == "NOT_FOUND"


def test_auth_failure():
    """Verify Section 6 auth failure format."""
    resp_missing = client.get("/v1/indices")
    assert resp_missing.status_code == 401
    err_missing = resp_missing.json()
    assert err_missing["error"]["code"] == "AUTHENTICATION_ERROR"

    resp_expired = client.get("/v1/indices", headers={"Authorization": "Bearer expired_token"})
    assert resp_expired.status_code == 401
    err_expired = resp_expired.json()
    assert err_expired["error"]["code"] == "AUTHENTICATION_ERROR"


def test_websocket():
    """Verify Section 6/7 WebSocket connection acceptance and subscribe message handling."""
    with client.websocket_connect("/v1/ws?token=test_token") as websocket:
        websocket.send_json({"type": "subscribe", "symbols": ["NVDA"]})
        websocket.send_json({"type": "unsubscribe", "symbols": ["NVDA"]})

    with client.websocket_connect("/v1/stream?symbols=NVDA,AVGO&token=test_token") as websocket:
        websocket.send_json({"type": "subscribe", "symbols": ["HOOD"]})
