"""APScheduler job definitions for daily digest."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.database import get_db
from app.fetchers.factory import FetcherFactory
from app.summarizer.llm import LLMSummarizer
from app.pipeline.digest import DigestPipeline

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def run_daily_digest() -> None:
    """Job function: execute the full digest pipeline."""
    settings = get_settings()
    db = await get_db()

    summarizer = LLMSummarizer(host=settings.ollama_host, model=settings.ollama_model)
    factory = FetcherFactory()

    pipeline = DigestPipeline(db=db, fetcher_factory=factory, summarizer=summarizer)
    await pipeline.run(
        recipient=settings.digest_recipient,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_password=settings.smtp_password,
    )


def start_scheduler() -> AsyncIOScheduler:
    """Start the APScheduler with the daily digest cron job."""
    global _scheduler
    settings = get_settings()

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_daily_digest,
        trigger=CronTrigger(
            hour=settings.digest_cron_hour,
            minute=settings.digest_cron_minute,
            timezone=settings.digest_timezone,
        ),
        id="daily_digest",
        name="Daily News Digest",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started: digest at %02d:%02d %s",
        settings.digest_cron_hour,
        settings.digest_cron_minute,
        settings.digest_timezone,
    )
    return _scheduler


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("Scheduler stopped")
    _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    """Return the current scheduler instance."""
    return _scheduler
