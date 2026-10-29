#!/usr/bin/env python3
"""Read-only, private Firecrawl production watchdog; no credential access."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

PROJECT = "mad4b-firecrawl-production"
EXPECTED = {"gateway", "api", "playwright-service", "nuq-postgres", "redis", "rabbitmq"}
HEALTHY = {"gateway", "nuq-postgres", "rabbitmq"}
OUT = Path("/var/lib/mad4b-firecrawl-monitor/status.json")

def execute(args, timeout=8):
    p = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
    if p.returncode:
        raise RuntimeError("command failed: " + args[0] + " " + args[1])
    return p.stdout

def http_code(path):
    req = urllib.request.Request("http://127.0.0.1:13082" + path)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code

def memory():
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        if ":" in line:
            key, rhs = line.split(":", 1)
            if key in ("MemAvailable", "SwapFree"):
                values[key] = int(rhs.split()[0]) * 1024
    return values

def inspect_services():
    ids = execute(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + PROJECT]).split()
    if not ids:
        return {}
    info = json.loads(execute(["docker", "inspect", *ids], timeout=12))
    services = {}
    for item in info:
        name = item["Config"]["Labels"].get("com.docker.compose.service")
        if name in EXPECTED:
            state = item.get("State") or {}
            services[name] = {"running": bool(state.get("Running")), "health": (state.get("Health") or {}).get("Status", "none")}
    return services

def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        assert len(EXPECTED) == 6 and HEALTHY.issubset(EXPECTED)
        assert PROJECT == "mad4b-firecrawl-production"
        print("watch-self-test: PASS")
        return 0
    errors = []
    checks = {}
    try:
        services = inspect_services()
        checks["services"] = services
        for name in sorted(EXPECTED):
            if not services.get(name, {}).get("running"):
                errors.append("service not running: " + name)
            elif name in HEALTHY and services[name]["health"] != "healthy":
                errors.append("service health degraded: " + name)
    except Exception as exc:
        errors.append("docker inventory failure: " + type(exc).__name__)
    for name, path, expected in (("health", "/__healthcheck", 200), ("unauthorized", "/v1/scrape", 401)):
        try:
            got = http_code(path)
            checks[name] = got
            if got != expected:
                errors.append(name + " returned unexpected HTTP code " + str(got))
        except Exception as exc:
            errors.append(name + " failed: " + type(exc).__name__)
    try:
        result = execute(["docker", "exec", PROJECT + "-api-1", "node", "-e",
                          "fetch('http://127.0.0.1:3002/v1/scrape', {signal:AbortSignal.timeout(4000)})"
                          ".then(r=>process.exit(r.status<500?0:2)).catch(()=>process.exit(2))"], timeout=7)
        checks["internal_api_responsive"] = True
    except Exception:
        checks["internal_api_responsive"] = False
        errors.append("internal API unresponsive")
    try:
        m = memory()
        storage = shutil.disk_usage("/")
        checks["mem_available_mib"] = round(m["MemAvailable"] / 2**20)
        checks["swap_free_mib"] = round(m["SwapFree"] / 2**20)
        checks["disk_free_gib"] = round(storage.free / 2**30, 1)
        if m["MemAvailable"] < 6 * 2**30: errors.append("RAM available below 6 GiB")
        if m["SwapFree"] < 512 * 2**20: errors.append("swap free below 512 MiB")
        if storage.free < 15 * 2**30: errors.append("disk free below 15 GiB")
    except Exception as exc:
        errors.append("resource probe failed: " + type(exc).__name__)
    report = {"timestamp_unix": int(time.time()), "project": PROJECT, "ok": not errors, "errors": errors, "checks": checks}
    OUT.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(OUT.parent, 0o700)
    temp = OUT.with_suffix(".tmp")
    temp.write_text(json.dumps(report, sort_keys=True) + "\n")
    os.chmod(temp, 0o600)
    temp.replace(OUT)
    print(json.dumps(report, sort_keys=True))
    return 0 if not errors else 2

if __name__ == "__main__":
    sys.exit(main())
