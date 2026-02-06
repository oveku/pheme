"""Tests for database layer."""

import pytest
import pytest_asyncio
from datetime import datetime

from app.database import (
    create_source,
    get_source,
    get_sources,
    update_source,
    delete_source,
    log_digest,
    get_digest_logs,
    update_source_last_fetched,
)
from app.models import SourceCreate, SourceType, SourceUpdate


class TestCreateSource:
    @pytest.mark.asyncio
    async def test_create_rss_source(self, db):
        source = await create_source(
            db,
            SourceCreate(
                name="Hacker News",
                type=SourceType.RSS,
                url="https://hnrss.org/best",
                category="tech",
            ),
        )
        assert source.id == 1
        assert source.name == "Hacker News"
        assert source.type == SourceType.RSS
        assert source.url == "https://hnrss.org/best"
        assert source.category == "tech"
        assert source.enabled is True
        assert source.last_fetched is None
        assert isinstance(source.created_at, datetime)

    @pytest.mark.asyncio
    async def test_create_reddit_source(self, db):
        source = await create_source(
            db,
            SourceCreate(
                name="r/technology",
                type=SourceType.REDDIT,
                url="technology",
                category="tech",
                config={"sort": "hot", "limit": 10},
            ),
        )
        assert source.type == SourceType.REDDIT
        assert source.config == {"sort": "hot", "limit": 10}

    @pytest.mark.asyncio
    async def test_create_web_source(self, db):
        source = await create_source(
            db,
            SourceCreate(
                name="Ars Technica",
                type=SourceType.WEB,
                url="https://arstechnica.com",
                config={"selector": "article h2"},
            ),
        )
        assert source.type == SourceType.WEB

    @pytest.mark.asyncio
    async def test_create_multiple_sources(self, db):
        s1 = await create_source(
            db, SourceCreate(name="S1", type=SourceType.RSS, url="https://a.com")
        )
        s2 = await create_source(
            db, SourceCreate(name="S2", type=SourceType.RSS, url="https://b.com")
        )
        assert s1.id != s2.id


class TestGetSource:
    @pytest.mark.asyncio
    async def test_get_existing_source(self, db):
        created = await create_source(
            db, SourceCreate(name="Test", type=SourceType.RSS, url="https://test.com")
        )
        fetched = await get_source(db, created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_source(self, db):
        result = await get_source(db, 999)
        assert result is None


class TestGetSources:
    @pytest.mark.asyncio
    async def test_get_all_sources(self, db):
        await create_source(
            db, SourceCreate(name="S1", type=SourceType.RSS, url="https://a.com")
        )
        await create_source(
            db, SourceCreate(name="S2", type=SourceType.REDDIT, url="tech")
        )
        sources = await get_sources(db)
        assert len(sources) == 2

    @pytest.mark.asyncio
    async def test_get_sources_empty(self, db):
        sources = await get_sources(db)
        assert sources == []

    @pytest.mark.asyncio
    async def test_get_enabled_sources_only(self, db):
        await create_source(
            db,
            SourceCreate(
                name="S1", type=SourceType.RSS, url="https://a.com", enabled=True
            ),
        )
        await create_source(
            db,
            SourceCreate(
                name="S2", type=SourceType.RSS, url="https://b.com", enabled=False
            ),
        )
        sources = await get_sources(db, enabled_only=True)
        assert len(sources) == 1
        assert sources[0].name == "S1"


class TestUpdateSource:
    @pytest.mark.asyncio
    async def test_update_name(self, db):
        created = await create_source(
            db, SourceCreate(name="Old", type=SourceType.RSS, url="https://test.com")
        )
        updated = await update_source(db, created.id, SourceUpdate(name="New"))
        assert updated is not None
        assert updated.name == "New"
        assert updated.url == "https://test.com"  # unchanged

    @pytest.mark.asyncio
    async def test_update_enabled(self, db):
        created = await create_source(
            db, SourceCreate(name="Test", type=SourceType.RSS, url="https://test.com")
        )
        updated = await update_source(db, created.id, SourceUpdate(enabled=False))
        assert updated.enabled is False

    @pytest.mark.asyncio
    async def test_update_config(self, db):
        created = await create_source(
            db,
            SourceCreate(
                name="Test",
                type=SourceType.RSS,
                url="https://test.com",
                config={"a": 1},
            ),
        )
        updated = await update_source(db, created.id, SourceUpdate(config={"b": 2}))
        assert updated.config == {"b": 2}

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self, db):
        result = await update_source(db, 999, SourceUpdate(name="New"))
        assert result is None


class TestDeleteSource:
    @pytest.mark.asyncio
    async def test_delete_existing(self, db):
        created = await create_source(
            db, SourceCreate(name="Test", type=SourceType.RSS, url="https://test.com")
        )
        result = await delete_source(db, created.id)
        assert result is True
        assert await get_source(db, created.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db):
        result = await delete_source(db, 999)
        assert result is False


class TestUpdateLastFetched:
    @pytest.mark.asyncio
    async def test_update_last_fetched(self, db):
        created = await create_source(
            db, SourceCreate(name="Test", type=SourceType.RSS, url="https://test.com")
        )
        assert created.last_fetched is None
        await update_source_last_fetched(db, created.id)
        fetched = await get_source(db, created.id)
        assert fetched.last_fetched is not None


class TestDigestLog:
    @pytest.mark.asyncio
    async def test_log_digest(self, db):
        log_id = await log_digest(
            db,
            recipient="test@example.com",
            source_count=5,
            article_count=30,
            entry_count=15,
            status="sent",
        )
        assert log_id > 0

    @pytest.mark.asyncio
    async def test_log_failed_digest(self, db):
        log_id = await log_digest(
            db,
            recipient="test@example.com",
            source_count=5,
            article_count=0,
            entry_count=0,
            status="failed",
            error="Connection refused",
        )
        logs = await get_digest_logs(db, limit=1)
        assert len(logs) == 1
        assert logs[0].status == "failed"
        assert logs[0].error == "Connection refused"

    @pytest.mark.asyncio
    async def test_get_digest_logs_ordered(self, db):
        await log_digest(
            db,
            recipient="a@b.com",
            source_count=1,
            article_count=1,
            entry_count=1,
            status="sent",
        )
        await log_digest(
            db,
            recipient="a@b.com",
            source_count=2,
            article_count=2,
            entry_count=2,
            status="sent",
        )
        logs = await get_digest_logs(db, limit=10)
        assert len(logs) == 2
        # Most recent first
        assert logs[0].source_count == 2

    @pytest.mark.asyncio
    async def test_get_digest_logs_limit(self, db):
        for i in range(5):
            await log_digest(
                db,
                recipient="a@b.com",
                source_count=i,
                article_count=i,
                entry_count=i,
                status="sent",
            )
        logs = await get_digest_logs(db, limit=3)
        assert len(logs) == 3
