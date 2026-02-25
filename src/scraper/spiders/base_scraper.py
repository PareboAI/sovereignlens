"""Abstract base class for all SovereignLens scrapers."""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from src.scraper.database import SessionLocal
from src.scraper.models import RawDocument, ScrapeRun
from src.scraper.models.document import OECDDocument


class BaseScraper(ABC):
    source_name: str = ""

    @abstractmethod
    def run(self) -> list[dict]:
        """Fetch items and return as a list of dicts."""
        ...

    def save_to_db(self, items: list[dict]) -> int:
        """Validate and persist items to PostgreSQL. Returns count saved."""
        if not items:
            logger.info(f"[{self.source_name}] No items to save.")
            return 0

        run_id = self._start_run()
        saved = 0

        for item in items:
            try:
                doc = OECDDocument(**item)
            except ValidationError as exc:
                logger.warning(f"Validation error for {item.get('source_url')!r}: {exc}")
                continue

            url_str = str(doc.source_url)
            db = SessionLocal()
            try:
                exists = db.query(RawDocument).filter(RawDocument.source_url == url_str).first()
                if exists:
                    logger.debug(f"Skipping duplicate: {url_str}")
                    continue

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
                saved += 1
                logger.info(f"Saved [{saved}]: {doc.title[:80]!r}")
            except IntegrityError:
                db.rollback()
                logger.debug(f"Duplicate race condition, skipping: {url_str}")
            except Exception as exc:
                db.rollback()
                logger.error(f"DB error for {url_str!r}: {exc}")
            finally:
                db.close()

        self._end_run(run_id, saved)
        return saved

    # ------------------------------------------------------------------
    # ScrapeRun lifecycle helpers
    # ------------------------------------------------------------------

    def _start_run(self) -> uuid.UUID:
        db = SessionLocal()
        try:
            run = ScrapeRun(
                source_name=self.source_name,
                started_at=datetime.utcnow(),
                status="running",
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            run_id = run.id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        logger.info(f"Scrape run {run_id} started for '{self.source_name}'")
        return run_id

    def _end_run(self, run_id: uuid.UUID, docs_saved: int) -> None:
        db = SessionLocal()
        try:
            run = db.get(ScrapeRun, run_id)
            if run:
                run.ended_at = datetime.utcnow()
                run.docs_scraped = docs_saved
                run.status = "success"
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        logger.info(f"Scrape run {run_id} finished — {docs_saved} document(s) saved")
