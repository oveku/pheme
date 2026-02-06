"""Base fetcher - Template Method pattern."""

from abc import ABC, abstractmethod

import httpx

from app.models import Article, Source


class BaseFetcher(ABC):
    """Abstract base class for all news source fetchers.

    Uses the Template Method pattern: fetch() defines the workflow,
    subclasses override connect(), extract(), and normalize().
    """

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch(self, source: Source) -> list[Article]:
        """Template method: connect -> extract -> normalize.

        Args:
            source: The source configuration to fetch from.

        Returns:
            List of normalized Article objects.
        """
        raw = await self.connect(source)
        extracted = await self.extract(raw, source)
        articles = await self.normalize(extracted, source)
        return articles

    @abstractmethod
    async def connect(self, source: Source) -> bytes | str:
        """Fetch raw content from the source.

        Args:
            source: The source to connect to.

        Returns:
            Raw response content (bytes or string).
        """
        ...

    @abstractmethod
    async def extract(self, raw: bytes | str, source: Source) -> list[dict]:
        """Extract article data from raw content.

        Args:
            raw: Raw content from connect().
            source: The source configuration.

        Returns:
            List of raw article dicts with at minimum 'title' and 'url'.
        """
        ...

    @abstractmethod
    async def normalize(
        self, raw_articles: list[dict], source: Source
    ) -> list[Article]:
        """Convert extracted data to Article models.

        Args:
            raw_articles: List of raw article dicts from extract().
            source: The source configuration.

        Returns:
            List of validated Article models.
        """
        ...

    async def _http_get(self, url: str, headers: dict | None = None) -> str:
        """Shared HTTP GET helper."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers=headers or {})
            resp.raise_for_status()
            return resp.text
