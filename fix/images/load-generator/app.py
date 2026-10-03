"""Simple load generator that sends requests to the ML API and Backend API."""

import os
import time
import random
import urllib.request
import urllib.error

ML_API_URL = os.environ.get("ML_API_URL", "http://ml-api.ml-api.svc.cluster.local:8000")
BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "http://backend-api.backend-api.svc.cluster.local:8000")
REQUEST_INTERVAL_MS = int(os.environ.get("REQUEST_INTERVAL_MS", "2000"))

def send_request(url, method="GET", data=None):
    try:
        req = urllib.request.Request(url, method=method, data=data)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except Exception as e:
        print(f"  error: {e}")
        return None

def main():
    print("Load generator starting...")
    time.sleep(10)  # Wait for services to come up

    while True:
        # Send prediction request
        print(f"POST {ML_API_URL}/predict")
        send_request(f"{ML_API_URL}/predict", method="POST", data=b'{}')

        time.sleep(random.uniform(0.5, 2.0))

        # Send document processing request
        print(f"POST {BACKEND_API_URL}/process")
        send_request(f"{BACKEND_API_URL}/process", method="POST", data=b'{}')

        time.sleep(REQUEST_INTERVAL_MS / 1000.0)

if __name__ == "__main__":
    main()
