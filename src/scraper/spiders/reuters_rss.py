"""BBC News RSS scraper using httpx + feedparser."""

from datetime import datetime

import feedparser
import httpx
from loguru import logger

from src.scraper.database import SessionLocal
from src.scraper.models import RawDocument
from src.scraper.spiders.base_scraper import BaseScraper

FEEDS = [
    "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "http://feeds.bbci.co.uk/news/business/rss.xml",
    "http://feeds.bbci.co.uk/news/world/rss.xml",
]


class BBCRSSScraper(BaseScraper):
    source_name = "bbc_news"

    def run(self) -> list[dict]:
        """Fetch BBC News RSS feeds and return new items as a list of dicts."""
        items: list[dict] = []

        for feed_url in FEEDS:
            try:
                feed_items = self._fetch_feed(feed_url)
                items.extend(feed_items)
            except Exception as exc:
                logger.error(f"Failed to process feed {feed_url!r}: {exc}")
                continue

        # Deduplicate across feeds (same article may appear in multiple feeds)
        seen: set[str] = set()
        unique_items = []
        for item in items:
            url = item["source_url"]
            if url not in seen:
                seen.add(url)
                unique_items.append(item)

        # Filter out URLs already in the database
        new_items = self._filter_existing(unique_items)
        logger.info(
            f"BBC News: {len(unique_items)} entries fetched, "
            f"{len(unique_items) - len(new_items)} already in DB, "
            f"{len(new_items)} new"
        )
        return new_items

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_feed(self, url: str) -> list[dict]:
        """Fetch a single RSS feed via httpx and parse it with feedparser."""
        logger.info(f"Fetching feed: {url}")
        try:
            response = httpx.get(url, timeout=30, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(f"HTTP error fetching {url!r}: {exc}")
            return []

        feed = feedparser.parse(response.text)

        if feed.bozo and feed.bozo_exception:
            logger.warning(f"Feed parse warning for {url!r}: {feed.bozo_exception}")

        items = []
        for entry in feed.entries:
            try:
                item = self._parse_entry(entry)
                if item:
                    items.append(item)
            except Exception as exc:
                logger.error(f"Error parsing entry {entry.get('link', '?')!r}: {exc}")
                continue

        logger.info(f"Feed {url}: parsed {len(items)} entries")
        return items

    def _parse_entry(self, entry) -> dict | None:
        """Extract fields from a single feedparser entry."""
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()

        if not title or not link:
            return None

        summary = (entry.get("summary") or "").strip()
        content = summary or title  # fall back to title if no summary

        # Parse published date; fall back to now
        scraped_at = datetime.utcnow()
        if entry.get("published_parsed") and entry.published_parsed:
            try:
                scraped_at = datetime(*entry.published_parsed[:6])
            except (TypeError, ValueError):
                pass

        return {
            "title": title,
            "source_url": link,
            "content": content,
            "source_name": self.source_name,
            "scraped_at": scraped_at,
        }

    def _filter_existing(self, items: list[dict]) -> list[dict]:
        """Remove items whose source_url is already in the database."""
        if not items:
            return []

        urls = [item["source_url"] for item in items]
        db = SessionLocal()
        try:
            existing = {
                row.source_url
                for row in db.query(RawDocument.source_url)
                .filter(RawDocument.source_url.in_(urls))
                .all()
            }
        except Exception as exc:
            logger.error(f"DB lookup error during deduplication: {exc}")
            existing = set()
        finally:
            db.close()

        return [item for item in items if item["source_url"] not in existing]
