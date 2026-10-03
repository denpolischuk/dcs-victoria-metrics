import os
import time
import random

import psycopg2
from psycopg2 import pool
from fastapi import FastAPI, Response, HTTPException
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

app = FastAPI(title="Backend API")

# --- Prometheus metrics ---
REQUEST_COUNT = Counter(
    "backend_api_requests_total", "Total requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "backend_api_request_duration_seconds",
    "Request latency",
    ["endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)
DB_CONNECTIONS_ACTIVE = Gauge(
    "backend_api_db_connections_active", "Active database connections"
)
DB_QUERY_COUNT = Counter("backend_api_db_queries_total", "Total DB queries", ["status"])

# --- Configuration ---
DB_HOST = os.environ.get("DB_HOST", "postgres.postgres.svc.cluster.local")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "voize")
DB_USER = os.environ.get("DB_USER", "voize")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "voize")
DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN", "2"))
DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "10"))

# --- Build-time configuration (set via ENV in Dockerfile) ---
_CONN_RETURN_MODE = os.environ.get("CONN_RETURN_MODE", "normal")
_QUERY_OVERHEAD_MS = int(os.environ.get("QUERY_OVERHEAD_MS", "0"))

# --- State ---
_db_pool = None
_held_connections: list = []


def _get_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = pool.ThreadedConnectionPool(
            DB_POOL_MIN,
            DB_POOL_MAX,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            connect_timeout=5,
        )
    return _db_pool


def _init_db():
    """Create tables if they don't exist."""
    try:
        p = _get_pool()
        conn = p.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id SERIAL PRIMARY KEY,
                        content TEXT NOT NULL,
                        processed_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                conn.commit()
        finally:
            p.putconn(conn)
    except Exception:
        pass  # DB might not be ready yet


@app.on_event("startup")
def startup():
    for attempt in range(5):
        try:
            _init_db()
            return
        except Exception:
            time.sleep(2)


@app.get("/health")
def health():
    REQUEST_COUNT.labels("GET", "/health", "200").inc()
    return {"status": "healthy"}


@app.get("/ready")
def ready():
    try:
        p = _get_pool()
        conn = p.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            p.putconn(conn)
        REQUEST_COUNT.labels("GET", "/ready", "200").inc()
        return {"status": "ready"}
    except Exception as e:
        REQUEST_COUNT.labels("GET", "/ready", "503").inc()
        return Response(status_code=503, content=f"not ready: {e}")


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/process")
def process_document():
    with REQUEST_LATENCY.labels("/process").time():
        try:
            p = _get_pool()
            conn = p.getconn()
            DB_CONNECTIONS_ACTIVE.inc()

            try:
                if _QUERY_OVERHEAD_MS > 0:
                    time.sleep(_QUERY_OVERHEAD_MS / 1000.0)

                with conn.cursor() as cur:
                    content = f"Document processed at {time.time()}"
                    cur.execute(
                        "INSERT INTO documents (content) VALUES (%s) RETURNING id",
                        (content,),
                    )
                    doc_id = cur.fetchone()[0]
                    conn.commit()

                DB_QUERY_COUNT.labels("success").inc()
                REQUEST_COUNT.labels("POST", "/process", "200").inc()

                return {"document_id": doc_id, "status": "processed"}

            finally:
                if _CONN_RETURN_MODE == "hold":
                    _held_connections.append(conn)
                else:
                    p.putconn(conn)
                    DB_CONNECTIONS_ACTIVE.dec()

        except pool.PoolError as e:
            DB_QUERY_COUNT.labels("pool_exhausted").inc()
            REQUEST_COUNT.labels("POST", "/process", "503").inc()
            raise HTTPException(status_code=503, detail=f"Connection pool exhausted: {e}")
        except Exception as e:
            DB_QUERY_COUNT.labels("error").inc()
            REQUEST_COUNT.labels("POST", "/process", "500").inc()
            raise HTTPException(status_code=500, detail=str(e))
