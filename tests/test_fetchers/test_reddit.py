"""Tests for Reddit fetcher with mocked API responses."""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.fetchers.reddit import RedditFetcher
from app.models import Source, SourceType


SAMPLE_REDDIT_JSON = json.dumps(
    {
        "data": {
            "children": [
                {
                    "data": {
                        "title": "AI breakthrough in edge computing",
                        "url": "https://example.com/ai-article",
                        "permalink": "/r/technology/comments/abc123/ai_breakthrough/",
                        "selftext": "",
                        "is_self": False,
                        "stickied": False,
                        "score": 1500,
                        "created_utc": 1738746000.0,
                    }
                },
                {
                    "data": {
                        "title": "Discussion: Best self-hosted tools",
                        "url": "https://www.reddit.com/r/selfhosted/comments/def456/best_tools/",
                        "permalink": "/r/selfhosted/comments/def456/best_tools/",
                        "selftext": "What are your favorite self-hosted tools for 2026?",
                        "is_self": True,
                        "stickied": False,
                        "score": 250,
                        "created_utc": 1738742400.0,
                    }
                },
                {
                    "data": {
                        "title": "Weekly Megathread",
                        "url": "https://www.reddit.com/r/technology/comments/ghi789/weekly/",
                        "permalink": "/r/technology/comments/ghi789/weekly/",
                        "selftext": "Post your questions here.",
                        "is_self": True,
                        "stickied": True,
                        "score": 50,
                        "created_utc": 1738738800.0,
                    }
                },
            ]
        }
    }
)

EMPTY_REDDIT_JSON = json.dumps({"data": {"children": []}})


def _make_source(**kwargs) -> Source:
    defaults = dict(
        id=1,
        name="r/technology",
        type=SourceType.REDDIT,
        url="technology",
        category="tech",
        config={"sort": "hot", "limit": 10},
        enabled=True,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return Source(**defaults)


class TestRedditFetcher:
    @pytest.mark.asyncio
    async def test_fetch_articles(self):
        fetcher = RedditFetcher()
        source = _make_source()

        with patch.object(
            fetcher,
            "_http_get",
            new_callable=AsyncMock,
            return_value=SAMPLE_REDDIT_JSON,
        ):
            articles = await fetcher.fetch(source)

        # Should skip stickied post
        assert len(articles) == 2
        assert articles[0].title == "AI breakthrough in edge computing"
        assert articles[0].url == "https://example.com/ai-article"
        assert articles[0].score == 1500.0

    @pytest.mark.asyncio
    async def test_self_post_uses_reddit_url(self):
        fetcher = RedditFetcher()
        source = _make_source()

        with patch.object(
            fetcher,
            "_http_get",
            new_callable=AsyncMock,
            return_value=SAMPLE_REDDIT_JSON,
        ):
            articles = await fetcher.fetch(source)

        # Self post should use reddit permalink
        assert "reddit.com" in articles[1].url

    @pytest.mark.asyncio
    async def test_self_post_has_content_preview(self):
        fetcher = RedditFetcher()
        source = _make_source()

        with patch.object(
            fetcher,
            "_http_get",
            new_callable=AsyncMock,
            return_value=SAMPLE_REDDIT_JSON,
        ):
            articles = await fetcher.fetch(source)

        assert (
            articles[1].content_preview
            == "What are your favorite self-hosted tools for 2026?"
        )

    @pytest.mark.asyncio
    async def test_skips_stickied_posts(self):
        fetcher = RedditFetcher()
        source = _make_source()

        with patch.object(
            fetcher,
            "_http_get",
            new_callable=AsyncMock,
            return_value=SAMPLE_REDDIT_JSON,
        ):
            articles = await fetcher.fetch(source)

        titles = [a.title for a in articles]
        assert "Weekly Megathread" not in titles

    @pytest.mark.asyncio
    async def test_handles_empty_subreddit(self):
        fetcher = RedditFetcher()
        source = _make_source()

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=EMPTY_REDDIT_JSON
        ):
            articles = await fetcher.fetch(source)

        assert articles == []

    @pytest.mark.asyncio
    async def test_constructs_correct_url(self):
        fetcher = RedditFetcher()
        source = _make_source(url="r/selfhosted", config={"sort": "top", "limit": 5})

        with patch.object(
            fetcher, "_http_get", new_callable=AsyncMock, return_value=EMPTY_REDDIT_JSON
        ) as mock_get:
            await fetcher.fetch(source)

        call_url = mock_get.call_args[0][0]
        assert "/r/selfhosted/top.json" in call_url
        assert "limit=5" in call_url

    @pytest.mark.asyncio
    async def test_strips_subreddit_prefix(self):
        fetcher = RedditFetcher()

        # Test various URL formats
        for url_format in ["technology", "r/technology", "/r/technology/"]:
            source = _make_source(url=url_format)
            with patch.object(
                fetcher,
                "_http_get",
                new_callable=AsyncMock,
                return_value=EMPTY_REDDIT_JSON,
            ) as mock_get:
                await fetcher.fetch(source)
            call_url = mock_get.call_args[0][0]
            assert "/r/technology/" in call_url
