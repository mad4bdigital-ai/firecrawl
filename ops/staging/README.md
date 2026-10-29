# Firecrawl isolated VPS staging (no public listener)

This is a **reviewable configuration**, not authorization to deploy to a production host. The validated source baseline before this PR was `main` commit `5ab4d5fe591399e979290ecbc8c8adda4b865a66`. Pin the exact new source commit after merging this PR. Do not deploy a moving branch.

## Why a separate Compose overlay?

The upstream root `docker-compose.yaml` publishes an unauthenticated API to all host interfaces on port 3002, uses default PostgreSQL credentials, and has no persistent storage for NuQ PostgreSQL, Redis or RabbitMQ. Never deploy the root file alone on this VPS. This overlay removes all host bindings (using Docker Compose `!reset`), separates internal data and scraper egress networks, requires a unique database password, persists queue state, disables optional FoundationDB by profile and caps resources.

Only API and Playwright have a dedicated outbound bridge; PostgreSQL, Redis and RabbitMQ are on an `internal: true` network. No reverse-proxy labels, DNS names, ingress routes, external volume mounts, or generic `docker compose up -d` are included.

| Service | Memory cap | CPU cap |
|---|---:|---:|
| API and workers | 4 GiB | 2.0 |
| Playwright | 2 GiB | 1.5 |
| NuQ Postgres 17 | 1 GiB | 0.75 |
| RabbitMQ | 768 MiB | 0.65 |
| Redis | 256 MiB | 0.4 |

## VPS preflight (October 29 snapshot)

Host `srv2030908`: 31 GiB RAM, approximately 17 GiB available, **4 GiB of 4 GiB swap already used**, 82 GiB free on root, 8 CPU cores, 50 containers running. Docker Compose v5.6.0 supports `!reset`. No Firecrawl containers are present. CPU and current memory pressure are low, but staging build of Chromium, Rust, Go and API can spike resources. The full swap plus shared-production load is a reason to require a separate runtime go/no-go before starting containers. Do not forcibly clear swap or prune Docker images on a shared host.

## Preparation (manual gate after CI)

1. Use a separate checkout under a staging-owned directory with `git fetch` and checkout the exact reviewed, tested commit. Do not change existing Coolify projects or Docker networks.
2. Provision a staging-only secret in a **non-versioned, owner-readable local file**, e.g. `/opt/mad4b/firecrawl-staging/.env.staging` (mode 0600), containing `FIRECRAWL_STAGING_POSTGRES_PASSWORD=<strong-unique-generated-secret>`. Never print or commit the secret. Do not reuse production DB credentials.
3. Check current swap/memory/disk, container count and port exposure again. Abort launch if the VPS has developed memory pressure, low disk, or uncontrolled container restarts. Ensure staging's build memory budget will not harm production.
4. Run this **read-only Compose config preflight** from the checkout, substituting the local env file path:

```bash
docker compose --env-file /opt/mad4b/firecrawl-staging/.env.staging \
  -f docker-compose.yaml -f ops/staging/compose.override.yaml \
  config --format json | python3 scripts/ci/verify_staging_compose.py
```

5. Only after a separate explicit staging-start approval and resource check, start **the API target**, not every service in the root file:

```bash
docker compose --env-file /opt/mad4b/firecrawl-staging/.env.staging \
  -f docker-compose.yaml -f ops/staging/compose.override.yaml \
  up -d --build api
```

6. Readiness is accessible **inside** the API container (there is no public or host-bound port). Example:

```bash
docker compose --env-file /opt/mad4b/firecrawl-staging/.env.staging \
  -f docker-compose.yaml -f ops/staging/compose.override.yaml \
  exec -T api node -e "fetch('http://127.0.0.1:3002/v0/health/readiness').then(r=>{console.log(r.status);process.exit(r.ok?0:1)}).catch(()=>process.exit(1))"
```

Do not put staging's unauthenticated API directly behind public routing, a Cloudflare tunnel or a shared public network. Before any external access, add a reviewed authentication gateway, TLS and ingress deny-by-default policy.

## Stop and rollback

The project name is `mad4b-firecrawl-staging`, isolating Compose-owned containers, networks and volumes from other environments. Stop using the same explicit `-f` files and `--env-file` arguments plus `down --remove-orphans`, **without `--volumes`**. Keep persistent volumes for recovery, and back them up before destructive schema changes. Recover by checking out the previous approved exact source SHA and rebuilding only this dedicated project. Never use host-wide `docker system prune`, `volume prune` or changes to the shared reverse proxy.

## Acceptance criteria before first container start

- The staging Compose CI is green on its exact source commit.
- Config validator reports no public ports, dedicated internal and egress networks, correct Postgres credentials, persistent storage and limits.
- Current 4 GiB swap saturation has been assessed and the build is not expected to starve other 50 containers.
- Staging launch is explicitly authorized; Production apps/ports/networks remain untouched.
