# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 appuser && \
    mkdir -p /app/reports /app/data && chown -R appuser:appuser /app
USER appuser

# Default: API server (scheduler runs in-process via lifespan).
# Override CMD to ["python","run_worker.py"] for a dedicated collector worker.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
