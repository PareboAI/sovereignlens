"""Stanford HAI news scraper using the HAI CMS JSON API.

Paginates https://hai.stanford.edu/cms/api/collections/news/entries, extracts
title + body text from each news entry, and stores results in raw_documents.
No per-page HTTP delays needed — the API returns clean JSON.
"""

from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.scraper.database import SessionLocal
from src.scraper.models import RawDocument
from src.scraper.spiders.base_scraper import BaseScraper

_API_BASE = "https://hai.stanford.edu/cms/api/collections/news/entries"
_SITE_BASE = "https://hai.stanford.edu"
_MIN_CONTENT_LEN = 80


class StanfordHAIScraper(BaseScraper):
    source_name = "stanford_hai"

    def run(self) -> list[dict]:
        entries = self._fetch_all_entries()
        logger.info(f"[stanford_hai] {len(entries)} entries fetched from CMS API")

        items = []
        for entry in entries:
            item = self._parse_entry(entry)
            if item:
                items.append(item)

        logger.info(f"[stanford_hai] {len(items)} entries parsed with sufficient content")

        new_items = self._filter_existing(items)
        logger.info(
            f"[stanford_hai] {len(items) - len(new_items)} already in DB, "
            f"{len(new_items)} new"
        )
        return new_items

    def _fetch_all_entries(self) -> list[dict]:
        """Paginate through the CMS API and collect all news entries."""
        entries = []
        page = 1

        while True:
            try:
                response = httpx.get(
                    _API_BASE, params={"page": page}, timeout=30, follow_redirects=True
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.error(f"[stanford_hai] Error fetching page {page}: {exc}")
                break

            page_data = data.get("data", [])
            if not page_data:
                break

            entries.extend(page_data)
            logger.info(f"[stanford_hai] Page {page}: {len(page_data)} entries")

            meta = data.get("meta", {})
            last_page = meta.get("last_page", 1)
            if page >= last_page:
                break
            page += 1

        return entries

    def _parse_entry(self, entry: dict) -> dict | None:
        # Skip external media mentions — they have no body content
        if entry.get("destination"):
            return None

        title = (entry.get("title") or "").strip()
        if not title:
            return None

        # Build canonical URL from permalink or uri
        permalink = entry.get("permalink") or ""
        if not permalink:
            uri = entry.get("uri") or ""
            permalink = _SITE_BASE + uri if uri else ""
        if not permalink:
            return None

        content = self._extract_content(entry)
        if len(content) < _MIN_CONTENT_LEN:
            return None

        scraped_at = datetime.utcnow()
        raw_date = entry.get("date") or ""
        if raw_date:
            try:
                scraped_at = datetime.strptime(raw_date[:19], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass

        return {
            "title": title,
            "source_url": permalink,
            "content": content,
            "source_name": self.source_name,
            "scraped_at": scraped_at,
        }

    def _extract_content(self, entry: dict) -> str:
        """Extract plain text from blocks.rich_text HTML, falling back to dek."""
        blocks = entry.get("blocks") or []
        parts = []
        for block in blocks:
            rich_texts = block.get("rich_text") or []
            for rt in rich_texts:
                html = (rt.get("text") or "").strip()
                if html:
                    text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
                    if text:
                        parts.append(text)

        if parts:
            return " ".join(parts)

        # Fallback: dek (short summary, often HTML)
        dek = (entry.get("dek") or "").strip()
        if dek:
            return BeautifulSoup(dek, "html.parser").get_text(separator=" ", strip=True)

        return ""

    def _filter_existing(self, items: list[dict]) -> list[dict]:
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
            logger.error(f"[stanford_hai] DB lookup error during deduplication: {exc}")
            existing = set()
        finally:
            db.close()

        return [item for item in items if item["source_url"] not in existing]
