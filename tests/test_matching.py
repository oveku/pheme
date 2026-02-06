"""Tests for the topic matching and ranking module."""

import pytest
from datetime import datetime, timezone, timedelta

from app.models import Article, Topic
from app.pipeline.matching import (
    score_article_for_topic,
    rank_articles_for_topic,
    match_articles_to_topics,
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
