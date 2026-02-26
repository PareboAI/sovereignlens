"""Prefect 3 flows and tasks for SovereignLens scrapers.

Each task wraps a scraper's run() + save_to_db() cycle and returns the doc
count saved.  Flows compose tasks into logical groups that map to different
scraping cadences.

Notes
-----
* The OECD scraper uses Scrapy's CrawlerProcess, which starts the Twisted
  reactor.  The reactor can only be started **once per process**, so
  run_oecd_task should not be executed more than once inside the same
  worker process.  Running it inside scrape_all_flow (which is a one-shot
  call) is safe; do not use a ConcurrentTaskRunner that would spawn a
  second OECD task in the same process.
"""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

from loguru import logger
from prefect import flow, task

# Ensure the project root is on sys.path when this module is imported
# directly (e.g. via `poetry run python src/scraper/flows.py`).
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@task(name="run-oecd", retries=3, retry_delay_seconds=30)
def run_oecd_task() -> int:
    """Run the OECD AI spider and persist new documents. Returns doc count."""
    from src.scraper.spiders.oecd_spider import OECDScraper

    source = "oecd_ai"
    logger.info(f"[{source}] Starting scrape")
    t0 = perf_counter()

    scraper = OECDScraper()
    items = scraper.run()
    saved = scraper.save_to_db(items)

    elapsed = perf_counter() - t0
    logger.info(f"[{source}] {saved} docs saved in {elapsed:.1f}s")
    return saved


@task(name="run-bbc", retries=3, retry_delay_seconds=30)
def run_bbc_task() -> int:
    """Fetch BBC News RSS feeds and persist new documents. Returns doc count."""
    from src.scraper.spiders.reuters_rss import BBCRSSScraper

    source = "bbc_news"
    logger.info(f"[{source}] Starting scrape")
    t0 = perf_counter()

    scraper = BBCRSSScraper()
    items = scraper.run()
    saved = scraper.save_to_db(items)

    elapsed = perf_counter() - t0
    logger.info(f"[{source}] {saved} docs saved in {elapsed:.1f}s")
    return saved


@task(name="run-stanford-hai", retries=3, retry_delay_seconds=30)
def run_stanford_task() -> int:
    """Scrape Stanford HAI and persist new documents. Returns doc count."""
    from src.scraper.spiders.stanford_hai_scraper import StanfordHAIScraper

    source = "stanford_hai"
    logger.info(f"[{source}] Starting scrape")
    t0 = perf_counter()

    scraper = StanfordHAIScraper()
    items = scraper.run()
    saved = scraper.save_to_db(items)

    elapsed = perf_counter() - t0
    logger.info(f"[{source}] {saved} docs saved in {elapsed:.1f}s")
    return saved


# ---------------------------------------------------------------------------
# Flows
# ---------------------------------------------------------------------------


@flow(name="scrape-news", log_prints=True)
def scrape_news_flow() -> int:
    """Fast flow: BBC News only.

    Intended cadence: every 6 hours.
    """
    saved = run_bbc_task()
    logger.info(f"[scrape_news_flow] Total docs saved: {saved}")
    return saved


@flow(name="scrape-research", log_prints=True)
def scrape_research_flow() -> int:
    """Slower flow: OECD AI Policy Observatory + Stanford HAI.

    Intended cadence: every Monday at 06:00.
    Tasks run sequentially to avoid Twisted-reactor conflicts.
    """
    oecd_saved = run_oecd_task()
    stanford_saved = run_stanford_task()
    total = oecd_saved + stanford_saved
    logger.info(f"[scrape_research_flow] Total docs saved: {total}")
    return total


@flow(name="scrape-all", log_prints=True)
def scrape_all_flow() -> int:
    """Run all scrapers sequentially and log total docs saved.

    Execution order: BBC → OECD → Stanford HAI.
    OECD is placed after the httpx-based scrapers so the Twisted reactor
    starts only once and doesn't interfere with earlier tasks.
    """
    bbc_saved = run_bbc_task()
    oecd_saved = run_oecd_task()
    stanford_saved = run_stanford_task()

    total = bbc_saved + oecd_saved + stanford_saved
    logger.info(
        f"[scrape_all_flow] Docs saved — "
        f"bbc={bbc_saved} oecd={oecd_saved} stanford={stanford_saved} total={total}"
    )
    return total
