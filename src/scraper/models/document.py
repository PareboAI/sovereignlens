from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class OECDDocument(BaseModel):
    title: str
    source_url: HttpUrl
    country: Optional[str] = None
    content: str
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    source_name: str = "oecd_ai"
