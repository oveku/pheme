"""Tests for email composer and sender."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.models import Article, DigestEntry, Digest
from app.email.composer import compose_digest_html, compose_digest_plain
from app.email.sender import send_digest_email


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_digest() -> Digest:
    articles = [
        Article(
            title="Python 3.14 Released",
            url="https://python.org/news/3.14",
            source_name="TLDR Tech",
            content_preview="Major new release.",
        ),
        Article(
            title="New AI Chip",
            url="https://techcrunch.com/ai-chip",
            source_name="TechCrunch",
            content_preview="A breakthrough chip.",
        ),
    ]
    entries = [
        DigestEntry(
            article=articles[0],
            summary="Python 3.14 brings performance gains and pattern matching improvements.",
        ),
        DigestEntry(
            article=articles[1],
            summary="A startup's new AI chip outperforms current GPUs by 10x.",
        ),
    ]
    return Digest(
        entries=entries,
        summary="Today: Python releases a major update and a new AI chip breaks records.",
        model="qwen2.5:1.5b-instruct",
        source_count=2,
        article_count=2,
        generated_at=datetime(2026, 2, 6, 6, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def empty_digest() -> Digest:
    return Digest(
        entries=[],
        source_count=0,
        article_count=0,
        generated_at=datetime(2026, 2, 6, 6, 0, 0, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# HTML Composer
# ---------------------------------------------------------------------------


class TestComposeDigestHtml:
    """Tests for HTML email composition."""

    def test_contains_title(self, sample_digest: Digest):
        html = compose_digest_html(sample_digest)
        assert "Pheme Daily Digest" in html

    def test_contains_date(self, sample_digest: Digest):
        html = compose_digest_html(sample_digest)
        assert "2026" in html

    def test_contains_article_titles(self, sample_digest: Digest):
        html = compose_digest_html(sample_digest)
        assert "Python 3.14 Released" in html
        assert "New AI Chip" in html

    def test_contains_article_urls(self, sample_digest: Digest):
        html = compose_digest_html(sample_digest)
        assert "https://python.org/news/3.14" in html
        assert "https://techcrunch.com/ai-chip" in html

    def test_contains_summaries(self, sample_digest: Digest):
        html = compose_digest_html(sample_digest)
        assert "performance gains" in html
        assert "outperforms current GPUs" in html

    def test_contains_overall_summary(self, sample_digest: Digest):
        html = compose_digest_html(sample_digest)
        assert "Today: Python releases a major update" in html

    def test_contains_model_attribution(self, sample_digest: Digest):
        html = compose_digest_html(sample_digest)
        assert "qwen2.5:1.5b-instruct" in html

    def test_contains_source_count(self, sample_digest: Digest):
        html = compose_digest_html(sample_digest)
        assert "2 articles" in html
        assert "2 sources" in html

    def test_empty_digest_shows_message(self, empty_digest: Digest):
        html = compose_digest_html(empty_digest)
        assert "No articles" in html

    def test_returns_valid_html(self, sample_digest: Digest):
        html = compose_digest_html(sample_digest)
        assert html.strip().startswith("<!DOCTYPE html>")
        assert "</html>" in html


# ---------------------------------------------------------------------------
# Plain-text Composer
# ---------------------------------------------------------------------------


class TestComposeDigestPlain:
    """Tests for plain-text email fallback."""

    def test_contains_title(self, sample_digest: Digest):
        text = compose_digest_plain(sample_digest)
        assert "Pheme Daily Digest" in text

    def test_contains_article_titles(self, sample_digest: Digest):
        text = compose_digest_plain(sample_digest)
        assert "Python 3.14 Released" in text
        assert "New AI Chip" in text

    def test_contains_urls(self, sample_digest: Digest):
        text = compose_digest_plain(sample_digest)
        assert "https://python.org/news/3.14" in text

    def test_contains_summaries(self, sample_digest: Digest):
        text = compose_digest_plain(sample_digest)
        assert "performance gains" in text

    def test_empty_digest(self, empty_digest: Digest):
        text = compose_digest_plain(empty_digest)
        assert "No articles" in text


# ---------------------------------------------------------------------------
# Email Sender
# ---------------------------------------------------------------------------


class TestSendDigestEmail:
    """Tests for SMTP email sending."""

    @pytest.mark.asyncio
    async def test_send_email_success(self, sample_digest: Digest):
        """Should send email via SMTP and return True."""
        with patch("app.email.sender.aiosmtplib") as mock_smtp:
            mock_smtp.send = AsyncMock()
            result = await send_digest_email(
                digest=sample_digest,
                recipient="test@example.com",
                smtp_host="smtp.test.com",
                smtp_port=587,
                smtp_user="user@test.com",
                smtp_password="password123",
            )

        assert result is True
        mock_smtp.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_includes_html_and_plain(self, sample_digest: Digest):
        """Should include both HTML and plain-text alternatives."""
        with patch("app.email.sender.aiosmtplib") as mock_smtp:
            mock_smtp.send = AsyncMock()
            await send_digest_email(
                digest=sample_digest,
                recipient="test@example.com",
                smtp_host="smtp.test.com",
                smtp_port=587,
                smtp_user="user@test.com",
                smtp_password="password123",
            )

        call_args = mock_smtp.send.call_args
        message = call_args[0][0]  # first positional arg
        # MIMEMultipart with alternatives
        payloads = message.get_payload()
        content_types = [p.get_content_type() for p in payloads]
        assert "text/plain" in content_types
        assert "text/html" in content_types

    @pytest.mark.asyncio
    async def test_send_email_correct_subject(self, sample_digest: Digest):
        """Subject should include Pheme and date."""
        with patch("app.email.sender.aiosmtplib") as mock_smtp:
            mock_smtp.send = AsyncMock()
            await send_digest_email(
                digest=sample_digest,
                recipient="test@example.com",
                smtp_host="smtp.test.com",
                smtp_port=587,
                smtp_user="user@test.com",
                smtp_password="password123",
            )

        call_args = mock_smtp.send.call_args
        message = call_args[0][0]
        assert "Pheme" in message["Subject"]

    @pytest.mark.asyncio
    async def test_send_email_correct_recipient(self, sample_digest: Digest):
        """To header should match recipient."""
        with patch("app.email.sender.aiosmtplib") as mock_smtp:
            mock_smtp.send = AsyncMock()
            await send_digest_email(
                digest=sample_digest,
                recipient="dest@example.com",
                smtp_host="smtp.test.com",
                smtp_port=587,
                smtp_user="user@test.com",
                smtp_password="password123",
            )

        call_args = mock_smtp.send.call_args
        message = call_args[0][0]
        assert message["To"] == "dest@example.com"

    @pytest.mark.asyncio
    async def test_send_email_failure_returns_false(self, sample_digest: Digest):
        """SMTP errors should return False, not raise."""
        with patch("app.email.sender.aiosmtplib") as mock_smtp:
            mock_smtp.send = AsyncMock(side_effect=Exception("SMTP error"))
            result = await send_digest_email(
                digest=sample_digest,
                recipient="test@example.com",
                smtp_host="smtp.test.com",
                smtp_port=587,
                smtp_user="user@test.com",
                smtp_password="password123",
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_skipped_when_no_recipient(self, sample_digest: Digest):
        """Should return False without sending when recipient is empty."""
        result = await send_digest_email(
            digest=sample_digest,
            recipient="",
            smtp_host="smtp.test.com",
            smtp_port=587,
            smtp_user="user@test.com",
            smtp_password="password123",
        )
        assert result is False
