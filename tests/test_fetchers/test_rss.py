"""Tests for RSS fetcher with mocked feeds."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.fetchers.rss import RSSFetcher
from app.models import Source, SourceType

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>First Article</title>
      <link>https://example.com/article-1</link>
      <description>This is the first article summary.</description>
      <pubDate>Wed, 05 Feb 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Second Article</title>
      <link>https://example.com/article-2</link>
      <description>This is the second article summary.</description>
      <pubDate>Wed, 05 Feb 2026 09:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Third Article</title>
      <link>https://example.com/article-3</link>
      <description>This is the third article.</description>
    </item>
  </channel>
</rss>"""

EMPTY_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>"""


def _make_source(**kwargs) -> Source:
    defaults = dict(
        id=1,
        name="Test Feed",
        type=SourceType.RSS,
        url="https://example.com/feed",
        category="tech",
        config={},
        enabled=True,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return Source(**defaults)


class TestRSSFetcher:
    @pytest.mark.asyncio
    async def test_fetch_articles(self):
        fetcher = RSSFetcher()
        source = _make_source()

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=SAMPLE_RSS
        ):
            articles = await fetcher.fetch(source)

        assert len(articles) == 3
        assert articles[0].title == "First Article"
        assert articles[0].url == "https://example.com/article-1"
        assert articles[0].source_name == "Test Feed"
        assert articles[0].category == "tech"
        assert "first article summary" in articles[0].content_preview.lower()

    @pytest.mark.asyncio
    async def test_respects_max_items(self):
        fetcher = RSSFetcher()
        source = _make_source(config={"max_items": 1})

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=SAMPLE_RSS
        ):
            articles = await fetcher.fetch(source)

        assert len(articles) == 1

    @pytest.mark.asyncio
    async def test_handles_empty_feed(self):
        fetcher = RSSFetcher()
        source = _make_source()

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=EMPTY_RSS
        ):
            articles = await fetcher.fetch(source)

        assert articles == []

    @pytest.mark.asyncio
    async def test_parses_published_date(self):
        fetcher = RSSFetcher()
        source = _make_source()

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=SAMPLE_RSS
        ):
            articles = await fetcher.fetch(source)

        assert articles[0].published_at is not None
        assert articles[0].published_at.year == 2026
        # Third article has no pubDate
        assert articles[2].published_at is None

    @pytest.mark.asyncio
    async def test_truncates_content_preview(self):
        long_desc = "x" * 1000
        rss_with_long_desc = f"""<?xml version="1.0"?>
        <rss version="2.0"><channel><title>T</title>
        <item><title>Long</title><link>https://x.com</link>
        <description>{long_desc}</description></item>
        </channel></rss>"""

        fetcher = RSSFetcher()
        source = _make_source()

        with patch.object(
            fetcher,
            "_http_get",
            new_callable=AsyncMock,
            return_value=rss_with_long_desc,
        ):
            articles = await fetcher.fetch(source)

        assert len(articles[0].content_preview) <= 500
