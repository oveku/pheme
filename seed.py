"""Seed default news sources into the database."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import get_settings
from app.database import get_db, init_db, create_source, get_sources, get_blocked_keywords, add_blocked_keyword
from app.models import SourceCreate, SourceType


DEFAULT_SOURCES = [
    SourceCreate(
        name="TLDR Tech",
        type=SourceType.RSS,
        url="https://tldr.tech/api/rss/tech",
        category="tech",
    ),
    SourceCreate(
        name="TLDR AI",
        type=SourceType.RSS,
        url="https://tldr.tech/api/rss/ai",
        category="ai",
    ),
    SourceCreate(
        name="Hacker News (Best)",
        type=SourceType.RSS,
        url="https://hnrss.org/best",
        config={"max_items": 15},
        category="tech",
    ),
    SourceCreate(
        name="r/MachineLearning",
        type=SourceType.REDDIT,
        url="r/MachineLearning",
        config={"sort": "hot", "limit": 10},
        category="ai",
    ),
    SourceCreate(
        name="r/Python",
        type=SourceType.REDDIT,
        url="r/Python",
        config={"sort": "hot", "limit": 10},
        category="programming",
    ),
    SourceCreate(
        name="r/selfhosted",
        type=SourceType.REDDIT,
        url="r/selfhosted",
        config={"sort": "hot", "limit": 10},
        category="homelab",
    ),
    SourceCreate(
        name="r/homelab",
        type=SourceType.REDDIT,
        url="r/homelab",
        config={"sort": "hot", "limit": 10},
        category="homelab",
    ),
    SourceCreate(
        name="Ars Technica",
        type=SourceType.RSS,
        url="https://feeds.arstechnica.com/arstechnica/index",
        config={"max_items": 10},
        category="tech",
    ),
    SourceCreate(
        name="The Verge",
        type=SourceType.RSS,
        url="https://www.theverge.com/rss/index.xml",
        config={"max_items": 10},
        category="tech",
    ),
]


async def seed():
    """Insert default sources if the database is empty."""
    db = await get_db()
    await init_db(db)

    existing = await get_sources(db)
    if existing:
        print(f"Database already has {len(existing)} sources, skipping source seed.")
    else:
        for source_data in DEFAULT_SOURCES:
            source = await create_source(db, source_data)
            print(f"  Added: {source.name} ({source.type.value}) - {source.url}")
        print(f"\nSeeded {len(DEFAULT_SOURCES)} default sources.")

    # Seed blocked keywords
    existing_keywords = await get_blocked_keywords(db)
    if existing_keywords:
        print(f"Database already has {len(existing_keywords)} blocked keywords, skipping seed.")
    else:
        default_keywords = ["Trump", "Epstein", "Donald Trump"]
        for kw in default_keywords:
            await add_blocked_keyword(db, kw)
            print(f"  Blocked: {kw}")
        print(f"\nSeeded {len(default_keywords)} default blocked keywords.")


if __name__ == "__main__":
    asyncio.run(seed())
