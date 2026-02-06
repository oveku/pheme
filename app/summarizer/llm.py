"""LLM-based article summarizer using Ollama on Ni (hailo-accelerated)."""

import logging
from dataclasses import dataclass, field

from ollama import AsyncClient

from app.models import Article

logger = logging.getLogger(__name__)


@dataclass
class SummarizerResult:
    """Container for summarization results."""

    summary: str
    success: bool
    model: str = ""
    error: str | None = None


@dataclass
class ArticleSummary:
    """Summary for a single article."""

    article: Article
    summary: str
    success: bool


def build_summary_prompt(articles: list[Article]) -> str:
    """Build the LLM prompt from a list of articles.

    Returns a structured prompt asking the model to produce
    a concise, readable digest summary.
    """
    if not articles:
        return "No articles to summarize."

    lines: list[str] = []
    lines.append(
        "You are a tech news editor. Summarize the following articles "
        "into a concise daily digest. For each article, write 1-2 sentences "
        "capturing the key point. Group related topics when possible. "
        "Use a professional, informative tone.\n"
    )

    for i, article in enumerate(articles, 1):
        lines.append(f"--- Article {i} ---")
        lines.append(f"Title: {article.title}")
        lines.append(f"Source: {article.source_name}")
        lines.append(f"URL: {article.url}")
        if article.full_text:
            # Use full text (truncated to ~2000 chars for prompt size)
            lines.append(f"Content: {article.full_text[:2000]}")
        elif article.content_preview:
            lines.append(f"Preview: {article.content_preview}")
        lines.append("")

    lines.append("Write the digest summary now. Keep it concise and scannable.")
    return "\n".join(lines)


def build_overview_prompt(topic_summaries: list[dict]) -> str:
    """Build a brief overview from already-summarized topic sections.

    Each item in topic_summaries: {"topic": str, "headlines": list[str]}
    Produces a 3-5 sentence executive summary of today's digest.
    """
    lines: list[str] = [
        "You are a news editor writing a brief overview for a daily digest email. "
        "Write exactly 3-5 short sentences highlighting the most important stories "
        "across all topics below. Be direct and concise. No bullet points, "
        "no headers, just a flowing paragraph.\n",
    ]
    for ts in topic_summaries:
        lines.append(f"Topic: {ts['topic']}")
        for h in ts["headlines"]:
            lines.append(f"  - {h}")
        lines.append("")
    lines.append("Write the brief overview now (3-5 sentences max):")
    return "\n".join(lines)


def build_article_summary_prompt(article: Article) -> str:
    """Build a prompt to summarize a single article.

    Uses full_text if available, otherwise falls back to content_preview.
    """
    lines: list[str] = []
    lines.append(
        "Summarize the following article in exactly 1 sentence (max 30 words). "
        "Be factual and direct. No filler words.\n"
    )
    lines.append(f"Title: {article.title}")
    lines.append(f"Source: {article.source_name}")

    if article.full_text:
        lines.append(f"Content:\n{article.full_text[:3000]}")
    elif article.content_preview:
        lines.append(f"Content:\n{article.content_preview}")
    else:
        lines.append("(No content available - summarize based on title)")

    lines.append("\nWrite exactly 1 sentence:")
    return "\n".join(lines)


class LLMSummarizer:
    """Summarizes articles using Ollama.

    Falls back to a simple title listing when the LLM is unreachable.
    """

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "qwen2.5:1.5b-instruct",
    ) -> None:
        self.host = host
        self.model = model

    async def summarize_overview(
        self, topic_summaries: list[dict]
    ) -> SummarizerResult:
        """Generate a brief overview from topic headlines.

        topic_summaries: [{"topic": str, "headlines": [str, ...]}, ...]
        """
        if not topic_summaries:
            return SummarizerResult(
                summary="No topics to summarize.",
                success=True,
                model=self.model,
            )

        prompt = build_overview_prompt(topic_summaries)

        try:
            client = AsyncClient(host=self.host)
            response = await client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response["message"]["content"]
            return SummarizerResult(
                summary=content.strip(),
                success=True,
                model=response.get("model", self.model),
            )
        except Exception as exc:
            # Fallback: list topic names
            fallback = ", ".join(ts["topic"] for ts in topic_summaries)
            return SummarizerResult(
                summary=f"Today's digest covers: {fallback}.",
                success=False,
                model=self.model,
                error=str(exc),
            )

    async def summarize(self, articles: list[Article]) -> SummarizerResult:
        """Summarize a batch of articles via the Ollama chat API.

        Returns a ``SummarizerResult`` with the LLM output on success,
        or a fallback bullet-list on failure.
        """
        if not articles:
            return SummarizerResult(
                summary="No articles to summarize.",
                success=True,
                model=self.model,
            )

        prompt = build_summary_prompt(articles)

        try:
            client = AsyncClient(host=self.host)
            response = await client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract content from response
            try:
                content = response["message"]["content"]
            except (KeyError, TypeError):
                return SummarizerResult(
                    summary=self._build_fallback(articles),
                    success=False,
                    model=self.model,
                    error="Malformed response from Ollama",
                )

            return SummarizerResult(
                summary=content,
                success=True,
                model=response.get("model", self.model),
            )

        except Exception as exc:
            return SummarizerResult(
                summary=self._build_fallback(articles),
                success=False,
                model=self.model,
                error=str(exc),
            )

    async def summarize_article(self, article: Article) -> ArticleSummary:
        """Summarize a single article using the LLM.

        Returns an ArticleSummary with the per-article summary text.
        Falls back to content_preview or title on failure.
        """
        prompt = build_article_summary_prompt(article)

        try:
            client = AsyncClient(host=self.host)
            response = await client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response["message"]["content"]
            return ArticleSummary(article=article, summary=content, success=True)
        except Exception as exc:
            logger.debug(
                "Per-article summarization failed for %s: %s", article.title, exc
            )
            fallback = (
                article.content_preview[:200]
                if article.content_preview
                else article.title
            )
            return ArticleSummary(article=article, summary=fallback, success=False)

    async def summarize_articles_batch(
        self, articles: list[Article]
    ) -> list[ArticleSummary]:
        """Summarize a list of articles individually.

        Processes sequentially to avoid overwhelming the LLM server.
        """
        results = []
        for article in articles:
            result = await self.summarize_article(article)
            results.append(result)
        return results

    def _build_fallback(self, articles: list[Article]) -> str:
        """Build a plain-text fallback when the LLM is unavailable."""
        lines = ["Today's articles:\n"]
        for article in articles:
            lines.append(f"- {article.title}")
            lines.append(f"  {article.url}")
            if article.content_preview:
                preview = article.content_preview[:200]
                lines.append(f"  {preview}")
            lines.append("")
        return "\n".join(lines)
