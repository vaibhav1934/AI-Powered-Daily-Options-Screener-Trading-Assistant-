from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Any
from app.core.broker_parser import FidelityCSVParser

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

@router.post("/upload")
async def upload_portfolio(file: UploadFile = File(...)) -> Any:
    """
    Upload a Fidelity positions CSV.
    Parses the positions and returns a concentration report.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Must be a CSV file")

    content = await file.read()
    try:
        csv_text = content.decode('utf-8')
    except UnicodeDecodeError:
        csv_text = content.decode('latin-1')

    parser = FidelityCSVParser()
    try:
        positions = parser.parse(csv_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    if not positions:
        return {"message": "No valid positions found", "positions": [], "total_value": 0.0}

    total_value = sum(p.current_value for p in positions)
    
    # Calculate basic concentration by ticker
    concentration = []
    for p in positions:
        weight = (p.current_value / total_value * 100) if total_value > 0 else 0
        concentration.append({
            "ticker": p.ticker,
            "value": p.current_value,
            "weight_pct": round(weight, 2)
        })
        
    concentration.sort(key=lambda x: x["weight_pct"], reverse=True)

    # In a full implementation, we would map tickers to sectors and check IT concentration.
    # For now, we return the ticker breakdown.
    
    return {
        "message": f"Successfully parsed {len(positions)} positions",
        "total_value": round(total_value, 2),
        "concentration": concentration,
        "flagged_risks": [
            f"High concentration in {concentration[0]['ticker']} ({concentration[0]['weight_pct']}%)"
        ] if concentration and concentration[0]['weight_pct'] > 15.0 else []
    }
