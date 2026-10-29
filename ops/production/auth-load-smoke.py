#!/usr/bin/env python3
"""Bounded real-gateway auth + scraping test; temporary credential never leaves VPS."""
import argparse
import base64
import concurrent.futures
import fcntl
import json
import os
from pathlib import Path
import secrets
import statistics
import subprocess
import time
import urllib.error
import urllib.request

GATEWAY = "http://127.0.0.1:13082"
AUTH_FILE = Path("/opt/mad4b/firecrawl-production/auth/.htpasswd")
LOCK_FILE = Path("/opt/mad4b/firecrawl-production/auth/.smoke.lock")

def call(path, headers=None, body=None, timeout=35):
    req = urllib.request.Request(GATEWAY + path, headers=headers or {}, data=body, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(2_000_000)
            return r.status, data
    except urllib.error.HTTPError as e:
        return e.code, b""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=4)
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()
    if not (1 <= args.requests <= 8 and 1 <= args.concurrency <= 2):
        parser.error("requests must be 1-8 and concurrency 1-2")
    if call("/__healthcheck")[0] != 200 or call("/v1/scrape")[0] != 401:
        raise RuntimeError("initial 200/401 gateway boundary checks failed")
    username = "firecrawl-smoke-" + secrets.token_hex(8)
    password = secrets.token_urlsafe(40)
    digest = subprocess.run(["openssl", "passwd", "-apr1", "-stdin"], input=password + "\n",
                            capture_output=True, text=True, check=True).stdout.strip()
    if not digest.startswith("$apr1$"):
        raise RuntimeError("password hash generation failed")
    LOCK_FILE.touch(mode=0o600, exist_ok=True)
    with LOCK_FILE.open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with AUTH_FILE.open("r+b") as auth:
            fcntl.flock(auth, fcntl.LOCK_EX)
            auth.seek(0, os.SEEK_END)
            offset = auth.tell()
            try:
                auth.write((username + ":" + digest + "\n").encode())
                auth.flush()
                os.fsync(auth.fileno())
                token = base64.b64encode((username + ":" + password).encode()).decode()
                headers = {"Authorization": "Basic " + token, "Content-Type": "application/json"}
                payload = json.dumps({"url": "https://example.com", "formats": ["markdown"], "onlyMainContent": True}).encode()
                def one(index):
                    started = time.monotonic()
                    code, raw = call("/v1/scrape", headers=headers, body=payload)
                    elapsed = round((time.monotonic() - started) * 1000)
                    success = False
                    if code == 200:
                        try:
                            result = json.loads(raw)
                            success = result.get("success") is True and bool((result.get("data") or {}).get("markdown"))
                        except (ValueError, TypeError):
                            pass
                    return {"http": code, "ok": success, "elapsed_ms": elapsed}
                with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                    results = list(pool.map(one, range(args.requests)))
            finally:
                auth.seek(offset)
                auth.truncate()
                auth.flush()
                os.fsync(auth.fileno())
                fcntl.flock(auth, fcntl.LOCK_UN)
    latencies = [x["elapsed_ms"] for x in results]
    print(json.dumps({"requests": args.requests, "concurrency": args.concurrency,
                      "successes": sum(x["ok"] for x in results),
                      "max_latency_ms": max(latencies), "avg_latency_ms": round(statistics.mean(latencies)),
                      "http_codes": [x["http"] for x in results],
                      "temporary_user_removed": True}, sort_keys=True))
    if sum(x["ok"] for x in results) != args.requests:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
