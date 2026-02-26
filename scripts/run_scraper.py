#!/usr/bin/env python
"""Run SovereignLens scrapers.

Usage:
    poetry run python scripts/run_scraper.py --source oecd
    poetry run python scripts/run_scraper.py --source reuters
    poetry run python scripts/run_scraper.py --source worldbank
    poetry run python scripts/run_scraper.py --source stanford_hai
    poetry run python scripts/run_scraper.py --source all

    # Run all scrapers through Prefect (records flow/task runs in Prefect UI)
    poetry run python scripts/run_scraper.py --prefect

Note on --source all
--------------------
httpx-based scrapers (reuters, worldbank, stanford_hai) run without touching
the Twisted reactor. The OECD scraper is Scrapy-based and starts the Twisted
reactor via CrawlerProcess. Run individual --source flags to combine scrapers
as needed.

Note on --prefect
-----------------
Calls scrape_all_flow() which runs bbc → oecd → stanford_hai sequentially
through Prefect task tracking.  A running Prefect server is not required for
a one-shot local run, but flow/task metadata will be stored if one is
reachable at the configured PREFECT_API_URL.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loguru import logger


def run_reuters() -> int:
    from src.scraper.spiders.reuters_rss import BBCRSSScraper

    scraper = BBCRSSScraper()
    items = scraper.run()
    return scraper.save_to_db(items)


def run_oecd() -> int:
    from src.scraper.spiders.oecd_spider import OECDScraper

    scraper = OECDScraper()
    items = scraper.run()
    return scraper.save_to_db(items)


def run_worldbank() -> int:
    from src.scraper.spiders.worldbank_scraper import WorldBankScraper

    scraper = WorldBankScraper()
    items = scraper.run()
    return scraper.save_to_db(items)


def run_stanford_hai() -> int:
    from src.scraper.spiders.stanford_hai_scraper import StanfordHAIScraper

    scraper = StanfordHAIScraper()
    items = scraper.run()
    return scraper.save_to_db(items)


SOURCES = {
    "reuters": run_reuters,
    "oecd": run_oecd,
    "worldbank": run_worldbank,
    "stanford_hai": run_stanford_hai,
}


def run_via_prefect() -> None:
    """Run scrape_all_flow() through Prefect task/flow tracking."""
    from src.scraper.flows import scrape_all_flow

    logger.info("Running scrape_all_flow via Prefect...")
    total = scrape_all_flow()
    logger.info(f"=== scrape_all_flow completed: {total} total document(s) saved ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SovereignLens scrapers")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--source",
        choices=["oecd", "reuters", "worldbank", "stanford_hai", "all"],
        help="Which scraper to run directly (without Prefect)",
    )
    mode.add_argument(
        "--prefect",
        action="store_true",
        help="Run all scrapers through Prefect (scrape_all_flow)",
    )

    args = parser.parse_args()

    if args.prefect:
        run_via_prefect()
        return

    if args.source == "all":
        total = 0
        for name, fn in SOURCES.items():
            logger.info(f"--- Starting {name} scraper ---")
            saved = fn()
            logger.info(f"--- {name} scraper finished: {saved} document(s) saved ---")
            total += saved
        logger.info(f"=== All scrapers done: {total} total document(s) saved ===")
    else:
        fn = SOURCES[args.source]
        logger.info(f"--- Starting {args.source} scraper ---")
        saved = fn()
        logger.info(f"--- {args.source} scraper finished: {saved} document(s) saved ---")


if __name__ == "__main__":
    main()
