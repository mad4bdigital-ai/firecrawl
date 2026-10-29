#!/usr/bin/env python3
"""Fail-closed checks for the resolved *merged* Firecrawl staging Compose config.

Usage: docker compose ... config --format json | python scripts/ci/verify_staging_compose.py
No host modifications or service launches are performed by this script.
"""
import json
import sys

def fail(message):
    print("STAGING CONTRACT FAILED:", message, file=sys.stderr)
    sys.exit(1)

try:
    cfg = json.load(sys.stdin)
except ValueError as exc:
    fail(f"invalid Docker Compose JSON: {exc}")

if cfg.get("name") != "mad4b-firecrawl-staging":
    fail("Compose project name is not dedicated to staging")

services = cfg.get("services", {})
core = ["api", "playwright-service", "nuq-postgres", "redis", "rabbitmq"]
for name in core:
    if name not in services:
        fail(f"missing {name}")
    s = services[name]
    if s.get("ports"):
        fail(f"{name} publishes host ports")
    if s.get("network_mode") == "host" or s.get("privileged"):
        fail(f"{name} has host/privileged networking")
    if not s.get("mem_limit") or not s.get("cpus"):
        fail(f"{name} has no memory or CPU cap")
    nets = s.get("networks") or {}
    if "backend" not in nets:
        fail(f"{name} must use the private backend network")

networks = cfg.get("networks", {})
if not (networks.get("backend") or {}).get("internal"):
    fail("backend network must block direct external egress")

for name in ("api", "playwright-service"):
    if "egress" not in services[name].get("networks", {}):
        fail(f"{name} lacks explicit egress network")

for name in ("nuq-postgres", "redis", "rabbitmq"):
    if "egress" in services[name].get("networks", {}):
        fail(f"{name} may not join outbound egress network")

api = services["api"]
if api.get("extra_hosts"):
    fail("API inherits root host-gateway alias")
for name in ("api", "playwright-service"):
    if str(services[name].get("environment", {}).get("ALLOW_LOCAL_WEBHOOKS", "")).upper() != "FALSE":
        fail(f"{name} could allow local SSRF targets")
if api.get("environment", {}).get("POSTGRES_PASSWORD") != services["nuq-postgres"].get("environment", {}).get("POSTGRES_PASSWORD"):
    fail("API and PostgreSQL credentials do not match")
if not api.get("environment", {}).get("POSTGRES_PASSWORD"):
    fail("missing staging database credential")
if str(api.get("environment", {}).get("USE_DB_AUTHENTICATION", "")).lower() != "false":
    fail("auth mode changed without a reviewed auth migration")

for name, target in [("nuq-postgres", "/var/lib/postgresql/data"),
                     ("redis", "/data"),
                     ("rabbitmq", "/var/lib/rabbitmq")]:
    mounts = services[name].get("volumes") or []
    if not any(v.get("type") == "volume" and v.get("target") == target for v in mounts):
        fail(f"{name} lacks staging-only persistent data volume {target}")

for name in ("foundationdb", "foundationdb-init"):
    if "foundationdb-experimental" not in services.get(name, {}).get("profiles", []):
        fail(f"{name} must not start in default staging profile")

print("PASS: no published ports, private data network, bounded resources, "
      "separate volumes, safe default backend and no local SSRF")
