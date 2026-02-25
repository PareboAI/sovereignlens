"""World Bank Open Knowledge Repository scraper using httpx.

Queries the World Bank search API for AI-related documents (reports, papers,
policy briefs) and stores title, abstract, and URL in the raw_documents table.
"""

from datetime import datetime

import httpx
from loguru import logger

from src.scraper.database import SessionLocal
from src.scraper.models import RawDocument
from src.scraper.spiders.base_scraper import BaseScraper

_API_URL = "https://search.worldbank.org/api/v2/wds"
_QUERY = "artificial intelligence"
_PAGE_SIZE = 50
_MAX_RESULTS = 200


class WorldBankScraper(BaseScraper):
    source_name = "worldbank"

    def run(self) -> list[dict]:
        items: list[dict] = []
        offset = 0

        while offset < _MAX_RESULTS:
            params = {
                "qterm": _QUERY,
                "format": "json",
                "rows": _PAGE_SIZE,
                "os": offset,
            }
            try:
                response = httpx.get(_API_URL, params=params, timeout=30, follow_redirects=True)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.error(f"[worldbank] Error fetching page at offset {offset}: {exc}")
                break

            documents = data.get("documents", {})
            if not documents:
                logger.info(f"[worldbank] No more documents at offset {offset}")
                break

            page_items = []
            for doc_id, doc in documents.items():
                if doc_id == "facets":
                    continue
                item = self._parse_document(doc)
                if item:
                    page_items.append(item)

            if not page_items:
                break

            items.extend(page_items)
            logger.info(f"[worldbank] Fetched {len(page_items)} documents at offset {offset}")
            offset += _PAGE_SIZE

        # Deduplicate within batch
        seen: set[str] = set()
        unique_items = []
        for item in items:
            url = item["source_url"]
            if url not in seen:
                seen.add(url)
                unique_items.append(item)

        new_items = self._filter_existing(unique_items)
        logger.info(
            f"[worldbank] {len(unique_items)} fetched, "
            f"{len(unique_items) - len(new_items)} already in DB, "
            f"{len(new_items)} new"
        )
        return new_items

    def _parse_document(self, doc: dict) -> dict | None:
        url = (doc.get("url") or "").strip()
        if not url:
            return None

        abstracts = doc.get("abstracts") or {}
        content = (abstracts.get("cdata!") or "").strip()
        if not content:
            return None

        title = (doc.get("display_title") or "").replace("\n", " ").strip()
        if not title:
            return None

        scraped_at = datetime.utcnow()
        raw_date = doc.get("docdt") or ""
        if raw_date:
            for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
                try:
                    scraped_at = datetime.strptime(raw_date[:19] if "T" in raw_date else raw_date[:10], fmt)
                    break
                except ValueError:
                    continue

        return {
            "title": title,
            "source_url": url,
            "content": content,
            "source_name": self.source_name,
            "scraped_at": scraped_at,
        }

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
            logger.error(f"[worldbank] DB lookup error during deduplication: {exc}")
            existing = set()
        finally:
            db.close()

        return [item for item in items if item["source_url"] not in existing]
