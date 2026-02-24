#!/usr/bin/env python
"""Bootstrap the database schema (idempotent — safe to run multiple times)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scraper.database import create_tables

if __name__ == "__main__":
    create_tables()
