import uuid
from datetime import datetime

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from src.scraper.database import SessionLocal
from src.scraper.models import RawDocument, ScrapeRun
from src.scraper.models.document import OECDDocument


class PostgresPipeline:
    """Validates items with Pydantic, deduplicates by source_url, and persists to PostgreSQL.

    Also manages a ScrapeRun record so every crawl is auditable.
    """

    def __init__(self):
        self._run_id: uuid.UUID | None = None
        self._docs_scraped: int = 0

    # ------------------------------------------------------------------
    # Scrapy lifecycle
    # ------------------------------------------------------------------

    def open_spider(self, spider):
        db = SessionLocal()
        try:
            run = ScrapeRun(
                source_name=spider.name,
                started_at=datetime.utcnow(),
                status="running",
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            self._run_id = run.id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        logger.info(f"Scrape run {self._run_id} started for spider '{spider.name}'")

    def close_spider(self, spider):
        db = SessionLocal()
        try:
            run = db.get(ScrapeRun, self._run_id)
            if run:
                run.ended_at = datetime.utcnow()
                run.docs_scraped = self._docs_scraped
                run.status = "success"
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        logger.info(
            f"Scrape run {self._run_id} finished — {self._docs_scraped} document(s) saved"
        )

    # ------------------------------------------------------------------
    # Item processing
    # ------------------------------------------------------------------

    def process_item(self, item, spider):
        # Validate with Pydantic
        try:
            doc = OECDDocument(**item)
        except ValidationError as exc:
            logger.warning(f"Validation error for {item.get('source_url')!r}: {exc}")
            return item

        url_str = str(doc.source_url)

        db = SessionLocal()
        try:
            # Duplicate check
            exists = db.query(RawDocument).filter(RawDocument.source_url == url_str).first()
            if exists:
                logger.debug(f"Skipping duplicate: {url_str}")
                return item

            raw = RawDocument(
                source_url=url_str,
                title=doc.title,
                content=doc.content,
                country=doc.country,
                source_name=doc.source_name,
                scraped_at=doc.scraped_at,
                processed=False,
            )
            db.add(raw)
            db.commit()
            self._docs_scraped += 1
            logger.info(f"Saved [{self._docs_scraped}]: {doc.title[:80]!r}")
        except IntegrityError:
            # Race condition: another process inserted the same URL between our check and insert
            db.rollback()
            logger.debug(f"Duplicate race condition, skipping: {url_str}")
        except Exception as exc:
            db.rollback()
            logger.error(f"DB error for {url_str!r}: {exc}")
        finally:
            db.close()

        return item
