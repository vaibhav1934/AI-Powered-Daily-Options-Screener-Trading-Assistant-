"""
Hugging Face Spaces Entry Point
=================================
Starts the StockGlass FastAPI backend on port 7860 (Hugging Face default port).
No duplicate Gradio autolaunch servers are instantiated, preventing port 7861 collisions.
"""

import os
import uvicorn
from app.main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
