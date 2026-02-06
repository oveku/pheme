"""Tests for BaseFetcher contract and FetcherFactory."""

import pytest
from datetime import datetime, timezone

from app.fetchers.base import BaseFetcher
from app.fetchers.factory import create_fetcher, get_registered_types, register_fetcher
from app.fetchers.rss import RSSFetcher
from app.fetchers.reddit import RedditFetcher
from app.fetchers.web import WebFetcher
from app.models import Article, Source, SourceType


class ConcreteFetcher(BaseFetcher):
    """Test implementation of BaseFetcher."""

    async def connect(self, source):
        return "raw data"

    async def extract(self, raw, source):
        return [{"title": "Test", "url": "https://test.com"}]

    async def normalize(self, raw_articles, source):
        return [
            Article(
                title=a["title"],
                url=a["url"],
                source_name=source.name,
                category=source.category,
            )
            for a in raw_articles
        ]


class TestBaseFetcher:
    @pytest.mark.asyncio
    async def test_fetch_calls_pipeline(self):
        fetcher = ConcreteFetcher()
        source = Source(
            id=1,
            name="Test",
            type=SourceType.RSS,
            url="https://test.com",
            category="tech",
            config={},
            enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        articles = await fetcher.fetch(source)
        assert len(articles) == 1
        assert articles[0].title == "Test"
        assert articles[0].source_name == "Test"

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseFetcher()


class TestFetcherFactory:
    def test_create_rss_fetcher(self):
        fetcher = create_fetcher(SourceType.RSS)
        assert isinstance(fetcher, RSSFetcher)

    def test_create_reddit_fetcher(self):
        fetcher = create_fetcher(SourceType.REDDIT)
        assert isinstance(fetcher, RedditFetcher)

    def test_create_web_fetcher(self):
        fetcher = create_fetcher(SourceType.WEB)
        assert isinstance(fetcher, WebFetcher)

    def test_get_registered_types(self):
        types = get_registered_types()
        assert SourceType.RSS in types
        assert SourceType.REDDIT in types
        assert SourceType.WEB in types

    def test_register_custom_fetcher(self):
        # Register our test fetcher
        register_fetcher(SourceType.RSS, ConcreteFetcher)
        fetcher = create_fetcher(SourceType.RSS)
        assert isinstance(fetcher, ConcreteFetcher)
        # Restore original
        register_fetcher(SourceType.RSS, RSSFetcher)
