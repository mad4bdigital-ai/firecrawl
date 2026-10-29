# Private Firecrawl production on shared MAD4B VPS

This is a production **internal-only** deployment (authenticated loopback gateway, no Internet-facing API). The root docker-compose.yaml MUST never be deployed alone; it publishes an unauthenticated API.

Use pinned Git commit and `-f docker-compose.yaml -f ops/production/compose.override.yaml`. Dedicated Compose project `mad4b-firecrawl-production`, separate networks, database/queue volumes, no inherited host-gateway alias, 4 GiB API / 2 GiB Playwright memory caps. FoundationDB remains profile-disabled.

Create owner-only non-versioned `/opt/mad4b/firecrawl-production/.env.production` with:
- `FIRECRAWL_PRODUCTION_POSTGRES_PASSWORD` (strong random)
- `FIRECRAWL_PRODUCTION_NGINX_CONFIG=/opt/mad4b/firecrawl-production/nginx.conf`
- `FIRECRAWL_PRODUCTION_HTPASSWD=/opt/mad4b/firecrawl-production/auth/.htpasswd`
- `FIRECRAWL_PRODUCTION_LOCAL_PORT=13082`

Create root-owned 0600 basic-auth hash file using `openssl passwd -apr1` and account `firecrawl`; store the plaintext credential only in a separate 0600 secret store (not GitHub, no logs). The provided nginx.conf is public template with NO secrets. HTTP Basic Auth is acceptable **only on loopback**; do not bind 0.0.0.0, expose through Coolify or Cloudflare, or forward plaintext credentials over an unencrypted link. For remote access, use encrypted SSH tunnel into localhost or a separately reviewed TLS/OAuth gateway. The API itself has `USE_DB_AUTHENTICATION=false` and must NEVER be reachable except through this gateway.

## Remote-build source authority

The API is intentionally NOT built on the shared VPS. GitHub Actions workflow `.github/workflows/firecrawl-fork-api-image.yml` builds the exact merged commit in the fork and pushes a SHA-tagged linux/amd64 image to `ghcr.io/mad4bdigital-ai/firecrawl-api`. Its post-build inspection must confirm the embedded source SHA and required runtime files. Set `FIRECRAWL_PRODUCTION_API_SHA` to that exact 40-character SHA only after publication and registry accessibility are independently confirmed. Never use a floating tag or an upstream-vendor image as a substitute. If GHCR is private/unreachable, do not bypass by rebuilding on the VPS during low disk/swap headroom. A separate registry permission/visibility review may be required.

## Release process
1. Validate exact commit, active SSH operator, capacity, swap, Docker health and disk. Require explicit Production deployment authority. Keep Production services untouched.
2. Use `docker compose --env-file .env.production -f ... config --format json | python3 scripts/ci/verify_production_compose.py` and inspect output without exposing secrets.
3. Build only exact pinned code. Build-time CPU/RAM may exceed runtime caps; monitor shared host pressure. Do not ignore a build or startup failure.
4. Start with `docker compose ... up -d api gateway`; check all 6 services are running and healthy, no unexpected port exposures, persistent volumes and auth: 401 without credentials, 200 for the private gateway health, and authorized API readiness. Do not claim Production operational before live readiness checks.
5. Record deployed SHA, image digests, health results, rollback path and credential-store location in a private root-only receipt. Keep a rollback window and storage.
6. For rollback, use same project and files `docker compose ... stop`, or pin old code and rebuild. NEVER `down --volumes`, system-wide prune, or change Coolify routing.

The service is useful internally on the VPS. Public access and a custom domain require a separately secured ingress configuration and associated tests.

## Internal consumers and operational monitoring

Firecrawl is **not** published on a public domain. Host-native clients may use the loopback-only authenticated `http://127.0.0.1:13082`; off-host clients must connect using an encrypted SSH tunnel or a separately reviewed TLS/OAuth gateway. Never send Basic credentials over an untrusted link.

Docker clients may join the isolated `mad4b-firecrawl-production_consumers` bridge, which contains the **gateway only**. Never join the `frontdoor`, `backend`, or `egress` networks. Once a consumer is separately approved, attach only its application container using `docker network connect mad4b-firecrawl-production_consumers <approved-client-container>`. Use `http://gateway:8080/v1/scrape` with HTTP Basic auth stored in the consumer's secrets store. Joining a container to this network is a separate security-affecting operator action: no client is automatically authorized or attached. Production identity and access mapping must be reviewed first. Individual consumer accounts must be provisioned with unique, revocable credentials; do not distribute the owner-only bootstrap credential.

To check the gateway authentication boundary and run a bounded functional load test without exposing production credentials:

```sh
python3 ops/production/auth-load-smoke.py --requests 4 --concurrency 2
```

The smoke script temporarily installs a random test identity in the existing root-protected htpasswd file, sends requests through the real gateway, and removes that identity in a `finally` block. It never prints passwords and accepts a maximum of 8 requests at 2 concurrent jobs. Run only from the VPS itself; avoid peak traffic.

Monitoring is fail-visible and read-only. After an exact-SHA release, install the two systemd units from this directory to `/etc/systemd/system/`, run `systemctl daemon-reload`, `systemctl enable --now mad4b-firecrawl-watch.timer`, then `systemctl start mad4b-firecrawl-watch.service`. Every 5 minutes the watcher records a sanitized result in the journal and `/var/lib/mad4b-firecrawl-monitor/status.json`. It checks all six services, internal API readiness, gateway 200/401 behavior, RAM/Swap/disk reserves, and service health. Failures exit nonzero. This is **local monitoring only**, not an external notification channel or a long-running soak test. Do not configure external alert forwarding without separately approved routing.

Do not use `docker network connect` on database or raw-API containers; keep Production ingress private. A successful gateway test does not imply that any particular MAD4B application has already been integrated.

## Email incident routing

Firecrawl's watchdog has `OnFailure=mad4b-alert-handler@%n.service`, using the VPS's existing MAD4B root-owned SMTP/Resend dispatcher and its approved recipient. No credentials enter the repository. The handler deduplicates service failure events for 15 minutes. Verify with `systemctl show -p OnFailure mad4b-firecrawl-watch.service`, and test existing channel via `/opt/mad4b-alerts/bin/mad4b-alert-dispatcher-v2.py check`. The `send-test` command sends a real test email, not a simulated failure. The existing shared dispatcher currently uses a generic "Backup Service Failure" subject on all failures; correct that in the shared dispatcher's source authority, not in this app's repository.
