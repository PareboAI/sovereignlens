#!/usr/bin/env python
"""Run SovereignLens scrapers.

Usage:
    poetry run python scripts/run_scraper.py --source oecd
    poetry run python scripts/run_scraper.py --source reuters
    poetry run python scripts/run_scraper.py --source all
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


SOURCES = {
    "reuters": run_reuters,
    "oecd": run_oecd,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SovereignLens scrapers")
    parser.add_argument(
        "--source",
        choices=["oecd", "reuters", "all"],
        required=True,
        help="Which scraper to run",
    )
    args = parser.parse_args()

    if args.source == "all":
        # Run Reuters first (pure Python, no Twisted reactor), then OECD (Scrapy)
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
