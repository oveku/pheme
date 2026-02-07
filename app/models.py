"""Pydantic models for Pheme."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Supported news source types."""

    RSS = "rss"
    REDDIT = "reddit"
    WEB = "web"


# ---------------------------------------------------------------------------
# Topic models
# ---------------------------------------------------------------------------


class TopicBase(BaseModel):
    """Base fields for creating/updating a topic."""

    name: str = Field(..., min_length=1, max_length=100, description="Topic name")
    keywords: list[str] = Field(
        default_factory=list, description="Keywords to match articles against"
    )
    include_patterns: list[str] = Field(
        default_factory=list, description="Regex patterns that must match"
    )
    exclude_patterns: list[str] = Field(
        default_factory=list, description="Regex patterns to exclude"
    )
    priority: int = Field(
        default=0, ge=0, le=100, description="Higher = more important"
    )
    max_articles: int = Field(
        default=10, ge=1, le=50, description="Max articles per digest"
    )
    enabled: bool = Field(default=True, description="Whether topic is active")


class TopicCreate(TopicBase):
    """Request model for creating a topic."""

    pass


class TopicUpdate(BaseModel):
    """Request model for updating a topic. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    keywords: list[str] | None = None
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    max_articles: int | None = Field(default=None, ge=1, le=50)
    enabled: bool | None = None


class Topic(TopicBase):
    """Full topic model with database fields."""

    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Source models
# ---------------------------------------------------------------------------


class SourceBase(BaseModel):
    """Base fields for creating/updating a source."""

    name: str = Field(
        ..., min_length=1, max_length=200, description="Human-readable source name"
    )
    type: SourceType = Field(..., description="Source fetcher type")
    url: str = Field(
        ..., min_length=1, description="Feed URL, subreddit name, or page URL"
    )
    category: str = Field(
        default="general", max_length=50, description="Content category"
    )
    config: dict = Field(
        default_factory=dict, description="Type-specific configuration"
    )
    enabled: bool = Field(default=True, description="Whether source is active")


class SourceCreate(SourceBase):
    """Request model for creating a source."""

    topic_ids: list[int] = Field(
        default_factory=list, description="Topic IDs to associate with this source"
    )


class SourceUpdate(BaseModel):
    """Request model for updating a source. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: SourceType | None = None
    url: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, max_length=50)
    config: dict | None = None
    enabled: bool | None = None
    topic_ids: list[int] | None = None


class Source(SourceBase):
    """Full source model with database fields."""

    id: int
    created_at: datetime
    last_fetched: datetime | None = None
    topic_ids: list[int] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class Article(BaseModel):
    """A single news article extracted from a source."""

    title: str = Field(..., min_length=1, description="Article headline")
    url: str = Field(..., description="Link to full article")
    source_name: str = Field(..., description="Name of the source")
    category: str = Field(default="general", description="Content category")
    published_at: datetime | None = Field(
        default=None, description="Publication timestamp"
    )
    content_preview: str = Field(
        default="", max_length=2000, description="First ~500 chars of content"
    )
    full_text: str = Field(
        default="", description="Full article text extracted from URL"
    )
    score: float | None = Field(
        default=None, description="Source-specific score (e.g. Reddit upvotes)"
    )


class BlockedKeyword(BaseModel):
    """A globally blocked keyword for article filtering."""

    id: int
    keyword: str = Field(..., min_length=1, description="Keyword or phrase to block")
    created_at: datetime

    model_config = {"from_attributes": True}


class DigestEntry(BaseModel):
    """An article paired with its LLM-generated summary."""

    article: Article
    summary: str = Field(
        ..., min_length=1, description="LLM-generated 2-3 sentence summary"
    )


class Digest(BaseModel):
    """A complete daily digest ready for email delivery."""

    entries: list[DigestEntry] = Field(default_factory=list)
    topic_sections: list["TopicSection"] = Field(default_factory=list)
    summary: str = Field(default="", description="Overall digest summary from LLM")
    model: str = Field(default="", description="LLM model used for summarization")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_count: int = Field(default=0, description="Number of sources fetched")
    article_count: int = Field(
        default=0, description="Total articles before summarization"
    )


class TopicSection(BaseModel):
    """A section of the digest grouped by topic."""

    topic_name: str
    topic_id: int
    entries: list[DigestEntry] = Field(default_factory=list)
    summary: str = Field(default="", description="Topic-level summary")


class DigestLog(BaseModel):
    """Record of a sent digest."""

    id: int
    sent_at: datetime
    recipient: str
    source_count: int
    article_count: int
    entry_count: int
    status: str = Field(default="sent", description="sent | failed")
    error: str | None = None
