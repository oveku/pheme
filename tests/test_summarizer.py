"""Tests for the LLM summarizer module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.models import Article
from app.summarizer.llm import (
    LLMSummarizer,
    build_summary_prompt,
    SummarizerResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_articles() -> list[Article]:
    return [
        Article(
            title="Python 3.14 Released",
            url="https://python.org/news/3.14",
            source_name="TLDR Tech",
            content_preview="Python 3.14 introduces pattern matching improvements and performance gains.",
        ),
        Article(
            title="New AI Chip Breaks Records",
            url="https://techcrunch.com/ai-chip",
            source_name="TechCrunch",
            content_preview="A startup has developed an AI chip that outperforms current GPUs by 10x.",
        ),
        Article(
            title="Linux 7.0 Kernel Released",
            url="https://kernel.org/7.0",
            source_name="Hacker News",
            content_preview="",
        ),
    ]


@pytest.fixture
def single_article() -> Article:
    return Article(
        title="Rust 2.0 Announced",
        url="https://rust-lang.org/announce",
        source_name="TLDR Tech",
        content_preview="Major Rust release with async-await improvements.",
    )


MOCK_LLM_RESPONSE = "Python 3.14 brings performance gains. A new AI chip outperforms GPUs. Linux 7.0 kernel is released."


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


class TestBuildSummaryPrompt:
    """Tests for prompt construction."""

    def test_prompt_includes_article_titles(self, sample_articles: list[Article]):
        prompt = build_summary_prompt(sample_articles)
        for article in sample_articles:
            assert article.title in prompt

    def test_prompt_includes_urls(self, sample_articles: list[Article]):
        prompt = build_summary_prompt(sample_articles)
        for article in sample_articles:
            assert article.url in prompt

    def test_prompt_includes_content_preview_when_present(
        self, sample_articles: list[Article]
    ):
        prompt = build_summary_prompt(sample_articles)
        assert "pattern matching improvements" in prompt

    def test_prompt_handles_missing_content_preview(
        self, sample_articles: list[Article]
    ):
        prompt = build_summary_prompt(sample_articles)
        # Should not crash; article with empty content_preview still included
        assert "Linux 7.0 Kernel Released" in prompt

    def test_prompt_includes_instructions(self, sample_articles: list[Article]):
        prompt = build_summary_prompt(sample_articles)
        assert "summar" in prompt.lower()  # "summarize" or "summary"

    def test_empty_articles_returns_fallback(self):
        prompt = build_summary_prompt([])
        assert "no articles" in prompt.lower() or prompt == ""


# ---------------------------------------------------------------------------
# SummarizerResult model
# ---------------------------------------------------------------------------


class TestSummarizerResult:
    """Tests for the result container."""

    def test_success_result(self):
        result = SummarizerResult(
            summary="Test summary", success=True, model="test-model"
        )
        assert result.summary == "Test summary"
        assert result.success is True
        assert result.model == "test-model"
        assert result.error is None

    def test_failure_result(self):
        result = SummarizerResult(summary="", success=False, error="Connection refused")
        assert result.success is False
        assert result.error == "Connection refused"


# ---------------------------------------------------------------------------
# LLMSummarizer
# ---------------------------------------------------------------------------


class TestLLMSummarizer:
    """Tests for the Ollama-backed summarizer."""

    def test_default_config(self):
        summarizer = LLMSummarizer()
        assert summarizer.host == "http://localhost:11434"
        assert summarizer.model == "qwen2.5:1.5b-instruct"

    def test_custom_config(self):
        summarizer = LLMSummarizer(host="http://localhost:11434", model="phi4")
        assert summarizer.host == "http://localhost:11434"
        assert summarizer.model == "phi4"

    @pytest.mark.asyncio
    async def test_summarize_articles(self, sample_articles: list[Article]):
        """Summarize should call Ollama and return the LLM response."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(
            return_value={
                "message": {"content": MOCK_LLM_RESPONSE},
                "model": "qwen2.5:1.5b-instruct",
            }
        )

        with patch("app.summarizer.llm.AsyncClient", return_value=mock_client):
            summarizer = LLMSummarizer()
            result = await summarizer.summarize(sample_articles)

        assert result.success is True
        assert result.summary == MOCK_LLM_RESPONSE
        assert result.model == "qwen2.5:1.5b-instruct"
        mock_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_passes_correct_model(self, sample_articles: list[Article]):
        """The model name should be passed to Ollama chat."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(
            return_value={
                "message": {"content": "summary"},
                "model": "phi4",
            }
        )

        with patch("app.summarizer.llm.AsyncClient", return_value=mock_client):
            summarizer = LLMSummarizer(model="phi4")
            await summarizer.summarize(sample_articles)

        call_kwargs = mock_client.chat.call_args
        assert (
            call_kwargs.kwargs.get("model") == "phi4"
            or call_kwargs[1].get("model") == "phi4"
        )

    @pytest.mark.asyncio
    async def test_summarize_empty_articles(self):
        """Empty article list should return a fallback without calling LLM."""
        summarizer = LLMSummarizer()
        result = await summarizer.summarize([])

        assert result.success is True
        assert "no articles" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_summarize_single_article(self, single_article: Article):
        """Single article should still produce a valid summary."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(
            return_value={
                "message": {"content": "Rust 2.0 improves async-await."},
                "model": "qwen2.5:1.5b-instruct",
            }
        )

        with patch("app.summarizer.llm.AsyncClient", return_value=mock_client):
            summarizer = LLMSummarizer()
            result = await summarizer.summarize([single_article])

        assert result.success is True
        assert len(result.summary) > 0

    @pytest.mark.asyncio
    async def test_summarize_handles_connection_error(
        self, sample_articles: list[Article]
    ):
        """Connection errors should return a failure result with truncated fallback."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("app.summarizer.llm.AsyncClient", return_value=mock_client):
            summarizer = LLMSummarizer()
            result = await summarizer.summarize(sample_articles)

        assert result.success is False
        assert result.error is not None
        assert "Connection refused" in result.error
        # Fallback summary should contain article titles
        assert "Python 3.14 Released" in result.summary

    @pytest.mark.asyncio
    async def test_summarize_handles_malformed_response(
        self, sample_articles: list[Article]
    ):
        """Malformed responses should fall back gracefully."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value={"unexpected": "format"})

        with patch("app.summarizer.llm.AsyncClient", return_value=mock_client):
            summarizer = LLMSummarizer()
            result = await summarizer.summarize(sample_articles)

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_fallback_summary_format(self, sample_articles: list[Article]):
        """Fallback summary should list article titles with URLs."""
        summarizer = LLMSummarizer()
        fallback = summarizer._build_fallback(sample_articles)

        assert "Python 3.14 Released" in fallback
        assert "https://python.org/news/3.14" in fallback
        assert "New AI Chip Breaks Records" in fallback
        assert "Linux 7.0 Kernel Released" in fallback
