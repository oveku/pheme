"""Topic management API routes."""

from fastapi import APIRouter, HTTPException, Query

from app.database import (
    create_topic,
    delete_topic,
    get_db,
    get_topic,
    get_topics,
    update_topic,
    get_sources_for_topic,
)
from app.models import Topic, TopicCreate, TopicUpdate, Source

router = APIRouter(prefix="/topics")


@router.get("", response_model=list[Topic])
async def list_topics(enabled_only: bool = Query(False)):
    """List all configured topics."""
    db = await get_db()
    return await get_topics(db, enabled_only=enabled_only)


@router.post("", response_model=Topic, status_code=201)
async def add_topic(data: TopicCreate):
    """Add a new topic."""
    db = await get_db()
    return await create_topic(db, data)


@router.get("/{topic_id}", response_model=Topic)
async def get_topic_detail(topic_id: int):
    """Get a topic by ID."""
    db = await get_db()
    topic = await get_topic(db, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.put("/{topic_id}", response_model=Topic)
async def update_topic_detail(topic_id: int, data: TopicUpdate):
    """Update a topic."""
    db = await get_db()
    topic = await update_topic(db, topic_id, data)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.delete("/{topic_id}")
async def remove_topic(topic_id: int):
    """Delete a topic."""
    db = await get_db()
    deleted = await delete_topic(db, topic_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {"ok": True}


@router.get("/{topic_id}/sources", response_model=list[Source])
async def get_topic_sources(topic_id: int):
    """Get all sources associated with a topic."""
    db = await get_db()
    topic = await get_topic(db, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return await get_sources_for_topic(db, topic_id)
