"""Fetcher factory - creates the correct fetcher based on source type."""

from app.fetchers.base import BaseFetcher
from app.fetchers.rss import RSSFetcher
from app.fetchers.reddit import RedditFetcher
from app.fetchers.web import WebFetcher
from app.models import SourceType


_FETCHER_REGISTRY: dict[SourceType, type[BaseFetcher]] = {
    SourceType.RSS: RSSFetcher,
    SourceType.REDDIT: RedditFetcher,
    SourceType.WEB: WebFetcher,
}


def register_fetcher(source_type: SourceType, fetcher_class: type[BaseFetcher]) -> None:
    """Register a new fetcher type. Allows extension without modifying this module."""
    _FETCHER_REGISTRY[source_type] = fetcher_class


def create_fetcher(source_type: SourceType | str) -> BaseFetcher:
    """Create a fetcher instance for the given source type.

    Args:
        source_type: The type of source (SourceType enum or string value).

    Returns:
        An instance of the appropriate fetcher.

    Raises:
        ValueError: If no fetcher is registered for the source type.
    """
    if isinstance(source_type, str):
        source_type = SourceType(source_type)
    fetcher_class = _FETCHER_REGISTRY.get(source_type)
    if fetcher_class is None:
        raise ValueError(f"No fetcher registered for source type: {source_type}")
    return fetcher_class()


def get_registered_types() -> list[SourceType]:
    """Get all registered source types."""
    return list(_FETCHER_REGISTRY.keys())


class FetcherFactory:
    """Class-based wrapper for fetcher creation (used by pipeline/DI)."""

    def create_fetcher(self, source_type: SourceType | str) -> BaseFetcher:
        """Create a fetcher for the given source type."""
        return create_fetcher(source_type)

    @staticmethod
    def register(source_type: SourceType, fetcher_class: type[BaseFetcher]) -> None:
        """Register a custom fetcher type."""
        register_fetcher(source_type, fetcher_class)

    @staticmethod
    def get_registered_types() -> list[SourceType]:
        """Get all registered source types."""
        return get_registered_types()
