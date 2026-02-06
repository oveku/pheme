"""SQLite database layer for Pheme."""

import json
from datetime import datetime, timezone

import aiosqlite

from app.config import get_settings
from app.models import (
    DigestLog,
    Source,
    SourceCreate,
    SourceType,
    SourceUpdate,
    Topic,
    TopicCreate,
    TopicUpdate,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    url TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    config TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_fetched TEXT
);

CREATE TABLE IF NOT EXISTS digest_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at TEXT NOT NULL,
    recipient TEXT NOT NULL,
    source_count INTEGER NOT NULL DEFAULT 0,
    article_count INTEGER NOT NULL DEFAULT 0,
    entry_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'sent',
    error TEXT
);

CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    keywords TEXT NOT NULL DEFAULT '[]',
    include_patterns TEXT NOT NULL DEFAULT '[]',
    exclude_patterns TEXT NOT NULL DEFAULT '[]',
    priority INTEGER NOT NULL DEFAULT 0,
    max_articles INTEGER NOT NULL DEFAULT 10,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_topics (
    source_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    PRIMARY KEY (source_id, topic_id),
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
"""

_db: aiosqlite.Connection | None = None


def _set_db(conn: aiosqlite.Connection) -> None:
    """Set the database connection (for testing)."""
    global _db
    _db = conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db(conn: aiosqlite.Connection | None = None) -> None:
    """Initialize database schema."""
    db = conn or await get_db()
    await db.executescript(SCHEMA)
    await db.commit()


async def get_db() -> aiosqlite.Connection:
    """Get or create database connection."""
    global _db
    if _db is None:
        settings = get_settings()
        _db = await aiosqlite.connect(settings.pheme_db_path)
        _db.row_factory = aiosqlite.Row
    return _db


async def close_db() -> None:
    """Close database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


def _row_to_source(row: aiosqlite.Row, topic_ids: list[int] | None = None) -> Source:
    """Convert a database row to a Source model."""
    return Source(
        id=row["id"],
        name=row["name"],
        type=SourceType(row["type"]),
        url=row["url"],
        category=row["category"],
        config=json.loads(row["config"]),
        enabled=bool(row["enabled"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        last_fetched=(
            datetime.fromisoformat(row["last_fetched"]) if row["last_fetched"] else None
        ),
        topic_ids=topic_ids or [],
    )


async def _get_topic_ids_for_source(
    db: aiosqlite.Connection, source_id: int
) -> list[int]:
    """Get topic IDs associated with a source."""
    rows = await db.execute_fetchall(
        "SELECT topic_id FROM source_topics WHERE source_id = ? ORDER BY topic_id",
        (source_id,),
    )
    return [row[0] for row in rows]


async def _set_source_topics(
    db: aiosqlite.Connection, source_id: int, topic_ids: list[int]
) -> None:
    """Replace source-topic associations."""
    await db.execute("DELETE FROM source_topics WHERE source_id = ?", (source_id,))
    for tid in topic_ids:
        await db.execute(
            "INSERT OR IGNORE INTO source_topics (source_id, topic_id) VALUES (?, ?)",
            (source_id, tid),
        )


def _row_to_digest_log(row: aiosqlite.Row) -> DigestLog:
    """Convert a database row to a DigestLog model."""
    return DigestLog(
        id=row["id"],
        sent_at=datetime.fromisoformat(row["sent_at"]),
        recipient=row["recipient"],
        source_count=row["source_count"],
        article_count=row["article_count"],
        entry_count=row["entry_count"],
        status=row["status"],
        error=row["error"],
    )


# --- Source CRUD ---


async def create_source(db: aiosqlite.Connection, data: SourceCreate) -> Source:
    """Create a new source."""
    now = _now()
    cursor = await db.execute(
        """INSERT INTO sources (name, type, url, category, config, enabled, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data.name,
            data.type.value,
            data.url,
            data.category,
            json.dumps(data.config),
            int(data.enabled),
            now,
        ),
    )
    source_id = cursor.lastrowid
    if data.topic_ids:
        await _set_source_topics(db, source_id, data.topic_ids)
    await db.commit()
    row = await db.execute_fetchall("SELECT * FROM sources WHERE id = ?", (source_id,))
    topic_ids = await _get_topic_ids_for_source(db, source_id)
    return _row_to_source(row[0], topic_ids)


async def get_source(db: aiosqlite.Connection, source_id: int) -> Source | None:
    """Get a source by ID."""
    rows = await db.execute_fetchall("SELECT * FROM sources WHERE id = ?", (source_id,))
    if not rows:
        return None
    topic_ids = await _get_topic_ids_for_source(db, source_id)
    return _row_to_source(rows[0], topic_ids)


async def get_sources(
    db: aiosqlite.Connection, enabled_only: bool = False
) -> list[Source]:
    """Get all sources, optionally filtered to enabled only."""
    if enabled_only:
        rows = await db.execute_fetchall(
            "SELECT * FROM sources WHERE enabled = 1 ORDER BY id"
        )
    else:
        rows = await db.execute_fetchall("SELECT * FROM sources ORDER BY id")
    sources = []
    for row in rows:
        topic_ids = await _get_topic_ids_for_source(db, row["id"])
        sources.append(_row_to_source(row, topic_ids))
    return sources


async def update_source(
    db: aiosqlite.Connection, source_id: int, data: SourceUpdate
) -> Source | None:
    """Update a source. Only non-None fields are updated."""
    existing = await get_source(db, source_id)
    if existing is None:
        return None

    fields = []
    values = []

    if data.name is not None:
        fields.append("name = ?")
        values.append(data.name)
    if data.type is not None:
        fields.append("type = ?")
        values.append(data.type.value)
    if data.url is not None:
        fields.append("url = ?")
        values.append(data.url)
    if data.category is not None:
        fields.append("category = ?")
        values.append(data.category)
    if data.config is not None:
        fields.append("config = ?")
        values.append(json.dumps(data.config))
    if data.enabled is not None:
        fields.append("enabled = ?")
        values.append(int(data.enabled))

    if not fields:
        return existing

    values.append(source_id)
    await db.execute(f"UPDATE sources SET {', '.join(fields)} WHERE id = ?", values)
    if data.topic_ids is not None:
        await _set_source_topics(db, source_id, data.topic_ids)
    await db.commit()
    return await get_source(db, source_id)


async def delete_source(db: aiosqlite.Connection, source_id: int) -> bool:
    """Delete a source. Returns True if deleted."""
    cursor = await db.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    await db.commit()
    return cursor.rowcount > 0


async def update_source_last_fetched(db: aiosqlite.Connection, source_id: int) -> None:
    """Update the last_fetched timestamp for a source."""
    await db.execute(
        "UPDATE sources SET last_fetched = ? WHERE id = ?", (_now(), source_id)
    )
    await db.commit()


# --- Digest Logs ---


async def log_digest(
    db: aiosqlite.Connection,
    *,
    recipient: str,
    source_count: int,
    article_count: int,
    entry_count: int,
    status: str = "sent",
    error: str | None = None,
) -> int:
    """Log a digest send attempt."""
    cursor = await db.execute(
        """INSERT INTO digest_logs (sent_at, recipient, source_count, article_count, entry_count, status, error)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (_now(), recipient, source_count, article_count, entry_count, status, error),
    )
    await db.commit()
    return cursor.lastrowid


async def get_digest_logs(db: aiosqlite.Connection, limit: int = 10) -> list[DigestLog]:
    """Get recent digest logs, most recent first."""
    rows = await db.execute_fetchall(
        "SELECT * FROM digest_logs ORDER BY id DESC LIMIT ?", (limit,)
    )
    return [_row_to_digest_log(row) for row in rows]


# --- Topic CRUD ---


def _row_to_topic(row: aiosqlite.Row) -> Topic:
    """Convert a database row to a Topic model."""
    return Topic(
        id=row["id"],
        name=row["name"],
        keywords=json.loads(row["keywords"]),
        include_patterns=json.loads(row["include_patterns"]),
        exclude_patterns=json.loads(row["exclude_patterns"]),
        priority=row["priority"],
        max_articles=row["max_articles"],
        enabled=bool(row["enabled"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


async def create_topic(db: aiosqlite.Connection, data: TopicCreate) -> Topic:
    """Create a new topic."""
    now = _now()
    cursor = await db.execute(
        """INSERT INTO topics (name, keywords, include_patterns, exclude_patterns,
           priority, max_articles, enabled, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data.name,
            json.dumps(data.keywords),
            json.dumps(data.include_patterns),
            json.dumps(data.exclude_patterns),
            data.priority,
            data.max_articles,
            int(data.enabled),
            now,
        ),
    )
    await db.commit()
    row = await db.execute_fetchall(
        "SELECT * FROM topics WHERE id = ?", (cursor.lastrowid,)
    )
    return _row_to_topic(row[0])


async def get_topic(db: aiosqlite.Connection, topic_id: int) -> Topic | None:
    """Get a topic by ID."""
    rows = await db.execute_fetchall("SELECT * FROM topics WHERE id = ?", (topic_id,))
    if not rows:
        return None
    return _row_to_topic(rows[0])


async def get_topics(
    db: aiosqlite.Connection, enabled_only: bool = False
) -> list[Topic]:
    """Get all topics, optionally filtered to enabled only."""
    if enabled_only:
        rows = await db.execute_fetchall(
            "SELECT * FROM topics WHERE enabled = 1 ORDER BY priority DESC, id"
        )
    else:
        rows = await db.execute_fetchall(
            "SELECT * FROM topics ORDER BY priority DESC, id"
        )
    return [_row_to_topic(row) for row in rows]


async def update_topic(
    db: aiosqlite.Connection, topic_id: int, data: TopicUpdate
) -> Topic | None:
    """Update a topic. Only non-None fields are updated."""
    existing = await get_topic(db, topic_id)
    if existing is None:
        return None

    fields = []
    values = []

    if data.name is not None:
        fields.append("name = ?")
        values.append(data.name)
    if data.keywords is not None:
        fields.append("keywords = ?")
        values.append(json.dumps(data.keywords))
    if data.include_patterns is not None:
        fields.append("include_patterns = ?")
        values.append(json.dumps(data.include_patterns))
    if data.exclude_patterns is not None:
        fields.append("exclude_patterns = ?")
        values.append(json.dumps(data.exclude_patterns))
    if data.priority is not None:
        fields.append("priority = ?")
        values.append(data.priority)
    if data.max_articles is not None:
        fields.append("max_articles = ?")
        values.append(data.max_articles)
    if data.enabled is not None:
        fields.append("enabled = ?")
        values.append(int(data.enabled))

    if not fields:
        return existing

    values.append(topic_id)
    await db.execute(f"UPDATE topics SET {', '.join(fields)} WHERE id = ?", values)
    await db.commit()
    return await get_topic(db, topic_id)


async def delete_topic(db: aiosqlite.Connection, topic_id: int) -> bool:
    """Delete a topic. Returns True if deleted."""
    cursor = await db.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
    await db.commit()
    return cursor.rowcount > 0


async def get_sources_for_topic(
    db: aiosqlite.Connection, topic_id: int
) -> list[Source]:
    """Get all sources associated with a topic."""
    rows = await db.execute_fetchall(
        """SELECT s.* FROM sources s
           JOIN source_topics st ON s.id = st.source_id
           WHERE st.topic_id = ? AND s.enabled = 1
           ORDER BY s.id""",
        (topic_id,),
    )
    sources = []
    for row in rows:
        topic_ids = await _get_topic_ids_for_source(db, row["id"])
        sources.append(_row_to_source(row, topic_ids))
    return sources
