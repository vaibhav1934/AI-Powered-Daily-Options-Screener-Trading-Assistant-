"""
Broker Export Parser
======================
Parses CSV exports from brokerages (like Fidelity) to extract positions.
Used for FR-21: cross-referencing scan output to flag concentration risks.
"""

from typing import Protocol, List
from pydantic import BaseModel
import csv
import io

class Position(BaseModel):
    ticker: str
    quantity: float
    current_value: float
    sector: str = "Unknown"

class BrokerExportParser(Protocol):
    def parse(self, csv_content: str) -> List[Position]:
        ...

class FidelityCSVParser:
    """
    Parses a typical Fidelity positions export.
    Generic implementation based on standard Fidelity headers.
    """
    def parse(self, csv_content: str) -> List[Position]:
        positions = []
        # Fidelity CSVs often have preamble or footer rows. 
        # We look for the row starting with "Symbol" or "Account"
        reader = csv.DictReader(io.StringIO(csv_content.strip()))
        
        # Determine actual column names dynamically just in case
        if not reader.fieldnames:
            return []
            
        symbol_col = next((col for col in reader.fieldnames if "Symbol" in col), None)
        qty_col = next((col for col in reader.fieldnames if "Quantity" in col), None)
        value_col = next((col for col in reader.fieldnames if "Current Value" in col), None)

        if not symbol_col or not qty_col or not value_col:
            raise ValueError("CSV missing required columns: Symbol, Quantity, Current Value")

        for row in reader:
            sym = row.get(symbol_col, "").strip()
            # Skip empty symbols, "Pending Activity", or "Core Account"
            if not sym or sym.lower() in ("pending activity", "core account", "margin"):
                continue
            
            try:
                # Remove commas and $ signs
                qty_str = row.get(qty_col, "0").replace(",", "").replace("$", "")
                val_str = row.get(value_col, "0").replace(",", "").replace("$", "")
                
                qty = float(qty_str) if qty_str else 0.0
                val = float(val_str) if val_str else 0.0
                
                if qty != 0:
                    positions.append(Position(
                        ticker=sym,
                        quantity=qty,
                        current_value=val
                    ))
            except ValueError:
                continue
                
        return positions
