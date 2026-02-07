"""Tests for the topic matching and ranking module."""

import pytest
from datetime import datetime, timezone, timedelta

from app.models import Article, Topic
from app.pipeline.matching import (
    score_article_for_topic,
    rank_articles_for_topic,
    match_articles_to_topics,
    deduplicate_across_topics,
    filter_blocked_articles,
    _build_searchable_text,
    _keyword_score,
    _recency_score,
)


@pytest.fixture
def ai_topic() -> Topic:
    return Topic(
        id=1,
        name="AI & ML",
        keywords=[
            "artificial intelligence",
            "machine learning",
            "neural network",
            "LLM",
        ],
        include_patterns=[],
        exclude_patterns=[],
        priority=80,
        max_articles=10,
        enabled=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def security_topic() -> Topic:
    return Topic(
        id=2,
        name="Security",
        keywords=["cybersecurity", "vulnerability", "exploit", "CVE"],
        include_patterns=[],
        exclude_patterns=[r"sponsored"],
        priority=70,
        max_articles=5,
        enabled=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def ai_article() -> Article:
    return Article(
        title="New Neural Network Architecture Breaks Records",
        url="https://example.com/ai",
        source_name="TechCrunch",
        content_preview="Researchers developed a new neural network that outperforms GPT.",
        full_text="A breakthrough in artificial intelligence. The neural network uses machine learning techniques.",
        published_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )


@pytest.fixture
def security_article() -> Article:
    return Article(
        title="Critical CVE-2026-1234 Vulnerability Found",
        url="https://example.com/sec",
        source_name="SecurityWeek",
        content_preview="A critical exploit was discovered in a popular library.",
        full_text="Cybersecurity researchers found a vulnerability. CVE-2026-1234 allows remote code execution.",
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )


@pytest.fixture
def unrelated_article() -> Article:
    return Article(
        title="Best Chocolate Cake Recipe",
        url="https://example.com/cake",
        source_name="FoodBlog",
        content_preview="Delicious chocolate cake with cream cheese frosting.",
        published_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sponsored_article() -> Article:
    return Article(
        title="CVE Scanner - Sponsored Review",
        url="https://example.com/sponsored",
        source_name="TechBlog",
        content_preview="This is a sponsored review of a vulnerability scanner.",
        full_text="Sponsored content about cybersecurity tools.",
    )


class TestBuildSearchableText:
    def test_combines_title_and_preview(self):
        article = Article(
            title="Test Title",
            url="https://example.com",
            source_name="Test",
            content_preview="Preview text here",
        )
        text = _build_searchable_text(article)
        assert "test title" in text
        assert "preview text here" in text

    def test_includes_full_text(self):
        article = Article(
            title="Title",
            url="https://example.com",
            source_name="Test",
            full_text="Full article content with details",
        )
        text = _build_searchable_text(article)
        assert "full article content" in text


class TestKeywordScore:
    def test_matching_keywords(self):
        score, matched = _keyword_score(
            "artificial intelligence and machine learning advances",
            ["artificial intelligence", "machine learning", "blockchain"],
        )
        assert score > 0
        assert "artificial intelligence" in matched
        assert "machine learning" in matched
        assert "blockchain" not in matched

    def test_no_matching_keywords(self):
        score, matched = _keyword_score("chocolate cake recipe", ["AI", "ML"])
        assert score == 0
        assert matched == []

    def test_empty_keywords(self):
        score, matched = _keyword_score("any text", [])
        assert score == 0
        assert matched == []

    def test_repeated_keyword_diminishing_returns(self):
        text = "AI AI AI AI AI"
        score_once, _ = _keyword_score("AI", ["AI"])
        score_many, _ = _keyword_score(text, ["AI"])
        assert score_many > score_once
        # But capped (not 5x)
        assert score_many < score_once * 3


class TestRecencyScore:
    def test_very_recent(self):
        article = Article(
            title="T",
            url="https://x.com",
            source_name="S",
            published_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert _recency_score(article) == 10.0

    def test_old_article(self):
        article = Article(
            title="T",
            url="https://x.com",
            source_name="S",
            published_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        assert _recency_score(article) == 1.0

    def test_no_date(self):
        article = Article(title="T", url="https://x.com", source_name="S")
        assert _recency_score(article) == 5.0


class TestScoreArticleForTopic:
    def test_matching_article(self, ai_article, ai_topic):
        result = score_article_for_topic(ai_article, ai_topic)
        assert result is not None
        assert result.score > 0
        assert len(result.matched_keywords) > 0

    def test_unrelated_article_returns_none(self, unrelated_article, ai_topic):
        result = score_article_for_topic(unrelated_article, ai_topic)
        assert result is None

    def test_exclude_pattern_filters(self, sponsored_article, security_topic):
        result = score_article_for_topic(sponsored_article, security_topic)
        assert result is None

    def test_include_pattern_required(self):
        topic = Topic(
            id=1,
            name="CVE Only",
            keywords=["vulnerability"],
            include_patterns=[r"CVE-\d+"],
            exclude_patterns=[],
            priority=50,
            max_articles=10,
            enabled=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        # Article with CVE
        article_match = Article(
            title="CVE-2026-5678 Found",
            url="https://x.com",
            source_name="S",
            content_preview="A vulnerability CVE-2026-5678 was discovered.",
        )
        result = score_article_for_topic(article_match, topic)
        assert result is not None

        # Article without CVE
        article_no_match = Article(
            title="General vulnerability discussion",
            url="https://x.com",
            source_name="S",
            content_preview="Discussion about vulnerabilities in general.",
        )
        result = score_article_for_topic(article_no_match, topic)
        assert result is None


class TestRankArticlesForTopic:
    def test_ranks_by_score(self, ai_topic):
        articles = [
            Article(
                title="Minor AI Update",
                url="https://x.com/1",
                source_name="S",
                content_preview="Small AI improvements.",
                published_at=datetime.now(timezone.utc) - timedelta(days=3),
            ),
            Article(
                title="Major Neural Network Breakthrough in Machine Learning",
                url="https://x.com/2",
                source_name="S",
                content_preview="Neural network and artificial intelligence revolution.",
                full_text="Machine learning and artificial intelligence advance rapidly with neural network innovations.",
                published_at=datetime.now(timezone.utc) - timedelta(hours=1),
            ),
        ]
        ranked = rank_articles_for_topic(articles, ai_topic)
        assert len(ranked) >= 1
        # Higher score first
        if len(ranked) == 2:
            assert ranked[0].score >= ranked[1].score

    def test_respects_max_articles(self):
        topic = Topic(
            id=1,
            name="AI",
            keywords=["python"],
            include_patterns=[],
            exclude_patterns=[],
            priority=50,
            max_articles=2,
            enabled=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        articles = [
            Article(
                title=f"Python Article {i}",
                url=f"https://x.com/{i}",
                source_name="S",
                content_preview="Python programming.",
            )
            for i in range(5)
        ]
        ranked = rank_articles_for_topic(articles, topic)
        assert len(ranked) <= 2


class TestMatchArticlesToTopics:
    def test_multi_topic_matching(
        self, ai_topic, security_topic, ai_article, security_article
    ):
        articles = [ai_article, security_article]
        topics = [ai_topic, security_topic]

        result = match_articles_to_topics(articles, topics)

        assert ai_topic.id in result
        assert security_topic.id in result

    def test_disabled_topic_excluded(self, ai_article):
        disabled_topic = Topic(
            id=1,
            name="Disabled",
            keywords=["neural"],
            include_patterns=[],
            exclude_patterns=[],
            priority=50,
            max_articles=10,
            enabled=False,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        result = match_articles_to_topics([ai_article], [disabled_topic])
        assert len(result) == 0

    def test_article_can_appear_in_multiple_topics(self):
        article = Article(
            title="AI Security Vulnerability in LLM Systems",
            url="https://x.com",
            source_name="S",
            content_preview="Machine learning model has cybersecurity vulnerability exploit.",
        )
        ai_topic = Topic(
            id=1,
            name="AI",
            keywords=["machine learning", "LLM"],
            include_patterns=[],
            exclude_patterns=[],
            priority=50,
            max_articles=10,
            enabled=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        sec_topic = Topic(
            id=2,
            name="Security",
            keywords=["cybersecurity", "vulnerability"],
            include_patterns=[],
            exclude_patterns=[],
            priority=50,
            max_articles=10,
            enabled=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        result = match_articles_to_topics([article], [ai_topic, sec_topic])
        assert ai_topic.id in result
        assert sec_topic.id in result


# ---------------------------------------------------------------------------
# Keyword filtering (blocklist)
# ---------------------------------------------------------------------------


class TestFilterBlockedArticles:
    """Tests for global keyword blocklist filtering (Strategy pattern)."""

    def _make_article(
        self,
        title: str = "Test Article",
        preview: str = "",
        full_text: str = "",
        url: str = "https://example.com/a",
    ) -> Article:
        return Article(
            title=title,
            url=url,
            source_name="TestSource",
            content_preview=preview,
            full_text=full_text,
        )

    def test_no_keywords_passes_all(self):
        articles = [self._make_article(title="Anything goes")]
        result = filter_blocked_articles(articles, [], use_full_text=False)
        assert len(result) == 1

    def test_blocks_keyword_in_title(self):
        articles = [
            self._make_article(title="Trump announces new policy"),
            self._make_article(title="Python 3.15 released"),
        ]
        result = filter_blocked_articles(articles, ["Trump"], use_full_text=False)
        assert len(result) == 1
        assert result[0].title == "Python 3.15 released"

    def test_blocks_keyword_in_content_preview(self):
        articles = [
            self._make_article(
                title="World News",
                preview="Epstein documents released today",
            ),
        ]
        result = filter_blocked_articles(articles, ["Epstein"], use_full_text=False)
        assert len(result) == 0

    def test_case_insensitive(self):
        articles = [self._make_article(title="TRUMP policy update")]
        result = filter_blocked_articles(articles, ["trump"], use_full_text=False)
        assert len(result) == 0

    def test_multi_word_keyword(self):
        articles = [
            self._make_article(title="Donald Trump signs executive order"),
            self._make_article(title="Donald Duck visits Disneyland"),
        ]
        result = filter_blocked_articles(
            articles, ["Donald Trump"], use_full_text=False
        )
        assert len(result) == 1
        assert "Duck" in result[0].title

    def test_full_text_scope_off_ignores_body(self):
        """When use_full_text=False, keywords in full_text don't trigger filtering."""
        articles = [
            self._make_article(
                title="Clean Title",
                preview="Clean preview",
                full_text="Trump mentioned deep in the article body",
            ),
        ]
        result = filter_blocked_articles(articles, ["Trump"], use_full_text=False)
        assert len(result) == 1  # Not filtered because full_text not checked

    def test_full_text_scope_on_checks_body(self):
        """When use_full_text=True, keywords in full_text trigger filtering."""
        articles = [
            self._make_article(
                title="Clean Title",
                preview="Clean preview",
                full_text="Trump mentioned deep in the article body",
            ),
        ]
        result = filter_blocked_articles(articles, ["Trump"], use_full_text=True)
        assert len(result) == 0  # Filtered because full_text is checked

    def test_multiple_blocked_keywords(self):
        articles = [
            self._make_article(title="Trump policy"),
            self._make_article(title="Epstein case update"),
            self._make_article(title="Python 3.15 released"),
        ]
        result = filter_blocked_articles(
            articles, ["Trump", "Epstein", "Donald Trump"], use_full_text=False
        )
        assert len(result) == 1
        assert result[0].title == "Python 3.15 released"

    def test_empty_articles_list(self):
        result = filter_blocked_articles([], ["Trump"], use_full_text=False)
        assert result == []

    def test_substring_match(self):
        """Blocked keyword 'Trump' should also block 'Trumpism'."""
        articles = [self._make_article(title="The rise of Trumpism")]
        result = filter_blocked_articles(articles, ["Trump"], use_full_text=False)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Cross-topic deduplication
# ---------------------------------------------------------------------------


class TestDeduplicateAcrossTopics:
    """Tests for the deduplication strategy that assigns each article to one topic."""

    def _make_topic(
        self, id: int, name: str, priority: int = 50, keywords: list[str] | None = None
    ) -> Topic:
        return Topic(
            id=id,
            name=name,
            keywords=keywords or ["test"],
            include_patterns=[],
            exclude_patterns=[],
            priority=priority,
            max_articles=10,
            enabled=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    def _make_scored(self, url: str, score: float) -> "ScoredArticle":
        from app.pipeline.matching import ScoredArticle

        article = Article(
            title=f"Article {url}",
            url=url,
            source_name="TestSource",
            content_preview="Some content",
        )
        return ScoredArticle(article=article, score=score, matched_keywords=["test"])

    def test_no_duplicates_unchanged(self):
        """Articles appearing in only one topic are not affected."""
        topics = {
            1: self._make_topic(1, "AI"),
            2: self._make_topic(2, "Security"),
        }
        matched = {
            1: [self._make_scored("https://a.com", 20.0)],
            2: [self._make_scored("https://b.com", 15.0)],
        }
        result = deduplicate_across_topics(matched, topics)
        assert len(result[1]) == 1
        assert len(result[2]) == 1

    def test_duplicate_assigned_to_highest_score(self):
        """Article in two topics goes to the one with the higher score."""
        topics = {
            1: self._make_topic(1, "AI", priority=50),
            2: self._make_topic(2, "Security", priority=50),
        }
        matched = {
            1: [self._make_scored("https://shared.com", 30.0)],
            2: [self._make_scored("https://shared.com", 20.0)],
        }
        result = deduplicate_across_topics(matched, topics)
        assert len(result.get(1, [])) == 1
        assert len(result.get(2, [])) == 0

    def test_tie_broken_by_priority(self):
        """Same score → article goes to the higher-priority topic."""
        topics = {
            1: self._make_topic(1, "AI", priority=80),
            2: self._make_topic(2, "Security", priority=70),
        }
        matched = {
            1: [self._make_scored("https://shared.com", 25.0)],
            2: [self._make_scored("https://shared.com", 25.0)],
        }
        result = deduplicate_across_topics(matched, topics)
        assert len(result.get(1, [])) == 1
        assert len(result.get(2, [])) == 0

    def test_tie_score_and_priority_broken_by_name(self):
        """Same score + same priority → deterministic via alphabetical topic name."""
        topics = {
            1: self._make_topic(1, "Bravo", priority=50),
            2: self._make_topic(2, "Alpha", priority=50),
        }
        matched = {
            1: [self._make_scored("https://shared.com", 25.0)],
            2: [self._make_scored("https://shared.com", 25.0)],
        }
        result = deduplicate_across_topics(matched, topics)
        # Alpha (id=2) wins alphabetically
        assert len(result.get(2, [])) == 1
        assert len(result.get(1, [])) == 0

    def test_empty_topics_after_dedup(self):
        """If a topic loses all its articles, it gets an empty list."""
        topics = {
            1: self._make_topic(1, "AI", priority=80),
            2: self._make_topic(2, "Security", priority=70),
        }
        matched = {
            1: [self._make_scored("https://shared.com", 30.0)],
            2: [self._make_scored("https://shared.com", 20.0)],
        }
        result = deduplicate_across_topics(matched, topics)
        assert result.get(2, []) == []

    def test_multiple_shared_articles(self):
        """Multiple articles shared across multiple topics."""
        topics = {
            1: self._make_topic(1, "AI", priority=80),
            2: self._make_topic(2, "Security", priority=70),
        }
        matched = {
            1: [
                self._make_scored("https://a.com", 30.0),
                self._make_scored("https://shared.com", 20.0),
            ],
            2: [
                self._make_scored("https://b.com", 25.0),
                self._make_scored("https://shared.com", 22.0),
            ],
        }
        result = deduplicate_across_topics(matched, topics)
        urls_1 = {sa.article.url for sa in result.get(1, [])}
        urls_2 = {sa.article.url for sa in result.get(2, [])}
        # shared.com should be in topic 2 (score 22 vs 20) — wait, 22 > 20
        assert "https://shared.com" in urls_2
        assert "https://shared.com" not in urls_1
        # unique articles stay
        assert "https://a.com" in urls_1
        assert "https://b.com" in urls_2

    def test_empty_input(self):
        result = deduplicate_across_topics({}, {})
        assert result == {}
