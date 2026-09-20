# GigEase AI REST API Microservice Containerfile
FROM python:3.11-slim

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt-get/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

# Copy project source code and assets
COPY backend/ /app/backend/
COPY src/ /app/src/
COPY data/ /app/data/
COPY models/ /app/models/
COPY mlflow.db /app/mlflow.db

EXPOSE 8000

ENV PYTHONPATH=/app
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
