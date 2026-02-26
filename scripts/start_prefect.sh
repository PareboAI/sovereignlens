#!/usr/bin/env bash
# start_prefect.sh — Start the Prefect server then serve scheduled deployments.
#
# Usage:
#   bash scripts/start_prefect.sh
#
# What it does:
#   1. Starts `prefect server start` in the background.
#   2. Polls http://localhost:4200/api/health until the server is ready
#      (up to 60 seconds).
#   3. Runs `src/scraper/schedules.py` in the foreground, which calls
#      prefect.serve() with both cron deployments (blocking).
#   4. On exit / Ctrl-C, kills the background server process.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFECT_HEALTH="http://localhost:4200/api/health"

# ---------------------------------------------------------------------------
# Cleanup: kill the background server when this script exits for any reason.
# ---------------------------------------------------------------------------
SERVER_PID=""

cleanup() {
    if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
        echo ""
        echo "Stopping Prefect server (PID $SERVER_PID)..."
        kill "$SERVER_PID"
    fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# 1. Start Prefect server in the background.
# ---------------------------------------------------------------------------
echo "Starting Prefect server..."
prefect server start &
SERVER_PID=$!

# ---------------------------------------------------------------------------
# 2. Wait until the health endpoint responds.
# ---------------------------------------------------------------------------
echo "Waiting for Prefect server to be ready at $PREFECT_HEALTH ..."
RETRIES=30
INTERVAL=2

for i in $(seq 1 $RETRIES); do
    if curl -sf "$PREFECT_HEALTH" >/dev/null 2>&1; then
        echo "Prefect server is ready (attempt $i/${RETRIES})."
        break
    fi

    if [[ $i -eq $RETRIES ]]; then
        echo "ERROR: Prefect server did not become ready after $((RETRIES * INTERVAL))s." >&2
        exit 1
    fi

    echo "  Not ready yet (attempt $i/${RETRIES}), retrying in ${INTERVAL}s..."
    sleep "$INTERVAL"
done

# ---------------------------------------------------------------------------
# 3. Start scheduled deployments (blocking — runs until Ctrl-C).
# ---------------------------------------------------------------------------
echo ""
echo "Starting scheduled deployments..."
echo "  scrape-news-6h       → every 6 hours (0 */6 * * *)"
echo "  scrape-research-weekly → every Monday 06:00 (0 6 * * 1)"
echo ""
cd "$ROOT_DIR" && poetry run python src/scraper/schedules.py
