"""Tests for source management API."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app, lifespan
from app.models import SourceType


@pytest_asyncio.fixture
async def client(db):
    """Provide an async HTTP client for API testing."""
    # Patch app to use our test db
    from app import database as db_module

    db_module._db = db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestCreateSource:
    @pytest.mark.asyncio
    async def test_create_rss_source(self, client):
        resp = await client.post(
            "/api/sources",
            json={
                "name": "Hacker News",
                "type": "rss",
                "url": "https://hnrss.org/best",
                "category": "tech",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Hacker News"
        assert data["type"] == "rss"
        assert data["id"] == 1
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_create_reddit_source(self, client):
        resp = await client.post(
            "/api/sources",
            json={
                "name": "r/technology",
                "type": "reddit",
                "url": "technology",
                "category": "tech",
                "config": {"sort": "hot", "limit": 10},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["config"] == {"sort": "hot", "limit": 10}

    @pytest.mark.asyncio
    async def test_create_web_source(self, client):
        resp = await client.post(
            "/api/sources",
            json={
                "name": "Ars Technica",
                "type": "web",
                "url": "https://arstechnica.com",
                "config": {"selector": "article h2", "max_items": 10},
            },
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_invalid_type(self, client):
        resp = await client.post(
            "/api/sources",
            json={
                "name": "Test",
                "type": "invalid",
                "url": "https://test.com",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_missing_name(self, client):
        resp = await client.post(
            "/api/sources",
            json={
                "type": "rss",
                "url": "https://test.com",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_empty_name(self, client):
        resp = await client.post(
            "/api/sources",
            json={
                "name": "",
                "type": "rss",
                "url": "https://test.com",
            },
        )
        assert resp.status_code == 422


class TestGetSources:
    @pytest.mark.asyncio
    async def test_get_empty(self, client):
        resp = await client.get("/api/sources")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_all(self, client):
        await client.post(
            "/api/sources", json={"name": "S1", "type": "rss", "url": "https://a.com"}
        )
        await client.post(
            "/api/sources", json={"name": "S2", "type": "rss", "url": "https://b.com"}
        )
        resp = await client.get("/api/sources")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_get_enabled_only(self, client):
        await client.post(
            "/api/sources",
            json={"name": "S1", "type": "rss", "url": "https://a.com", "enabled": True},
        )
        await client.post(
            "/api/sources",
            json={
                "name": "S2",
                "type": "rss",
                "url": "https://b.com",
                "enabled": False,
            },
        )
        resp = await client.get("/api/sources", params={"enabled_only": True})
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestGetSource:
    @pytest.mark.asyncio
    async def test_get_existing(self, client):
        create_resp = await client.post(
            "/api/sources",
            json={"name": "Test", "type": "rss", "url": "https://test.com"},
        )
        source_id = create_resp.json()["id"]
        resp = await client.get(f"/api/sources/{source_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, client):
        resp = await client.get("/api/sources/999")
        assert resp.status_code == 404


class TestUpdateSource:
    @pytest.mark.asyncio
    async def test_update_name(self, client):
        create_resp = await client.post(
            "/api/sources",
            json={"name": "Old", "type": "rss", "url": "https://test.com"},
        )
        source_id = create_resp.json()["id"]
        resp = await client.put(f"/api/sources/{source_id}", json={"name": "New"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    @pytest.mark.asyncio
    async def test_update_disable(self, client):
        create_resp = await client.post(
            "/api/sources",
            json={"name": "Test", "type": "rss", "url": "https://test.com"},
        )
        source_id = create_resp.json()["id"]
        resp = await client.put(f"/api/sources/{source_id}", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, client):
        resp = await client.put("/api/sources/999", json={"name": "New"})
        assert resp.status_code == 404


class TestDeleteSource:
    @pytest.mark.asyncio
    async def test_delete_existing(self, client):
        create_resp = await client.post(
            "/api/sources",
            json={"name": "Test", "type": "rss", "url": "https://test.com"},
        )
        source_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/sources/{source_id}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        # Verify deleted
        get_resp = await client.get(f"/api/sources/{source_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, client):
        resp = await client.delete("/api/sources/999")
        assert resp.status_code == 404


class TestDigestEndpoints:
    @pytest.mark.asyncio
    async def test_digest_history_empty(self, client):
        resp = await client.get("/api/digest/history")
        assert resp.status_code == 200
        assert resp.json() == []
