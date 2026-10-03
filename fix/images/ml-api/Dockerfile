FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8000
ENV MEM_ALLOC_MB=0 MEM_ALLOC_INTERVAL=10 RESPONSE_OVERHEAD_MS=0 HEALTH_TTL_SECONDS=0
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000"]
