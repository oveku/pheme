"""Topic matching, article ranking, filtering, and deduplication.

Implements the Strategy pattern for article filtering and a deduplication
pass to ensure each article appears in at most one topic section.
"""

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


# ---------------------------------------------------------------------------
# Article age filtering
# ---------------------------------------------------------------------------


def filter_old_articles(
    articles: list[Article],
    max_age_hours: int,
    *,
    now: "datetime | None" = None,
) -> list[Article]:
    """Remove articles older than max_age_hours.

    Args:
        articles: List of articles to filter.
        max_age_hours: Maximum age in hours. 0 means no filtering.
        now: Override current time (for testing).

    Returns:
        Filtered list. Articles without a published_at date are kept
        (benefit of the doubt).
    """
    if max_age_hours <= 0:
        return list(articles)

    from datetime import datetime, timezone, timedelta

    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=max_age_hours)
    filtered: list[Article] = []

    for article in articles:
        if article.published_at is None:
            filtered.append(article)  # No date → keep
            continue
        if article.published_at >= cutoff:
            filtered.append(article)
        else:
            logger.info(
                "Dropped stale article '%s' (published %s)",
                article.title[:80],
                article.published_at.isoformat(),
            )

    dropped = len(articles) - len(filtered)
    if dropped:
        logger.info(
            "Age filter: dropped %d of %d articles (max_age=%dh)",
            dropped, len(articles), max_age_hours,
        )
    return filtered


# ---------------------------------------------------------------------------
# Global keyword blocklist filtering (Strategy pattern)
# ---------------------------------------------------------------------------


def filter_blocked_articles(
    articles: list[Article],
    blocked_keywords: list[str],
    *,
    use_full_text: bool = False,
) -> list[Article]:
    """Remove articles containing any blocked keyword (case-insensitive).

    Args:
        articles: List of articles to filter.
        blocked_keywords: Keywords/phrases to block.
        use_full_text: When True, also search article.full_text.
                       When False, only title + content_preview are checked.

    Returns:
        Filtered list with blocked articles removed.
    """
    if not blocked_keywords:
        return list(articles)

    keywords_lower = [kw.lower() for kw in blocked_keywords]
    filtered: list[Article] = []

    for article in articles:
        body = (
            (article.full_text or "")
            if use_full_text
            else (article.content_preview or "")
        )
        searchable = (article.title + " " + body).lower()

        if any(kw in searchable for kw in keywords_lower):
            logger.info(
                "Blocked article '%s' — matched keyword blocklist",
                article.title[:80],
            )
            continue

        filtered.append(article)

    blocked_count = len(articles) - len(filtered)
    if blocked_count:
        logger.info(
            "Keyword filter: blocked %d of %d articles", blocked_count, len(articles)
        )
    return filtered


# ---------------------------------------------------------------------------
# Cross-topic deduplication
# ---------------------------------------------------------------------------


def deduplicate_across_topics(
    matched: dict[int, list[ScoredArticle]],
    topics_by_id: dict[int, Topic],
) -> dict[int, list[ScoredArticle]]:
    """Assign each article to exactly one topic (highest score wins).

    When an article appears in multiple topics, it is kept only in the topic
    where it scored highest.  Ties are broken by:
      1. Topic priority (higher wins)
      2. Topic name alphabetically (deterministic fallback)

    Args:
        matched: topic_id → list of ScoredArticle (from match_articles_to_topics).
        topics_by_id: topic_id → Topic (for priority / name lookups).

    Returns:
        A new dict with the same structure, but each article URL appears at most once.
    """
    if not matched:
        return {}

    # 1. Build a map: article_url → list[(topic_id, score)]
    url_to_entries: dict[str, list[tuple[int, float]]] = {}
    for topic_id, scored_articles in matched.items():
        for sa in scored_articles:
            url_to_entries.setdefault(sa.article.url, []).append(
                (topic_id, sa.score)
            )

    # 2. Determine the winning topic for each duplicated article
    urls_to_remove: dict[int, set[str]] = {}  # topic_id → urls to remove
    for url, entries in url_to_entries.items():
        if len(entries) <= 1:
            continue  # Not duplicated

        # Sort by: score DESC, priority DESC, name ASC
        def _sort_key(entry: tuple[int, float]) -> tuple[float, int, str]:
            tid, score = entry
            topic = topics_by_id.get(tid)
            priority = topic.priority if topic else 0
            name = topic.name if topic else ""
            # Negate score and priority so higher values sort first;
            # name sorts ascending naturally.
            return (-score, -priority, name)

        entries.sort(key=_sort_key)
        winner_topic_id = entries[0][0]

        # Mark this URL for removal from all non-winning topics
        for tid, _ in entries[1:]:
            urls_to_remove.setdefault(tid, set()).add(url)

    # 3. Build cleaned result
    result: dict[int, list[ScoredArticle]] = {}
    for topic_id, scored_articles in matched.items():
        remove_set = urls_to_remove.get(topic_id, set())
        cleaned = [sa for sa in scored_articles if sa.article.url not in remove_set]
        result[topic_id] = cleaned

    deduped = sum(len(s) for s in urls_to_remove.values())
    if deduped:
        logger.info(
            "Deduplication: removed %d cross-topic duplicate article placements",
            deduped,
        )

    return result
