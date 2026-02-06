"""Reddit JSON API fetcher."""

from datetime import datetime, timezone

from app.fetchers.base import BaseFetcher
from app.models import Article, Source

import json


class RedditFetcher(BaseFetcher):
    """Fetches articles from Reddit subreddits via JSON API."""

    REDDIT_BASE = "https://www.reddit.com"

    async def connect(self, source: Source) -> str:
        """Fetch subreddit JSON listing."""
        subreddit = source.url.strip("/").removeprefix("r/")
        sort = source.config.get("sort", "hot")
        limit = source.config.get("limit", 10)
        url = f"{self.REDDIT_BASE}/r/{subreddit}/{sort}.json?limit={limit}&raw_json=1"
        headers = {"User-Agent": "Pheme/0.1 (news digest bot)"}
        return await self._http_get(url, headers=headers)

    async def extract(self, raw: str, source: Source) -> list[dict]:
        """Parse Reddit JSON into article dicts."""
        data = json.loads(raw)
        posts = data.get("data", {}).get("children", [])

        articles = []
        for post in posts:
            p = post.get("data", {})
            if p.get("stickied", False):
                continue

            created = datetime.fromtimestamp(p.get("created_utc", 0), tz=timezone.utc)

            # Use the actual link for link posts, self URL for text posts
            url = p.get("url", "")
            if p.get("is_self", False):
                url = f"{self.REDDIT_BASE}{p.get('permalink', '')}"

            content_preview = p.get("selftext", "")[:500] if p.get("is_self") else ""

            articles.append(
                {
                    "title": p.get("title", "Untitled"),
                    "url": url,
                    "published_at": created,
                    "content_preview": content_preview,
                    "score": float(p.get("score", 0)),
                }
            )

        return articles

    async def normalize(
        self, raw_articles: list[dict], source: Source
    ) -> list[Article]:
        """Convert Reddit posts to Article models."""
        return [
            Article(
                title=a["title"],
                url=a["url"],
                source_name=source.name,
                category=source.category,
                published_at=a.get("published_at"),
                content_preview=a.get("content_preview", ""),
                score=a.get("score"),
            )
            for a in raw_articles
            if a.get("title") and a.get("url")
        ]
