"""Tests for Topic API endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models import SourceType


@pytest_asyncio.fixture
async def client(db):
    """Provide an async HTTP client for API testing."""
    from app import database as db_module

    db_module._db = db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestTopicCRUD:
    @pytest.mark.asyncio
    async def test_create_topic(self, client):
        resp = await client.post(
            "/api/topics",
            json={
                "name": "AI & ML",
                "keywords": ["artificial intelligence", "machine learning"],
                "priority": 80,
                "max_articles": 10,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "AI & ML"
        assert data["keywords"] == ["artificial intelligence", "machine learning"]
        assert data["priority"] == 80
        assert data["id"] == 1
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_create_topic_minimal(self, client):
        resp = await client.post(
            "/api/topics",
            json={"name": "General"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "General"
        assert data["keywords"] == []
        assert data["priority"] == 0
        assert data["max_articles"] == 10

    @pytest.mark.asyncio
    async def test_list_topics(self, client):
        await client.post("/api/topics", json={"name": "AI", "priority": 90})
        await client.post("/api/topics", json={"name": "Security", "priority": 80})

        resp = await client.get("/api/topics")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Ordered by priority DESC
        assert data[0]["name"] == "AI"

    @pytest.mark.asyncio
    async def test_list_enabled_only(self, client):
        await client.post("/api/topics", json={"name": "AI", "enabled": True})
        await client.post("/api/topics", json={"name": "Old", "enabled": False})

        resp = await client.get("/api/topics", params={"enabled_only": True})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_get_topic(self, client):
        create_resp = await client.post("/api/topics", json={"name": "AI"})
        topic_id = create_resp.json()["id"]

        resp = await client.get(f"/api/topics/{topic_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "AI"

    @pytest.mark.asyncio
    async def test_get_nonexistent_topic(self, client):
        resp = await client.get("/api/topics/999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_topic(self, client):
        create_resp = await client.post(
            "/api/topics", json={"name": "AI", "priority": 50}
        )
        topic_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/topics/{topic_id}",
            json={"name": "AI & ML", "priority": 90, "keywords": ["AI", "ML"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "AI & ML"
        assert data["priority"] == 90
        assert data["keywords"] == ["AI", "ML"]

    @pytest.mark.asyncio
    async def test_update_nonexistent_topic(self, client):
        resp = await client.put("/api/topics/999", json={"name": "New"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_topic(self, client):
        create_resp = await client.post("/api/topics", json={"name": "AI"})
        topic_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/topics/{topic_id}")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        resp = await client.get(f"/api/topics/{topic_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_topic(self, client):
        resp = await client.delete("/api/topics/999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_topic_sources(self, client):
        # Create topic
        topic_resp = await client.post("/api/topics", json={"name": "AI"})
        topic_id = topic_resp.json()["id"]

        # Create source linked to topic
        await client.post(
            "/api/sources",
            json={
                "name": "HN",
                "type": "rss",
                "url": "https://hnrss.org/best",
                "topic_ids": [topic_id],
            },
        )

        resp = await client.get(f"/api/topics/{topic_id}/sources")
        assert resp.status_code == 200
        sources = resp.json()
        assert len(sources) == 1
        assert sources[0]["name"] == "HN"


class TestSourceWithTopics:
    @pytest.mark.asyncio
    async def test_create_source_with_topic_ids(self, client):
        topic_resp = await client.post("/api/topics", json={"name": "AI"})
        topic_id = topic_resp.json()["id"]

        resp = await client.post(
            "/api/sources",
            json={
                "name": "HN",
                "type": "rss",
                "url": "https://hnrss.org/best",
                "topic_ids": [topic_id],
            },
        )
        assert resp.status_code == 201
        assert resp.json()["topic_ids"] == [topic_id]

    @pytest.mark.asyncio
    async def test_get_source_has_topic_ids(self, client):
        topic_resp = await client.post("/api/topics", json={"name": "AI"})
        topic_id = topic_resp.json()["id"]

        create_resp = await client.post(
            "/api/sources",
            json={
                "name": "HN",
                "type": "rss",
                "url": "https://hnrss.org/best",
                "topic_ids": [topic_id],
            },
        )
        source_id = create_resp.json()["id"]

        resp = await client.get(f"/api/sources/{source_id}")
        assert resp.status_code == 200
        assert resp.json()["topic_ids"] == [topic_id]
