"""
Hugging Face Spaces Entry Point
=================================
Starts the StockGlass FastAPI backend on port 7860 (Hugging Face default port).
Includes a ZeroGPU compatibility hook so Hugging Face ZeroGPU spaces do not shut down.
"""

import os
import uvicorn
from app.main import app

# ZeroGPU compatibility: Hugging Face ZeroGPU supervisor monitors startup for @spaces.GPU.
# If running on ZeroGPU hardware without this decorator, the container is terminated.
try:
    import spaces
    @spaces.GPU(duration=1)
    def _zero_gpu_compatibility_hook():
        return "ZeroGPU registered"
    # Invoke once at startup to register active GPU lease with ZeroGPU supervisor
    _zero_gpu_compatibility_hook()
except Exception:
    pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
