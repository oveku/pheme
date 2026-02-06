"""Source management API routes."""

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.database import (
    create_source,
    delete_source,
    get_db,
    get_digest_logs,
    get_source,
    get_sources,
    update_source,
)
from app.fetchers.factory import FetcherFactory
from app.models import Source, SourceCreate, SourceUpdate, DigestLog
from app.pipeline.digest import DigestPipeline
from app.summarizer.llm import LLMSummarizer
from app.api.topics import router as topics_router

router = APIRouter(prefix="/api")
router.include_router(topics_router, prefix="")


@router.get("/sources", response_model=list[Source])
async def list_sources(enabled_only: bool = Query(False)):
    """List all configured news sources."""
    db = await get_db()
    return await get_sources(db, enabled_only=enabled_only)


@router.post("/sources", response_model=Source, status_code=201)
async def add_source(data: SourceCreate):
    """Add a new news source."""
    db = await get_db()
    return await create_source(db, data)


@router.get("/sources/{source_id}", response_model=Source)
async def get_source_detail(source_id: int):
    """Get a source by ID."""
    db = await get_db()
    source = await get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.put("/sources/{source_id}", response_model=Source)
async def update_source_detail(source_id: int, data: SourceUpdate):
    """Update a source."""
    db = await get_db()
    source = await update_source(db, source_id, data)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.delete("/sources/{source_id}")
async def remove_source(source_id: int):
    """Delete a source."""
    db = await get_db()
    deleted = await delete_source(db, source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"ok": True}


@router.get("/digest/history", response_model=list[DigestLog])
async def digest_history(limit: int = Query(10, ge=1, le=100)):
    """Get digest send history."""
    db = await get_db()
    return await get_digest_logs(db, limit=limit)


@router.post("/digest/trigger")
async def trigger_digest():
    """Manually trigger a digest run."""
    settings = get_settings()
    db = await get_db()
    summarizer = LLMSummarizer(host=settings.ollama_host, model=settings.ollama_model)
    factory = FetcherFactory()

    pipeline = DigestPipeline(db=db, fetcher_factory=factory, summarizer=summarizer)
    digest = await pipeline.run(
        recipient=settings.digest_recipient,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_password=settings.smtp_password,
    )
    return {
        "status": "completed",
        "source_count": digest.source_count,
        "article_count": digest.article_count,
        "summary_length": len(digest.summary),
    }
