from src.scraper.models import Base, RawDocument, ScrapeRun


def test_models_importable():
    assert RawDocument is not None
    assert ScrapeRun is not None


def test_raw_document_columns():
    cols = {c.name for c in RawDocument.__table__.columns}
    assert cols == {"id", "source_url", "title", "content", "country", "source_name", "scraped_at", "processed", "metadata"}


def test_scrape_run_columns():
    cols = {c.name for c in ScrapeRun.__table__.columns}
    assert cols == {"id", "source_name", "started_at", "ended_at", "docs_scraped", "status", "error_message"}


def test_base_has_both_tables():
    assert "raw_documents" in Base.metadata.tables
    assert "scrape_runs" in Base.metadata.tables
