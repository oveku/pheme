"""Tests for blocked_keywords and app_settings database operations."""

import pytest
import pytest_asyncio

from app.database import (
    get_blocked_keywords,
    add_blocked_keyword,
    delete_blocked_keyword,
    get_app_setting,
    set_app_setting,
)


class TestBlockedKeywordsCRUD:
    """Tests for the blocked_keywords table CRUD operations."""

    @pytest.mark.asyncio
    async def test_empty_by_default(self, db):
        keywords = await get_blocked_keywords(db)
        assert keywords == []

    @pytest.mark.asyncio
    async def test_add_keyword(self, db):
        kw = await add_blocked_keyword(db, "Trump")
        assert kw.keyword == "Trump"
        assert kw.id is not None
        assert kw.created_at is not None

    @pytest.mark.asyncio
    async def test_add_multiple_keywords(self, db):
        await add_blocked_keyword(db, "Trump")
        await add_blocked_keyword(db, "Epstein")
        await add_blocked_keyword(db, "Donald Trump")
        keywords = await get_blocked_keywords(db)
        assert len(keywords) == 3
        names = {kw.keyword for kw in keywords}
        assert names == {"Trump", "Epstein", "Donald Trump"}

    @pytest.mark.asyncio
    async def test_delete_keyword(self, db):
        kw = await add_blocked_keyword(db, "Trump")
        deleted = await delete_blocked_keyword(db, kw.id)
        assert deleted is True
        keywords = await get_blocked_keywords(db)
        assert len(keywords) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_keyword(self, db):
        deleted = await delete_blocked_keyword(db, 999)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_duplicate_keyword_allowed(self, db):
        """We don't enforce uniqueness at DB level — UI can prevent it."""
        await add_blocked_keyword(db, "Trump")
        await add_blocked_keyword(db, "Trump")
        keywords = await get_blocked_keywords(db)
        assert len(keywords) == 2

    @pytest.mark.asyncio
    async def test_keywords_ordered_by_keyword(self, db):
        await add_blocked_keyword(db, "Zebra")
        await add_blocked_keyword(db, "Alpha")
        await add_blocked_keyword(db, "Middle")
        keywords = await get_blocked_keywords(db)
        names = [kw.keyword for kw in keywords]
        assert names == sorted(names)


class TestAppSettings:
    """Tests for generic key/value app_settings store."""

    @pytest.mark.asyncio
    async def test_default_when_missing(self, db):
        value = await get_app_setting(db, "nonexistent", default="fallback")
        assert value == "fallback"

    @pytest.mark.asyncio
    async def test_set_and_get(self, db):
        await set_app_setting(db, "filter_scope", "title_preview")
        value = await get_app_setting(db, "filter_scope")
        assert value == "title_preview"

    @pytest.mark.asyncio
    async def test_upsert_overwrites(self, db):
        await set_app_setting(db, "filter_scope", "title_preview")
        await set_app_setting(db, "filter_scope", "full_text")
        value = await get_app_setting(db, "filter_scope")
        assert value == "full_text"

    @pytest.mark.asyncio
    async def test_multiple_keys(self, db):
        await set_app_setting(db, "key_a", "val_a")
        await set_app_setting(db, "key_b", "val_b")
        assert await get_app_setting(db, "key_a") == "val_a"
        assert await get_app_setting(db, "key_b") == "val_b"

    @pytest.mark.asyncio
    async def test_default_none_when_no_default(self, db):
        value = await get_app_setting(db, "missing")
        assert value is None
