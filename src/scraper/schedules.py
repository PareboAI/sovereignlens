"""Prefect 3 deployment schedules for SovereignLens scrapers.

Run this module directly to start both deployments in a single long-lived
process that polls the Prefect API for scheduled runs:

    poetry run python src/scraper/schedules.py

Deployments
-----------
scrape-news-6h       scrape_news_flow    every 6 hours           (0 */6 * * *)
scrape-research-weekly  scrape_research_flow  every Monday 06:00  (0 6 * * 1)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when run as a script.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from prefect import serve  # noqa: E402  (import after path setup)

from src.scraper.flows import scrape_news_flow, scrape_research_flow  # noqa: E402

NEWS_DEPLOYMENT = scrape_news_flow.to_deployment(
    name="scrape-news-6h",
    cron="0 */6 * * *",
    description="Scrape BBC News RSS feeds every 6 hours.",
    tags=["news", "bbc"],
)

RESEARCH_DEPLOYMENT = scrape_research_flow.to_deployment(
    name="scrape-research-weekly",
    cron="0 6 * * 1",
    description="Scrape OECD AI Observatory and Stanford HAI every Monday at 06:00.",
    tags=["research", "oecd", "stanford-hai"],
)


if __name__ == "__main__":
    serve(NEWS_DEPLOYMENT, RESEARCH_DEPLOYMENT)
