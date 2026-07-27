"""
Hugging Face Spaces (Gradio SDK) Entry Point
==============================================
Mounts the StockGlass FastAPI backend onto a lightweight Gradio interface
so that it can be hosted on Hugging Face Spaces' 100% FREE Gradio SDK tier.
"""

import os
import uvicorn
import gradio as gr
from app.main import app as fastapi_app

# Create a clean Gradio interface for Hugging Face Spaces compliance
with gr.Blocks(title="StockGlass AI Trading Assistant Backend") as demo:
    gr.Markdown("# 🚀 StockGlass AI Trading Assistant Backend")
    gr.Markdown("This Hugging Face Space is running the FastAPI backend server for StockGlass AI.")
    gr.Markdown("### API Endpoints & Resources")
    gr.Markdown("- **Interactive API Docs (Swagger UI)**: [`/docs`](/docs)\n- **ReDoc Documentation**: [`/redoc`](/redoc)\n- **Health Check Endpoint**: [`/v1/health`](/v1/health)")
    
    with gr.Row():
        gr.Markdown("*Note: Your Vercel frontend seamlessly communicates with this server via the `/v1` REST API and SSE endpoints.*")

# Mount Gradio onto the root of our FastAPI app
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__" and not os.environ.get("SPACE_ID") and not os.environ.get("SYSTEM") == "spaces":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
