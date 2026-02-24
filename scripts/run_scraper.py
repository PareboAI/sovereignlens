#!/usr/bin/env python
"""Run the OECD AI Observatory spider."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.scraper.settings as _s
from scrapy.crawler import CrawlerProcess
from src.scraper.spiders.oecd_spider import OECDAISpider

settings = {k: getattr(_s, k) for k in dir(_s) if k.isupper()}

if __name__ == "__main__":
    process = CrawlerProcess(settings=settings)
    process.crawl(OECDAISpider)
    process.start()
