"""Digest pipeline - orchestrates fetch, extract, match, summarize, and send."""

import logging
from datetime import datetime, timezone

import aiosqlite

from app.models import Article, DigestEntry, Digest, Source, Topic, TopicSection
from app.database import (
    get_sources,
    get_topics,
    get_blocked_keywords,
    get_app_setting,
    update_source_last_fetched,
    log_digest,
)
from app.fetchers.factory import FetcherFactory
from app.fetchers.extractor import fetch_full_text
from app.summarizer.llm import LLMSummarizer, SummarizerResult
from app.pipeline.matching import (
    match_articles_to_topics,
    deduplicate_across_topics,
    filter_blocked_articles,
)
from app.email.sender import send_digest_email

logger = logging.getLogger(__name__)


class DigestPipeline:
    """Orchestrates the daily digest: fetch -> extract -> match -> summarize -> email.

    Uses dependency injection for db, fetcher factory, and summarizer,
    making all components testable in isolation.
    """

    def __init__(
        self,
        db,
        fetcher_factory: FetcherFactory | None = None,
        summarizer: LLMSummarizer | None = None,
    ) -> None:
        self.db = db
        self.fetcher_factory = fetcher_factory or FetcherFactory()
        self.summarizer = summarizer or LLMSummarizer()

    async def run(
        self,
        recipient: str = "",
        smtp_host: str = "",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_password: str = "",
    ) -> Digest:
        """Execute the full pipeline and return the digest.

        Steps:
        1. Fetch articles from all enabled sources
        2. Extract full text from article URLs
        3. Match articles to topics and rank
        4. Summarize per-article with LLM
        5. Build topic-grouped digest
        6. Send email (if recipient configured)
        7. Log to database
        """
        start = datetime.now(timezone.utc)
        logger.info("Digest pipeline started at %s", start.isoformat())

        # 1. Fetch from all enabled sources
        sources = await self._get_sources()
        all_articles: list[Article] = []
        successful_source_ids: list[int] = []

        for source in sources:
            try:
                fetcher = self.fetcher_factory.create_fetcher(source.type.value)
                articles = await fetcher.fetch(source)
                all_articles.extend(articles)
                successful_source_ids.append(source.id)
                logger.info("Fetched %d articles from %s", len(articles), source.name)
            except Exception as exc:
                logger.error("Failed to fetch from %s: %s", source.name, exc)

        # Update last_fetched for successful sources
        for source_id in successful_source_ids:
            await self._update_last_fetched(source_id)

        # 2. Extract full text
        await self._extract_full_text(all_articles)

        # 2b. Apply global keyword blocklist filter
        blocked_keywords_models = await self._get_blocked_keywords()
        blocked_keywords = [bk.keyword for bk in blocked_keywords_models]
        use_full_text = await self._get_filter_scope_full_text()
        if blocked_keywords:
            all_articles = filter_blocked_articles(
                all_articles, blocked_keywords, use_full_text=use_full_text
            )
            logger.info(
                "After keyword filter: %d articles remain", len(all_articles)
            )

        # 3. Get topics and match articles
        topics = await self._get_topics()
        topic_sections: list[TopicSection] = []

        if topics:
            # Topic-based mode: match and rank
            matches = match_articles_to_topics(all_articles, topics)
            topics_by_id = {t.id: t for t in topics}

            # 3b. Deduplicate: each article in at most one topic section
            matches = deduplicate_across_topics(matches, topics_by_id)

            for topic_id, scored_articles in matches.items():
                topic = topics_by_id[topic_id]
                articles_for_topic = [sa.article for sa in scored_articles]

                # 4. Summarize per-article
                article_summaries = await self.summarizer.summarize_articles_batch(
                    articles_for_topic
                )

                entries = [
                    DigestEntry(
                        article=asummary.article,
                        summary=asummary.summary,
                    )
                    for asummary in article_summaries
                ]

                topic_sections.append(
                    TopicSection(
                        topic_name=topic.name,
                        topic_id=topic.id,
                        entries=entries,
                    )
                )
        else:
            # Legacy mode: no topics configured, summarize all
            pass

        # 5. Build overview from topic headlines (not all 99 articles)
        if topic_sections:
            topic_summaries = [
                {
                    "topic": ts.topic_name,
                    "headlines": [e.article.title for e in ts.entries],
                }
                for ts in topic_sections
                if ts.entries
            ]
            summarizer_result = await self.summarizer.summarize_overview(
                topic_summaries
            )
        else:
            summarizer_result = await self.summarizer.summarize(all_articles)

        if summarizer_result.success:
            logger.info("Summarization complete (model: %s)", summarizer_result.model)
        else:
            logger.warning(
                "Summarization failed: %s (using fallback)", summarizer_result.error
            )

        # Build legacy entries (flat list for backwards compatibility)
        entries = [
            DigestEntry(
                article=article,
                summary=article.content_preview or article.title,
            )
            for article in all_articles
        ]

        digest = Digest(
            entries=entries,
            topic_sections=topic_sections,
            summary=summarizer_result.summary,
            model=summarizer_result.model,
            generated_at=datetime.now(timezone.utc),
            source_count=len(sources),
            article_count=len(all_articles),
        )

        # 6. Send email
        email_sent = False
        if recipient:
            email_sent = await send_digest_email(
                digest=digest,
                recipient=recipient,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
            )

        # 7. Log digest run
        entry_count = sum(len(ts.entries) for ts in topic_sections) or len(entries)
        status = (
            "sent" if email_sent else ("completed" if not recipient else "email_failed")
        )
        await self._log_digest(
            recipient=recipient,
            source_count=len(sources),
            article_count=len(all_articles),
            entry_count=entry_count,
            status=status,
        )

        logger.info(
            "Digest pipeline complete: %d sources, %d articles, %d topics, status=%s",
            len(sources),
            len(all_articles),
            len(topic_sections),
            status,
        )
        return digest

    # --- Full-text extraction ---

    async def _extract_full_text(self, articles: list[Article]) -> None:
        """Fetch full text for all articles. Modifies articles in-place."""
        for article in articles:
            if article.full_text:
                continue  # Already has full text
            result = await fetch_full_text(article.url)
            if result.success:
                article.full_text = result.text
                logger.debug(
                    "Extracted %d words from %s", result.word_count, article.url
                )

    # --- DB adapter methods (allow mocking in tests) ---

    async def _get_sources(self) -> list[Source]:
        """Get enabled sources. Handles both mock and real db."""
        if hasattr(self.db, "get_sources"):
            return await self.db.get_sources(enabled_only=True)
        return await get_sources(self.db, enabled_only=True)

    async def _get_topics(self) -> list[Topic]:
        """Get enabled topics. Handles both mock and real db."""
        if hasattr(self.db, "get_topics"):
            return await self.db.get_topics(enabled_only=True)
        return await get_topics(self.db, enabled_only=True)

    async def _get_blocked_keywords(self):
        """Get all blocked keywords from DB."""
        if hasattr(self.db, "get_blocked_keywords"):
            return await self.db.get_blocked_keywords()
        return await get_blocked_keywords(self.db)

    async def _get_filter_scope_full_text(self) -> bool:
        """Read the filter_scope setting; returns True if full_text enabled."""
        if hasattr(self.db, "get_app_setting"):
            val = await self.db.get_app_setting("filter_scope", default="title_preview")
        else:
            val = await get_app_setting(self.db, "filter_scope", default="title_preview")
        return val == "full_text"

    async def _update_last_fetched(self, source_id: int) -> None:
        if hasattr(self.db, "update_source_last_fetched"):
            await self.db.update_source_last_fetched(source_id)
        else:
            await update_source_last_fetched(self.db, source_id)

    async def _log_digest(self, **kwargs) -> None:
        if hasattr(self.db, "log_digest"):
            await self.db.log_digest(**kwargs)
        else:
            await log_digest(self.db, **kwargs)
