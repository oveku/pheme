"""Tests for Topic model and database CRUD operations."""

import pytest
import pytest_asyncio
from datetime import datetime

from app.database import (
    create_topic,
    get_topic,
    get_topics,
    update_topic,
    delete_topic,
    create_source,
    get_source,
    get_sources_for_topic,
    _set_source_topics,
    _get_topic_ids_for_source,
)
from app.models import TopicCreate, TopicUpdate, SourceCreate, SourceType


class TestTopicCreate:
    @pytest.mark.asyncio
    async def test_create_basic_topic(self, db):
        topic = await create_topic(
            db,
            TopicCreate(
                name="AI & ML",
                keywords=[
                    "artificial intelligence",
                    "machine learning",
                    "neural network",
                ],
                priority=80,
            ),
        )
        assert topic.id == 1
        assert topic.name == "AI & ML"
        assert topic.keywords == [
            "artificial intelligence",
            "machine learning",
            "neural network",
        ]
        assert topic.priority == 80
        assert topic.max_articles == 10
        assert topic.enabled is True
        assert isinstance(topic.created_at, datetime)

    @pytest.mark.asyncio
    async def test_create_topic_with_patterns(self, db):
        topic = await create_topic(
            db,
            TopicCreate(
                name="Security",
                keywords=["cybersecurity", "vulnerability", "exploit"],
                include_patterns=[r"CVE-\d+"],
                exclude_patterns=[r"sponsored", r"advertisement"],
                priority=70,
                max_articles=5,
            ),
        )
        assert topic.include_patterns == [r"CVE-\d+"]
        assert topic.exclude_patterns == ["sponsored", "advertisement"]
        assert topic.max_articles == 5

    @pytest.mark.asyncio
    async def test_create_topic_defaults(self, db):
        topic = await create_topic(db, TopicCreate(name="General"))
        assert topic.keywords == []
        assert topic.include_patterns == []
        assert topic.exclude_patterns == []
        assert topic.priority == 0
        assert topic.max_articles == 10
        assert topic.enabled is True

    @pytest.mark.asyncio
    async def test_create_multiple_topics(self, db):
        t1 = await create_topic(db, TopicCreate(name="AI"))
        t2 = await create_topic(db, TopicCreate(name="Security"))
        assert t1.id != t2.id


class TestGetTopic:
    @pytest.mark.asyncio
    async def test_get_existing_topic(self, db):
        created = await create_topic(db, TopicCreate(name="AI", keywords=["AI"]))
        fetched = await get_topic(db, created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "AI"

    @pytest.mark.asyncio
    async def test_get_nonexistent_topic(self, db):
        result = await get_topic(db, 999)
        assert result is None


class TestGetTopics:
    @pytest.mark.asyncio
    async def test_get_all_topics(self, db):
        await create_topic(db, TopicCreate(name="AI", priority=80))
        await create_topic(db, TopicCreate(name="Security", priority=90))
        topics = await get_topics(db)
        assert len(topics) == 2
        # Ordered by priority DESC
        assert topics[0].name == "Security"
        assert topics[1].name == "AI"

    @pytest.mark.asyncio
    async def test_get_enabled_topics_only(self, db):
        await create_topic(db, TopicCreate(name="AI", enabled=True))
        await create_topic(db, TopicCreate(name="Security", enabled=False))
        topics = await get_topics(db, enabled_only=True)
        assert len(topics) == 1
        assert topics[0].name == "AI"

    @pytest.mark.asyncio
    async def test_get_topics_empty(self, db):
        topics = await get_topics(db)
        assert topics == []


class TestUpdateTopic:
    @pytest.mark.asyncio
    async def test_update_name(self, db):
        created = await create_topic(db, TopicCreate(name="Old"))
        updated = await update_topic(db, created.id, TopicUpdate(name="New"))
        assert updated is not None
        assert updated.name == "New"

    @pytest.mark.asyncio
    async def test_update_keywords(self, db):
        created = await create_topic(db, TopicCreate(name="AI", keywords=["AI"]))
        updated = await update_topic(
            db, created.id, TopicUpdate(keywords=["AI", "ML", "deep learning"])
        )
        assert updated.keywords == ["AI", "ML", "deep learning"]

    @pytest.mark.asyncio
    async def test_update_priority(self, db):
        created = await create_topic(db, TopicCreate(name="AI", priority=50))
        updated = await update_topic(db, created.id, TopicUpdate(priority=90))
        assert updated.priority == 90

    @pytest.mark.asyncio
    async def test_update_enabled(self, db):
        created = await create_topic(db, TopicCreate(name="AI"))
        updated = await update_topic(db, created.id, TopicUpdate(enabled=False))
        assert updated.enabled is False

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self, db):
        result = await update_topic(db, 999, TopicUpdate(name="New"))
        assert result is None

    @pytest.mark.asyncio
    async def test_update_no_fields(self, db):
        created = await create_topic(db, TopicCreate(name="AI", priority=50))
        updated = await update_topic(db, created.id, TopicUpdate())
        assert updated.name == "AI"
        assert updated.priority == 50


class TestDeleteTopic:
    @pytest.mark.asyncio
    async def test_delete_existing(self, db):
        created = await create_topic(db, TopicCreate(name="AI"))
        result = await delete_topic(db, created.id)
        assert result is True
        assert await get_topic(db, created.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db):
        result = await delete_topic(db, 999)
        assert result is False


class TestSourceTopicAssociation:
    @pytest.mark.asyncio
    async def test_create_source_with_topics(self, db):
        t1 = await create_topic(db, TopicCreate(name="AI"))
        t2 = await create_topic(db, TopicCreate(name="Security"))

        source = await create_source(
            db,
            SourceCreate(
                name="HN",
                type=SourceType.RSS,
                url="https://hnrss.org/best",
                topic_ids=[t1.id, t2.id],
            ),
        )
        assert sorted(source.topic_ids) == sorted([t1.id, t2.id])

    @pytest.mark.asyncio
    async def test_create_source_without_topics(self, db):
        source = await create_source(
            db,
            SourceCreate(
                name="HN",
                type=SourceType.RSS,
                url="https://hnrss.org/best",
            ),
        )
        assert source.topic_ids == []

    @pytest.mark.asyncio
    async def test_get_source_includes_topic_ids(self, db):
        topic = await create_topic(db, TopicCreate(name="AI"))
        created = await create_source(
            db,
            SourceCreate(
                name="HN",
                type=SourceType.RSS,
                url="https://hnrss.org/best",
                topic_ids=[topic.id],
            ),
        )
        fetched = await get_source(db, created.id)
        assert fetched.topic_ids == [topic.id]

    @pytest.mark.asyncio
    async def test_get_sources_for_topic(self, db):
        t1 = await create_topic(db, TopicCreate(name="AI"))
        t2 = await create_topic(db, TopicCreate(name="Security"))

        s1 = await create_source(
            db,
            SourceCreate(
                name="S1", type=SourceType.RSS, url="https://a.com", topic_ids=[t1.id]
            ),
        )
        s2 = await create_source(
            db,
            SourceCreate(
                name="S2",
                type=SourceType.RSS,
                url="https://b.com",
                topic_ids=[t1.id, t2.id],
            ),
        )
        s3 = await create_source(
            db,
            SourceCreate(
                name="S3", type=SourceType.RSS, url="https://c.com", topic_ids=[t2.id]
            ),
        )

        ai_sources = await get_sources_for_topic(db, t1.id)
        assert len(ai_sources) == 2
        assert {s.name for s in ai_sources} == {"S1", "S2"}

        sec_sources = await get_sources_for_topic(db, t2.id)
        assert len(sec_sources) == 2
        assert {s.name for s in sec_sources} == {"S2", "S3"}
