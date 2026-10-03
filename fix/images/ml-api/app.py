import os
import time
import random
import threading

from fastapi import FastAPI, Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

app = FastAPI(title="ML Inference API")

# --- Prometheus metrics ---
REQUEST_COUNT = Counter(
    "ml_api_requests_total", "Total requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "ml_api_request_duration_seconds",
    "Request latency",
    ["endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)
PREDICTION_COUNT = Counter("ml_api_predictions_total", "Total predictions made")
MEMORY_USAGE = Gauge("ml_api_memory_bytes", "Simulated memory usage in bytes")

# --- Configuration (set at build time via ENV in Dockerfile) ---
_PROFILE = os.environ.get("APP_PROFILE", "default")
_MEM_ALLOC_MB = int(os.environ.get("MEM_ALLOC_MB", "0"))
_MEM_ALLOC_INTERVAL = int(os.environ.get("MEM_ALLOC_INTERVAL", "10"))
_RESPONSE_OVERHEAD_MS = int(os.environ.get("RESPONSE_OVERHEAD_MS", "0"))
_HEALTH_TTL_SECONDS = int(os.environ.get("HEALTH_TTL_SECONDS", "0"))

# --- State ---
_start_time = time.time()
_allocated_chunks: list[bytes] = []
_total_allocated_bytes = 0


def _background_allocator():
    """Background thread that gradually allocates memory."""
    global _total_allocated_bytes
    while True:
        time.sleep(_MEM_ALLOC_INTERVAL)
        chunk = b"\x00" * (_MEM_ALLOC_MB * 1024 * 1024)
        _allocated_chunks.append(chunk)
        _total_allocated_bytes += len(chunk)
        MEMORY_USAGE.set(_total_allocated_bytes)


if _MEM_ALLOC_MB > 0:
    t = threading.Thread(target=_background_allocator, daemon=True)
    t.start()


def _health_expired() -> bool:
    if _HEALTH_TTL_SECONDS > 0:
        return (time.time() - _start_time) > _HEALTH_TTL_SECONDS
    return False


@app.get("/health")
def health():
    if _health_expired():
        REQUEST_COUNT.labels("GET", "/health", "503").inc()
        return Response(status_code=503, content="unhealthy")
    REQUEST_COUNT.labels("GET", "/health", "200").inc()
    return {"status": "healthy"}


@app.get("/ready")
def ready():
    REQUEST_COUNT.labels("GET", "/ready", "200").inc()
    return {"status": "ready"}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict")
def predict():
    with REQUEST_LATENCY.labels("/predict").time():
        # Simulate inference latency (100-400ms) + any configured overhead
        time.sleep(random.uniform(0.1, 0.4))
        if _RESPONSE_OVERHEAD_MS > 0:
            time.sleep(_RESPONSE_OVERHEAD_MS / 1000.0)

        PREDICTION_COUNT.inc()
        REQUEST_COUNT.labels("POST", "/predict", "200").inc()

        return {
            "transcription": "Medikamente wurden gegeben",
            "confidence": round(random.uniform(0.85, 0.99), 3),
            "duration_ms": random.randint(100, 400),
        }
