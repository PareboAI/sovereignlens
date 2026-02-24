#!/usr/bin/env python
"""Bootstrap the database schema (idempotent — safe to run multiple times)."""

from src.scraper.database import create_tables

if __name__ == "__main__":
    create_tables()
