# Firecrawl fork feature shortlist — verified GitHub audit, 2026-10-29

## Completed census (run 40881278959)

- Workflow: https://github.com/mad4bdigital-ai/firecrawl/actions/runs/40881278959
- Pagination: 105 pages, `sort=oldest`, 10,488 **unique fork records**.
- Comparison sample: 150 prioritized fork HEADs, **15 with independent commits**, 131 behind only, 2 identical, 2 comparison errors (404).
- The upstream `forks_count` metadata returned 10,376 during this run; counts can lag, so GitHub pagination exhaustion and zero duplicates are primary evidence of a completed census at a single point in time.
- GitHub compare changed-file lists may be truncated at 300. A positive `ahead` only identifies code divergence; it does **not** prove a feature is safe or absent from newer upstream.
- The two 404 comparisons are `oga35767-eng/firecrawl` and `orbisai0security/firecrawl`; categorize as unresolved, not feature-free.

## Verified divergent candidates

| Fork | Ahead / behind | Observed specific change | Intake verdict |
|---|---:|---|---|
| [tekgnosis-net/firecrawl](https://github.com/tekgnosis-net/firecrawl) | 49 / 445 | Adds `apps/camoufox-service-ts`, Camoufox browser engine, metrics, tests and upstream-sync automation | **Explore optional engine separately**; browser binary, experimental package, egress policy and failure modes require QA; not a default deployment dependency |
| [StephenQiu30/firecrawl](https://github.com/StephenQiu30/firecrawl) | 11 / 396 | Adds Playwright proxy-header/request handling tests, logger redaction, DNS/SSRF-oriented changes, local deployment guides | **High-priority security review**; isolate portable tests and safeguards; never copy its machine-specific allowlist |
| [grantjr1842/firecrawl](https://github.com/grantjr1842/firecrawl) | 21 / 1,049 | Adds admin panel, bench harness, SSRF tests, queue failover tests and sizeable alternate anti-bot stack | **Selective source review** of benchmarks, tests and admin monitoring; avoid wholesale queue/storage/anti-bot replacements |
| [ice-zeus/firecrawl](https://github.com/ice-zeus/firecrawl) | 20 / 251 | PULSE tenant identity routing, never-cache and proxy state handling with private external coordinator | **Design reference only** until dependency/licensing and signature trust models independently available |
| [loorisr/firecrawl-searxng](https://github.com/loorisr/firecrawl-searxng) | 40 / 3,835 | Historical SearXNG integration | **Do not duplicate**; current official Compose supports `SEARXNG_ENDPOINT` |
| [devflowinc/firecrawl-simple](https://github.com/devflowinc/firecrawl-simple) | 61 / 4,951 | Hero browser service, lightweight v1-only self-host design, removes SaaS and AI subsystems | **Architecture reference only** due severe API drift |
| [MitsuhaYuki/firecrawl-docker-image](https://github.com/MitsuhaYuki/firecrawl-docker-image) | 5 / 2,683 | Workflow/image build changes | **CI pattern reference**; do not adopt old images |

Other sampled forks ahead of upstream: `sugarforever/coolcrawl` (14), `DLozF/firecrawl` (10), `oladapodev/fireflare` (8), `markusknudtsen-droid/firecrawl` (3), `alphavictorechotangotango07/firecrawl` (2), `JesseGauntlet/firecrawl-searxng` (1), `Balerion107/firecrawl` (1), `HenryBui21/firecrawl` (1). They still require source-level assessment; minor divergence alone is not proof of value.

## Recommended upstream-compatibility phases

1. **CI and fork isolation first**: draft [PR #4](https://github.com/mad4bdigital-ai/firecrawl/pull/4) guards inherited release workflows and replaces proprietary runner labels. Wait for green native API build, unit tests and policy preflight before merge.
2. **Security and portability**: review `StephenQiu30` proxy header and logger tests against the latest upstream source. Promote tests first; only port code when latest upstream is missing behavior.
3. **Operations**: review the benchmark harness, admin reporting and health metrics in `grantjr1842` and the separate `tekgnosis-net/firecrawl-dashboard` (the latter is *not* a Firecrawl fork).
4. **Optional browser engine**: consider `tekgnosis-net` Camoufox only behind an explicit feature flag and with bounded concurrency, trusted-host policy, egress rules and controlled tests.
5. **Avoid needless duplication**: SearXNG is already upstream; PULSE private coordinator cannot be copied safely as a standalone feature.

## Remaining coverage

- The inventory enumerated the fork list, but only 150 out of 10,488 HEADs were compared against current upstream.
- Run additional comparison batches (current workflow accepts `compare_offset` / `compare_limit`) under GitHub API rate limits, persist and aggregate their artifacts before declaring full feature coverage.
- Validate each selected patch's tests, license, current-upstream parity, health, configuration, dependency identity and rollback behavior.
- No repo merge, image publication, VPS installation or production mutation is authorized by this shortlist.
