# Firecrawl fork intake — 2026-10-29

## Objective and scope

Build a maintainable MAD4B self-hosted Firecrawl deployment. Do not install an old fork as a replacement for the upstream source, and do not cherry-pick code without proving differences, current upstream parity, license compatibility, and tests.

- Owner fork: https://github.com/mad4bdigital-ai/firecrawl
- Upstream: https://github.com/firecrawl/firecrawl
- Owner fork baseline before synchronization: `5cc12e43f0bc0c5a771257ae983374033a0b072b`
- Upstream pin: `33f295dc1f09133c02fc1e096d6685abda3464a7`
- Upstream-only commits at comparison: 1,126; owner fork ahead: 0.
- Sync PR: https://github.com/mad4bdigital-ai/firecrawl/pull/2 (draft, unmerged at intake).
- Existing CI PR: https://github.com/mad4bdigital-ai/firecrawl/pull/1 (do not silently discard).

## Audited candidate forks

These are *verified divergence counts*, not feature acceptance.

| Repository | Ahead of upstream | Behind | Source-backed feature or observation | Decision |
| --- | ---: | ---: | --- | --- |
| [devflowinc/firecrawl-simple](https://github.com/devflowinc/firecrawl-simple) | 61 | 4,951 | README says it removes billing/AI features and replaces browser workflow with Hero; only narrower v1 API | **Research patterns only**; obsolete large fork |
| [ice-zeus/firecrawl](https://github.com/ice-zeus/firecrawl) | 20 | 251 | PULSE.md indexes signed tenant identity, proxy routing and never-cache protections; depends on private Pulse coordinator | **Design review** only until private dependencies and trust boundaries are mapped |
| [Agentic-Assets/firecrawl](https://github.com/Agentic-Assets/firecrawl) | 1,286 | 178 | Agent tooling, local operation guidance, Docling/PDF and optional model routing, heavy internal project customization | **Isolate portable parts**; do not merge entire fork |
| [loorisr/firecrawl-searxng](https://github.com/loorisr/firecrawl-searxng) | 40 | 3,835 | SearXNG compatibility, patched Docker/images, separate browser service; its own README says most changes arrived upstream | **Do not duplicate SearXNG**; current upstream Compose already exposes SEARXNG_ENDPOINT |
| [MitsuhaYuki/firecrawl-docker-image](https://github.com/MitsuhaYuki/firecrawl-docker-image) | 5 | 2,683 | Image build workflows | **CI inspiration only**, not deploy artifacts as-is |
| [EveryInc/firecrawl](https://github.com/EveryInc/firecrawl) | 0 | 2,591 | No commits beyond current upstream | Ignore as feature source |
| [Chroma01/firecrawl](https://github.com/Chroma01/firecrawl) | 0 | 0 | Identical at audit time | Ignore as feature source |
| [Zekiog/firecrawl](https://github.com/Zekiog/firecrawl) | 0 | 852 | No commits beyond current upstream | Ignore as feature source |
| [mad4bdigital-ai/firecrawl](https://github.com/mad4bdigital-ai/firecrawl) | 0 | 1,126 | Owner fork before sync | Sync with upstream |

Counts are point-in-time and may change with upstream activity.

Companion projects (NOT upstream Firecrawl forks):
- [obeone/firecrawl-ui](https://github.com/obeone/firecrawl-ui): Browser-based v2 scrape/crawl/search/map/extract client; auth and API key handling need independent review.
- [tekgnosis-net/firecrawl-dashboard](https://github.com/tekgnosis-net/firecrawl-dashboard): Proxy, monitoring, dashboards, SQLite storage, alerts; ensure client secrets, target URLs and traffic metadata are protected.

## Full GitHub fork inventory

Run `scripts/research/firecrawl_forks_audit.py` (read-only) from GitHub Actions using `.github/workflows/firecrawl-fork-audit.yml` or locally with a token. This enumerates the **actual forks of firecrawl/firecrawl** via `/repos/firecrawl/firecrawl/forks`, not an unrelated name search.

Outputs:
- `forks.csv` / `forks.json` — every enumerated fork and metadata
- `comparisons.csv` / `comparisons.json` — selected fork HEAD ahead/behind and filename-based discovery hints
- `progress.json` — checkpoint of fork pagination
- `summary.md` — candidate summary and explicit completion flag

The default comparison batch checks the first 150 discovery-ranked forks. **Full enumeration is not full code review.** Compare the rest with later offset/limit batches; GitHub compare file listings can truncate at 300 files. Any promising candidate requires manual commit review and a focused regression test.

## Candidate evaluation gates

1. Feature must be absent from the pinned official upstream or materially better in a reproducible benchmark.
2. No reliance on closed/private services, credentials or proprietary scraping bypass without explicit agreement.
3. Source license, dependencies, API schemas, TypeScript version and runtime compatibility must pass.
4. Must have unit tests, an opt-in feature flag, security isolation and rollback plan.
5. Avoid SaaS-only promises: the public README covers features that may require separate services and providers in self-hosted mode.

## VPS discovery and deployment hold

Read-only infrastructure checks on the target VPS returned:
- 8 vCPU, approximately 31 GiB RAM, approximately 18 GiB currently available
- 4 GiB swap virtually full (without sustained swapping at the sampled moment)
- 86 GiB filesystem available, /opt/hostinger-migrations ~201 GiB (not approved for deletion)
- Docker 29.9.0, 48 running containers; host port 3002 available at observation
- UFW inactive; do not expose the unauthenticated stock API on `0.0.0.0`
- Several Oct 27 cgroup-specific OOM events in an unrelated service with 256 MiB MemoryMax

**No deploy until**: pin release/commit; review Compose; create isolated private network; TLS + gateway authentication; loopback bind; persistent Postgres/Redis/RabbitMQ volumes + verified backups; CPU/RAM ceilings and low browser concurrency; logging/retention; smoke tests; and rollback rehearsal. Production services must remain unchanged.

## Current acceptance status

- Upstream branch created: **yes**.
- Sync draft PR: **yes**, checks pending when created.
- Fork inventory script and GitHub workflow: **proposed on research branch**, not yet merged.
- Full fork inventory execution: **pending evidence from GitHub Actions**.
- Selective cherry-pick: **none approved**.
- VPS deployment: **not started**.
