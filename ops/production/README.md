# Private Firecrawl production on shared MAD4B VPS

This is a production **internal-only** deployment (authenticated loopback gateway, no Internet-facing API). The root docker-compose.yaml MUST never be deployed alone; it publishes an unauthenticated API.

Use pinned Git commit and `-f docker-compose.yaml -f ops/production/compose.override.yaml`. Dedicated Compose project `mad4b-firecrawl-production`, separate networks, database/queue volumes, no inherited host-gateway alias, 4 GiB API / 2 GiB Playwright memory caps. FoundationDB remains profile-disabled.

Create owner-only non-versioned `/opt/mad4b/firecrawl-production/.env.production` with:
- `FIRECRAWL_PRODUCTION_POSTGRES_PASSWORD` (strong random)
- `FIRECRAWL_PRODUCTION_NGINX_CONFIG=/opt/mad4b/firecrawl-production/nginx.conf`
- `FIRECRAWL_PRODUCTION_HTPASSWD=/opt/mad4b/firecrawl-production/auth/.htpasswd`
- `FIRECRAWL_PRODUCTION_LOCAL_PORT=13082`

Create root-owned 0600 basic-auth hash file using `openssl passwd -apr1` and account `firecrawl`; store the plaintext credential only in a separate 0600 secret store (not GitHub, no logs). The provided nginx.conf is public template with NO secrets. HTTP Basic Auth is acceptable **only on loopback**; do not bind 0.0.0.0, expose through Coolify or Cloudflare, or forward plaintext credentials over an unencrypted link. For remote access, use encrypted SSH tunnel into localhost or a separately reviewed TLS/OAuth gateway. The API itself has `USE_DB_AUTHENTICATION=false` and must NEVER be reachable except through this gateway.

## Release process
1. Validate exact commit, active SSH operator, capacity, swap, Docker health and disk. Require explicit Production deployment authority. Keep Production services untouched.
2. Use `docker compose --env-file .env.production -f ... config --format json | python3 scripts/ci/verify_production_compose.py` and inspect output without exposing secrets.
3. Build only exact pinned code. Build-time CPU/RAM may exceed runtime caps; monitor shared host pressure. Do not ignore a build or startup failure.
4. Start with `docker compose ... up -d api gateway`; check all 6 services are running and healthy, no unexpected port exposures, persistent volumes and auth: 401 without credentials, 200 for the private gateway health, and authorized API readiness. Do not claim Production operational before live readiness checks.
5. Record deployed SHA, image digests, health results, rollback path and credential-store location in a private root-only receipt. Keep a rollback window and storage.
6. For rollback, use same project and files `docker compose ... stop`, or pin old code and rebuild. NEVER `down --volumes`, system-wide prune, or change Coolify routing.

The service is useful internally on the VPS. Public access and a custom domain require a separately secured ingress configuration and associated tests.
