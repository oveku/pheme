"""Generic web page scraper fetcher."""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from app.fetchers.base import BaseFetcher
from app.models import Article, Source


class WebFetcher(BaseFetcher):
    """Scrapes articles from web pages using BeautifulSoup."""

    async def connect(self, source: Source) -> str:
        """Fetch the web page HTML."""
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Pheme/0.1; news digest)",
        }
        return await self._http_get(source.url, headers=headers)

    async def extract(self, raw: str, source: Source) -> list[dict]:
        """Extract article data from HTML using CSS selectors."""
        soup = BeautifulSoup(raw, "html.parser")
        selector = source.config.get("selector", "article h2 a, h2 a, h3 a")
        max_items = source.config.get("max_items", 15)

        elements = soup.select(selector)[:max_items]

        articles = []
        for el in elements:
            # Find the link - either the element itself or a child/parent <a>
            link_el = None
            if el.name == "a":
                link_el = el
            else:
                link_el = el.find("a")
                if link_el is None:
                    # Try parent
                    link_el = el.find_parent("a")

            if link_el is None:
                continue

            title = link_el.get_text(strip=True)
            href = link_el.get("href", "")
            url = urljoin(source.url, href) if href else ""

            if not title or not url:
                continue

            articles.append(
                {
                    "title": title,
                    "url": url,
                }
            )

        return articles

    async def normalize(
        self, raw_articles: list[dict], source: Source
    ) -> list[Article]:
        """Convert scraped data to Article models."""
        return [
            Article(
                title=a["title"],
                url=a["url"],
                source_name=source.name,
                category=source.category,
            )
            for a in raw_articles
            if a.get("title") and a.get("url")
        ]
