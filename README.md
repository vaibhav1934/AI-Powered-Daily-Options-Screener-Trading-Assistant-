---
title: StockGlass AI Trading Assistant
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "5.15.0"
python_version: "3.11"
app_file: app.py
pinned: false
---

# 🚀 StockGlass AI Trading Assistant Backend

This Hugging Face Space hosts the institutional 50-factor, 10-layer options and stock screener backend powered by FastAPI and Uvicorn.

## 📡 API Endpoints & Documentation

- **Interactive Swagger UI**: [`/docs`](/docs)
- **ReDoc API Documentation**: [`/redoc`](/redoc)
- **Health Check Endpoint**: [`/v1/health`](/v1/health)

## 🏗️ Architecture & Integration

This space runs a hybrid FastAPI + Gradio server on port `7860`.
Your frontend application (e.g. hosted on Vercel) connects to the `/v1` REST API and Server-Sent Events (SSE) streaming endpoints.
