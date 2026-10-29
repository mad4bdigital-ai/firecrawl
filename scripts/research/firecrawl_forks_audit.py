#!/usr/bin/env python3
"""Read-only, resumable GitHub fork inventory. Standard library only."""
import argparse
import csv
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UPSTREAM = "firecrawl/firecrawl"
API = "https://api.github.com"
CATEGORIES = {
    "auth-security": ("auth", "token", "tenant", "security", "ssrf", "permission"),
    "scraping-browser": ("scrap", "playwright", "puppeteer", "browser", "hero"),
    "search": ("search", "searx", "google", "brave"),
    "pdf-ocr": ("pdf", "ocr", "docling", "document", "parse"),
    "queues": ("queue", "worker", "nuq", "postgres", "rabbitmq"),
    "cache": ("redis", "cache", "index"),
    "deployment": ("compose", "docker", "helm", "kubernetes", "self_host"),
    "monitoring": ("monitor", "metric", "telemetry", "health", "logging"),
    "agents-mcp": ("mcp", "agent", "skill", "cli"),
}
def save_json(path, obj):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)

def gh(path, token):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "mad4b-firecrawl-forks-audit/1.0",
        "Authorization": "Bearer " + token,
    }
    for attempt in range(6):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(API + path, headers=headers), timeout=50
            ) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:180]
            if exc.code in (403, 429):
                remaining = exc.headers.get("X-RateLimit-Remaining", "")
                retry_after = exc.headers.get("Retry-After")
                reset = int(exc.headers.get("X-RateLimit-Reset") or 0)
                if remaining == "0":
                    delay = min(3900, max(2, reset - int(time.time()) + 3))
                else:
                    delay = min(120, int(retry_after) if retry_after and retry_after.isdigit() else 12 * (attempt + 1))
                if attempt < 5:
                    print(f"Rate limit/abuse prevention ({exc.code}): sleep {delay}s", flush=True)
                    time.sleep(delay)
                    continue
            if exc.code in (500, 502, 503, 504) and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"GitHub API {exc.code}: {path}: {detail}") from exc
    raise RuntimeError("GitHub API retries exhausted")

def write_csv(file, items, keys):
    with file.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(items)

def fork_row(repo):
    return {
        "name": repo["full_name"],
        "url": repo["html_url"],
        "branch": repo.get("default_branch") or "main",
        "stars": repo.get("stargazers_count", 0),
        "pushed_at": repo.get("pushed_at") or "",
        "created_at": repo.get("created_at") or "",
        "archived": bool(repo.get("archived")),
        "size_kb": repo.get("size", 0),
        "description": repo.get("description") or "",
    }

def collect(out, token, max_pages):
    store = out / "forks.json"
    progress = out / "progress.json"
    rows = json.loads(store.read_text(encoding="utf-8")) if store.exists() else []
    state = json.loads(progress.read_text(encoding="utf-8")) if progress.exists() else {}
    if state and state.get("paging_scheme") != "oldest-v2":
        raise RuntimeError("Old fork pagination checkpoint is unsafe; choose a new --out directory")
    current = int(state.get("next_page", 1))
    complete = bool(state.get("complete", False))
    seen = {row["name"] for row in rows}
    run_pages = 0
    while not complete and (max_pages == 0 or run_pages < max_pages):
        repos = gh(f"/repos/{UPSTREAM}/forks?sort=oldest&per_page=100&page={current}", token)
        if not isinstance(repos, list):
            raise ValueError("Unexpected forks payload")
        for repo in repos:
            if repo["full_name"] not in seen:
                rows.append(fork_row(repo))
                seen.add(repo["full_name"])
        complete = len(repos) < 100
        current += 1
        run_pages += 1
        save_json(store, rows)
        save_json(progress, {"paging_scheme": "oldest-v2", "complete": complete,
                             "next_page": current, "count": len(rows)})
        print(f"Forks page {current-1}: {len(repos)}; unique {len(rows)}; pagination_complete={complete}", flush=True)
    # GitHub may list fewer accessible forks than the repository metadata count.
    # Never claim full coverage when pagination yields far fewer unique repositories.
    upstream = gh(f"/repos/{UPSTREAM}", token)
    expected = int(upstream.get("forks_count") or 0)
    fraction = len(rows) / expected if expected else None
    coverage_ok = bool(complete and (not expected or fraction >= 0.98))
    save_json(progress, {"paging_scheme": "oldest-v2", "complete": coverage_ok,
                         "pagination_exhausted": complete, "next_page": current,
                         "count": len(rows), "upstream_reported_forks": expected,
                         "coverage_fraction": fraction})
    if complete and not coverage_ok:
        print(f"WARNING: GitHub reports {expected} forks but only {len(rows)} "
              f"unique repositories were returned; audit is INCOMPLETE", file=sys.stderr)
    return rows, coverage_ok

def datetime_score(value):
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0

def score(row):
    # Discovery ranking only. NOT a quality or security score.
    return (min(int(row.get("stars") or 0), 1000) * 3 +
            datetime_score(row.get("pushed_at")) / 1e7 +
            (0 if not row.get("archived") else -100))

def compare(row, token):
    owner = row["name"].split("/")[0]
    head = urllib.parse.quote(owner + ":" + row["branch"], safe=":")
    try:
        result = gh(f"/repos/{UPSTREAM}/compare/main...{head}", token)
        files = [f.get("filename", "") for f in result.get("files", [])]
        flags = sorted(k for k, fragments in CATEGORIES.items()
                       if any(fragment in f.lower() for fragment in fragments for f in files))
        return {
            "name": row["name"], "url": row["url"], "stars": row["stars"],
            "status": result.get("status", "unknown"),
            "ahead": result.get("ahead_by", 0), "behind": result.get("behind_by", 0),
            "changed_files_returned": len(files), "file_list_may_be_truncated": len(files) >= 300,
            "discovery_tags": ",".join(flags), "sample_files": ";".join(files[:35]),
            "error": "",
        }
    except Exception as exc:
        return {"name": row["name"], "url": row["url"], "status": "error",
                "ahead": "", "behind": "", "error": str(exc)[:260]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="fork-audit-results")
    parser.add_argument("--max-pages", type=int, default=0, help="0 = enumerate all fork pages")
    parser.add_argument("--compare-limit", type=int, default=150)
    parser.add_argument("--compare-offset", type=int, default=0)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        sys.exit("GITHUB_TOKEN required (read-only public GitHub API scope)")
    out = pathlib.Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    forks, complete = collect(out, token, args.max_pages)
    write_csv(out / "forks.csv", forks,
              ["name", "url", "branch", "stars", "pushed_at", "created_at",
               "archived", "size_kb", "description"])
    ordered = sorted(forks, key=score, reverse=True)
    subset = ordered[args.compare_offset:args.compare_offset + args.compare_limit]
    cache = out / "comparisons.json"
    results = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    for i, row in enumerate(subset, 1):
        if row["name"] not in results:
            results[row["name"]] = compare(row, token)
            save_json(cache, results)
        if i % 10 == 0:
            print(f"Compared {i}/{len(subset)}", flush=True)
    comparisons = list(results.values())
    write_csv(out / "comparisons.csv", comparisons,
              ["name", "url", "stars", "status", "ahead", "behind",
               "changed_files_returned", "file_list_may_be_truncated",
               "discovery_tags", "sample_files", "error"])
    divergent = [r for r in comparisons if isinstance(r.get("ahead"), int) and r["ahead"] > 0]
    divergent.sort(key=lambda r: -r["ahead"])
    report = [
        "# Firecrawl Fork Inventory", "",
        f"Upstream: https://github.com/{UPSTREAM}",
        f"Forks enumerated: **{len(forks)}**",
        f"Full enumeration: **{'YES' if complete else 'NO'}**",
        f"Fork HEADs compared: **{len(comparisons)}**",
        f"Forks with independent commits: **{len(divergent)}**", "",
        "## Forks requiring source-level review", "",
        "| Fork | Ahead | Behind | Filename-derived discovery tags |",
        "|---|---:|---:|---|",
    ]
    for row in divergent[:100]:
        report.append(f"| [{row['name']}]({row['url']}) | {row['ahead']} | "
                      f"{row['behind']} | {row.get('discovery_tags', '')} |")
    report.extend([
        "", "## Limitations", "",
        "- All forks are enumerated via the original repository's /forks endpoint.",
        "- Only the selected head range is compared on this run; use offset/limit for subsequent batches.",
        "- GitHub compare file lists can truncate at 300; inspect large divergences separately.",
        "- Filename keywords signal candidates, not verified feature implementation.",
        "- Nothing is merged, checked out on VPS, or deployed by this program.",
    ])
    (out / "summary.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Inventory complete={complete}, forks={len(forks)}, "
          f"comparisons={len(comparisons)}, divergent={len(divergent)}", flush=True)
    if not complete:
        sys.exit("INCOMPLETE fork census: reconcile upstream fork count before acceptance")

if __name__ == "__main__":
    main()
