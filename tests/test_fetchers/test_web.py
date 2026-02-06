"""Tests for Web scraper fetcher with mocked HTML."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.fetchers.web import WebFetcher
from app.models import Source, SourceType

SAMPLE_HTML = """
<html>
<body>
  <article>
    <h2><a href="/article/first">First Article Title</a></h2>
    <p>Some preview text here.</p>
  </article>
  <article>
    <h2><a href="https://other.com/second">Second Article Title</a></h2>
    <p>Another preview.</p>
  </article>
  <article>
    <h2><a href="/article/third">Third Article Title</a></h2>
  </article>
</body>
</html>"""

EMPTY_HTML = "<html><body><p>No articles here.</p></body></html>"

NO_LINKS_HTML = """
<html><body>
  <article><h2>Title Without Link</h2></article>
</body></html>"""


def _make_source(**kwargs) -> Source:
    defaults = dict(
        id=1,
        name="Test Site",
        type=SourceType.WEB,
        url="https://example.com",
        category="tech",
        config={"selector": "article h2 a"},
        enabled=True,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return Source(**defaults)


class TestWebFetcher:
    @pytest.mark.asyncio
    async def test_fetch_articles(self):
        fetcher = WebFetcher()
        source = _make_source()

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=SAMPLE_HTML
        ):
            articles = await fetcher.fetch(source)

        assert len(articles) == 3
        assert articles[0].title == "First Article Title"
        assert articles[0].source_name == "Test Site"

    @pytest.mark.asyncio
    async def test_resolves_relative_urls(self):
        fetcher = WebFetcher()
        source = _make_source()

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=SAMPLE_HTML
        ):
            articles = await fetcher.fetch(source)

        assert articles[0].url == "https://example.com/article/first"

    @pytest.mark.asyncio
    async def test_keeps_absolute_urls(self):
        fetcher = WebFetcher()
        source = _make_source()

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=SAMPLE_HTML
        ):
            articles = await fetcher.fetch(source)

        assert articles[1].url == "https://other.com/second"

    @pytest.mark.asyncio
    async def test_respects_max_items(self):
        fetcher = WebFetcher()
        source = _make_source(config={"selector": "article h2 a", "max_items": 2})

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=SAMPLE_HTML
        ):
            articles = await fetcher.fetch(source)

        assert len(articles) == 2

    @pytest.mark.asyncio
    async def test_handles_empty_page(self):
        fetcher = WebFetcher()
        source = _make_source()

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=EMPTY_HTML
        ):
            articles = await fetcher.fetch(source)

        assert articles == []

    @pytest.mark.asyncio
    async def test_skips_elements_without_links(self):
        fetcher = WebFetcher()
        source = _make_source(config={"selector": "article h2"})

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=NO_LINKS_HTML
        ):
            articles = await fetcher.fetch(source)

        assert articles == []

    @pytest.mark.asyncio
    async def test_custom_selector(self):
        html = """<html><body>
        <div class="news"><a href="/story">Custom Story</a></div>
        </body></html>"""

        fetcher = WebFetcher()
        source = _make_source(config={"selector": "div.news a"})

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=html
        ):
            articles = await fetcher.fetch(source)

        assert len(articles) == 1
        assert articles[0].title == "Custom Story"
