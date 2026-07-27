# Use official lightweight Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

# Set working directory
WORKDIR /app

# Install system dependencies (needed for compiling C extensions or database drivers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY . .

# Create necessary directories for local SQLite database, cache, or screenshots with permissions
RUN mkdir -p /app/data /app/screenshots && chmod -R 777 /app/data /app/screenshots

# Expose default Hugging Face Spaces port
EXPOSE 7860

# Start Uvicorn server bound to 0.0.0.0 and port 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
