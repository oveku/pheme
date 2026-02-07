"""Pheme FastAPI application."""

import logging
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import close_db, get_db, init_db
from app.api import router as api_router
from app.ui import router as ui_router
from app.scheduler.jobs import start_scheduler, stop_scheduler

# Configure logging so all app loggers emit INFO+ to stderr (Docker captures this)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    db = await get_db()
    await init_db(db)
    start_scheduler()
    yield
    stop_scheduler()
    await close_db()


app = FastAPI(
    title="Pheme",
    description="Daily news digest service - gathers, summarizes, and delivers",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(api_router)
app.include_router(ui_router)

_static_dir = pathlib.Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.2.0"}
