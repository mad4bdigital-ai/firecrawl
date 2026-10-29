#!/usr/bin/env bash
# Read-only VPS admission check. No docker build/start/stop, no mutations.
set -euo pipefail
fail=0
warn() { printf 'BLOCKED: %s\n' "$*" >&2; fail=1; }

for bin in docker df awk; do
  command -v "$bin" >/dev/null 2>&1 || warn "missing prerequisite: $bin"
done
if ! docker info >/dev/null 2>&1; then
  warn "Docker daemon is unreachable"
fi
if ! docker compose version >/dev/null 2>&1; then
  warn "Docker Compose plugin is unavailable"
fi

mem_available_kb="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
swap_total_kb="$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)"
swap_free_kb="$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)"
docker_disk_available_kb="$(df -Pk /var/lib/docker | awk 'NR==2 {print $4}')"

printf 'Firecrawl staging preflight (read-only)\n'
printf 'Available RAM: %s MiB\n' "$((mem_available_kb / 1024))"
printf 'Swap free: %s MiB of %s MiB\n' "$((swap_free_kb / 1024))" "$((swap_total_kb / 1024))"
printf 'Docker disk available: %s GiB\n' "$((docker_disk_available_kb / 1024 / 1024))"
printf 'Running Docker containers: %s\n' "$(docker ps -q | wc -l)"

# Conservative admission thresholds for shared VPS with ~50 live containers.
if (( mem_available_kb < 12 * 1024 * 1024 )); then
  warn "less than 12 GiB RAM available for a resource-intensive multi-language build"
fi
if (( docker_disk_available_kb < 55 * 1024 * 1024 )); then
  warn "less than 55 GiB free in Docker's filesystem"
fi
if (( swap_total_kb > 0 && swap_free_kb < 256 * 1024 )); then
  warn "swap nearly exhausted; explicit host capacity remediation/review required"
fi

if (( fail != 0 )); then
  echo 'NO-GO: do not run docker compose up/build on the shared VPS.' >&2
  exit 2
fi
echo 'RESOURCE PREFLIGHT PASS (does not approve staging deployment by itself)'
