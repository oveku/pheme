"""Tests for the digest pipeline orchestrator."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.models import Source, SourceType, Article, DigestEntry, Digest
from app.summarizer.llm import SummarizerResult
from app.pipeline.digest import DigestPipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_sources() -> list[Source]:
    return [
        Source(
            id=1,
            name="TLDR Tech",
            type=SourceType.RSS,
            url="https://tldr.tech/api/rss/tech",
            config={},
            category="tech",
            enabled=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        Source(
            id=2,
            name="r/python",
            type=SourceType.REDDIT,
            url="r/python",
            config={"sort": "hot", "limit": 10},
            category="programming",
            enabled=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
    ]


@pytest.fixture
def sample_articles() -> list[Article]:
    return [
        Article(
            title="Python 3.14 Released",
            url="https://python.org/3.14",
            source_name="TLDR Tech",
            content_preview="Major new release.",
        ),
        Article(
            title="FastAPI Tips",
            url="https://reddit.com/r/python/fastapi",
            source_name="r/python",
            content_preview="Top tips.",
        ),
        Article(
            title="Async Python Guide",
            url="https://reddit.com/r/python/async",
            source_name="r/python",
            content_preview="Async patterns.",
        ),
    ]


@pytest.fixture
def sample_summarizer_result() -> SummarizerResult:
    return SummarizerResult(
        summary="Python 3.14 drops. FastAPI tips trending. Async guide published.",
        success=True,
        model="qwen2.5:1.5b-instruct",
    )


# ---------------------------------------------------------------------------
# Pipeline Tests
# ---------------------------------------------------------------------------

class TestDigestPipeline:
    """Tests for the full fetch-summarize-email pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_fetches_from_all_sources(
        self, sample_sources, sample_articles
    ):
        """Pipeline should call fetcher for each enabled source."""
        mock_fetcher = AsyncMock(return_value=sample_articles[:1])
        mock_factory = MagicMock()
        mock_factory.create_fetcher.return_value = MagicMock(fetch=mock_fetcher)

        mock_db = AsyncMock()
        mock_db.get_sources.return_value = sample_sources

        mock_summarizer = AsyncMock()
        mock_summarizer.summarize.return_value = SummarizerResult(
            summary="Summary", success=True, model="test"
        )

        pipeline = DigestPipeline(
            db=mock_db,
            fetcher_factory=mock_factory,
            summarizer=mock_summarizer,
        )
        digest = await pipeline.run()

        assert mock_factory.create_fetcher.call_count == 2
        assert digest.source_count == 2

    @pytest.mark.asyncio
    async def test_pipeline_aggregates_articles(
        self, sample_sources, sample_articles
    ):
        """Articles from all sources should be collected."""
        # Source 1 returns 1 article, source 2 returns 2
        call_count = 0

        async def fetch_side_effect(source, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return sample_articles[:1]
            return sample_articles[1:]

        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.fetch = AsyncMock(side_effect=fetch_side_effect)

        mock_factory = MagicMock()
        mock_factory.create_fetcher.return_value = mock_fetcher_instance

        mock_db = AsyncMock()
        mock_db.get_sources.return_value = sample_sources

        mock_summarizer = AsyncMock()
        mock_summarizer.summarize.return_value = SummarizerResult(
            summary="Summary", success=True, model="test"
        )

        pipeline = DigestPipeline(
            db=mock_db,
            fetcher_factory=mock_factory,
            summarizer=mock_summarizer,
        )
        digest = await pipeline.run()

        assert digest.article_count == 3

    @pytest.mark.asyncio
    async def test_pipeline_summarizes_articles(
        self, sample_sources, sample_articles, sample_summarizer_result
    ):
        """Pipeline should pass all articles to the summarizer."""
        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.fetch = AsyncMock(return_value=sample_articles)

        mock_factory = MagicMock()
        mock_factory.create_fetcher.return_value = mock_fetcher_instance

        mock_db = AsyncMock()
        mock_db.get_sources.return_value = sample_sources[:1]

        mock_summarizer = MagicMock()
        mock_summarizer.summarize = AsyncMock(return_value=sample_summarizer_result)

        pipeline = DigestPipeline(
            db=mock_db,
            fetcher_factory=mock_factory,
            summarizer=mock_summarizer,
        )
        digest = await pipeline.run()

        mock_summarizer.summarize.assert_called_once()
        assert digest.summary == sample_summarizer_result.summary
        assert digest.model == sample_summarizer_result.model

    @pytest.mark.asyncio
    async def test_pipeline_sends_email(
        self, sample_sources, sample_articles, sample_summarizer_result
    ):
        """Pipeline should send email when recipient is configured."""
        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.fetch = AsyncMock(return_value=sample_articles[:1])

        mock_factory = MagicMock()
        mock_factory.create_fetcher.return_value = mock_fetcher_instance

        mock_db = AsyncMock()
        mock_db.get_sources.return_value = sample_sources[:1]

        mock_summarizer = MagicMock()
        mock_summarizer.summarize = AsyncMock(return_value=sample_summarizer_result)

        with patch("app.pipeline.digest.send_digest_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            pipeline = DigestPipeline(
                db=mock_db,
                fetcher_factory=mock_factory,
                summarizer=mock_summarizer,
            )
            digest = await pipeline.run(
                recipient="test@example.com",
                smtp_host="smtp.test.com",
                smtp_port=587,
                smtp_user="user@test.com",
                smtp_password="pass",
            )

            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_skips_email_when_no_recipient(
        self, sample_sources, sample_articles, sample_summarizer_result
    ):
        """Pipeline should skip email when no recipient configured."""
        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.fetch = AsyncMock(return_value=sample_articles[:1])

        mock_factory = MagicMock()
        mock_factory.create_fetcher.return_value = mock_fetcher_instance

        mock_db = AsyncMock()
        mock_db.get_sources.return_value = sample_sources[:1]

        mock_summarizer = MagicMock()
        mock_summarizer.summarize = AsyncMock(return_value=sample_summarizer_result)

        with patch("app.pipeline.digest.send_digest_email", new_callable=AsyncMock) as mock_send:
            pipeline = DigestPipeline(
                db=mock_db,
                fetcher_factory=mock_factory,
                summarizer=mock_summarizer,
            )
            digest = await pipeline.run()  # no recipient

            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_handles_fetcher_error(self, sample_sources):
        """Failing fetcher should not crash the pipeline; other sources proceed."""
        call_count = 0

        async def fetch_side_effect(source, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network error")
            return [Article(
                title="Surviving Article",
                url="https://example.com",
                source_name="r/python",
            )]

        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.fetch = AsyncMock(side_effect=fetch_side_effect)

        mock_factory = MagicMock()
        mock_factory.create_fetcher.return_value = mock_fetcher_instance

        mock_db = AsyncMock()
        mock_db.get_sources.return_value = sample_sources

        mock_summarizer = MagicMock()
        mock_summarizer.summarize = AsyncMock(return_value=SummarizerResult(
            summary="Summary", success=True, model="test"
        ))

        pipeline = DigestPipeline(
            db=mock_db,
            fetcher_factory=mock_factory,
            summarizer=mock_summarizer,
        )
        digest = await pipeline.run()

        # One source failed, but the other succeeded
        assert digest.article_count == 1
        assert len(digest.entries) > 0

    @pytest.mark.asyncio
    async def test_pipeline_logs_digest(
        self, sample_sources, sample_articles, sample_summarizer_result
    ):
        """Pipeline should log the digest run to database."""
        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.fetch = AsyncMock(return_value=sample_articles[:1])

        mock_factory = MagicMock()
        mock_factory.create_fetcher.return_value = mock_fetcher_instance

        mock_db = AsyncMock()
        mock_db.get_sources.return_value = sample_sources[:1]

        mock_summarizer = MagicMock()
        mock_summarizer.summarize = AsyncMock(return_value=sample_summarizer_result)

        pipeline = DigestPipeline(
            db=mock_db,
            fetcher_factory=mock_factory,
            summarizer=mock_summarizer,
        )
        await pipeline.run()

        mock_db.log_digest.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_empty_sources(self):
        """Pipeline with no sources should produce empty digest."""
        mock_db = AsyncMock()
        mock_db.get_sources.return_value = []

        mock_factory = MagicMock()
        mock_summarizer = MagicMock()
        mock_summarizer.summarize = AsyncMock(return_value=SummarizerResult(
            summary="No articles to summarize.", success=True, model="test"
        ))

        pipeline = DigestPipeline(
            db=mock_db,
            fetcher_factory=mock_factory,
            summarizer=mock_summarizer,
        )
        digest = await pipeline.run()

        assert digest.source_count == 0
        assert digest.article_count == 0

    @pytest.mark.asyncio
    async def test_pipeline_updates_last_fetched(
        self, sample_sources, sample_articles
    ):
        """Pipeline should update last_fetched timestamp for successful sources."""
        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.fetch = AsyncMock(return_value=sample_articles[:1])

        mock_factory = MagicMock()
        mock_factory.create_fetcher.return_value = mock_fetcher_instance

        mock_db = AsyncMock()
        mock_db.get_sources.return_value = sample_sources[:1]

        mock_summarizer = MagicMock()
        mock_summarizer.summarize = AsyncMock(return_value=SummarizerResult(
            summary="Summary", success=True, model="test"
        ))

        pipeline = DigestPipeline(
            db=mock_db,
            fetcher_factory=mock_factory,
            summarizer=mock_summarizer,
        )
        await pipeline.run()

        mock_db.update_source_last_fetched.assert_called_once_with(sample_sources[0].id)
