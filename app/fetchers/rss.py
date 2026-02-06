"""RSS/Atom feed fetcher."""

from datetime import datetime, timezone
from time import mktime

import feedparser

from app.fetchers.base import BaseFetcher
from app.models import Article, Source


class RSSFetcher(BaseFetcher):
    """Fetches articles from RSS/Atom feeds using feedparser."""

    async def connect(self, source: Source) -> str:
        """Fetch the RSS/Atom feed XML."""
        return await self._http_get(source.url)

    async def extract(self, raw: str, source: Source) -> list[dict]:
        """Parse feed XML into article dicts."""
        feed = feedparser.parse(raw)
        max_items = source.config.get("max_items", 15)
        entries = feed.entries[:max_items]

        articles = []
        for entry in entries:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime.fromtimestamp(
                    mktime(entry.published_parsed), tz=timezone.utc
                )
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = datetime.fromtimestamp(
                    mktime(entry.updated_parsed), tz=timezone.utc
                )

            content_preview = ""
            if hasattr(entry, "summary") and entry.summary:
                content_preview = entry.summary[:500]
            elif hasattr(entry, "description") and entry.description:
                content_preview = entry.description[:500]

            articles.append(
                {
                    "title": entry.get("title", "Untitled"),
                    "url": entry.get("link", ""),
                    "published_at": published,
                    "content_preview": content_preview,
                }
            )

        return articles

    async def normalize(
        self, raw_articles: list[dict], source: Source
    ) -> list[Article]:
        """Convert feed entries to Article models."""
        return [
            Article(
                title=a["title"],
                url=a["url"],
                source_name=source.name,
                category=source.category,
                published_at=a.get("published_at"),
                content_preview=a.get("content_preview", ""),
            )
            for a in raw_articles
            if a.get("title") and a.get("url")
        ]
