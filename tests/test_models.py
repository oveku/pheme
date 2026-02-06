"""Tests for Pydantic models."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.models import (
    Article,
    Digest,
    DigestEntry,
    DigestLog,
    Source,
    SourceCreate,
    SourceType,
    SourceUpdate,
)


class TestSourceType:
    def test_valid_types(self):
        assert SourceType.RSS == "rss"
        assert SourceType.REDDIT == "reddit"
        assert SourceType.WEB == "web"

    def test_all_types_enumerated(self):
        assert len(SourceType) == 3


class TestSourceCreate:
    def test_minimal_source(self):
        source = SourceCreate(
            name="Test", type=SourceType.RSS, url="https://example.com/feed"
        )
        assert source.name == "Test"
        assert source.type == SourceType.RSS
        assert source.url == "https://example.com/feed"
        assert source.category == "general"
        assert source.config == {}
        assert source.enabled is True

    def test_full_source(self):
        source = SourceCreate(
            name="Hacker News",
            type=SourceType.RSS,
            url="https://hnrss.org/best",
            category="tech",
            config={"max_items": 10},
            enabled=True,
        )
        assert source.name == "Hacker News"
        assert source.category == "tech"
        assert source.config == {"max_items": 10}

    def test_reddit_source(self):
        source = SourceCreate(
            name="r/technology",
            type=SourceType.REDDIT,
            url="technology",
            category="tech",
            config={"sort": "hot", "limit": 10},
        )
        assert source.type == SourceType.REDDIT
        assert source.config["sort"] == "hot"

    def test_web_source(self):
        source = SourceCreate(
            name="Ars Technica",
            type=SourceType.WEB,
            url="https://arstechnica.com",
            category="tech",
            config={"selector": "article h2", "max_items": 10},
        )
        assert source.type == SourceType.WEB

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            SourceCreate(name="", type=SourceType.RSS, url="https://example.com")

    def test_empty_url_rejected(self):
        with pytest.raises(ValidationError):
            SourceCreate(name="Test", type=SourceType.RSS, url="")

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            SourceCreate(name="Test", type="invalid", url="https://example.com")

    def test_name_max_length(self):
        with pytest.raises(ValidationError):
            SourceCreate(name="x" * 201, type=SourceType.RSS, url="https://example.com")


class TestSourceUpdate:
    def test_partial_update(self):
        update = SourceUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.type is None
        assert update.url is None
        assert update.enabled is None

    def test_empty_update(self):
        update = SourceUpdate()
        assert update.name is None
        assert update.type is None

    def test_disable_source(self):
        update = SourceUpdate(enabled=False)
        assert update.enabled is False


class TestSource:
    def test_full_source(self):
        now = datetime.now(timezone.utc)
        source = Source(
            id=1,
            name="Test",
            type=SourceType.RSS,
            url="https://example.com",
            category="tech",
            config={},
            enabled=True,
            created_at=now,
            last_fetched=None,
        )
        assert source.id == 1
        assert source.created_at == now
        assert source.last_fetched is None


class TestArticle:
    def test_minimal_article(self):
        article = Article(
            title="Test Article",
            url="https://example.com/article",
            source_name="Test Source",
        )
        assert article.title == "Test Article"
        assert article.category == "general"
        assert article.content_preview == ""
        assert article.score is None
        assert article.published_at is None

    def test_full_article(self):
        now = datetime.now(timezone.utc)
        article = Article(
            title="AI Breakthrough",
            url="https://example.com/ai",
            source_name="Hacker News",
            category="ai",
            published_at=now,
            content_preview="Researchers have developed...",
            score=42.0,
        )
        assert article.score == 42.0
        assert article.published_at == now

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            Article(title="", url="https://example.com", source_name="Test")

    def test_content_preview_max_length(self):
        with pytest.raises(ValidationError):
            Article(
                title="Test",
                url="https://example.com",
                source_name="Test",
                content_preview="x" * 2001,
            )


class TestDigestEntry:
    def test_entry(self):
        article = Article(title="Test", url="https://example.com", source_name="Test")
        entry = DigestEntry(
            article=article, summary="This is a summary of the article."
        )
        assert entry.summary == "This is a summary of the article."
        assert entry.article.title == "Test"

    def test_empty_summary_rejected(self):
        article = Article(title="Test", url="https://example.com", source_name="Test")
        with pytest.raises(ValidationError):
            DigestEntry(article=article, summary="")


class TestDigest:
    def test_empty_digest(self):
        digest = Digest()
        assert digest.entries == []
        assert digest.source_count == 0
        assert digest.article_count == 0
        assert isinstance(digest.generated_at, datetime)

    def test_digest_with_entries(self):
        article = Article(title="Test", url="https://example.com", source_name="Test")
        entry = DigestEntry(article=article, summary="Summary here.")
        digest = Digest(entries=[entry], source_count=1, article_count=5)
        assert len(digest.entries) == 1
        assert digest.source_count == 1
        assert digest.article_count == 5


class TestDigestLog:
    def test_digest_log(self):
        now = datetime.now(timezone.utc)
        log = DigestLog(
            id=1,
            sent_at=now,
            recipient="test@example.com",
            source_count=5,
            article_count=30,
            entry_count=15,
            status="sent",
        )
        assert log.status == "sent"
        assert log.error is None

    def test_failed_digest_log(self):
        now = datetime.now(timezone.utc)
        log = DigestLog(
            id=2,
            sent_at=now,
            recipient="test@example.com",
            source_count=5,
            article_count=0,
            entry_count=0,
            status="failed",
            error="SMTP connection refused",
        )
        assert log.status == "failed"
        assert "SMTP" in log.error
