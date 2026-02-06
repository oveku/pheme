"""Topic matching and article ranking for the digest pipeline."""

import logging
import re
from dataclasses import dataclass, field

from app.models import Article, Topic

logger = logging.getLogger(__name__)


@dataclass
class ScoredArticle:
    """An article with a relevance score for a specific topic."""

    article: Article
    score: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)


def _build_searchable_text(article: Article) -> str:
    """Combine all article text fields into one searchable string."""
    parts = [article.title, article.content_preview]
    if article.full_text:
        parts.append(article.full_text)
    return " ".join(parts).lower()


def _keyword_score(text: str, keywords: list[str]) -> tuple[float, list[str]]:
    """Score text based on keyword matches.

    Returns (score, matched_keywords).
    Each keyword match adds points based on frequency (capped).
    """
    if not keywords:
        return 0.0, []

    score = 0.0
    matched = []
    text_lower = text.lower()

    for kw in keywords:
        kw_lower = kw.lower()
        count = text_lower.count(kw_lower)
        if count > 0:
            # Diminishing returns: first match = 10, each additional = 2 (cap 20)
            kw_score = 10.0 + min(count - 1, 5) * 2.0
            score += kw_score
            matched.append(kw)

    return score, matched


def _pattern_matches(text: str, patterns: list[str]) -> bool:
    """Check if any regex pattern matches the text."""
    for pattern in patterns:
        try:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        except re.error:
            logger.warning("Invalid regex pattern: %s", pattern)
    return False


def _recency_score(article: Article) -> float:
    """Score bonus for recent articles (0-10 points)."""
    if article.published_at is None:
        return 5.0  # Neutral if no date
    from datetime import datetime, timezone

    age_hours = (
        datetime.now(timezone.utc) - article.published_at
    ).total_seconds() / 3600
    if age_hours < 6:
        return 10.0
    elif age_hours < 24:
        return 8.0
    elif age_hours < 48:
        return 5.0
    elif age_hours < 72:
        return 3.0
    return 1.0


def score_article_for_topic(article: Article, topic: Topic) -> ScoredArticle | None:
    """Score an article's relevance to a topic.

    Returns None if the article is excluded by patterns or has zero relevance.
    """
    text = _build_searchable_text(article)

    # Check exclude patterns first
    if topic.exclude_patterns and _pattern_matches(text, topic.exclude_patterns):
        return None

    # Check include patterns (if any are set, at least one must match)
    if topic.include_patterns and not _pattern_matches(text, topic.include_patterns):
        return None

    # Score keywords
    kw_score, matched = _keyword_score(text, topic.keywords)

    # If topic has keywords but none matched, skip
    if topic.keywords and not matched:
        return None

    # Recency bonus
    recency = _recency_score(article)

    # Priority bonus
    priority_bonus = topic.priority * 0.5

    # Source score bonus (Reddit upvotes etc.)
    source_bonus = 0.0
    if article.score is not None and article.score > 0:
        source_bonus = min(article.score / 100, 10.0)

    total = kw_score + recency + priority_bonus + source_bonus

    return ScoredArticle(
        article=article,
        score=total,
        matched_keywords=matched,
    )


def rank_articles_for_topic(
    articles: list[Article], topic: Topic
) -> list[ScoredArticle]:
    """Rank articles by relevance to a topic.

    Returns up to topic.max_articles results, sorted by score descending.
    """
    scored = []
    for article in articles:
        result = score_article_for_topic(article, topic)
        if result is not None:
            scored.append(result)

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[: topic.max_articles]


def match_articles_to_topics(
    articles: list[Article], topics: list[Topic]
) -> dict[int, list[ScoredArticle]]:
    """Match all articles against all topics.

    Returns a dict mapping topic_id -> list of scored articles (ranked, capped).
    Articles can appear in multiple topics.
    """
    result: dict[int, list[ScoredArticle]] = {}

    for topic in topics:
        if not topic.enabled:
            continue
        ranked = rank_articles_for_topic(articles, topic)
        if ranked:
            result[topic.id] = ranked

    return result
