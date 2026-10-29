#!/usr/bin/env python3
"""Fail-closed structural check for MAD4B's Firecrawl fork.
The check protects publication jobs, it does not replace source/test security review.
"""
from pathlib import Path
import sys
import yaml

WORKFLOW_DIR = Path(".github/workflows")
UPSTREAM_WRITERS = {
    "deploy-go-service.yaml",
    "deploy-image-staging.yml",
    "deploy-image.yml",
    "deploy-nuq-postgres.yml",
    "deploy-playwright.yml",
    "deploy-redis.yml",
    "eval-prod.yml",
    "ghcr-clean.yml",
    "scrape-evals.yml",
    "npm-audit-claude-remediation.yml",
    "publish-dotnet-sdk.yml",
    "publish-elixir-sdk.yml",
    "publish-go-sdk.yml",
    "publish-java-sdk.yml",
    "publish-js-sdk.yml",
    "publish-php-sdk.yml",
    "publish-python-sdk.yml",
    "publish-ruby-sdk.yml",
    "publish-rust-sdk.yml",
    "sync-skills-catalog.yml",
}
GUARD = "github.repository == 'firecrawl/firecrawl'"


def validate():
    failures = []
    checked = 0
    for name in sorted(UPSTREAM_WRITERS):
        path = WORKFLOW_DIR / name
        if not path.is_file():
            failures.append(f"{name}: expected upstream workflow is missing")
            continue
        try:
            obj = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            failures.append(f"{name}: YAML error: {exc}")
            continue
        jobs = obj.get("jobs", {}) if isinstance(obj, dict) else {}
        if not isinstance(jobs, dict) or not jobs:
            failures.append(f"{name}: no valid jobs")
            continue
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                failures.append(f"{name}/{job_name}: job is not a mapping")
                continue
            expr = str(job.get("if", ""))
            if GUARD not in expr:
                failures.append(f"{name}/{job_name}: upstream repository guard missing")
            checked += 1

    # External repository dispatch can mutate another GitHub repository even
    # when the local workflow has permissions: {} (it may use a PAT secret).
    # Do not permit new dispatch-bearing workflows to evade the explicit
    # upstream-only guarded job allowlist.
    for path in sorted(WORKFLOW_DIR.glob("*")):
        if path.suffix not in (".yml", ".yaml"):
            continue
        source = path.read_text(encoding="utf-8")
        if "createDispatchEvent(" in source and path.name not in UPSTREAM_WRITERS:
            failures.append(
                f"{path}: cross-repository dispatch requires guarded-job review"
            )

    test_paths = list(WORKFLOW_DIR.glob("test-*")) + [WORKFLOW_DIR / "npm-audit.yml"]
    for path in test_paths:
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        if "blacksmith-" in content:
            failures.append(f"{path}: proprietary runner still referenced")
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as exc:
            failures.append(f"{path}: YAML error: {exc}")
    print(f"Release workflows={len(UPSTREAM_WRITERS)}, guarded jobs checked={checked}, "
          f"test workflows checked={len(test_paths)}")
    if failures:
        for msg in failures:
            print("ERROR:", msg, file=sys.stderr)
        return 1
    print("PASS: upstream publishing guarded and CI runner labels portable")
    return 0


if __name__ == "__main__":
    sys.exit(validate())
